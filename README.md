# nr-mcp

<!-- mcp-name: io.github.texan-nxtassist/nr-mcp -->

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server that lets AI assistants interact with [Node-RED](https://nodered.org) — read flows, search nodes, edit function code, deploy changes safely, and manage modules.

Built to solve real problems: the existing Node-RED MCP implementations use `PUT /flow/:id` which **reorders your tabs**. nr-mcp uses the correct `GET → POST /flows` pattern with optimistic locking, so your tab order is always preserved.

## Features

**13 tools** for complete Node-RED flow management:

| Tool | Description |
|------|-------------|
| `nr_get_flow_summary` | Overview of all tabs with node counts and groups |
| `nr_get_flow` | Get a single tab with all nodes — by name or ID |
| `nr_search_nodes` | Search nodes by name, type, or JavaScript code content |
| `nr_get_function_code` | Extract full JS code from function nodes (incl. init/finalize) |
| `nr_get_node_config` | Full config with computed upstream/downstream connections |
| `nr_get_flow_context` | Read flow-level context variables |
| `nr_safe_deploy` | Deploy changes with optimistic locking — **never reorders tabs** |
| `nr_create_nodes` | Batch-create nodes/groups in a single deploy |
| `nr_delete_nodes` | Batch-delete with automatic wire and group cleanup |
| `nr_inject` | Trigger inject nodes remotely to test flows |
| `nr_get_installed_modules` | List installed modules and available node types |
| `nr_install_module` | Install npm packages from the Node-RED registry |
| `nr_get_debug_output` | Read debug/error data from flow context |

### Why not just use the existing MCP servers?

- **Tab reorder bug**: Other implementations use `PUT /flow/:id` which silently reorders your tabs in Node-RED. nr-mcp uses the correct `GET → POST /flows` full-deploy pattern.
- **Optimistic locking**: Every deploy checks the `rev` field. If someone else deployed between your read and write, you get a clear conflict error instead of silent data loss.
- **Smart search**: Search across node names, types, function code, templates, and actions in one call.
- **Production-tested**: Built and used daily for managing complex Node-RED installations (home automation, IoT, energy management).

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Node-RED instance with [Admin API](https://nodered.org/docs/api/admin/) enabled

### Install from PyPI

```bash
pip install nr-mcp
```

### Install with uv (recommended)

```bash
uv tool install nr-mcp
```

Or from source:

```bash
git clone https://github.com/Texan-NXTassist/nr-mcp.git
cd nr-mcp
uv tool install .
```

This creates the `nr-mcp` command in `~/.local/bin/`.

## Configuration

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NR_URL` | No | Node-RED URL (default: `http://localhost:1880`) |
| `NR_TOKEN` | No* | Bearer token for token-based auth |
| `NR_USER` | No* | Username for Basic Auth |
| `NR_PASS` | No* | Password for Basic Auth |

\* At least one auth method is recommended. Auth is checked in order: token → basic auth → no auth.

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nr-mcp": {
      "command": "nr-mcp",
      "env": {
        "NR_URL": "http://localhost:1880",
        "NR_USER": "admin",
        "NR_PASS": "your-password"
      }
    }
  }
}
```

> **Tip**: If you get a "working directory" error, create a wrapper script:
> ```bash
> #!/bin/bash
> cd /tmp
> exec nr-mcp "$@"
> ```
> Then point `command` to the wrapper path.

### Cursor / VS Code

Add to your MCP settings (`.cursor/mcp.json` or VS Code equivalent):

```json
{
  "mcpServers": {
    "nr-mcp": {
      "command": "nr-mcp",
      "env": {
        "NR_URL": "http://localhost:1880",
        "NR_TOKEN": "your-access-token"
      }
    }
  }
}
```

## Usage examples

Once connected, you can ask your AI assistant things like:

- *"Show me all Node-RED tabs and their node counts"*
- *"Search for nodes that contain 'mqtt' in their code"*
- *"Show me the function code for node abc123"*
- *"Update the function code in node xyz to add error handling"*
- *"Create an inject node and an HTTP request node on the Weather tab"*
- *"What modules are installed? Is node-red-dashboard available?"*
- *"Install node-red-contrib-influxdb"*
- *"Trigger the 'Test' inject node and check for errors"*

## Architecture

nr-mcp is a Python MCP server that communicates with Node-RED via its [Admin API](https://nodered.org/docs/api/admin/). It uses `stdio` transport (standard for MCP) and makes HTTP calls to your Node-RED instance.

```
AI Assistant ↔ MCP (stdio) ↔ nr-mcp ↔ HTTP ↔ Node-RED Admin API
```

### Key design decisions

- **GET→POST pattern**: All deploys fetch full flows, modify in-place, then POST back. Never uses `PUT /flow/:id` which reorders tabs.
- **Optimistic locking**: Uses the Node-RED `rev` field to detect concurrent modifications.
- **No caching**: Every tool call fetches fresh data. Slightly slower, but always correct.
- **Single retry on conflict**: Deploy operations retry once on 409 Conflict.

For more details, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Node-RED setup

The Admin API must be enabled (it is by default). If you've restricted it, ensure these endpoints are accessible:

- `GET /flows` and `POST /flows` — flow read/write
- `GET /context/flow/:id` — flow context
- `POST /inject/:id` — inject trigger
- `GET /nodes` and `POST /nodes` — module management

See [Node-RED Admin API docs](https://nodered.org/docs/api/admin/) for auth configuration.

## Contributing

Contributions welcome! Please open an issue first to discuss what you'd like to change.

```bash
git clone https://github.com/Texan-NXTassist/nr-mcp.git
cd nr-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
```

## License

MIT — see [LICENSE](LICENSE).
