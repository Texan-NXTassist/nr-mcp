# nr-mcp — Tool Specification

## Tool 1: `nr_get_flow_summary`
**Purpose:** Quick overview of all tabs with node counts and groups.

**Parameters:** none

**Returns:**
```json
{
  "total_nodes": 1731,
  "total_tabs": 14,
  "tabs": [
    {
      "id": "0b97b524508685f2",
      "label": "AC DC",
      "node_count": 154,
      "groups": [
        {"id": "g1", "label": "PV Smart Charge", "node_count": 47},
        {"id": "g2", "label": "Energy Monitor", "node_count": 31}
      ]
    }
  ]
}
```

---

## Tool 2: `nr_get_flow`
**Purpose:** Get a single tab with all its nodes and groups. Accepts name OR ID.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `name_or_id` | string | yes | Tab name (e.g., "AC DC") or tab ID |

**Returns:**
```json
{
  "tab": {"id": "...", "label": "AC DC", "type": "tab", "info": ""},
  "nodes": [
    {"id": "abc123", "type": "function", "name": "pv_strategy_func", "z": "tab-id", ...}
  ],
  "groups": [
    {"id": "g1", "label": "PV Smart Charge", "nodes": ["n1", "n2", "n3"]}
  ],
  "total_nodes": 154
}
```

**Name resolution:** Case-insensitive partial match. "ac dc" matches "AC DC". If ambiguous → return error with matching tab names.

---

## Tool 3: `nr_search_nodes`
**Purpose:** Search nodes by name, type, or function code content.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Search term (name, type, or code snippet) |
| `type` | string | no | Filter by node type (e.g., "function", "api-call-service") |
| `flow` | string | no | Filter by tab name or ID |
| `max_results` | int | no | Limit results (default: 20) |

**Search targets:** node.name, node.type, node.func (JS code), node.template, node.action

**Returns:**
```json
{
  "results": [
    {
      "id": "abc123",
      "name": "pv_strategy_func",
      "type": "function",
      "flow_id": "tab-id",
      "flow_label": "AC DC",
      "match_in": "func",
      "snippet": "if (msg.payload.soc < target) {..."
    }
  ],
  "total": 5,
  "truncated": false
}
```

**Snippet:** First 200 chars of matched field content.

---

## Tool 4: `nr_get_function_code`
**Purpose:** Extract full JavaScript code from a function node.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | yes | Function node ID |

**Returns:**
```json
{
  "node_id": "abc123",
  "name": "pv_strategy_func",
  "code": "// Full JS code here...",
  "outputs": 1,
  "initialize": "",
  "finalize": ""
}
```

**Error:** If node is not type "function" → return error with actual type.

---

## Tool 5: `nr_get_node_config`
**Purpose:** Get full node object including wires, for any node type.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | yes | Any node ID |

**Returns:** Full node object as-is from Node-RED API, plus:
```json
{
  ...all node fields...,
  "_flow_label": "AC DC",
  "_group_label": "PV Smart Charge",
  "_downstream": ["node-id-1", "node-id-2"],
  "_upstream": ["node-id-3"]
}
```

`_downstream` = nodes this node wires TO.
`_upstream` = nodes that wire TO this node.
`_group_label` = group containing this node (if any).

---

## Tool 6: `nr_get_flow_context`
**Purpose:** Read flow-level context (used by SLC system, PV strategy, etc.)

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | yes | Tab ID |
| `key` | string | no | Specific context key (null = list all keys) |

**Returns (all keys):**
```json
{
  "flow_id": "tab-id",
  "keys": ["pv_target_soc", "battery_efficiency", "slc_factors", "last_snapshot"]
}
```

**Returns (specific key):**
```json
{
  "flow_id": "tab-id",
  "key": "slc_factors",
  "value": {"hour_6": 1.15, "hour_7": 0.92, ...}
}
```

**API endpoint:** `GET /context/flow/:id` — returns `{memory: {key: {msg: value, format: type}}}`. No separate endpoint for single key; we fetch full context and filter.

---

## Tool 7: `nr_safe_deploy`
**Purpose:** Deploy changes to Node-RED with optimistic locking. THE critical tool that fixes the PUT bug.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | yes | ID of node to modify |
| `fields` | object | yes | Fields to update (patch, not replace) |
| `description` | string | no | Deploy description for logs |

**Immutable fields (cannot be changed):** `id`, `type`, `z` (tab membership).

**Example call:**
```json
{
  "node_id": "abc123",
  "fields": {
    "name": "pv_strategy_v5",
    "func": "// Updated code\nconst target = msg.payload.target_soc;..."
  },
  "description": "Update PV strategy function to v5"
}
```

