"""
Simulator management endpoints (CRUD) and Device Template CRUD merged into one router.

This file consolidates endpoints previously split across:
- backend/app/routes/sapro.py (simulator endpoints)
- backend/app/routes/sapro_simulator.py (if existed)
- backend/app/routes/device_templates.py (device template CRUD)

Router: single APIRouter(prefix="/api", tags=["sapro"]) with simulator endpoints first,
then template endpoints.
"""
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from backend.app.schemas.sapro_simulator import (
    SaproSimulatorCreate,
    SaproSimulatorUpdate,
    SaproSimulatorResponse,
)
from backend.app.schemas.common import SuccessResponse
from backend.app.models.simulator import Simulator
from backend.app.utils.database import get_db, get_mongo_db
from backend.app.utils.auth import require_sapro_access
from backend.app.modules import get_sapro_handler
from backend.app.modules.mongo_models import (
    DeviceTemplateCreate,
    DeviceTemplateUpdate,
)
from backend.app.modules.sapro.template_converter import json_to_xml
from backend.app.utils.logger import logger

router = APIRouter(prefix="/api", tags=["sapro"])


# ----------------------------- Helper Functions -----------------------------
def _replace_ip_in_template(template_dict: Dict[str, Any], ip_address: str) -> Dict[str, Any]:
    """Replace '<ip>' placeholders in template dict with actual IP address.

    Args:
        template_dict: Template dictionary with potential <ip> placeholders
        ip_address: IP address to replace placeholders with

    Returns:
        Copy of template with <ip> replaced
    """
    import copy
    result = copy.deepcopy(template_dict)

    def replace_recursive(obj):
        if isinstance(obj, dict):
            for key, val in obj.items():
                if isinstance(val, str) and val == '<ip>':
                    obj[key] = ip_address
                elif isinstance(val, (dict, list)):
                    replace_recursive(val)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and item == '<ip>':
                    obj[i] = ip_address
                elif isinstance(item, (dict, list)):
                    replace_recursive(item)

    replace_recursive(result)
    return result


