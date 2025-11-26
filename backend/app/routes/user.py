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

from backend.app.schemas.user import UserCreate, UserResponse, UserUpdate, UserWithRolesResponse, AssignRoleRequest
from backend.app.schemas.auth import LoginRequest, LoginResponse
from backend.app.schemas.common import ErrorResponse
from backend.app.models.user import User
from backend.app.models.role import Role
from backend.app.models.user_role import UserRole
from backend.app.utils.database import get_db
from backend.app.utils.auth import hash_password, verify_password, create_access_token, get_current_user, require_admin

router = APIRouter(prefix="/api", tags=["users"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}})
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin_user: User = Depends(require_admin)) -> UserResponse:
    """Create a new user (admin only).

    Requires the requesting user to have the 'admin' role.
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


@router.put("/users/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK, responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 403: {"model": ErrorResponse}})
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), admin_user: User = Depends(require_admin)) -> UserResponse:
    """Update a user by ID (admin only).

    Requires the requesting user to have the 'admin' role.
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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 400: {"model": ErrorResponse}})
def delete_user(user_id: int, db: Session = Depends(get_db), admin_user: User = Depends(require_admin)) -> None:
    """Delete a user by ID (admin only).

    Requires the requesting user to have the 'admin' role.
    Prevents admins from deleting themselves to avoid lockout.
    """
    # Check if user exists
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent self-deletion
    if user.user_id == admin_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    try:
        db.delete(user)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


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

    return LoginResponse(access_token=token, token_type="bearer", user=UserWithRolesResponse(
        user_id=user.user_id,
        username=user.username,
        roles=[role.role_name for role in user.roles],
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    ))


@router.get("/users/{username}/roles", response_model=UserWithRolesResponse, responses={404: {"model": ErrorResponse}})
def get_user_with_roles(
    username: str,
    db: Session = Depends(get_db),
    _current_user: Any = Depends(get_current_user)
) -> UserWithRolesResponse:
    """Get a user with their assigned roles (protected).

    Requires authentication. Returns user info including list of role names.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found")

    # Get role names
    role_names = [role.role_name for role in user.roles]

    return UserWithRolesResponse(
        user_id=user.user_id,
        username=user.username,
        roles=role_names,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    )


@router.post("/users/{username}/roles", response_model=UserWithRolesResponse, status_code=status.HTTP_200_OK, responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 403: {"model": ErrorResponse}})
def assign_role_to_user(
    username: str,
    payload: AssignRoleRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
) -> UserWithRolesResponse:
    """Assign a role to a user (admin only).

    Requires the requesting user to have the 'admin' role.
    Assigns the specified role to the target user if not already assigned.
    """
    # Check if user exists
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found")

    # Check if role exists
    role = db.query(Role).filter(Role.role_name == payload.role_name).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{payload.role_name}' not found. Available roles: admin, sapro_admin, cc_admin"
        )

    # Check if user already has this role
    existing = db.query(UserRole).filter(
        UserRole.user_id == user.user_id,
        UserRole.role_id == role.role_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{username}' already has role '{payload.role_name}'"
        )

    # Assign the role
    try:
        user_role = UserRole(user_id=user.user_id, role_id=role.role_id)
        db.add(user_role)
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Return user with updated roles
    role_names = [r.role_name for r in user.roles]

    return UserWithRolesResponse(
        user_id=user.user_id,
        username=user.username,
        roles=role_names,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    )


@router.delete("/users/{username}/roles/{role_name}", response_model=UserWithRolesResponse, responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}})
def remove_role_from_user(
    username: str,
    role_name: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
) -> UserWithRolesResponse:
    """Remove a role from a user (admin only).

    Requires the requesting user to have the 'admin' role.
    Prevents removing admin role from yourself to avoid lockout.
    """
    # Check if user exists
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found")

    # Check if role exists
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_name}' not found")

    # Prevent removing admin role from yourself
    if username == admin_user.username and role_name == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove admin role from your own account"
        )

    # Find the user_role association
    user_role = db.query(UserRole).filter(
        UserRole.user_id == user.user_id,
        UserRole.role_id == role.role_id
    ).first()

    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' does not have role '{role_name}'"
        )

    # Remove the role
    try:
        db.delete(user_role)
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Return user with updated roles
    role_names = [r.role_name for r in user.roles]

    return UserWithRolesResponse(
        user_id=user.user_id,
        username=user.username,
        roles=role_names,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    )
