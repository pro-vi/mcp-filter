"""Package version."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-filter")
except PackageNotFoundError:
    __version__ = "0+unknown"
