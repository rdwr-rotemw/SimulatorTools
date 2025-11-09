"""
CyberController Credentials management endpoints.

Endpoints:
- POST   /api/cc-credentials            -> create_cc_credential
- GET    /api/cc-credentials/{cc_ip}    -> get_cc_credential
- GET    /api/cc-credentials            -> list_cc_credentials
- PUT    /api/cc-credentials/{cc_ip}    -> update_cc_credential
- DELETE /api/cc-credentials/{cc_ip}    -> delete_cc_credential

Notes:
- Responses SHOULD NOT include the `encrypted_password` field.
- Modifying endpoints require authentication via `get_current_user`.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.app.schemas.cc_credentials import CCCredentialsCreate, CCCredentialsResponse
from backend.app.schemas.common import SuccessResponse
from backend.app.models.cc_credentials import CCCredentials
from backend.app.utils.database import get_db
from backend.app.utils.auth import get_current_user

router = APIRouter(prefix="/api", tags=["cc_credentials"])


@router.post("/cc-credentials", response_model=CCCredentialsResponse, status_code=status.HTTP_201_CREATED)
def create_cc_credential(payload: CCCredentialsCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> CCCredentialsResponse:
    """Create a new CyberController credential entry.

    Returns 201 with the created credential (without password) or 409 if cc_ip exists.
    """
    existing = db.get(CCCredentials, payload.cc_ip)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CC credential with this IP already exists")

    cred = CCCredentials(
        cc_ip=payload.cc_ip,
        cc_host=payload.cc_host,
        cc_port=payload.cc_port or 443,
        username=payload.username,
        encrypted_password=payload.encrypted_password,
    )
    try:
        db.add(cred)
        db.commit()
        db.refresh(cred)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CC credential with this IP already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return CCCredentialsResponse(
        cc_ip=cred.cc_ip,
        cc_host=cred.cc_host,
        cc_port=cred.cc_port,
        username=cred.username,
        created_at=cred.created_at,
    )


@router.get("/cc-credentials/{cc_ip}", response_model=CCCredentialsResponse)
def get_cc_credential(cc_ip: str, db: Session = Depends(get_db)) -> CCCredentialsResponse:
    """Retrieve CC credential by cc_ip (do not expose password)."""
    cred = db.get(CCCredentials, cc_ip)
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CC credential not found")
    return CCCredentialsResponse(
        cc_ip=cred.cc_ip,
        cc_host=cred.cc_host,
        cc_port=cred.cc_port,
        username=cred.username,
        created_at=cred.created_at,
    )


@router.get("/cc-credentials", response_model=List[CCCredentialsResponse])
def list_cc_credentials(db: Session = Depends(get_db)) -> List[CCCredentialsResponse]:
    """List all CC credentials (omit passwords)."""
    creds = db.query(CCCredentials).all()
    return [
        CCCredentialsResponse(
            cc_ip=c.cc_ip,
            cc_host=c.cc_host,
            cc_port=c.cc_port,
            username=c.username,
            created_at=c.created_at,
        )
        for c in creds
    ]


@router.put("/cc-credentials/{cc_ip}", response_model=CCCredentialsResponse)
def update_cc_credential(cc_ip: str, payload: CCCredentialsCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> CCCredentialsResponse:
    """Update existing CC credential fields. Does not return the password."""
    cred = db.get(CCCredentials, cc_ip)
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CC credential not found")

    # Update fields
    cred.cc_host = payload.cc_host
    cred.cc_port = payload.cc_port or cred.cc_port
    cred.username = payload.username
    if payload.encrypted_password:
        cred.encrypted_password = payload.encrypted_password

    try:
        db.add(cred)
        db.commit()
        db.refresh(cred)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CC credential conflict on update")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return CCCredentialsResponse(
        cc_ip=cred.cc_ip,
        cc_host=cred.cc_host,
        cc_port=cred.cc_port,
        username=cred.username,
        created_at=cred.created_at,
    )


@router.delete("/cc-credentials/{cc_ip}", response_model=SuccessResponse)
def delete_cc_credential(cc_ip: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> SuccessResponse:
    """Delete a CC credential by cc_ip and return success message."""
    cred = db.get(CCCredentials, cc_ip)
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CC credential not found")
    try:
        db.delete(cred)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SuccessResponse(message="CC credential deleted successfully", data={"cc_ip": cc_ip})

