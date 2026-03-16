# nr-mcp — New Tools Implementation Spec

> For Cursor / AI-assisted implementation.
> Existing codebase: `src/nr_mcp/` (server.py, client.py, tools.py)
> Pattern: async tool → tools.py function → NRClient HTTP → JSON result

---

## Overview

6 new tools to add, grouped by priority. All follow existing patterns:
- `@mcp.tool()` decorator in `server.py`
- Implementation in `tools.py`
- Return JSON dict via `_handle_result()`
- Errors via `NRError` hierarchy

### Current NRClient methods (client.py)

```python
async def get_flows() -> tuple[list[dict], str]   # GET /flows → (flows, rev)
async def post_flows(flows: list[dict], rev: str) -> str  # POST /flows → new_rev
async def get_context(flow_id: str) -> dict        # GET /context/flow/:id
async def close()
```

New tools will need new client methods (specified per tool below).

---

## Priority 1: Core CRUD

### Tool 1: `nr_create_nodes`

**Why:** Currently there's no way to create new nodes. Building flows requires raw GET→append→POST /flows dance outside of MCP. This was 80% of effort when building the kite forecast flow (10+ nodes, groups, config nodes).

**Signature:**
```python
@mcp.tool()
async def nr_create_nodes(
    nodes: list[dict],
    description: str | None = None
) -> str:
    """Create one or more new nodes/groups in a single deploy. Each node dict must include 'id', 'type', and 'z' (target tab ID). Groups need 'type': 'group'. Config nodes (e.g. ha-entity-config) use 'z': '' for global scope."""
```

**Parameters:**
- `nodes` — list of node dicts. Each must have at minimum:
  - `id` (str) — unique node ID (caller generates, e.g. `kite_http_rewa1`)
  - `type` (str) — node type (e.g. `function`, `http request`, `inject`, `ha-sensor`, `group`)
  - `z` (str) — tab/flow ID to place node on. Empty string `""` for global config nodes.
  - ...plus any type-specific fields (`func`, `url`, `wires`, `name`, etc.)
- `description` — optional deploy note

**Implementation (in tools.py):**
```python
async def create_nodes(client: NRClient, nodes: list[dict], description: str | None) -> dict:
    # 1. Validate each node has 'id', 'type', 'z'
    for n in nodes:
        if not n.get("id") or not n.get("type"):
            raise NRError(f"Node missing required 'id' or 'type': {n}")
        if "z" not in n and n["type"] not in ("tab", "subflow"):
            raise NRError(f"Node '{n['id']}' missing 'z' (target tab ID)")

    # 2. GET current flows + rev
    flows, rev = await client.get_flows()

    # 3. Verify target tabs exist
    tab_ids = {f["id"] for f in flows if f.get("type") == "tab"}
    for n in nodes:
        z = n.get("z", "")
        if z and z not in tab_ids and n["type"] not in ("tab", "subflow"):
            raise NRError(f"Target tab '{z}' not found for node '{n['id']}'")

    # 4. Check for ID collisions
    existing_ids = {f["id"] for f in flows}
    for n in nodes:
        if n["id"] in existing_ids:
            raise NRError(f"Node ID '{n['id']}' already exists")

    # 5. Append nodes to flows array
    flows.extend(nodes)

    # 6. POST /flows with rev (preserving tab order)
    new_rev = await client.post_flows(flows, rev)

    return {
        "success": True,
        "created": len(nodes),
        "node_ids": [n["id"] for n in nodes],
        "rev": new_rev,
        "description": description
    }
```

**Error cases:**
- Missing id/type/z → NRError with details
- Tab not found → NRError
- ID collision → NRError
- 409 Conflict → retry once (GET fresh, re-append, POST)

**Example usage by LLM:**
```json
{
  "nodes": [
    {
      "id": "my_inject_01",
      "type": "inject",
      "z": "e992b87abd3c5998",
      "name": "Every 30min",
      "repeat": "1800",
      "once": true,
      "onceDelay": "15",
      "x": 130,
      "y": 500,
      "wires": [["my_http_01"]]
    },
    {
      "id": "my_http_01",
      "type": "http request",
      "z": "e992b87abd3c5998",
      "name": "Fetch API",
      "method": "GET",
      "url": "https://api.example.com/data",
      "ret": "obj",
      "x": 350,
      "y": 500,
      "wires": [["my_func_01"]]
    }
  ],
  "description": "Add API fetch nodes to Weather tab"
}
```

---

