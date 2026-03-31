"""Standalone MCP client for connecting to MCP servers via SSE transport.

Used when running the pipeline outside of Claude Code (e.g., via cron/scheduler).
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class StandaloneMCPClient:
    """Lightweight MCP client that connects to an MCP server via SSE/HTTP."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self._session = None
        self._connected = False

    async def connect(self):
        """Establish connection to the MCP server."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            self._sse_cm = sse_client(self.server_url)
            streams = await self._sse_cm.__aenter__()
            self._session = ClientSession(*streams)
            await self._session.__aenter__()
            await self._session.initialize()
            self._connected = True
            logger.info("MCP client connected to %s", self.server_url)
        except Exception as e:
            logger.warning("MCP connection failed for %s: %s", self.server_url, e)
            self._connected = False

    async def close(self):
        """Close the MCP connection."""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
        if hasattr(self, "_sse_cm"):
            try:
                await self._sse_cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._connected = False

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return the result."""
        if not self._connected or not self._session:
            logger.warning("MCP not connected — cannot call %s", tool_name)
            return []

        try:
            result = await self._session.call_tool(tool_name, arguments)
            # Parse the result content
            if hasattr(result, "content") and result.content:
                for block in result.content:
                    if hasattr(block, "text"):
                        try:
                            return json.loads(block.text)
                        except (json.JSONDecodeError, TypeError):
                            return block.text
            return result
        except Exception as e:
            logger.error("MCP tool call failed (%s): %s", tool_name, e)
            return []

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()


async def create_mcp_clients(servers: dict[str, str]) -> dict[str, StandaloneMCPClient]:
    """Create and connect MCP clients for all configured servers.

    Args:
        servers: Dict of server_name -> server_url

    Returns:
        Dict of server_name -> connected client (or None if failed)
    """
    clients = {}
    for name, url in servers.items():
        client = StandaloneMCPClient(url)
        try:
            await client.connect()
            clients[name] = client
        except Exception as e:
            logger.warning("Failed to connect MCP client '%s': %s", name, e)
            clients[name] = None
    return clients


async def close_mcp_clients(clients: dict[str, StandaloneMCPClient | None]):
    """Close all MCP client connections."""
    for name, client in clients.items():
        if client:
            await client.close()
