<div align="center">
  <img src="logo.png" alt="MCP Filter" width="300">
  <h1>MCP Filter</h1>
  <p>A proxy MCP (Model Context Protocol) server that filters the upstream tool surface to just the tools you need. Expose one or two critical tools (for example, <code>execute_sql</code> on Supabase) while filtering out the token-costly ones, without having to modify the upstream implementation.</p>
</div>

## Before & After

**Before:** Unfiltered MCP servers consumed ~50k tokens on a fresh Claude Code session

```
⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁   claude-sonnet-4-5 · 112k/200k tokens (56%)
⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁
⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁   ⛁ System: 2.3k tokens
⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁   ⛁ System tools: 11.8k tokens
⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁   ⛁ MCP tools: 50.1k tokens (25%)  ← Large!
⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛶ Free space: 88k (44%)
```

**After:** With mcp-filter, reduced to ~13.7k tokens (72% reduction) while keeping all necessary tools.

```
⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛶ ⛶   claude-sonnet-4-5 · 80k/200k tokens (40%)
⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛁ ⛶ ⛶ ⛶
⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ System: 2.3k tokens
⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ System tools: 11.8k tokens
⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛁ MCP tools: 13.7k tokens (6.9%)  ← Filtered!
⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶ ⛶   ⛶ Free space: 120k (60%)  ← +32k gained
```

Filter only the tools you need, save context for longer sessions.

**To see your token usage:** Open Claude Code and run `/context` to view the breakdown.

## What & Why

- **Static allowlist** keeps the exposed tool list tiny, cutting context usage for clients that serialize tool schemas.
- **Drop-in proxy**: stands in front of any MCP server that speaks stdio or HTTP/SSE, forwarding calls transparently.
- **Safety guardrails**: optional regex-based deny list, optional prefix, and optional health tool for observability.

## Installation

Python 3.10+ is supported; 3.11 is recommended.

### Using pip

```bash
pip install mcp-filter
```

### Using uv (faster, modern alternative)

```bash
# Run directly without installing (like npx)
uvx mcp-filter --version

# Or install globally
uv tool install mcp-filter
```

**From source (development):**

```bash
pyenv install 3.11.9
pyenv local 3.11.9
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Quick Start

```bash
mcp-filter run \
  -t stdio \
  --stdio-command npx \
  --stdio-arg "-y @supabase/mcp-server-supabase@latest --access-token YOUR_TOKEN" \
  -a "execute_sql,list_tables,get_project"
```

**Shorthand flags:** `-t` (transport), `-a` (allow-tool), `-d` (deny-pattern), `-p` (prefix)

**Note:** Both `--stdio-arg` and `-a` support flexible input - use repeatable flags or comma-separated strings, whichever is cleaner for your use case.

## How to Wrap Your MCP

### Concept

Transform any existing MCP server config by wrapping it with mcp-filter. The filter proxies your original command and only exposes the tools you specify with `-a`.

**Before (original Supabase config):**

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--access-token",
        "YOUR_TOKEN"
      ]
    }
  }
}
```

This exposes all 29 tools (**~20.8k tokens**):

<details>
<summary>Show all tools</summary>

