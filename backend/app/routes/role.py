"""
Role management endpoints.

- POST /api/roles -> create_role
- GET  /api/roles/{role_id} -> get_role
- GET  /api/roles -> list_roles
- PUT  /api/roles/{role_id} -> update_role
- DELETE /api/roles/{role_id} -> delete_role

All endpoints use `get_db` for DB sessions and `get_current_user` for
authentication where modification is required.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.app.schemas.role import RoleCreate, RoleResponse
from backend.app.schemas.common import SuccessResponse
from backend.app.models.role import Role
from backend.app.utils.database import get_db
from backend.app.utils.auth import get_current_user

router = APIRouter(tags=["roles"])


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> RoleResponse:
    """Create a new role.

    Returns 201 with the created role or 409 if role_name already exists.
    """
    role = Role(role_name=payload.role_name, description=payload.description)
    try:
        db.add(role)
        db.commit()
        db.refresh(role)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return RoleResponse(role_id=role.role_id, role_name=role.role_name, description=role.description, created_at=role.created_at)


@router.get("/roles/{role_id}", response_model=RoleResponse)
def get_role(role_id: int, db: Session = Depends(get_db)) -> RoleResponse:
    """Retrieve a role by ID."""
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return RoleResponse(role_id=role.role_id, role_name=role.role_name, description=role.description, created_at=role.created_at)


@router.get("/roles", response_model=List[RoleResponse])
def list_roles(db: Session = Depends(get_db)) -> List[RoleResponse]:
    """List all roles."""
    roles = db.query(Role).all()
    return [RoleResponse(role_id=r.role_id, role_name=r.role_name, description=r.description, created_at=r.created_at) for r in roles]


@router.put("/roles/{role_id}", response_model=RoleResponse)
def update_role(role_id: int, payload: RoleCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> RoleResponse:
    """Update role name/description."""
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    role.role_name = payload.role_name
    role.description = payload.description
    try:
        db.add(role)
        db.commit()
        db.refresh(role)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return RoleResponse(role_id=role.role_id, role_name=role.role_name, description=role.description, created_at=role.created_at)


@router.delete("/roles/{role_id}", response_model=SuccessResponse)
def delete_role(role_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> SuccessResponse:
    """Delete a role by ID and return a success message."""
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    try:
        db.delete(role)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SuccessResponse(message="Role deleted successfully", data={"role_id": role_id})

