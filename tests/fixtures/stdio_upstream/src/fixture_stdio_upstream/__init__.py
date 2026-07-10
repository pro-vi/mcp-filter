"""Minimal dependency-free MCP stdio server for subprocess E2E tests."""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _result(message_id: object, result: dict[str, Any]) -> None:
    _write({"jsonrpc": "2.0", "id": message_id, "result": result})


def _handle(message: dict[str, Any]) -> None:
    message_id = message.get("id")
    if message_id is None:
        return

    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        _result(
            message_id,
            {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "fixture-stdio-upstream", "version": "0.0.0"},
            },
        )
        return

    if method == "ping":
        _result(message_id, {})
        return

    if method == "tools/list":
        _result(
            message_id,
            {
                "tools": [
                    {
                        "name": "runtime_snapshot",
                        "description": "Return one environment variable and the process arguments.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment_variable": {"type": "string"},
                            },
                            "required": ["environment_variable"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        )
        return

    if method == "tools/call" and params.get("name") == "runtime_snapshot":
        arguments = params.get("arguments") or {}
        variable = str(arguments.get("environment_variable", ""))
        snapshot = {
            "environment_value": os.environ.get(variable),
            "arguments": sys.argv[1:],
        }
        _result(
            message_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(snapshot, separators=(",", ":")),
                    }
                ],
                "isError": False,
            },
        )
        return

    _write(
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": -32601, "message": f"Unsupported method: {method}"},
        }
    )


def main() -> None:
    for line in sys.stdin:
        if line.strip():
            _handle(json.loads(line))


if __name__ == "__main__":
    main()