### Tool 2: `nr_delete_nodes`

**Why:** Removing nodes created by mistake (e.g. wrong dashboard nodes) required full GET/POST flows manipulation.

**Signature:**
```python
@mcp.tool()
async def nr_delete_nodes(
    node_ids: list[str],
    description: str | None = None
) -> str:
    """Delete one or more nodes by ID. Also cleans up references: removes deleted IDs from group.nodes arrays and from other nodes' wires arrays."""
```

**Parameters:**
- `node_ids` — list of node IDs to delete
- `description` — optional deploy note

**Implementation:**
```python
async def delete_nodes(client: NRClient, node_ids: list[str], description: str | None) -> dict:
    flows, rev = await client.get_flows()

    ids_to_delete = set(node_ids)
    existing_ids = {f["id"] for f in flows}

    # Verify all IDs exist
    missing = ids_to_delete - existing_ids
    if missing:
        raise NRError(f"Nodes not found: {missing}")

    # Safety: refuse to delete tabs (use a separate tool or explicit flag)
    for f in flows:
        if f["id"] in ids_to_delete and f.get("type") == "tab":
            raise NRError(f"Refusing to delete tab '{f['id']}'. Remove all nodes first.")

    # Filter out deleted nodes
    new_flows = [f for f in flows if f["id"] not in ids_to_delete]

    # Clean up group.nodes references
    for f in new_flows:
        if f.get("type") == "group" and "nodes" in f:
            f["nodes"] = [nid for nid in f["nodes"] if nid not in ids_to_delete]

    # Clean up wires references
    for f in new_flows:
        if "wires" in f:
            f["wires"] = [
                [w for w in output if w not in ids_to_delete]
                for output in f["wires"]
            ]

    new_rev = await client.post_flows(new_flows, rev)

    return {
        "success": True,
        "deleted": len(node_ids),
        "node_ids": node_ids,
        "rev": new_rev
    }
```

---

### Tool 3: `nr_inject`

**Why:** Cannot trigger inject nodes to test flows after deploy. Had to wait for auto-trigger or use external curl (blocked by network).

**New client method needed:**
```python
# Add to NRClient (client.py)
async def inject(node_id: str) -> bool:
    """POST /inject/:id — trigger an inject node."""
    resp = await self._client.post(f"/inject/{node_id}")
    if resp.status_code == 200:
        return True
    elif resp.status_code == 404:
        raise NRNotFoundError(f"Inject node '{node_id}' not found")
    else:
        raise NRError(f"Inject failed: {resp.status_code} {resp.text}")
```

**Signature:**
```python
@mcp.tool()
async def nr_inject(node_id: str) -> str:
    """Trigger an inject node to fire immediately. Use nr_search_nodes to find inject nodes first. The node must be of type 'inject'."""
```

**Implementation:**
```python
async def inject_node(client: NRClient, node_id: str) -> dict:
    # Optional: verify node exists and is type 'inject'
    flows, _ = await client.get_flows()
    node = next((f for f in flows if f["id"] == node_id), None)
    if not node:
        raise NRNotFoundError(f"Node '{node_id}' not found")
    if node.get("type") != "inject":
        raise NRError(f"Node '{node_id}' is type '{node['type']}', not 'inject'")

    await client.inject(node_id)

    return {
        "success": True,
        "node_id": node_id,
        "node_name": node.get("name", ""),
        "message": "Inject triggered"
    }
```

---

## Priority 2: Diagnostics

### Tool 4: `nr_get_debug_output`

**Why:** After deploying changes, there's no way to see if a function node threw errors or what data flowed through. Currently the only feedback is checking HA sensor state — very indirect.

**Node-RED Comms API:** Node-RED uses WebSocket for real-time debug messages. However, a simpler approach is the runtime API:

