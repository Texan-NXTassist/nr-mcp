# nr-mcp — Architecture & Design Decisions

## Problem
Existing `mcp-node-red` (npm, v1.1.0) has critical bugs:
1. `update_flow` uses `PUT /flow/:id` which **reorders tabs** in Node-RED
2. `dotenv@17` writes to stdout, breaking MCP stdio protocol (requires manual patch after every update)
3. No smart search across nodes/code
4. No safe deploy with optimistic locking

## Solution
Custom Python MCP server with correct Node-RED Admin API v2 usage.

## Key Design Decisions

### 1. Language: Python (not TypeScript/Node.js)
- Matches ha-mcp pattern already in use
- MCP Python SDK is mature (`mcp` package)
- `httpx` async client is simpler than Node.js for HTTP + Basic Auth
- No npm/dotenv pollution issues
- Installation via `uv tool install` (proven pattern)

### 2. Deploy: GET→POST (never PUT)
**CRITICAL**: Node-RED's `PUT /flow/:id` endpoint reorders tabs. This is a known issue.

Correct pattern:
```
GET /flows → returns {flows: [...], rev: "abc123"}
Modify node(s) in-place within the flows array
POST /flows with headers:
  - Node-RED-API-Version: v2
  - Node-RED-Deployment-Type: full
  - Content-Type: application/json
Body: {rev: "abc123", flows: [...modified flows...]}
```

On 409 Conflict → rev mismatch (another client deployed) → retry with fresh GET.

### 3. Auth: Basic Auth to port 1880
- Direct to Node-RED on `192.168.1.31:1880`
- NOT through HA ingress proxy on port 8123 (uses session cookies, not Basic Auth)
- Credentials via env vars: `NR_URL`, `NR_USER`, `NR_PASS`
- 1Password references in claude_desktop_config.json

### 4. No caching
- Flows change outside MCP (Node-RED UI, other clients)
- Staleness risk too high for deploy operations
- Every tool call fetches fresh data
- Trade-off: slightly slower reads, but always correct

### 5. Single-file tools module
- All 7 tools in one `tools.py` (they share the same client + flows data)
- Keeps project minimal and easy to understand
- Can split later if needed

## Node-RED Flow Structure Reference

```
flows array contains:
├── Tab objects:     {id, type: "tab", label, info, disabled, order}
├── Node objects:    {id, type: "function"|"api-call-service"|..., name, z: "<tab-id>", ...}
├── Group objects:   {id, type: "group", name, z: "<tab-id>", nodes: ["node-id-1", ...], style: {...}}
├── Subflow defs:    {id, type: "subflow", name, ...}
├── Subflow instances: {id, type: "subflow:<subflow-id>", name, z: "<tab-id>", ...}
└── Config nodes:    {id, type: "server"|"mqtt-broker"|..., z: "" (global) or "<tab-id>"}
```

Key relationships:
- Node → Tab: via `z` field (tab ID)
- Node → Group: group's `nodes` array contains node IDs
- Subflow instance → Subflow def: type is `subflow:<def-id>`
- Config node → Tab: `z` = tab ID (or empty = global)

## Current Node-RED State (as of 2026-03-08)
- 14 flow tabs, ~1731 nodes total
- Key flows: AC DC (154 nodes), Komfo (341 nodes), solar, Cars, etc.
- Node-RED v4.1.6 on HASS (Proxmox VM 101)
- HA server config node: `44b2605f.5d41`
