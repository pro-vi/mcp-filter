# Changelog

All notable changes to this project are documented in this file.

## [0.2.0] - 2026-07-09

### Added

- Selective upstream environment forwarding with repeatable `--stdio-env KEY=VALUE`
  options and `MF_STDIO_ENV` configuration.
- Exact-argument stdio spawning for `uvx`, `uv run`, `npx`, and custom commands.
- Real subprocess coverage for Python runners and the minimum and latest supported
  FastMCP versions.

### Changed

- Require FastMCP 2.14.5 or newer for configured stdio environments.
- Preserve legacy `python` and direct `.py` command shapes while using FastMCP's
  generic stdio transport.
- Treat each repeatable `--stdio-arg` value literally. `MF_STDIO_ARGS` continues to
  support shell-style splitting.
- Stop implicitly adding `--prefer-offline` to `npx`; configured arguments are now
  passed unchanged.

### Security

- Forward only configured environment variables plus the MCP SDK's minimal default
  environment instead of the filter's complete environment.
- Redact malformed environment values from configuration errors and keep diagnostics
  off the MCP protocol output stream.

### Contributors

- Daniel Nowicki ([#1](https://github.com/pro-vi/mcp-filter/pull/1))
- Radko Jiroušek ([#3](https://github.com/pro-vi/mcp-filter/pull/3))

## [0.1.0] - 2025-10-11

- Initial release.

[0.2.0]: https://github.com/pro-vi/mcp-filter/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/pro-vi/mcp-filter/releases/tag/v0.1.0