**New client method:**
```python
# Node-RED doesn't have a REST endpoint for debug history.
# Two approaches:
#
# Option A (recommended): Use the WebSocket /comms endpoint
#   - Connect to ws://<host>/comms
#   - Auth via access_token from /auth/token
#   - Subscribe to "debug" topic
#   - Collect messages for N seconds
#
# Option B (simpler): Use the /context/node/:id endpoint
#   - Some debug nodes store to context
#   - Limited but doesn't require WebSocket
#
# Option C (pragmatic): Add a "catch" + "function" node pattern
#   - Catch node catches errors from all nodes on tab
#   - Function stores last N errors in flow context
#   - Read via existing nr_get_flow_context

# Recommended: Option A with timeout
async def get_debug_messages(self, timeout_seconds: int = 5) -> list[dict]:
    """Connect to Node-RED WebSocket, subscribe to debug, collect messages."""
    import websockets
    import json
    import asyncio

    ws_url = self.url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url += "/comms"

    messages = []
    try:
        async with websockets.connect(ws_url) as ws:
            # Auth
            auth_msg = {"auth": self._get_token()}  # need to implement
            await ws.send(json.dumps(auth_msg))

            # Subscribe to debug
            await ws.send(json.dumps({"subscribe": "debug"}))

            # Collect for timeout_seconds
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
                    data = json.loads(msg)
                    if isinstance(data, list):
                        for item in data:
                            if item.get("topic") == "debug":
                                messages.append(item)
                    elif data.get("topic") == "debug":
                        messages.append(data)
            except asyncio.TimeoutError:
                pass
    except Exception as e:
        raise NRError(f"WebSocket connection failed: {e}")

    return messages
```

**Signature:**
```python
@mcp.tool()
async def nr_get_debug_output(
    timeout: int = 5,
    node_id: str | None = None
) -> str:
    """Listen for debug messages from Node-RED for up to `timeout` seconds. Optionally filter by source node_id. Requires an active flow execution (trigger with nr_inject first). Returns list of debug messages with timestamps, node source, and payload."""
```

**Implementation notes:**
- WebSocket approach requires `websockets` package → add to pyproject.toml
- Auth: Node-RED with httpNodeAuth uses Basic Auth → may need token exchange
- Alternative: if WebSocket is complex, implement the "catch node + flow context" pattern as v1 and document WebSocket as v2
- **Pragmatic v1:** Just add `websockets>=12.0` dependency and implement basic subscribe/collect

**Simpler v1 alternative (no WebSocket):**
```python
@mcp.tool()
async def nr_get_debug_output(node_id: str) -> str:
    """Read the last debug message cached in a node's status. Works with debug nodes that have 'status' output enabled. For richer output, use nr_get_flow_context to read custom debug data stored by function nodes."""
```

This reads from `GET /node/:id/status` — simpler but less powerful.

**Recommendation:** Start with v1 (simple status check + flow context), add WebSocket v2 later.

---

### Tool 5: `nr_get_installed_modules`

**Why:** Need to know what node types are available before creating nodes. In our session, checking for `node-red-dashboard` returned HTML because we didn't set Accept header.

**New client method:**
```python
async def get_nodes(self) -> list[dict]:
    """GET /nodes — list all installed node modules and types."""
    resp = await self._client.get(
        "/nodes",
        headers={"Accept": "application/json", "Node-RED-API-Version": "v2"}
    )
    self._check_response(resp)
    return resp.json()
```

**Signature:**
```python
@mcp.tool()
async def nr_get_installed_modules(
    query: str | None = None
) -> str:
    """List installed Node-RED modules and their node types. Optionally filter by module name or node type containing `query` string. Returns module name, version, and list of node types provided."""
```

**Implementation:**
```python
async def get_installed_modules(client: NRClient, query: str | None) -> dict:
    raw = await client.get_nodes()

    # Node-RED /nodes returns array of module objects, each with:
    # { "id": "module-name", "name": "module-name", "version": "1.2.3",
    #   "local": true, "types": ["node-type-1", "node-type-2"],
    #   "nodes": [{...node details...}] }

    modules = []
    for mod in raw:
        name = mod.get("name", mod.get("id", "unknown"))
        version = mod.get("version", "?")
        types = mod.get("types", [])

        # If module has nested nodes array with types
        if not types and "nodes" in mod:
            types = []
            for n in mod["nodes"]:
                types.extend(n.get("types", []))

        if query:
            q = query.lower()
            if q not in name.lower() and not any(q in t.lower() for t in types):
                continue

        modules.append({
            "name": name,
            "version": version,
            "types": types,
            "enabled": mod.get("enabled", True)
        })

    return {
        "modules": modules,
        "total": len(modules),
        "query": query
    }
```

**Example output:**
```json
{
  "modules": [
    {"name": "node-red-contrib-home-assistant-websocket", "version": "0.72.2",
     "types": ["ha-sensor", "ha-entity-config", "ha-api", ...], "enabled": true},
    {"name": "node-red-dashboard", "version": "3.6.5",
     "types": ["ui_tab", "ui_group", "ui_chart", ...], "enabled": true}
  ],
  "total": 2,
  "query": null
}
```

---

### Tool 6: `nr_install_module`