def _load_template_and_convert_to_xml(
    mongo_db,
    template_id: str,
    ip_address: str
) -> tuple[Dict[str, Any], str]:
    """Load template from MongoDB and convert to XML.

    Args:
        mongo_db: MongoDB database instance
        template_id: Template ObjectId as string
        ip_address: IP address to inject into template

    Returns:
        Tuple of (template_doc, xml_content)

    Raises:
        HTTPException: If template not found or conversion fails
    """
    # Load template from MongoDB
    try:
        tpl_oid = ObjectId(template_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template_id")

    templates_coll = mongo_db["device_templates"]
    tpl_doc = templates_coll.find_one({"_id": tpl_oid})
    if not tpl_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    template_field = tpl_doc.get("template")
    if template_field is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template is missing 'template' field")

    # Convert template to XML
    try:
        if isinstance(template_field, str):
            # Raw XML string - replace literal '<ip>' occurrences
            xml_content = template_field.replace('<ip>', ip_address)
        else:
            # JSON dict - replace <ip> placeholders then convert to XML
            template_with_ip = _replace_ip_in_template(template_field, ip_address)
            xml_content = json_to_xml(template_with_ip)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to convert template to XML: {exc}")

    return tpl_doc, xml_content


# ----------------------------- Simulator Endpoints -----------------------------
@router.post("/simulators", response_model=SaproSimulatorResponse, status_code=status.HTTP_201_CREATED)
def create_simulator(
        payload: SaproSimulatorCreate,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler),
        mongo_db = Depends(get_mongo_db),
) -> SaproSimulatorResponse:
    """Create a new simulator in Sapro and persist it to the DB.

    New flow (safe):
    1. Ensure simulator doesn't already exist in DB
    2. Load template from Mongo
    3. Convert template to XML (or use raw XML if stored that way)
    4. Call sapro_handler.create_device(...) to provision on Sapro
    5. Only if Sapro call returns success -> persist to DB
    6. If DB save fails after successful Sapro creation, attempt best-effort cleanup in Sapro
    """
    # 1) Check DB for existing simulator
    existing = db.get(Simulator, payload.ip_address)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator with this IP already exists")

    # 2-3) Load template and convert to XML
    tpl_doc, xml_content = _load_template_and_convert_to_xml(mongo_db, payload.template_id, payload.ip_address)

    # 4) Call Sapro to create device using the XML content
    success, message = sapro_handler.create_device(payload.ip_address, xml_content, payload.map)
    if not success:
        # Sapro reported failure - do not persist to DB
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    # 5) Persist to DB only after Sapro creation succeeded
    sim = Simulator(
        ip_address=payload.ip_address,
        type=(tpl_doc.get("name") or ""),
        version=(tpl_doc.get("description") or ""),
        map=payload.map,
        status="running",
    )

    try:
        db.add(sim)
        db.commit()
        db.refresh(sim)
    except IntegrityError:
        db.rollback()
        # Race condition: another process created the DB entry meanwhile
        # Attempt to remove the previously-created Sapro device to avoid orphan
        try:
            sapro_handler.delete_device(payload.map, payload.ip_address)
        except Exception:
            logger.exception("Failed to cleanup Sapro device after DB integrity error for %s", payload.ip_address)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator with this IP already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        # Best-effort cleanup in Sapro since DB save failed
        try:
            ok, msg = sapro_handler.delete_device(payload.map, payload.ip_address)
            if ok:
                logger.info("Cleaned up Sapro device %s after DB failure", payload.ip_address)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save simulator to DB: {str(exc)}; device removed from Sapro")
            else:
                logger.error("Failed to remove Sapro device %s after DB failure: %s", payload.ip_address, msg)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save simulator to DB: {str(exc)}; additionally failed to cleanup device on Sapro: {msg}")
        except Exception as cleanup_exc:
            logger.exception("Cleanup after DB failure also failed for device %s: %s", payload.ip_address, cleanup_exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save simulator to DB and cleanup Sapro device: {cleanup_exc}")

    # 6) Return response
    resp = SaproSimulatorResponse.model_validate(sim)
    return resp


@router.get("/simulators/{simulator_ip}", response_model=SaproSimulatorResponse)
def get_simulator(simulator_ip: str, db: Session = Depends(get_db)) -> SaproSimulatorResponse:
    """Retrieve a Sapro-managed simulator by IP address from the DB."""
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")
    return SaproSimulatorResponse.model_validate(sim)


@router.get("/simulators", response_model=List[SaproSimulatorResponse])
def list_simulators(
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler)
) -> List[SaproSimulatorResponse]:
    """Get all devices from Sapro and sync to DB.

    New behavior:
    1. Query Sapro for currently running devices
    2. Upsert each Sapro device into the SQL DB
    3. Remove any DB simulators that are not present in Sapro (orphan cleanup)
    4. Return the current DB simulator list
    """
    try:
        devices = sapro_handler.get_all_devices()  # List[SaproDevice]
    except Exception as exc:
        logger.exception("Failed to query Sapro for devices: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to query Sapro: {exc}")

    # Upsert devices returned by Sapro into DB using PostgreSQL INSERT ON CONFLICT
    for device in devices:
        stmt = insert(Simulator).values(
            ip_address=device.ip_address,
            type=device.type or "",  # Default to empty string if SNMP query failed
            version=device.version or "",  # Default to empty string if SNMP query failed
            map=device.map,
            status=device.status,
            created_at=datetime.now(timezone.utc)
        ).on_conflict_do_update(
            index_elements=['ip_address'],
            set_={
                'type': device.type or "",
                'version': device.version or "",
                'map': device.map,
                'status': device.status
            }
        )
        db.execute(stmt)
    db.commit()

    # Build set of Sapro IPs and remove any DB records not present in Sapro
    sapro_ips = {d.ip_address for d in devices}

    db_sims = db.query(Simulator).all()
    removed = 0
    for sim in db_sims:
        if sim.ip_address not in sapro_ips:
            try:
                db.delete(sim)
                removed += 1
            except Exception:
                logger.exception("Failed to delete orphaned simulator %s from DB", sim.ip_address)
    if removed:
        db.commit()
        logger.info("Removed %d orphaned simulator(s) from DB not present in Sapro", removed)

    # Return the remaining simulators from DB
    sims = db.query(Simulator).all()
    return [SaproSimulatorResponse.model_validate(s) for s in sims]


