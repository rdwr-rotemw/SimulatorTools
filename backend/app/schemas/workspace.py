"""Workspace schemas."""
from pydantic import BaseModel, Field
from typing import List


class WorkspaceInfo(BaseModel):
    """Information about a Sapro workspace."""
    name: str = Field(..., description="Workspace name (without .wsp extension)")
    full_path: str = Field(..., description="Full path to workspace file")


class WorkspaceListResponse(BaseModel):
    """List of available workspaces."""
    workspaces: List[WorkspaceInfo] = Field(..., description="Available workspaces")
