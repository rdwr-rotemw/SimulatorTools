from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from pydantic import BaseModel

from backend.app.models.user import User
from backend.app.utils.auth import require_cc_access
from backend.app.utils.database import get_mongo_db

router = APIRouter(prefix="/api/cc/{cc_ip}/reporter/snmp", tags=["snmp_templates"])


class SNMPTemplate(BaseModel):
    name: str
    traps: List[Dict[str, Any]]


class SNMPTemplateResponse(BaseModel):
    name: str
    created_at: str
    trap_count: int


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def save_template(
    cc_ip: str,
    template: SNMPTemplate,
    current_user: User = Depends(require_cc_access),
    mongo_db = Depends(get_mongo_db),
):
    """Save SNMP trap template to MongoDB."""
    collection = mongo_db["snmp_templates"]

    # Check if template name already exists
    existing = collection.find_one({"name": template.name, "user_id": current_user.user_id})
    if existing:
        raise HTTPException(status_code=400, detail="Template name already exists")

    # Save template
    from datetime import datetime

    doc = {
        "name": template.name,
        "traps": template.traps,
        "user_id": current_user.user_id,
        "cc_ip": cc_ip,
        "created_at": datetime.utcnow().isoformat(),
    }
    collection.insert_one(doc)

    return {"success": True, "message": f"Template '{template.name}' saved successfully"}


@router.get("/templates", response_model=List[SNMPTemplateResponse])
async def list_templates(
    cc_ip: str,
    current_user: User = Depends(require_cc_access),
    mongo_db = Depends(get_mongo_db),
):
    """List all SNMP templates for current user."""
    collection = mongo_db["snmp_templates"]
    templates = collection.find(
        {"user_id": current_user.user_id, "cc_ip": cc_ip},
        {"_id": 0, "name": 1, "created_at": 1, "traps": 1}
    )

    result = []
    for t in templates:
        result.append({
            "name": t["name"],
            "created_at": t.get("created_at", ""),
            "trap_count": len(t.get("traps", []))
        })
    return result


@router.get("/templates/{template_name}")
async def get_template(
    cc_ip: str,
    template_name: str,
    current_user: User = Depends(require_cc_access),
    mongo_db = Depends(get_mongo_db),
):
    """Get specific SNMP template."""
    collection = mongo_db["snmp_templates"]
    template = collection.find_one(
        {"name": template_name, "user_id": current_user.user_id, "cc_ip": cc_ip},
        {"_id": 0}
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.delete("/templates/{template_name}")
async def delete_template(
    cc_ip: str,
    template_name: str,
    current_user: User = Depends(require_cc_access),
    mongo_db = Depends(get_mongo_db),
):
    """Delete SNMP template."""
    collection = mongo_db["snmp_templates"]
    result = collection.delete_one({"name": template_name, "user_id": current_user.user_id, "cc_ip": cc_ip})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"success": True, "message": f"Template '{template_name}' deleted"}


__all__ = ["router"]

