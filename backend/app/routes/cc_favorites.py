"""
CC Favorites routes — CRUD for saved CyberController login credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.user import User
from backend.app.schemas.cc_favorites import CCFavoriteCreate, CCFavoriteResponse
from backend.app.utils.auth import require_cc_access
from backend.app.utils.database import get_mongo_db

router = APIRouter(prefix="/api/cc", tags=["cc_favorites"])


@router.get("/favorites", response_model=List[CCFavoriteResponse])
async def list_favorites(
    current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
):
    """List all CC favorites for the current user."""
    collection = mongo_db["cc_favorites"]
    docs = collection.find(
        {"user_id": current_user.user_id},
        {"_id": 0, "cc_ip": 1, "username": 1, "password": 1, "created_at": 1},
    )
    return list(docs)


@router.post("/favorites", status_code=status.HTTP_200_OK)
async def save_favorite(
    favorite: CCFavoriteCreate,
    current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
):
    """Save or update a CC favorite. Upserts by (user_id, cc_ip)."""
    collection = mongo_db["cc_favorites"]
    now = datetime.now(timezone.utc).isoformat()
    collection.update_one(
        {"user_id": current_user.user_id, "cc_ip": favorite.cc_ip},
        {
            "$set": {
                "username": favorite.username,
                "password": favorite.password,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )
    return {"success": True, "message": f"Favorite for {favorite.cc_ip} saved"}


@router.delete("/favorites/{cc_ip}")
async def delete_favorite(
    cc_ip: str,
    current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
):
    """Remove a CC favorite."""
    collection = mongo_db["cc_favorites"]
    result = collection.delete_one(
        {"user_id": current_user.user_id, "cc_ip": cc_ip}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return {"success": True, "message": f"Favorite for {cc_ip} removed"}
