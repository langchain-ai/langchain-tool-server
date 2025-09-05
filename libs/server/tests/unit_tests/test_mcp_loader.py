"""Unit tests for MCP server loader functionality."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_tool_server.mcp_loader import (
    MCPConfigError,
    initialize_mcp_client,
    load_mcp_servers_tools,
    validate_mcp_config,
)


class TestValidateMCPConfig:
    """Test MCP configuration validation."""

    def test_validate_stdio_config(self):
        """Test validation of stdio transport configuration."""
        config = {
            "name": "test_server",
            "transport": "stdio",
            "command": "python",
            "args": ["-m", "test_server"],
            "env": {"KEY": "value"},
            "cwd": "/path/to/dir",
        }

        result = validate_mcp_config(config)

        assert result["transport"] == "stdio"
        assert result["command"] == "python"
        assert result["args"] == ["-m", "test_server"]
        assert result["env"] == {"KEY": "value"}
        assert result["cwd"] == "/path/to/dir"

    def test_validate_streamable_http_config(self):
        """Test validation of streamable_http transport configuration."""
        config = {
            "name": "test_server",
            "transport": "streamable_http",
            "url": "http://localhost:8000/mcp/",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 30,
        }

        result = validate_mcp_config(config)

        assert result["transport"] == "streamable_http"
        assert result["url"] == "http://localhost:8000/mcp/"
        assert result["headers"] == {"Authorization": "Bearer token"}
        assert result["timeout"] == timedelta(seconds=30)

    def test_validate_sse_config(self):
        """Test validation of SSE transport configuration."""
        config = {
            "name": "test_server",
            "transport": "sse",
            "url": "http://localhost:9000/sse",
            "headers": {"X-Custom": "header"},
            "timeout": 10.5,
        }

        result = validate_mcp_config(config)

        assert result["transport"] == "sse"
        assert result["url"] == "http://localhost:9000/sse"
        assert result["headers"] == {"X-Custom": "header"}
        assert result["timeout"] == 10.5

    def test_validate_websocket_config(self):
        """Test validation of WebSocket transport configuration."""
        config = {
            "name": "test_server",
            "transport": "websocket",
            "url": "ws://localhost:8080/ws",
        }

        result = validate_mcp_config(config)

        assert result["transport"] == "websocket"
        assert result["url"] == "ws://localhost:8080/ws"

    def test_missing_name(self):
        """Test that missing name raises error."""
        config = {
            "transport": "stdio",
            "command": "python",
        }

        with pytest.raises(MCPConfigError, match="must have a 'name' field"):
            validate_mcp_config(config)

    def test_missing_transport(self):
        """Test that missing transport raises error."""
        config = {
            "name": "test_server",
        }

        with pytest.raises(MCPConfigError, match="must specify a 'transport' type"):
            validate_mcp_config(config)

    def test_unknown_transport(self):
        """Test that unknown transport type raises error."""
        config = {
            "name": "test_server",
            "transport": "unknown",
        }

        with pytest.raises(MCPConfigError, match="Unknown transport type"):
            validate_mcp_config(config)

    def test_stdio_missing_command(self):
        """Test that stdio without command raises error."""
        config = {
            "name": "test_server",
            "transport": "stdio",
        }

        with pytest.raises(MCPConfigError, match="must specify 'command'"):
            validate_mcp_config(config)

    def test_http_missing_url(self):
        """Test that streamable_http without URL raises error."""
        config = {
            "name": "test_server",
            "transport": "streamable_http",
        }

        with pytest.raises(MCPConfigError, match="must specify 'url'"):
            validate_mcp_config(config)


class TestLoadMCPServersTools:
    """Test MCP server tools loading."""

    @pytest.mark.asyncio
    async def test_empty_config_list(self):
        """Test that empty config list returns empty tools list."""
        tools = await load_mcp_servers_tools([])
        assert tools == []

    @pytest.mark.asyncio
    async def test_load_tools_with_prefix(self):
        """Test loading tools with name prefixing."""
        configs = [
            {
                "name": "math",
                "transport": "stdio",
                "command": "python",
                "args": ["-m", "math_server"],
            }
        ]

        # Mock the MultiServerMCPClient and load_mcp_tools
        with patch(
            "langchain_tool_server.mcp_loader.MultiServerMCPClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Create mock session context manager
            mock_session = AsyncMock()
            mock_client.session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_client.session.return_value.__aexit__ = AsyncMock()

            # Mock tools
            mock_tool = MagicMock()
            mock_tool.name = "add"
            mock_tool.metadata = {}

            with patch("langchain_tool_server.mcp_loader.load_mcp_tools") as mock_load:
                mock_load.return_value = [mock_tool]

                tools = await load_mcp_servers_tools(configs, prefix_tools=True)

                assert len(tools) == 1
                assert tools[0].name == "math.add"
                assert tools[0].base_tool.metadata["mcp_server"] == "math"
                assert tools[0].base_tool.metadata["original_name"] == "add"

    @pytest.mark.asyncio
    async def test_load_tools_without_prefix(self):
        """Test loading tools without name prefixing."""
        configs = [
            {
                "name": "math",
                "transport": "stdio",
                "command": "python",
            }
        ]

        with patch(
            "langchain_tool_server.mcp_loader.MultiServerMCPClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_session = AsyncMock()
            mock_client.session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_client.session.return_value.__aexit__ = AsyncMock()

            mock_tool = MagicMock()
            mock_tool.name = "add"

            with patch("langchain_tool_server.mcp_loader.load_mcp_tools") as mock_load:
                mock_load.return_value = [mock_tool]

                tools = await load_mcp_servers_tools(configs, prefix_tools=False)

                assert len(tools) == 1
                assert tools[0].name == "add"  # Name not prefixed

    @pytest.mark.asyncio
    async def test_handle_failed_server(self):
        """Test that failing to load from one server doesn't stop others."""
        configs = [
            {
                "name": "failing_server",
                "transport": "stdio",
                "command": "python",
            },
            {
                "name": "working_server",
                "transport": "stdio",
                "command": "python",
            },
        ]

        with patch("langchain_tool_server.mcp_loader.load_mcp_tools") as mock_load:
            # Create a working tool mock
            mock_working_tool = MagicMock()
            mock_working_tool.name = "test_tool"
            mock_working_tool.metadata = {}

            # Track call count to distinguish between servers
            call_count = 0

            def load_side_effect(session=None, connection=None):
                nonlocal call_count
                call_count += 1

                # First call (failing_server) should raise exception
                if call_count == 1:
                    raise Exception("Connection failed")
                # Second call (working_server) should return tools
                else:
                    return [mock_working_tool]

            mock_load.side_effect = load_side_effect

            tools = await load_mcp_servers_tools(configs)

            # Should have loaded tools from working server only
            assert len(tools) == 1
            assert tools[0].base_tool.metadata["mcp_server"] == "working_server"

    @pytest.mark.asyncio
    async def test_invalid_config_raises_error(self):
        """Test that invalid configuration raises MCPConfigError."""
        configs = [
            {
                "transport": "stdio",  # Missing name
                "command": "python",
            }
        ]

        with pytest.raises(MCPConfigError):
            await load_mcp_servers_tools(configs)