@router.put("/simulators/{simulator_ip}", response_model=SaproSimulatorResponse)
def update_simulator(
        simulator_ip: str,
        payload: SaproSimulatorUpdate,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler),
        mongo_db=Depends(get_mongo_db),
) -> SaproSimulatorResponse:
    """Update a Sapro-managed simulator by delete → edit file → add device.

    Flow:
    1. Verify simulator exists in DB
    2. Validate required fields (template_id and map)
    3. Delete device from map via SSH (deldev command)
    4. Overwrite device file with new template content
    5. Add device back to map via SSH (adddev command)
    6. Update DB with new metadata

    Only map and template_id are updatable. IP cannot change.
    """
    # 1) Verify simulator exists
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    # 2) Validate required fields
    template_id = payload.template_id
    if not template_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="template_id is required for update")

    # Use provided map or keep existing
    map_name = payload.map if payload.map else sim.map
    if not map_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Map is required")

    # 3) Delete device from map using SSH deldev command
    logger.info(f"Deleting device {simulator_ip} from map {map_name}")
    success, message = sapro_handler.delete_device(map_name, simulator_ip)
    if not success:
        logger.warning(f"Delete device warning (continuing anyway): {message}")
        # Don't fail - device might not be in map, we'll add it back

    # 4) Load template and convert to XML, then overwrite device file
    logger.info(f"Updating device file for {simulator_ip} with template {template_id}")
    tpl_doc, xml_content = _load_template_and_convert_to_xml(mongo_db, template_id, simulator_ip)

    device_file_path = f"{sapro_handler.map_directory}{map_name}/{simulator_ip}.map"
    success, message = sapro_handler.create_device_file_on_server(device_file_path, xml_content)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update device file: {message}")

    # 5) Add device to map using SSH adddev command (matching Java implementation)
    logger.info(f"Adding device {simulator_ip} back to map {map_name}")
    from backend.app.utils.sapro_ssh import get_sapro_ssh_client

    map_path = f"/opt/sapro/map/{map_name}.map"
    cmd = f"/opt/sapro/bin/sapcnsl -p {sapro_handler.sapro_port} -m {map_path} -c adddev -f {device_file_path}"

    try:
        ssh_client = get_sapro_ssh_client()
        success, output = ssh_client.execute_command(cmd, check_stderr=False)

        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add device to map: {output}")

        logger.info(f"Device {simulator_ip} added to map successfully: {output}")
    except Exception as exc:
        logger.error(f"Failed to execute adddev command: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add device to map: {exc}")

    # 6) Update DB with new metadata
    sim.type = tpl_doc.get("name") or sim.type
    sim.version = tpl_doc.get("description") or sim.version
    sim.map = map_name
    sim.status = "running"  # Assume running after successful add

    try:
        db.add(sim)
        db.commit()
        db.refresh(sim)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Failed to update DB for {simulator_ip}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Device updated on Sapro but failed to update DB: {str(exc)}")

    logger.info(f"Simulator {simulator_ip} updated successfully")
    return SaproSimulatorResponse.model_validate(sim)


@router.delete("/simulators/{simulator_ip}", response_model=SuccessResponse)
def delete_simulator(
        simulator_ip: str,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler),
) -> SuccessResponse:
    """Delete a Sapro-managed simulator from Sapro and the DB.

    Calls the Sapro handler to remove the device from the map/server first,
    then removes the record from the local DB on success.
    """
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    # Attempt to delete from Sapro first
    map_name = sim.map or ""
    success, message = sapro_handler.delete_device(map_name, simulator_ip)
    if not success:
        # Sapro deletion failed
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    try:
        db.delete(sim)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return SuccessResponse(message="Simulator deleted successfully", data={"ip_address": simulator_ip})


@router.get("/maps", response_model=List[Dict[str, str]])
def list_maps(
     _current_user=Depends(require_sapro_access),
     sapro_handler=Depends(get_sapro_handler)
 ) -> List[Dict[str, str]]:
    """Get list of all available maps from Sapro workspace with their status.

    Returns:
        List of dicts with:
        - name: Map name (without .map extension)
        - status: "running" (R), "stopped" (empty), or "error" (other)
    """
    try:
        maps = sapro_handler.get_all_maps()
        return maps
    except Exception as exc:
        logger.exception("Failed to get map list from Sapro: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get map list: {exc}"
        )


@router.post("/maps/{map_name}/start", response_model=SuccessResponse)
def start_map(
    map_name: str,
    _current_user=Depends(require_sapro_access),
    sapro_handler=Depends(get_sapro_handler)
) -> SuccessResponse:
    """Start a map and wait until it's running.

    Executes start command and polls status every 2 seconds until running.
    Timeout: 5 minutes.

    Args:
        map_name: Map name (without .map extension)

    Returns:
        Success response when map is running
    """
    try:
        success, message = sapro_handler.start_map_and_wait(map_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
        return SuccessResponse(message=message, data={"map": map_name, "status": "running"})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to start map %s: %s", map_name, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start map: {exc}"
        )


