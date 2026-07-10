from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "stdio_upstream"
FIXTURE_SCRIPT = FIXTURE_PROJECT / "src" / "fixture_stdio_upstream" / "__init__.py"


def _run_cli(
    *args: str,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(env or {})
    return subprocess.run(
        [sys.executable, "-m", "mcp_filter", *args],
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
        check=False,
    )


@asynccontextmanager
async def _filter_session(
    upstream_command: str,
    upstream_args: Sequence[str],
    *,
    configured_env: Mapping[str, str] | None = None,
    filter_env: Mapping[str, str] | None = None,
) -> AsyncIterator[ClientSession]:
    args = [
        "-m",
        "mcp_filter",
        "run",
        "--transport",
        "stdio",
        "--stdio-command",
        upstream_command,
        "--allow-tool",
        "runtime_snapshot",
    ]
    args.extend(f"--stdio-arg={arg}" for arg in upstream_args)
    for key, value in (configured_env or {}).items():
        args.extend(("--stdio-env", f"{key}={value}"))

    environment = os.environ.copy()
    environment.update(filter_env or {})
    parameters = StdioServerParameters(
        command=sys.executable,
        args=args,
        env=environment,
    )

    with tempfile.TemporaryFile(mode="w+") as stderr:
        try:
            async with stdio_client(parameters, errlog=stderr) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=120),
                ) as session:
                    await session.initialize()
                    yield session
        except Exception as exc:
            stderr.seek(0)
            raise AssertionError(f"mcp-filter subprocess failed:\n{stderr.read()}") from exc


async def _runtime_snapshot(session: ClientSession, variable: str) -> dict[str, object]:
    tools = await session.list_tools()
    assert [tool.name for tool in tools.tools] == ["runtime_snapshot"]

    result = await session.call_tool(
        "runtime_snapshot",
        {"environment_variable": variable},
    )
    assert result.isError is False
    assert len(result.content) == 1
    text = getattr(result.content[0], "text", None)
    assert isinstance(text, str)
    return json.loads(text)


@pytest.mark.asyncio
async def test_cli_environment_is_forwarded_selectively_to_real_upstream() -> None:
    async with _filter_session(
        sys.executable,
        (str(FIXTURE_SCRIPT), "--sentinel", "python"),
        configured_env={
            "EXPLICIT_SECRET": "value=with=equals",
            "SECOND_EXPLICIT": "second;value",
        },
        filter_env={
            "MF_STDIO_ENV": "AMBIENT_SECRET=must-be-replaced",
            "UNRELATED_SECRET": "must-not-reach-upstream",
        },
    ) as session:
        explicit = await _runtime_snapshot(session, "EXPLICIT_SECRET")
        second = await _runtime_snapshot(session, "SECOND_EXPLICIT")
        ambient = await _runtime_snapshot(session, "AMBIENT_SECRET")
        unrelated = await _runtime_snapshot(session, "UNRELATED_SECRET")

    assert explicit == {
        "environment_value": "value=with=equals",
        "arguments": ["--sentinel", "python"],
    }
    assert second["environment_value"] == "second;value"
    assert ambient["environment_value"] is None
    assert unrelated["environment_value"] is None


@pytest.mark.asyncio
async def test_environment_configuration_reaches_real_upstream() -> None:
    async with _filter_session(
        sys.executable,
        (str(FIXTURE_SCRIPT),),
        filter_env={"MF_STDIO_ENV": r"CONFIG_SECRET=from\;config;SECOND_CONFIG=second"},
    ) as session:
        snapshot = await _runtime_snapshot(session, "CONFIG_SECRET")
        second = await _runtime_snapshot(session, "SECOND_CONFIG")

    assert snapshot["environment_value"] == "from;config"
    assert second["environment_value"] == "second"


@pytest.mark.asyncio
@pytest.mark.network
@pytest.mark.skipif(
    shutil.which("uv") is None or shutil.which("uvx") is None,
    reason="real uv and uvx executables are required",
)
@pytest.mark.parametrize(
    ("runner", "upstream_args"),
    [
        (
            "uvx",
            ("--from", str(FIXTURE_PROJECT), "fixture-stdio-upstream", "--sentinel", "uvx"),
        ),
        ("uv", ("run", "--no-project", str(FIXTURE_SCRIPT), "--sentinel", "uv")),
    ],
)
async def test_python_package_runners_serve_tools_end_to_end(
    runner: str,
    upstream_args: Sequence[str],
) -> None:
    async with _filter_session(
        runner,
        upstream_args,
        configured_env={"E2E_RUNNER": runner},
    ) as session:
        snapshot = await _runtime_snapshot(session, "E2E_RUNNER")

    assert snapshot == {
        "environment_value": runner,
        "arguments": ["--sentinel", runner],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("command_shape", ["python", "script"])
async def test_python_command_shapes_and_arguments_with_spaces(
    command_shape: str,
    tmp_path: Path,
) -> None:
    script_dir = tmp_path / "Project With Spaces"
    script_dir.mkdir()
    script = script_dir / "fixture server.py"
    shutil.copyfile(FIXTURE_SCRIPT, script)
    sentinel = f"{command_shape} value with spaces"

    if command_shape == "python":
        command = "python"
        args = (str(script), "--sentinel", sentinel)
    else:
        command = str(script)
        args = ("--sentinel", sentinel)

    async with _filter_session(command, args) as session:
        snapshot = await _runtime_snapshot(session, "UNSET")

    assert snapshot["arguments"] == ["--sentinel", sentinel]


def test_missing_upstream_command_reports_stderr_without_protocol_output() -> None:
    result = _run_cli(
        "run",
        "--stdio-command",
        "definitely-not-an-installed-mcp-runner",
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "was not found or is not executable" in result.stderr


def test_invalid_cli_environment_fails_before_starting_upstream() -> None:
    secret = "sk-secret-that-must-not-be-logged"
    result = _run_cli(
        "run",
        "--stdio-command",
        sys.executable,
        "--stdio-env",
        secret,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Configuration error" in result.stderr
    assert "Environment entry 1 must be in KEY=VALUE format" in result.stderr
    assert secret not in result.stderr


def test_invalid_environment_configuration_redacts_raw_value() -> None:
    secret = "token-that-must-not-be-logged"
    result = _run_cli(
        "run",
        env={
            "MF_STDIO_COMMAND": sys.executable,
            "MF_STDIO_ENV": secret,
        },
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Environment entry 1 must be in KEY=VALUE format" in result.stderr
    assert secret not in result.stderr
