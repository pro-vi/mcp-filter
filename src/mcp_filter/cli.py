"""Command line interface for the MCP tool filter."""

from __future__ import annotations

import asyncio
import platform
from typing import Dict, List, Optional

import typer
from rich.console import Console
from typing_extensions import Annotated

from .config import ConfigError, ConfigOverrides, load_config
from .filter_server import build_server
from .version import __version__

app = typer.Typer(
    name="mcp-filter",
    help="Proxy MCP server that exposes a filtered tool surface.",
    no_args_is_help=True,
)
console = Console()
error_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"mcp-filter version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Top-level Typer callback used for eager --version."""
    _ = version


@app.command()
def run(
    name: Optional[str] = typer.Option(None, "--name", help="Server display name."),
    transport: Optional[str] = typer.Option(
        None, "--transport", "-t", help="Upstream transport: stdio or http."
    ),
    stdio_command: Optional[str] = typer.Option(
        None, "--stdio-command", help="Executable to launch for stdio transport."
    ),
    stdio_args: Optional[List[str]] = typer.Option(
        None,
        "--stdio-arg",
        help=(
            "One literal argument for the stdio command (repeatable). "
            "Use --stdio-arg=value when the value begins with '-'."
        ),
    ),
    stdio_env: Optional[List[str]] = typer.Option(
        None,
        "--stdio-env",
        help="Environment variable for the stdio command as KEY=VALUE (repeatable).",
    ),
    http_url: Optional[str] = typer.Option(
        None, "--http-url", help="HTTP/SSE endpoint for the upstream MCP server."
    ),
    http_headers: Optional[List[str]] = typer.Option(
        None,
        "--http-header",
        help="Additional HTTP header key=value (repeatable).",
    ),
    allow_tools: Optional[List[str]] = typer.Option(
        None,
        "--allow-tool",
        "-a",
        help="Exact tool name to expose (repeatable, or comma-separated).",
    ),
    allow_patterns: Optional[List[str]] = typer.Option(
        None,
        "--allow-pattern",
        help="Regex pattern for tool names to expose (repeatable, or comma-separated).",
    ),
    deny_patterns: Optional[List[str]] = typer.Option(
        None,
        "--deny-pattern",
        help="Regex pattern for tool names to block (repeatable, or comma-separated).",
    ),
    rename_prefix: Optional[str] = typer.Option(
        None,
        "--prefix",
        "-p",
        help="Prefix applied to exposed tool names.",
    ),
    log_level: Optional[str] = typer.Option(
        None, "--log-level", help="Log level (DEBUG, INFO, WARNING, ERROR)."
    ),
    health: bool = typer.Option(
        False,
        "--health",
        help="Enable the built-in health tool (disabled by default).",
    ),
    no_token_estimates: bool = typer.Option(
        False,
        "--no-token-estimates",
        help="Disable token estimate logging.",
    ),
) -> None:
    """Run the filter server with the given configuration."""

    try:
        overrides = ConfigOverrides(
            name=name,
            log_level=log_level.upper() if log_level else None,
            include_health_tool=True if health else None,
            show_token_estimates=False if no_token_estimates else None,
            transport=transport.lower() if transport else None,
            stdio_command=stdio_command,
            stdio_args=_parse_stdio_args(stdio_args),
            stdio_env=_parse_stdio_env(stdio_env),
            http_url=http_url,
            http_headers=_parse_headers(http_headers),
            allow_tools=allow_tools,
            allow_patterns=allow_patterns,
            deny_patterns=deny_patterns,
            rename_prefix=rename_prefix,
        )
        config = load_config(overrides=overrides)
    except ConfigError as exc:
        error_console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _maybe_install_uvloop()

    async def _run() -> None:
        application = await build_server(config)
        await application.run()

    try:
        asyncio.run(_run())
    except ConfigError as exc:
        error_console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        error_console.print("\n[yellow]Shutting down...[/yellow]")


def _parse_headers(values: Optional[List[str]]) -> Optional[Dict[str, str]]:
    if not values:
        return None
    headers: Dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ConfigError(f"HTTP header '{item}' must be in key=value format.")
        key, value = item.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers


def _parse_stdio_env(values: Optional[List[str]]) -> Optional[Dict[str, str]]:
    if not values:
        return None
    env: Dict[str, str] = {}
    for index, item in enumerate(values, start=1):
        if "=" not in item:
            raise ConfigError(f"Environment entry {index} must be in KEY=VALUE format.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigError("Environment variable name cannot be empty.")
        env[key] = value
    return env


def _parse_stdio_args(values: Optional[List[str]]) -> Optional[List[str]]:
    """Preserve each repeatable option value as one upstream argument."""
    if not values:
        return None
    return list(values)


def _maybe_install_uvloop() -> None:
    if platform.system().lower() == "windows":
        return
    try:
        import uvloop  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        return
    uvloop.install()
