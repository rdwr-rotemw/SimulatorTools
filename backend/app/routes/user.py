"""
User management routes (create, get, list, update, login).

Endpoints:
- POST /api/users -> create_user
- GET  /api/users -> get_all_users (protected)
- GET  /api/users/{user_id} -> get_user (protected)
- PUT  /api/users/{user_id} -> update_user (protected)
- POST /api/login -> login

This module implements DB operations using SQLAlchemy sessions from
`get_db` and uses `auth` utilities for hashing and JWT creation.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.app.schemas.user import UserCreate, UserResponse, UserUpdate
from backend.app.schemas.auth import LoginRequest, LoginResponse
from backend.app.schemas.common import ErrorResponse
from backend.app.models.user import User
from backend.app.utils.database import get_db
from backend.app.utils.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api", tags=["users"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, responses={400: {"model": ErrorResponse}})
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """Create a new user.

    - Hashes the provided password using `hash_password`.
    - Persists the user record to the database.
    - Returns the created user (without the password hash).
    """
    hashed = hash_password(payload.password)
    user = User(username=payload.username, password_hash=hashed)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    )


@router.get("/users/{user_id}", response_model=UserResponse, responses={404: {"model": ErrorResponse}})
def get_user(user_id: int, db: Session = Depends(get_db), _current_user: Any = Depends(get_current_user)) -> UserResponse:
    """Retrieve a user by ID (protected).

    Requires authentication (via `get_current_user`).
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    )


@router.get("/users", response_model=list[UserResponse], status_code=status.HTTP_200_OK)
def get_all_users(db: Session = Depends(get_db), _current_user: Any = Depends(get_current_user)) -> list[UserResponse]:
    """Retrieve all users (protected).

    Requires authentication (via `get_current_user`).
    """
    users = db.query(User).all()
    return [
        UserResponse(
            user_id=user.user_id,
            username=user.username,
            created_at=user.created_at,
            updated_at=getattr(user, "updated_at", None),
        )
        for user in users
    ]


@router.put("/users/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK, responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _current_user: Any = Depends(get_current_user)) -> UserResponse:
    """Update a user by ID (protected).

    Requires authentication (via `get_current_user`).
    Updates only the fields provided in the payload.
    """
    # Check if user exists
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update fields if provided
    if payload.username is not None:
        user.username = payload.username

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    )


@router.post("/login", response_model=LoginResponse, responses={401: {"model": ErrorResponse}})
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate a user and return a JWT LoginResponse.

    - Validates credentials against the stored password hash.
    - Returns an access token and optional user info on success.
    """
    # Find user by username
    user = db.query(User).filter(User.username == payload.username).one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.user_id)})

    return LoginResponse(access_token=token, token_type="bearer", user=UserResponse(
        user_id=user.user_id,
        username=user.username,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    ))
