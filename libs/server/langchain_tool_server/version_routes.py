"""Version management API routes."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from langchain_tool_server.database import Database
from langchain_tool_server.models import (
    ToolCreate,
    ToolResponse,
    ToolVersionCreate,
    ToolVersionResponse,
)


def create_version_router(database: Database) -> APIRouter:
    """Create version management router with database dependency."""
    router = APIRouter(tags=["versions"])

    @router.post("/tools", response_model=ToolResponse)
    async def create_tool(tool: ToolCreate) -> ToolResponse:
        """Create a new tool."""
        existing = await database.get_tool_by_name(tool.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tool '{tool.name}' already exists"
            )
        return await database.create_tool(tool)

    @router.get("/tools", response_model=List[ToolResponse])
    async def list_tools() -> List[ToolResponse]:
        """List all tools."""
        return await database.list_tools()

    @router.get("/tools/{tool_name}", response_model=ToolResponse)
    async def get_tool(tool_name: str) -> ToolResponse:
        """Get a tool by name."""
        tool = await database.get_tool_by_name(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        return tool

    @router.delete("/tools/{tool_name}")
    async def delete_tool(tool_name: str) -> dict:
        """Delete a tool and all its versions."""
        tool = await database.get_tool_by_name(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        deleted = await database.delete_tool(tool.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete tool"
            )
        
        return {"message": f"Tool '{tool_name}' deleted"}

    @router.post("/tools/{tool_name}/versions", response_model=ToolVersionResponse)
    async def create_tool_version(tool_name: str, version_data: ToolVersionCreate) -> ToolVersionResponse:
        """Create a new version of a tool."""
        # Verify tool exists
        tool = await database.get_tool_by_name(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        # Ensure tool_id matches
        if version_data.tool_id != tool.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tool_id in request body does not match tool"
            )
        
        # Check if version already exists
        existing = await database.get_tool_version(tool.id, version_data.version)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version '{version_data.version}' already exists for tool '{tool_name}'"
            )
        
        return await database.create_tool_version(version_data)

    @router.get("/tools/{tool_name}/versions", response_model=List[ToolVersionResponse])
    async def list_tool_versions(tool_name: str) -> List[ToolVersionResponse]:
        """List all versions of a tool."""
        tool = await database.get_tool_by_name(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        return await database.list_tool_versions(tool.id)

    @router.get("/tools/{tool_name}/versions/{version}", response_model=ToolVersionResponse)
    async def get_tool_version(tool_name: str, version: str) -> ToolVersionResponse:
        """Get a specific version of a tool."""
        tool = await database.get_tool_by_name(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        tool_version = await database.get_tool_version(tool.id, version)
        if not tool_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version '{version}' not found for tool '{tool_name}'"
            )
        
        return tool_version

    @router.get("/tools/{tool_name}/versions/latest", response_model=ToolVersionResponse)
    async def get_latest_tool_version(tool_name: str) -> ToolVersionResponse:
        """Get the latest version of a tool."""
        tool = await database.get_tool_by_name(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        tool_version = await database.get_latest_tool_version(tool.id)
        if not tool_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No versions found for tool '{tool_name}'"
            )
        
        return tool_version

    @router.delete("/tools/{tool_name}/versions/{version}")
    async def delete_tool_version(tool_name: str, version: str) -> dict:
        """Delete a specific version of a tool."""
        tool = await database.get_tool_by_name(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        tool_version = await database.get_tool_version(tool.id, version)
        if not tool_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version '{version}' not found for tool '{tool_name}'"
            )
        
        deleted = await database.delete_tool_version(tool_version.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete version"
            )
        
        return {"message": f"Version '{version}' of tool '{tool_name}' deleted"}

    return router