**Why:** After finding the right package via Perplexity, need to install it without leaving MCP context.

**New client method:**
```python
async def install_module(self, module_name: str) -> dict:
    """POST /nodes — install a new npm module."""
    resp = await self._client.post(
        "/nodes",
        json={"module": module_name},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=120.0  # npm install can be slow
    )
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 400:
        raise NRError(f"Module '{module_name}' not found or invalid")
    elif resp.status_code == 409:
        raise NRError(f"Module '{module_name}' already installed")
    else:
        raise NRError(f"Install failed: {resp.status_code} {resp.text}")
```

**Signature:**
```python
@mcp.tool()
async def nr_install_module(module_name: str) -> str:
    """Install a new Node-RED module (npm package) from the registry. Use nr_get_installed_modules to check what's already installed first. Installation may take 30-60 seconds."""
```

**Implementation:**
```python
async def install_module(client: NRClient, module_name: str) -> dict:
    # Safety: basic validation
    if not module_name or " " in module_name:
        raise NRError(f"Invalid module name: '{module_name}'")

    result = await client.install_module(module_name)

    return {
        "success": True,
        "module": module_name,
        "version": result.get("version", "unknown"),
        "types": result.get("types", []),
        "message": f"Module '{module_name}' installed successfully"
    }
```

---

## Implementation Checklist

### Files to modify:

**`src/nr_mcp/client.py`** — add methods:
- [ ] `inject(node_id: str) -> bool`
- [ ] `get_nodes() -> list[dict]`
- [ ] `install_module(module_name: str) -> dict`
- [ ] (Optional v2) `get_debug_messages(timeout: int) -> list[dict]`

**`src/nr_mcp/tools.py`** — add functions:
- [ ] `create_nodes(client, nodes, description) -> dict`
- [ ] `delete_nodes(client, node_ids, description) -> dict`
- [ ] `inject_node(client, node_id) -> dict`
- [ ] `get_installed_modules(client, query) -> dict`
- [ ] `install_module(client, module_name) -> dict`
- [ ] (v1 simple) `get_debug_output(client, node_id) -> dict`

**`src/nr_mcp/server.py`** — add `@mcp.tool()` decorators:
- [ ] `nr_create_nodes(nodes, description)`
- [ ] `nr_delete_nodes(node_ids, description)`
- [ ] `nr_inject(node_id)`
- [ ] `nr_get_installed_modules(query)`
- [ ] `nr_install_module(module_name)`
- [ ] `nr_get_debug_output(timeout, node_id)`

**`pyproject.toml`** — optionally add:
- [ ] `websockets>=12.0` (only if implementing WebSocket debug v2)

**`docs/TOOL_SPEC.md`** — update with new tool specs

### Testing order:
1. `nr_get_installed_modules` — read-only, safe to test first
2. `nr_inject` — triggers existing flow, low risk
3. `nr_create_nodes` — creates nodes, test on empty tab
4. `nr_delete_nodes` — test deleting what was just created
5. `nr_install_module` — installs npm, test with known small package
6. `nr_get_debug_output` — needs active flow, test after inject

### Node-RED API reference:
- Admin API: https://nodered.org/docs/api/admin/methods/
- `POST /inject/:id` — trigger inject node
- `GET /nodes` — list installed modules
- `POST /nodes` — install module
- `DELETE /nodes/:module` — uninstall (not implemented here, future)
- `GET /flows` + `POST /flows` — full flow manipulation (existing)

---

## Architecture Notes

### Why batch create (not single node)?
Creating 10 nodes one-by-one means 10 deploys × 10 restarts. Batch `nr_create_nodes` does a single GET→append all→POST. The LLM prepares the full node array (with wires, positions, groups) and deploys in one shot.

### 409 Conflict retry strategy:
Both `nr_create_nodes` and `nr_delete_nodes` should implement a single retry on 409:
```python
try:
    new_rev = await client.post_flows(modified_flows, rev)
except NRConflictError:
    # Someone else deployed between our GET and POST
    flows, rev = await client.get_flows()  # fresh
    # Re-apply our changes to fresh flows
    # ... (re-append or re-filter)
    new_rev = await client.post_flows(modified_flows, rev)
```

### Safety guardrails:
- `nr_delete_nodes` refuses to delete tabs (prevents catastrophic flow loss)
- `nr_create_nodes` checks for ID collisions (prevents overwriting existing nodes)
- `nr_install_module` validates module name format
- All mutations log `description` for audit trail