```
└ mcp__supabase__search_docs (supabase): 2.8k tokens
└ mcp__supabase__list_organizations (supabase): 582 tokens
└ mcp__supabase__get_organization (supabase): 604 tokens
└ mcp__supabase__list_projects (supabase): 600 tokens
└ mcp__supabase__get_project (supabase): 603 tokens
└ mcp__supabase__get_cost (supabase): 646 tokens
└ mcp__supabase__confirm_cost (supabase): 682 tokens
└ mcp__supabase__create_project (supabase): 832 tokens
└ mcp__supabase__pause_project (supabase): 599 tokens
└ mcp__supabase__restore_project (supabase): 599 tokens
└ mcp__supabase__list_tables (supabase): 640 tokens
└ mcp__supabase__list_extensions (supabase): 596 tokens
└ mcp__supabase__list_migrations (supabase): 596 tokens
└ mcp__supabase__apply_migration (supabase): 668 tokens
└ mcp__supabase__execute_sql (supabase): 657 tokens
└ mcp__supabase__get_logs (supabase): 677 tokens
└ mcp__supabase__get_advisors (supabase): 699 tokens
└ mcp__supabase__get_project_url (supabase): 599 tokens
└ mcp__supabase__get_anon_key (supabase): 601 tokens
└ mcp__supabase__generate_typescript_types (supabase): 600 tokens
└ mcp__supabase__list_edge_functions (supabase): 603 tokens
└ mcp__supabase__get_edge_function (supabase): 625 tokens
└ mcp__supabase__deploy_edge_function (supabase): 907 tokens
└ mcp__supabase__create_branch (supabase): 718 tokens
└ mcp__supabase__list_branches (supabase): 625 tokens
└ mcp__supabase__delete_branch (supabase): 596 tokens
└ mcp__supabase__merge_branch (supabase): 603 tokens
└ mcp__supabase__reset_branch (supabase): 636 tokens
└ mcp__supabase__rebase_branch (supabase): 617 tokens
```

</details>

**After (wrapped with mcp-filter):**

```json
{
  "mcpServers": {
    "supabase": {
      "command": "mcp-filter",
      "args": [
        "run",
        "-t",
        "stdio",
        "--stdio-command",
        "npx",
        "--stdio-arg",
        "-y @supabase/mcp-server-supabase@latest --access-token YOUR_TOKEN",
        "-a",
        "execute_sql,list_tables,get_project"
      ]
    }
  }
}
```

This only exposes 3 tools we allowed (**~1.9k tokens** = 91% reduction!):

```
└ mcp__supabase__get_project (supabase): 605 tokens
└ mcp__supabase__list_tables (supabase): 642 tokens
└ mcp__supabase__execute_sql (supabase): 659 tokens
```

### Examples for Claude Code / Claude Desktop

`examples/mcp.json.sample` includes common setups. Add to your `mcp.json`:

**Supabase (stdio)** – wrap the official MCP binary:

```json
"supabase": {
  "command": "mcp-filter",
  "args": [
    "run",
    "-t", "stdio",
    "--stdio-command", "npx",
    "--stdio-arg", "-y @supabase/mcp-server-supabase@latest --access-token YOUR_TOKEN",
    "-a", "execute_sql,list_tables,get_project"
  ]
}
```

**Or use `uvx` for faster, ephemeral execution:**

```json
"supabase": {
  "command": "uvx",
  "args": [
    "mcp-filter",
    "run",
    "-t", "stdio",
    "--stdio-command", "npx",
    "--stdio-arg", "-y @supabase/mcp-server-supabase@latest --access-token YOUR_TOKEN",
    "-a", "execute_sql,list_tables,get_project"
  ]
}
```

**Linear (stdio wrapping mcp-remote)** – preserves OAuth browser flow:

```json
"linear": {
  "command": "mcp-filter",
  "args": [
    "run",
    "-t", "stdio",
    "--stdio-command", "npx",
    "--stdio-arg", "-y mcp-remote https://mcp.linear.app/sse",
    "-a", "get_issue,list_issues,create_issue,update_issue,create_comment"
  ]
}
```

Adjust auth-tokens/headers to match your environment; the filter never logs or exposes them.

## Configuration Reference

Environment variables (prefixed with `MF_`) override CLI flags. See `.env.example` for a template.

- `MF_TRANSPORT` / `-t`: `stdio` (default) or `http`
- `MF_STDIO_COMMAND` / `MF_STDIO_ARGS`: upstream binary + args
- `MF_STDIO_ENV` / `--stdio-env`: environment variables for stdio subprocess (`KEY=value;ANOTHER=value` or repeatable `--stdio-env KEY=value`)
- `MF_HTTP_URL` / `MF_HTTP_HEADERS`: SSE/HTTP endpoint and extra headers (`key=value;Another=Value`)
- `MF_ALLOW_TOOLS` / `-a`: exact tool names (repeatable, or comma-separated)
- `MF_ALLOW_PATTERNS`: regex patterns for tool names (repeatable, or comma-separated)
- `MF_DENY_PATTERNS` / `-d`: regex patterns to block (repeatable, or comma-separated)
- `MF_RENAME_PREFIX` / `-p` / `--prefix`: prefix exposed tool names (e.g., `supabase_`)
- `MF_INCLUDE_HEALTH_TOOL=1` / `--health`: enable built-in health tool (disabled by default)
- `MF_SHOW_TOKEN_ESTIMATES=1`: enable token estimate logging (disabled by default)

