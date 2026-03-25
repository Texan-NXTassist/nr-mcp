# nr-mcp — Architecture & Design Decisions

## Problem

Existing Node-RED MCP servers have critical issues:

1. **Tab reorder bug**: `PUT /flow/:id` silently reorders tabs in Node-RED
2. **stdout pollution**: Some npm-based servers write to stdout, breaking MCP stdio transport
3. **No smart search**: Can't search across function code, templates, or actions
4. **No optimistic locking**: Deploys can silently overwrite concurrent changes

## Solution

A Python MCP server that uses the Node-RED Admin API v2 correctly.

## Key Design Decisions

### 1. Language: Python

- MCP Python SDK is mature (`mcp` package with FastMCP)
- `httpx` async client handles HTTP + auth cleanly
- No npm/dotenv pollution issues that break stdio
- Installation via `uv tool install` (single command, isolated env)

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

### 3. Authentication

Three methods supported (checked in order):
1. **Bearer token** (`NR_TOKEN`) — for token-based Node-RED auth
2. **Basic Auth** (`NR_USER` + `NR_PASS`) — for httpNodeAuth / adminAuth with credentials
3. **No auth** — for unsecured local instances

All credentials via environment variables. Never hardcoded.

### 4. No caching

- Flows change outside MCP (Node-RED editor, other clients, deploys)
- Staleness risk too high for deploy operations
- Every tool call fetches fresh data
- Trade-off: slightly slower reads, but always correct

### 5. Single-file tools module

- All tools in one `tools.py` (they share the same client + flows data)
- Keeps project minimal and easy to understand
- Server decorators in `server.py`, pure logic in `tools.py`

## Node-RED Flow Structure Reference

```
flows array contains:
├── Tab objects:        {id, type: "tab", label, info, disabled, order}
├── Node objects:       {id, type: "function"|"inject"|..., name, z: "<tab-id>", wires, ...}
├── Group objects:      {id, type: "group", name, z: "<tab-id>", nodes: ["id-1", ...], style}
├── Subflow defs:       {id, type: "subflow", name, ...}
├── Subflow instances:  {id, type: "subflow:<def-id>", name, z: "<tab-id>", ...}
└── Config nodes:       {id, type: "mqtt-broker"|..., z: "" (global) or "<tab-id>"}
```

Key relationships:
- **Node → Tab**: via `z` field (tab ID)
- **Node → Group**: group's `nodes` array contains node IDs
- **Subflow instance → Subflow def**: type is `subflow:<def-id>`
- **Config node → Tab**: `z` = tab ID (or empty = global)

## Error Handling Strategy

| HTTP Status | Error Type | Action |
|-------------|-----------|--------|
| 401 / 403 | `NRAuthError` | Check credentials |
| 404 | `NRNotFoundError` | Node/flow/key not found |
| 409 | `NRConflictError` | Rev mismatch — retry once |
| Other 4xx/5xx | `NRError` | Generic error with message |

All errors are caught at the server layer and returned as JSON `{"error": "..."}` — never crashes the MCP server.
