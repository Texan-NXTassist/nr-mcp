# nr-mcp — Installation Guide

## Prerequisites
- Python 3.11+
- `uv` installed (`brew install uv` or `pip install uv`)
- Node-RED running on 192.168.1.31:1880 with Basic Auth

## Step 1: Install from local repo
```bash
cd ~/Projects/aaGITHUB/node-red-mcp-custom
uv tool install --force .
```
This creates `~/.local/bin/nr-mcp`.

## Step 2: Create wrapper script
Node-RED MCP (like ha-mcp) needs a wrapper because Claude Desktop starts MCP servers
from a read-only working directory.

Create `~/.local/bin/nr-mcp-wrapper`:
```bash
#!/bin/bash
cd /tmp
exec nr-mcp "$@"
```
Then: `chmod +x ~/.local/bin/nr-mcp-wrapper`

## Step 3: Register in Claude Desktop config
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
"nr-mcp": {
  "command": "/Users/bartosz/.local/bin/nr-mcp-wrapper",
  "env": {
    "NR_URL": "http://192.168.1.31:1880",
    "NR_USER": "op://AI / MCP / Dev/HASS Prox/Username",
    "NR_PASS": "op://AI / MCP / Dev/HASS Prox/Password"
  }
}
```

## Step 4: Restart Claude Desktop
Quit and reopen Claude Desktop. The new MCP should appear in tools.

## Step 5: Test
In Claude conversation, try:
- "Use nr_get_flow_summary to show me all Node-RED tabs"
- "Search for nodes containing 'pv_strategy'"
- "Show me the function code for node XYZ"

## Post-install: Disable old mcp-node-red
Once nr-mcp works, remove or comment out old `node-red` entry from
`claude_desktop_config.json` to avoid confusion with 2 Node-RED MCPs.

## Updating
```bash
cd ~/Projects/aaGITHUB/node-red-mcp-custom
git pull  # if using git
uv tool install --force .
```
No wrapper patching needed (unlike the old npm mcp-node-red).
