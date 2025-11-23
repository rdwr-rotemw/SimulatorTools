"""
Permission management endpoints.

- POST /api/permissions -> create_permission
- GET  /api/permissions/{permission_id} -> get_permission
- GET  /api/permissions -> list_permissions
- PUT  /api/permissions/{permission_id} -> update_permission
- DELETE /api/permissions/{permission_id} -> delete_permission

All modifying endpoints require authentication via `get_current_user`.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.app.schemas.permission import PermissionCreate, PermissionResponse
from backend.app.schemas.common import SuccessResponse
from backend.app.models.permission import Permission
from backend.app.utils.database import get_db
from backend.app.utils.auth import get_current_user

router = APIRouter(tags=["permissions"])


@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(payload: PermissionCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> PermissionResponse:
    """Create a new permission.

    Returns 201 with created permission or 409 if permission_name already exists.
    """
    perm = Permission(permission_name=payload.permission_name, resource=payload.resource, action=payload.action, description=payload.description)
    try:
        db.add(perm)
        db.commit()
        db.refresh(perm)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Permission name already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return PermissionResponse(permission_id=perm.permission_id, permission_name=perm.permission_name, resource=perm.resource, action=perm.action, description=perm.description)


@router.get("/permissions/{permission_id}", response_model=PermissionResponse)
def get_permission(permission_id: int, db: Session = Depends(get_db)) -> PermissionResponse:
    """Retrieve a permission by ID."""
    perm = db.get(Permission, permission_id)
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    return PermissionResponse(permission_id=perm.permission_id, permission_name=perm.permission_name, resource=perm.resource, action=perm.action, description=perm.description)


@router.get("/permissions", response_model=List[PermissionResponse])
def list_permissions(db: Session = Depends(get_db)) -> List[PermissionResponse]:
    """List all permissions."""
    perms = db.query(Permission).all()
    return [PermissionResponse(permission_id=p.permission_id, permission_name=p.permission_name, resource=p.resource, action=p.action, description=p.description) for p in perms]


@router.put("/permissions/{permission_id}", response_model=PermissionResponse)
def update_permission(permission_id: int, payload: PermissionCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> PermissionResponse:
    """Update permission fields."""
    perm = db.get(Permission, permission_id)
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    perm.permission_name = payload.permission_name
    perm.resource = payload.resource
    perm.action = payload.action
    perm.description = payload.description
    try:
        db.add(perm)
        db.commit()
        db.refresh(perm)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Permission name already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PermissionResponse(permission_id=perm.permission_id, permission_name=perm.permission_name, resource=perm.resource, action=perm.action, description=perm.description)


@router.delete("/permissions/{permission_id}", response_model=SuccessResponse)
def delete_permission(permission_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> SuccessResponse:
    """Delete a permission by ID and return success message."""
    perm = db.get(Permission, permission_id)
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    try:
        db.delete(perm)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SuccessResponse(message="Permission deleted successfully", data={"permission_id": permission_id})