@router.post("/maps/{map_name}/stop", response_model=SuccessResponse)
def stop_map(
    map_name: str,
    _current_user=Depends(require_sapro_access),
    sapro_handler=Depends(get_sapro_handler)
) -> SuccessResponse:
    """Stop a map and wait until terminated.

    Executes stop command (synchronous, waits for termination).
    Timeout: 5 minutes.

    Args:
        map_name: Map name (without .map extension)

    Returns:
        Success response when map is stopped
    """
    try:
        success, message = sapro_handler.stop_map_and_wait(map_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
        return SuccessResponse(message=message, data={"map": map_name, "status": "stopped"})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to stop map %s: %s", map_name, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop map: {exc}"
        )


# Note: create_map and delete_map endpoints have been removed. Map file management
# should be performed by the administrator or other tooling outside of these APIs.


@router.post("/simulators/{simulator_ip}/start", response_model=SuccessResponse)
def start_simulator(
        simulator_ip: str,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler)
) -> SuccessResponse:
    """Start a simulator device.

    Retrieves the simulator's map from DB and calls Sapro to start the device.
    """
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    map_name = sim.map or ""
    if not map_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Simulator has no map assigned")

    try:
        success, message = sapro_handler.start_devices_from_map(map_name, [simulator_ip])
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

        return SuccessResponse(message=f"Simulator {simulator_ip} started successfully", data={"ip_address": simulator_ip})
    except Exception as exc:
        logger.exception("Failed to start simulator %s: %s", simulator_ip, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start simulator: {exc}")


@router.post("/simulators/{simulator_ip}/stop", response_model=SuccessResponse)
def stop_simulator(
        simulator_ip: str,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler)
) -> SuccessResponse:
    """Stop a simulator device.

    Retrieves the simulator's map from DB and calls Sapro to stop the device.
    """
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    map_name = sim.map or ""
    if not map_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Simulator has no map assigned")

    try:
        success, message = sapro_handler.stop_devices_from_map(map_name, [simulator_ip])
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

        return SuccessResponse(message=f"Simulator {simulator_ip} stopped successfully", data={"ip_address": simulator_ip})
    except Exception as exc:
        logger.exception("Failed to stop simulator %s: %s", simulator_ip, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to stop simulator: {exc}")


# ----------------------------- Device Template Endpoints -----------------------------
@router.post("/device-templates", status_code=status.HTTP_201_CREATED)
async def create_device_template(
    payload: DeviceTemplateCreate,
    current_user=Depends(require_sapro_access),
    mongo_db = Depends(get_mongo_db),
):
    """Create a new device template. Returns minimal metadata on success.

    Error: 409 if name already exists.
    """
    collection = mongo_db["device_templates"]

    # Check unique name
    existing = collection.find_one({"name": payload.name})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template name already exists")

    now = datetime.now(timezone.utc)
    doc = {
        "name": payload.name,
        "description": payload.description,
        "template": payload.template,
        "created_at": now,
        "updated_at": now,
    }

    result = collection.insert_one(doc)

    return {
        "_id": str(result.inserted_id),
        "name": payload.name,
        "description": payload.description,
        "created_at": now.isoformat(),
    }


@router.get("/device-templates", response_model=List[Dict[str, Any]])
async def list_device_templates(
    current_user=Depends(require_sapro_access),
    mongo_db = Depends(get_mongo_db),
):
    """List all device templates (lightweight listing without full template body)."""
    collection = mongo_db["device_templates"]

    cursor = collection.find({}, {"template": 0})

    result: List[Dict[str, Any]] = []
    for d in cursor:
        created = d.get("created_at")
        if isinstance(created, datetime):
            created_val = created.isoformat()
        else:
            created_val = created or ""

        result.append({
            "_id": str(d.get("_id")),
            "name": d.get("name"),
            "description": d.get("description"),
            "created_at": created_val,
        })

    return result


@router.get("/device-templates/{template_id}")
async def get_device_template(
    template_id: str,
    current_user=Depends(require_sapro_access),
    mongo_db = Depends(get_mongo_db),
):
    """Return full device template by id."""
    collection = mongo_db["device_templates"]
    try:
        oid = ObjectId(template_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    doc = collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    # Convert datetimes and ObjectId to serializable types
    created = doc.get("created_at")
    updated = doc.get("updated_at")
    if isinstance(created, datetime):
        doc["created_at"] = created.isoformat()
    if isinstance(updated, datetime):
        doc["updated_at"] = updated.isoformat()

    doc["_id"] = str(doc.get("_id"))

    return doc


@router.put("/device-templates/{template_id}")
async def update_device_template(
    template_id: str,
    payload: DeviceTemplateUpdate,
    current_user=Depends(require_sapro_access),
    mongo_db = Depends(get_mongo_db),
):
    """Update fields of a device template. Returns updated metadata.

    Error: 404 if not found.
    """
    collection = mongo_db["device_templates"]
    try:
        oid = ObjectId(template_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    existing = collection.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    update_fields: Dict[str, Any] = {}
    if payload.name is not None:
        # Ensure uniqueness of name when changing
        conflict = collection.find_one({"name": payload.name, "_id": {"$ne": oid}})
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template name already exists")
        update_fields["name"] = payload.name
    if payload.description is not None:
        update_fields["description"] = payload.description
    if payload.template is not None:
        update_fields["template"] = payload.template

    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        collection.update_one({"_id": oid}, {"$set": update_fields})

    # Fetch updated doc for response
    doc = collection.find_one({"_id": oid}, {"template": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    updated = doc.get("updated_at")
    if isinstance(updated, datetime):
        updated_val = updated.isoformat()
    else:
        updated_val = updated or ""

    return {
        "_id": str(doc.get("_id")),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "updated_at": updated_val,
    }


@router.delete("/device-templates/{template_id}")
async def delete_device_template(
    template_id: str,
    current_user=Depends(require_sapro_access),
    mongo_db = Depends(get_mongo_db),
):
    """Delete device template by id."""
    collection = mongo_db["device_templates"]
    try:
        oid = ObjectId(template_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    result = collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return {"success": True, "message": f"Template '{template_id}' deleted"}


# ----------------------------- Sapro File Listing Endpoints -----------------------------
@router.get("/sapro-files/{file_type}")
async def list_sapro_files(
    file_type: str,
    current_user=Depends(require_sapro_access),
):
    """List files from Sapro server directories for template field dropdowns.

    Args:
        file_type: Type of files to list
            - "mib": List .cmf files from /opt/sapro/cmf/
            - "agent": List .var and .cva files from /opt/sapro/var/
            - "ssh": List .tel files from /opt/sapro/telnet/
            - "soap": List .xmf files from /opt/sapro/xml/
            - "modeling": List .tcl files from /opt/sapro/tcl/

    Returns:
        Dict with file_type and list of files

    Error: 400 if invalid file_type
    """
    from backend.app.utils.sapro_ssh import get_sapro_ssh_client

    # Map file types to directories and extensions
    file_type_map = {
        "mib": ("/opt/sapro/cmf/", [".cmf"]),
        "agent": ("/opt/sapro/var/", [".var", ".cva"]),
        "ssh": ("/opt/sapro/telnet/", [".tel"]),
        "soap": ("/opt/sapro/xml/", [".xmf"]),
        "modeling": ("/opt/sapro/tcl/", [".tcl"]),
    }

    if file_type not in file_type_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file_type. Must be one of: {', '.join(file_type_map.keys())}"
        )

    directory, extensions = file_type_map[file_type]

    try:
        ssh_client = get_sapro_ssh_client()

        # Check if directory exists
        if not ssh_client.file_exists(directory):
            logger.warning(f"Directory not found: {directory}")
            return {
                "file_type": file_type,
                "directory": directory,
                "files": [],
            }

        # List all files in directory
        all_files = ssh_client.list_directory(directory)

        # Filter by extensions
        filtered_files = [
            f for f in all_files
            if any(f.endswith(ext) for ext in extensions)
        ]

        # Sort files alphabetically
        filtered_files.sort()

        logger.info(f"Listed {len(filtered_files)} {file_type} files from {directory}")

        return {
            "file_type": file_type,
            "directory": directory,
            "files": filtered_files,
        }

    except Exception as e:
        logger.error(f"Failed to list {file_type} files from {directory}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get("/sapro-files/validate/{file_path:path}")
async def validate_sapro_file(
    file_path: str,
    current_user=Depends(require_sapro_access),
):
    """Check if a file exists on the Sapro server.

    Args:
        file_path: Full path to file (e.g., /opt/sapro/cmf/file.cmf)

    Returns:
        Dict with exists (bool) and path (str)
    """
    from backend.app.utils.sapro_ssh import get_sapro_ssh_client

    try:
        ssh_client = get_sapro_ssh_client()
        exists = ssh_client.file_exists(file_path)

        logger.debug(f"File validation for {file_path}: exists={exists}")

        return {
            "exists": exists,
            "path": file_path,
        }

    except Exception as e:
        logger.error(f"Failed to validate file {file_path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate file: {str(e)}"
        )


__all__ = ["router"]
