# nr-mcp — Installation Guide

## Prerequisites

- Python 3.11+
- `uv` installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- Node-RED running with Admin API enabled

## Step 1: Install nr-mcp

### From GitHub (recommended)

```bash
uv tool install git+https://github.com/Texan-NXTassist/nr-mcp.git
```

### From local clone

```bash
git clone https://github.com/Texan-NXTassist/nr-mcp.git
cd nr-mcp
uv tool install .
```

This creates the `nr-mcp` command in `~/.local/bin/`.

## Step 2: Configure your MCP client

### Claude Desktop

Edit your Claude Desktop config:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "nr-mcp": {
      "command": "nr-mcp",
      "env": {
        "NR_URL": "http://localhost:1880",
        "NR_USER": "your-username",
        "NR_PASS": "your-password"
      }
    }
  }
}
```

Alternatively, if using token-based auth:

```json
{
  "mcpServers": {
    "nr-mcp": {
      "command": "nr-mcp",
      "env": {
        "NR_URL": "http://your-node-red-host:1880",
        "NR_TOKEN": "your-access-token"
      }
    }
  }
}
```

> **Note**: If Claude Desktop reports a working directory error, create a wrapper:
> ```bash
> #!/bin/bash
> cd /tmp
> exec nr-mcp "$@"
> ```
> Save as `~/.local/bin/nr-mcp-wrapper`, run `chmod +x` on it, and point `command` to the wrapper.

### Cursor / VS Code

Add to `.cursor/mcp.json` (project-level) or global MCP config:

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

## Step 3: Restart your MCP client

Quit and reopen Claude Desktop / Cursor. The nr-mcp tools should appear in the available tools list.

## Step 4: Test

Try these prompts:
- *"Use nr_get_flow_summary to show me all Node-RED tabs"*
- *"Search for nodes containing 'mqtt'"*
- *"Show me the function code for node [some-id]"*

## Updating

```bash
# From GitHub
uv tool install --force git+https://github.com/Texan-NXTassist/nr-mcp.git

# From local clone
cd /path/to/nr-mcp
git pull
uv tool install --force .
```

## Troubleshooting

### "Authentication failed (401)"
Check that `NR_USER`/`NR_PASS` or `NR_TOKEN` match your Node-RED auth settings.

### "Connection refused"
Verify `NR_URL` points to your Node-RED instance and the Admin API is accessible.

### "Working directory" error in Claude Desktop
Use the wrapper script described in Step 2.

### MCP tools not appearing
Check Claude Desktop logs for startup errors. The `nr-mcp` command must be in your PATH.
