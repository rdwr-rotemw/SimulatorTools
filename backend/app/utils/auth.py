from __future__ import annotations

"""
Authentication utilities: password hashing (bcrypt) and JWT helpers.

This module provides:
- `hash_password` and `verify_password` using passlib's bcrypt
- `create_access_token` to create a JWT access token
- `verify_token` to validate and decode JWT tokens
- `get_current_user` FastAPI dependency using HTTPBearer to extract
  the Authorization header and return the decoded token payload

Notes:
- This module intentionally does not perform any database queries; it
  only handles cryptography and token validation.
- Replace `settings.JWT_SECRET_KEY` with a strong secret in production.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, ExpiredSignatureError, jwt
from passlib.context import CryptContext
import logging

from backend.app.utils.config import settings

logger = logging.getLogger("sim-tools.auth")

# Use bcrypt primarily but include pbkdf2_sha256 as a robust fallback
#pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
# Fallback-only context
#_fallback_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
# We'll use Argon2 via argon2-cffi for hashing (no bcrypt length issues)
from argon2 import PasswordHasher, exceptions as argon2_exceptions

# Argon2 has sensible defaults; create a PasswordHasher instance
_argon_hasher = PasswordHasher()
pwd_context = None
_fallback_context = None

# HTTP bearer scheme for extracting tokens from Authorization header
http_bearer = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2 and return the hash string.

    Uses `argon2.PasswordHasher` under the hood.
    """
    if password is None:
        raise ValueError("Password must not be None")
    return _argon_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Returns True when the password matches, False otherwise.
    """
    try:
        return _argon_hasher.verify(hashed_password, plain_password)
    except argon2_exceptions.VerifyMismatchError:
        return False
    except Exception:
        # For other argon2 errors (e.g., malformed hash) return False
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.

    `data` is a dict of claims to include (should include at least a "sub"
    claim identifying the subject). `expires_delta` may be provided to
    override the default expiry from settings.
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def verify_token(token: str) -> Dict[str, Any]:
    """Validate and decode a JWT token.

    Raises HTTPException with 401 on invalid/expired tokens.
    Returns the decoded payload as a dict on success.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception

    if not isinstance(payload, dict) or "sub" not in payload:
        raise credentials_exception
    return payload


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(http_bearer)) -> Dict[str, Any]:
    """FastAPI dependency that extracts the bearer token and returns the
    decoded token payload representing the current user.

    This does not query the database. In production, resolve the user
    from the DB using the `sub` claim if needed.
    """
    token = credentials.credentials
    payload = verify_token(token)
    return payload


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "verify_token",
    "get_current_user",
    "http_bearer",
]
