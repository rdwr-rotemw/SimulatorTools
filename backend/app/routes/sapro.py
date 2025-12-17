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

    # 2) Load template from MongoDB
    try:
        tpl_oid = ObjectId(payload.template_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template_id")

    templates_coll = mongo_db["device_templates"]
    tpl_doc = templates_coll.find_one({"_id": tpl_oid})
    if not tpl_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    template_field = tpl_doc.get("template")
    if template_field is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template is missing 'template' field")

    # Helper: replace '<ip>' placeholders inside nested template dict/list
    def replace_ip_in_template(template_dict: Dict[str, Any], ip_address: str) -> Dict[str, Any]:
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

    # 3) Prepare XML content: support stored JSON dict or raw XML string
    try:
        if isinstance(template_field, str):
            # If template is stored as raw XML string, replace literal '<ip>' occurrences in the string
            # to preserve original behavior where templates contained the <ip> placeholder.
            xml_content = template_field.replace('<ip>', payload.ip_address)
        else:
            # Replace <ip> placeholder with actual IP in the JSON structure, then convert to XML
            template_with_ip = replace_ip_in_template(template_field, payload.ip_address)
            xml_content = json_to_xml(template_with_ip)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to convert template to XML: {exc}")

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

    # Upsert devices returned by Sapro into DB
    for device in devices:
        db.merge(Simulator(
            ip_address=device.ip_address,
            type=device.type or "",  # Default to empty string if SNMP query failed
            version=device.version or "",  # Default to empty string if SNMP query failed
            map=device.map,
            status=device.status
        ))
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
) -> SaproSimulatorResponse:
    """Update metadata for a Sapro-managed simulator.

    Only provided fields are updated; Sapro side operations are not
    performed here (they could be added later if needed).
    """

    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    # Apply provided updates (only non-None values)
    if payload.type is not None:
        sim.type = payload.type
    if payload.version is not None:
        sim.version = payload.version
    if payload.map is not None:
        sim.map = payload.map
    if payload.status is not None:  # backward-compat: keep handling if provided in payload type
        sim.status = payload.status

    try:
        db.add(sim)
        db.commit()
        db.refresh(sim)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator conflict on update")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

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
