"""Configuration loading for the MCP tool filter server."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional
from typing import Literal

from pydantic import AnyUrl, BaseModel, Field, ValidationError, field_validator

Transport = Literal["stdio", "http"]


class AllowRules(BaseModel):
    """Tool allow/deny configuration."""

    allow_tools: List[str] = Field(default_factory=list)
    allow_patterns: List[str] = Field(default_factory=list)
    deny_patterns: List[str] = Field(default_factory=list)
    rename_prefix: Optional[str] = None

    @field_validator("allow_tools", "allow_patterns", "deny_patterns", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            cleaned = [item.strip() for item in value.split(",")]
            return [item for item in cleaned if item]
        if isinstance(value, Iterable):
            # Flatten comma-separated strings in lists
            result: List[str] = []
            for item in value:
                item_str = str(item)
                if "," in item_str:
                    # Split comma-separated values
                    result.extend(part.strip() for part in item_str.split(",") if part.strip())
                else:
                    result.append(item_str)
            return result
        raise TypeError("Value must be a string or iterable of strings")


class UpstreamConfig(BaseModel):
    """Settings for how the filter connects to the upstream MCP server."""

    transport: Transport = "stdio"
    stdio_command: Optional[str] = None
    stdio_args: List[str] = Field(default_factory=list)
    stdio_env: Dict[str, str] = Field(default_factory=dict)
    http_url: Optional[AnyUrl] = None
    http_headers: Dict[str, str] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    """Top-level configuration for the filter server."""

    name: str = "mcp-filter"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    include_health_tool: bool = False
    show_token_estimates: bool = False
    upstream: UpstreamConfig = Field(default_factory=UpstreamConfig)
    rules: AllowRules = Field(default_factory=AllowRules)


class ConfigError(RuntimeError):
    """Raised when configuration is invalid."""


@dataclass
class ConfigOverrides:
    """CLI-provided overrides."""

    name: Optional[str] = None
    log_level: Optional[str] = None
    include_health_tool: Optional[bool] = None
    show_token_estimates: Optional[bool] = None
    transport: Optional[Transport] = None
    stdio_command: Optional[str] = None
    stdio_args: Optional[List[str]] = None
    stdio_env: Optional[Dict[str, str]] = None
    http_url: Optional[str] = None
    http_headers: Optional[Dict[str, str]] = None
    allow_tools: Optional[List[str]] = None
    allow_patterns: Optional[List[str]] = None
    deny_patterns: Optional[List[str]] = None
    rename_prefix: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """Convert overrides into nested dictionary structure."""
        data: Dict[str, Any] = {}
        if self.name is not None:
            data["name"] = self.name
        if self.log_level is not None:
            data["log_level"] = self.log_level
        if self.include_health_tool is not None:
            data["include_health_tool"] = self.include_health_tool
        if self.show_token_estimates is not None:
            data["show_token_estimates"] = self.show_token_estimates

        upstream: Dict[str, Any] = {}
        if self.transport is not None:
            upstream["transport"] = self.transport
        if self.stdio_command is not None:
            upstream["stdio_command"] = self.stdio_command
        if self.stdio_args is not None:
            upstream["stdio_args"] = self.stdio_args
        if self.stdio_env is not None:
            upstream["stdio_env"] = self.stdio_env
        if self.http_url is not None:
            upstream["http_url"] = self.http_url
        if self.http_headers is not None:
            upstream["http_headers"] = self.http_headers
        if upstream:
            data["upstream"] = upstream

        rules: Dict[str, Any] = {}
        if self.allow_tools is not None:
            rules["allow_tools"] = self.allow_tools
        if self.allow_patterns is not None:
            rules["allow_patterns"] = self.allow_patterns
        if self.deny_patterns is not None:
            rules["deny_patterns"] = self.deny_patterns
        if self.rename_prefix is not None:
            rules["rename_prefix"] = self.rename_prefix
        if rules:
            data["rules"] = rules

        return data


def load_config(
    overrides: Optional[ConfigOverrides] = None,
    env: Optional[Mapping[str, str]] = None,
) -> ServerConfig:
    """Load the full server configuration from environment + overrides."""

    base = ServerConfig().model_copy(deep=True).model_dump()
    env_data = _load_from_env(env or os.environ)
    merged = _deep_update(base, env_data)
    if overrides is not None:
        merged = _deep_update(merged, overrides.as_dict())

    try:
        config = ServerConfig(**merged)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc

    _validate_config(config)
    return config


def _load_from_env(env: Mapping[str, str]) -> Dict[str, Any]:
    """Read configuration values from environment variables."""

    data: Dict[str, Any] = {}

    server_level = env.get("MF_LOG_LEVEL")
    if server_level:
        data["log_level"] = server_level.upper()

    server_name = env.get("MF_NAME")
    if server_name:
        data["name"] = server_name

    if "MF_INCLUDE_HEALTH_TOOL" in env:
        data["include_health_tool"] = _to_bool(env["MF_INCLUDE_HEALTH_TOOL"])
    if "MF_NO_HEALTH" in env:
        data["include_health_tool"] = not _to_bool(env["MF_NO_HEALTH"])
    if "MF_SHOW_TOKEN_ESTIMATES" in env:
        data["show_token_estimates"] = _to_bool(env["MF_SHOW_TOKEN_ESTIMATES"])

    upstream: Dict[str, Any] = {}
    transport = env.get("MF_TRANSPORT")
    if transport:
        upstream["transport"] = transport.lower()

    stdio_cmd = env.get("MF_STDIO_COMMAND")
    if stdio_cmd:
        upstream["stdio_command"] = stdio_cmd
    stdio_args = env.get("MF_STDIO_ARGS")
    if stdio_args:
        upstream["stdio_args"] = shlex.split(stdio_args)
    stdio_env_raw = env.get("MF_STDIO_ENV")
    if stdio_env_raw:
        upstream["stdio_env"] = _parse_env_vars(stdio_env_raw)

    http_url = env.get("MF_HTTP_URL")
    if http_url:
        upstream["http_url"] = http_url
    headers_raw = env.get("MF_HTTP_HEADERS")
    if headers_raw:
        upstream["http_headers"] = _parse_headers(headers_raw)

    if upstream:
        data["upstream"] = upstream

    rules: Dict[str, Any] = {}
    allow_tools = env.get("MF_ALLOW_TOOLS")
    if allow_tools:
        rules["allow_tools"] = _split_csv(allow_tools)

    allow_patterns = env.get("MF_ALLOW_PATTERNS")
    if allow_patterns:
        rules["allow_patterns"] = _split_csv(allow_patterns)

    deny_patterns = env.get("MF_DENY_PATTERNS")
    if deny_patterns:
        rules["deny_patterns"] = _split_csv(deny_patterns)

    rename_prefix = env.get("MF_RENAME_PREFIX")
    if rename_prefix:
        rules["rename_prefix"] = rename_prefix

    if rules:
        data["rules"] = rules

    return data


def _split_csv(value: str) -> List[str]:
    return [item for item in (part.strip() for part in value.split(",")) if item]


def _parse_headers(value: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for item in value.split(";"):
        if not item.strip():
            continue
        if "=" not in item:
            raise ConfigError(
                f"HTTP header '{item}' must be in key=value form (separated by ';')."
            )
        key, val = item.split("=", 1)
        headers[key.strip()] = val.strip()
    return headers


def _parse_env_vars(value: str) -> Dict[str, str]:
    """Parse environment variables from semicolon-separated key=value pairs."""
    env_vars: Dict[str, str] = {}
    for item in value.split(";"):
        if not item.strip():
            continue
        if "=" not in item:
            raise ConfigError(
                f"Environment variable '{item}' must be in key=value form (separated by ';')."
            )
        key, val = item.split("=", 1)
        env_vars[key.strip()] = val.strip()
    return env_vars


def _to_bool(value: str) -> bool:
    truthy = {"1", "true", "t", "yes", "y", "on"}
    falsy = {"0", "false", "f", "no", "n", "off"}
    lower = value.strip().lower()
    if lower in truthy:
        return True
    if lower in falsy:
        return False
    raise ConfigError(f"Cannot parse boolean value '{value}'.")


def _deep_update(base: MutableMapping[str, Any], updates: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, Mapping):
            base_sub = base.get(key, {})
            if not isinstance(base_sub, Mapping):
                base_sub = {}
            result[key] = _deep_update(dict(base_sub), value)
        else:
            result[key] = value
    return result


def _validate_config(config: ServerConfig) -> None:
    if config.upstream.transport == "stdio":
        if not config.upstream.stdio_command:
            raise ConfigError("stdio transport requires --stdio-command or MF_STDIO_COMMAND.")
    elif config.upstream.transport == "http":
        if not config.upstream.http_url:
            raise ConfigError("http transport requires --http-url or MF_HTTP_URL.")
