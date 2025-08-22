"""create tool tables

Revision ID: 001_create_tool_tables
Revises: 
Create Date: 2025-01-22 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "001_create_tool_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tools table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tools (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )

    # Create tool_versions table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
            version VARCHAR(50) NOT NULL,
            schema_json JSONB NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE(tool_id, version)
        );
        """
    )

    # Create indexes for tools
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tools_name
        ON tools (name);
        """
    )

    # Create indexes for tool_versions
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tool_versions_tool_id
        ON tool_versions (tool_id);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tool_versions_created_at
        ON tool_versions (created_at);
        """
    )


def downgrade() -> None:
    # Drop tables in reverse order (tool_versions first due to foreign key)
    op.execute("DROP TABLE IF EXISTS tool_versions CASCADE;")
    op.execute("DROP TABLE IF EXISTS tools CASCADE;")