class TestInitializeMCPClient:
    """Test MCP client initialization."""

    @pytest.mark.asyncio
    async def test_initialize_client_success(self):
        """Test successful client initialization."""
        configs = [
            {
                "name": "server1",
                "transport": "stdio",
                "command": "python",
            },
            {
                "name": "server2",
                "transport": "streamable_http",
                "url": "http://localhost:8000/mcp/",
            },
        ]

        with patch(
            "langchain_tool_server.mcp_loader.MultiServerMCPClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = await initialize_mcp_client(configs)

            assert client == mock_client
            mock_client_class.assert_called_once()

            # Check that both servers were configured
            call_args = mock_client_class.call_args[0][0]
            assert "server1" in call_args
            assert "server2" in call_args

    @pytest.mark.asyncio
    async def test_initialize_client_skip_invalid(self):
        """Test that invalid configs are skipped during initialization."""
        configs = [
            {
                "name": "valid_server",
                "transport": "stdio",
                "command": "python",
            },
            {
                "transport": "stdio",  # Missing name - should be skipped
                "command": "python",
            },
        ]

        with patch(
            "langchain_tool_server.mcp_loader.MultiServerMCPClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = await initialize_mcp_client(configs)

            assert client == mock_client

            # Only valid server should be configured
            call_args = mock_client_class.call_args[0][0]
            assert "valid_server" in call_args
            assert len(call_args) == 1

    @pytest.mark.asyncio
    async def test_initialize_client_all_invalid(self):
        """Test that all invalid configs returns None."""
        configs = [
            {
                "transport": "stdio",  # Missing name
                "command": "python",
            },
            {
                "name": "test",  # Missing transport
            },
        ]

        client = await initialize_mcp_client(configs)
        assert client is None