## FAQ

**Can I expose more than one tool?** Yes—pass multiple `--allow-tool` flags or use regex patterns. All exposed tools share the optional rename prefix.

**Are my credentials safe?** Yes. The filter never logs secrets passed as CLI arguments or headers.

**What if the upstream goes down?** Health checks surface the failure while the filter continues to reject new calls with a clear error.

**Can I merge config files?** Env + CLI merging is built in. For more complex setups, script the CLI invocation or add a thin wrapper that loads `mf.toml` and passes flags.

## Advanced

### Observability & Health

- Rich-based structured logging annotates server name, transport, and exposed tool count.
- Optional built-in health tool (disabled by default, ~500 tokens per server) returns upstream liveness and exposed tool names; output is safe JSON. Enable with `MF_INCLUDE_HEALTH_TOOL=1` or `--health`.

### Security Notes

- Only tools explicitly allowlisted or matching an allow regex are exposed.
- Deny-patterns apply last to ensure sensitive tools stay hidden.
- Optional rename prefix avoids tool collisions when multiple filtered proxies run side-by-side.
- Health payload (when enabled) avoids secrets—only structural metadata is emitted.
- **Credentials & secrets**: Arguments and headers passed via CLI flags are never logged. For production deployments, prefer environment variables (e.g., `MF_STDIO_ARGS`) to avoid exposing credentials in process lists.

### Requirements

- Python 3.10+ (3.11 recommended)
- `mcp>=1.0.0` and `fastmcp>=0.3.0` (installed automatically)
- Upstream tool list is fixed per session; mid-run changes require restart
- HTTP transport requires SSE-compatible upstream servers

## Roadmap

### v0.2.0 (Planned)

**Schema Pruning** — Additional 30-60% token reduction

- Add `--prune-schema [off|safe|aggressive]` to strip non-essential schema fields
- Safe mode: remove `title`, `description`, `examples`, `default` while preserving contract
- Aggressive mode: strip all descriptions except top-level (≤140 chars)

**Enhanced Error Handling**

- Return proper JSON-RPC error codes (e.g., `-32602` for blocked tools)
- Include helpful error details: `{"public_tools": [...], "tool_requested": "...", "reason": "not_allowlisted"}`

**Collision-Safe Naming**

- Replace collision failures with deterministic suffixes (`tool_name_{hash[:4]}`)
- Log warnings but continue operation

**Full JSON Schema Validation**

- Validate tool arguments locally before forwarding upstream
- Provide clear, early error messages for invalid calls
- Compile schemas at startup for performance

**Structured Logging & Monitoring**

- Add `--log-format [pretty|json]` for production-friendly JSON lines
- Add `--redact-keys` to automatically redact sensitive field names
- Expose metrics for blocked calls, latency, and tool usage

**Operational Controls**

- Add `--timeout-ms` (default: 120000) for per-call timeouts
- Add `--max-concurrency` (default: 8) to limit parallel upstream calls

**Resources & Prompts Filtering**

- Add `--allow-resources` and `--allow-prompts` (off by default)
- Apply same pattern-based filtering as tools

### Future Considerations

- Multi-upstream mode: `--upstream NAME=cmd...` for managing multiple filtered servers
- Compressor mode: meta-tools with on-demand forwarding (separate from filter mode)
- Built-in deny presets: `--deny-dangerous-verbs` to block destructive operations by default

## Testing

```bash
source .venv/bin/activate
python -m pytest
```

The suite exercises filtering precedence, rename collisions, schema validation, health handling, and call forwarding against a fake upstream server.
