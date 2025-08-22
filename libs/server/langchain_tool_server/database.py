"""Database configuration and CRUD operations."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
from langchain_tool_server.models import ToolCreate, ToolResponse, ToolVersionCreate, ToolVersionResponse


class Database:
    """Database connection and CRUD operations."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Connect to the database."""
        self._pool = await asyncpg.create_pool(self.database_url)
    
    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._pool:
            await self._pool.close()
    
    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool."""
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool
    
    async def create_tool(self, tool: ToolCreate) -> ToolResponse:
        """Create a new tool."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tools (name, description, created_at, updated_at)
                VALUES ($1, $2, $3, $3)
                RETURNING id, name, description, created_at, updated_at
                """,
                tool.name,
                tool.description,
                datetime.utcnow()
            )
            return ToolResponse(**dict(row))
    
    async def get_tool_by_name(self, name: str) -> Optional[ToolResponse]:
        """Get a tool by name."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, description, created_at, updated_at
                FROM tools
                WHERE name = $1
                """,
                name
            )
            return ToolResponse(**dict(row)) if row else None
    
    async def get_tool_by_id(self, tool_id: uuid.UUID) -> Optional[ToolResponse]:
        """Get a tool by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, description, created_at, updated_at
                FROM tools
                WHERE id = $1
                """,
                tool_id
            )
            return ToolResponse(**dict(row)) if row else None
    
    async def list_tools(self) -> List[ToolResponse]:
        """List all tools."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, description, created_at, updated_at
                FROM tools
                ORDER BY created_at DESC
                """
            )
            return [ToolResponse(**dict(row)) for row in rows]
    
    async def update_tool(self, tool_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[ToolResponse]:
        """Update a tool."""
        if not updates:
            return await self.get_tool_by_id(tool_id)
        
        set_clauses = []
        values = []
        param_idx = 1
        
        for key, value in updates.items():
            if key in ["name", "description"]:
                set_clauses.append(f"{key} = ${param_idx}")
                values.append(value)
                param_idx += 1
        
        if not set_clauses:
            return await self.get_tool_by_id(tool_id)
        
        # Always update updated_at
        set_clauses.append(f"updated_at = ${param_idx}")
        values.append(datetime.utcnow())
        param_idx += 1
        
        # Add tool_id as the last parameter
        values.append(tool_id)
        
        query = f"""
            UPDATE tools
            SET {', '.join(set_clauses)}
            WHERE id = ${param_idx}
            RETURNING id, name, description, created_at, updated_at
        """
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            return ToolResponse(**dict(row)) if row else None
    
    async def delete_tool(self, tool_id: uuid.UUID) -> bool:
        """Delete a tool."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tools WHERE id = $1",
                tool_id
            )
            return result.split()[-1] == "1"
    
    async def create_tool_version(self, tool_version: ToolVersionCreate) -> ToolVersionResponse:
        """Create a new tool version."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tool_versions (tool_id, version, schema_json, code, created_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, tool_id, version, schema_json, code, created_at
                """,
                tool_version.tool_id,
                tool_version.version,
                tool_version.schema_json,
                tool_version.code,
                datetime.utcnow()
            )
            return ToolVersionResponse(**dict(row))
    
    async def get_tool_version(self, tool_id: uuid.UUID, version: str) -> Optional[ToolVersionResponse]:
        """Get a specific tool version."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tool_id, version, schema_json, code, created_at
                FROM tool_versions
                WHERE tool_id = $1 AND version = $2
                """,
                tool_id,
                version
            )
            return ToolVersionResponse(**dict(row)) if row else None
    
    async def get_latest_tool_version(self, tool_id: uuid.UUID) -> Optional[ToolVersionResponse]:
        """Get the latest version of a tool."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, tool_id, version, schema_json, code, created_at
                FROM tool_versions
                WHERE tool_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                tool_id
            )
            return ToolVersionResponse(**dict(row)) if row else None
    
    async def list_tool_versions(self, tool_id: uuid.UUID) -> List[ToolVersionResponse]:
        """List all versions of a tool."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, tool_id, version, schema_json, code, created_at
                FROM tool_versions
                WHERE tool_id = $1
                ORDER BY created_at DESC
                """,
                tool_id
            )
            return [ToolVersionResponse(**dict(row)) for row in rows]
    
    async def delete_tool_version(self, tool_version_id: uuid.UUID) -> bool:
        """Delete a tool version."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tool_versions WHERE id = $1",
                tool_version_id
            )
            return result.split()[-1] == "1"