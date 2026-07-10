"""Utilities for interacting with an upstream MCP server."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel

from .config import ConfigError, UpstreamConfig

logger = logging.getLogger(__name__)


class ToolSchema(BaseModel):
    """Normalized representation of upstream tool metadata."""

    name: str
    description: str
    input_schema: Dict[str, Any]


class Upstream(Protocol):
    """Interface for upstream MCP clients."""

    async def list_tools(self) -> List[ToolSchema]:
        """Fetch the list of tools exposed by the upstream server."""

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Invoke a tool on the upstream server."""


class _FastMCPUpstream:
    """Wrapper around a fastmcp client instance."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def list_tools(self) -> List[ToolSchema]:
        tools = await self._client.list_tools()
        normalized: List[ToolSchema] = []
        for tool in tools:
            name = getattr(tool, "name", None)
            if name is None and isinstance(tool, dict):
                name = tool.get("name")
            description = getattr(tool, "description", None)
            if description is None and isinstance(tool, dict):
                description = tool.get("description", "")
            if description is None:
                description = ""
            # Try camelCase first (MCP standard), then snake_case
            input_schema = getattr(tool, "inputSchema", None)
            if input_schema is None:
                input_schema = getattr(tool, "input_schema", None)
            if input_schema is None and isinstance(tool, dict):
                input_schema = tool.get("inputSchema") or tool.get("input_schema", {})
            if input_schema is None:
                input_schema = {}

            if not name:
                raise ConfigError("Upstream returned a tool without a name.")

            normalized.append(
                ToolSchema(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                )
            )
        return normalized

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        result = await self._client.call_tool(name=name, arguments=args)

        # Extract content from CallToolResult if needed
        # MCP Server's call_tool handler expects a list of content items
        if hasattr(result, 'content'):
            return result.content
        elif isinstance(result, dict) and 'content' in result:
            return result['content']

        # If it's already a list, return as-is
        return result


async def make_upstream(cfg: UpstreamConfig) -> Upstream:
    """Create a connection to the upstream MCP server."""

    try:
        import fastmcp
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise ConfigError(
            "The 'fastmcp' package is required to connect to an upstream server."
        ) from exc

    if cfg.transport == "stdio":
        if not cfg.stdio_command:
            raise ConfigError("stdio transport requires a command to spawn.")
        client = await _connect_stdio(fastmcp, cfg.stdio_command, cfg.stdio_args, cfg.stdio_env)
    elif cfg.transport == "http":
        if not cfg.http_url:
            raise ConfigError("http transport requires an http_url.")
        client = await _connect_http(fastmcp, cfg.http_url, cfg.http_headers)
    else:  # pragma: no cover - guarded by typing
        raise ConfigError(f"Unsupported transport '{cfg.transport}'.")

    return _FastMCPUpstream(client)


async def _connect_stdio(fastmcp: Any, command: str, args: Optional[List[str]], env: Optional[Dict[str, str]] = None) -> Any:
    args = args or []

    # Try modern FastMCP (>= 2.0) with Client + StdioTransport
    try:
        from fastmcp import Client
        from fastmcp.client import NpxStdioTransport, PythonStdioTransport

        # Detect transport type based on command
        if command == "npx":
            # npx @package args -> NpxStdioTransport(package, args)
            if not args:
                raise ConfigError("npx transport requires a package name")
            package = args[0]
            package_args = args[1:] if len(args) > 1 else []
            transport = NpxStdioTransport(package=package, args=package_args, env_vars=env)
        elif command.endswith(".py") or command == "python":
            # python script.py args -> PythonStdioTransport(script, args)
            if command == "python" and args:
                script = args[0]
                script_args = args[1:] if len(args) > 1 else []
            else:
                script = command
                script_args = args
            transport = PythonStdioTransport(script_path=script, args=script_args, env=env)
        else:
            # Generic command -> try importing generic StdioTransport or NodeStdioTransport
            from fastmcp.client import StdioTransport
            # StdioTransport might not accept command directly, let's check NodeStdioTransport
            try:
                from fastmcp.client import NodeStdioTransport
                transport = NodeStdioTransport(command=command, args=args, env=env)
            except (ImportError, TypeError):
                # Fallback to generic if available
                transport = StdioTransport(command=command, args=args, env=env)

        client = Client(transport)

        # Client requires async context manager, enter it now
        if hasattr(client, "__aenter__"):
            await client.__aenter__()

        return client
    except (ImportError, AttributeError) as e:
        logger.debug(f"Modern FastMCP transport failed: {e}")

    # Fallback: try legacy patterns
    if hasattr(fastmcp, "connect_stdio"):
        return await fastmcp.connect_stdio(command, *args)
    if hasattr(fastmcp, "client"):
        client_mod = fastmcp.client
        if hasattr(client_mod, "connect_stdio"):
            return await client_mod.connect_stdio(command, args=args)

    raise ConfigError("Installed fastmcp version does not expose a stdio client.")


async def _connect_http(fastmcp: Any, url: str, headers: Optional[Dict[str, str]]) -> Any:
    headers = headers or {}

    # Try modern FastMCP (>= 2.0) with Client + SSETransport
    try:
        from fastmcp import Client
        from fastmcp.client import SSETransport

        transport = SSETransport(url=url, headers=headers)
        client = Client(transport)

        # Client requires async context manager, enter it now
        if hasattr(client, "__aenter__"):
            await client.__aenter__()

        return client
    except (ImportError, AttributeError):
        pass

    # Fallback: try legacy patterns
    if hasattr(fastmcp, "connect_http"):
        return await fastmcp.connect_http(url, headers=headers)
    if hasattr(fastmcp, "client"):
        client_mod = fastmcp.client
        if hasattr(client_mod, "connect_http"):
            return await client_mod.connect_http(url, headers=headers)

    raise ConfigError("Installed fastmcp version does not expose an HTTP client.")