**Algorithm:**
1. `GET /flows` → get all flows + `rev`
2. Find node with matching `node_id` in flows array
3. Validate: node exists, fields are not immutable
4. Apply field patches (merge, don't replace entire node)
5. `POST /flows` with `{rev, flows}` + API v2 headers
6. On 409 → return conflict error with suggestion to retry
7. On success → return new rev + change summary

**Returns (success):**
```json
{
  "success": true,
  "rev": "new-rev-hash",
  "deployed_at": "2026-03-08T14:23:45Z",
  "node_id": "abc123",
  "fields_updated": ["name", "func"],
  "tab_order_preserved": true
}
```

**Returns (conflict):**
```json
{
  "success": false,
  "error": "Conflict: flow modified by another client",
  "suggestion": "Retry — will fetch fresh state automatically"
}
```

---

## Tool 8: `nr_get_installed_modules`
**Purpose:** List installed Node-RED modules and their node types. Use before creating nodes to know what types are available.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | no | Filter by module name or node type containing this string |

**Returns:**
```json
{
  "modules": [
    {
      "name": "node-red-contrib-home-assistant-websocket",
      "version": "0.72.2",
      "types": ["ha-sensor", "ha-entity-config", "ha-api", ...],
      "enabled": true
    },
    {
      "name": "node-red-dashboard",
      "version": "3.6.5",
      "types": ["ui_tab", "ui_group", "ui_chart", ...],
      "enabled": true
    }
  ],
  "total": 2,
  "query": null
}
```

**API endpoint:** `GET /nodes` with `Accept: application/json`, `Node-RED-API-Version: v2`

---

## Tool 9: `nr_inject`
**Purpose:** Trigger an inject node to fire immediately. Use to test flows after deploy.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | yes | ID of inject node to trigger |

**Returns:**
```json
{
  "success": true,
  "node_id": "abc123",
  "node_name": "Every 30min",
  "message": "Inject triggered"
}
```

**Errors:** Node not found → NOT_FOUND. Node not type "inject" → VALIDATION.

**API endpoint:** `POST /inject/:id`

---

## Tool 10: `nr_create_nodes`
**Purpose:** Create one or more new nodes/groups in a single deploy. Batch operation for efficiency.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `nodes` | list[dict] | yes | Node dicts. Each must have `id`, `type`, `z` (tab ID; `""` for config nodes) |
| `description` | string | no | Optional deploy note |

**Required node fields:** `id` (unique), `type` (e.g. `function`, `inject`, `group`), `z` (target tab ID; empty for global config nodes).

**Returns:**
```json
{
  "success": true,
  "created": 2,
  "node_ids": ["my_inject_01", "my_http_01"],
  "rev": "new-rev-hash",
  "description": "Add API fetch nodes to Weather tab"
}
```

**Errors:** Missing id/type/z → VALIDATION. Tab not found → VALIDATION. ID collision → VALIDATION. 409 Conflict → retried once automatically.

**Algorithm:** GET /flows → validate → append nodes → POST /flows. Single retry on 409.

---

## Tool 11: `nr_delete_nodes`
**Purpose:** Delete one or more nodes by ID. Cleans up group.nodes and wires references.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_ids` | list[string] | yes | IDs of nodes to delete |
| `description` | string | no | Optional deploy note |

**Returns:**
```json
{
  "success": true,
  "deleted": 2,
  "node_ids": ["n1", "n2"],
  "rev": "new-rev-hash"
}
```

**Safety:** Refuses to delete tabs. Use a separate flow to remove all nodes first.

**Errors:** Nodes not found → VALIDATION. Attempt to delete tab → VALIDATION. 409 Conflict → retried once automatically.

---

## Tool 12: `nr_install_module`
**Purpose:** Install a new Node-RED module (npm package) from the registry.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `module_name` | string | yes | npm package name (e.g. `node-red-dashboard`) |

**Returns:**
```json
{
  "success": true,
  "module": "node-red-dashboard",
  "version": "3.6.5",
  "types": ["ui_tab", "ui_group", ...],
  "message": "Module 'node-red-dashboard' installed successfully"
}
```

**Errors:** Invalid name (empty, contains space) → VALIDATION. Module not found → VALIDATION. Already installed → VALIDATION.

**Note:** Installation may take 30-60 seconds. Uses 120s timeout.

**API endpoint:** `POST /nodes` with `{"module": "module-name"}`

---

## Tool 13: `nr_get_debug_output`
**Purpose:** Read debug output from flow context (v1). Use when a flow has a catch node that stores errors/debug data to flow context.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | yes | Tab ID |
| `key` | string | no | Context key (null = list all keys) |

**Returns:** Same format as `nr_get_flow_context` — either `{flow_id, keys: [...]}` or `{flow_id, key, value}`.

**Usage pattern:** Add a catch node + function node that stores last N errors to flow context. Trigger flow with `nr_inject`, then read via this tool. For richer real-time debug, WebSocket v2 is planned.

---

## Error Codes (all tools)

| Code | Meaning |
|------|---------|
| `AUTH_ERROR` | Bad credentials (401/403) |
| `NOT_FOUND` | Node, flow, or key not found |
| `CONFLICT` | Rev mismatch on deploy (409) |
| `VALIDATION` | Invalid parameters or immutable field change |
| `CONNECTION` | Cannot reach Node-RED |
