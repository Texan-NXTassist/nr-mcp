# nr-mcp — Tool Specification

## Tool 1: `nr_get_flow_summary`
**Purpose:** Quick overview of all tabs with node counts and groups.

**Parameters:** none

**Returns:**
```json
{
  "total_nodes": 450,
  "total_tabs": 8,
  "tabs": [
    {
      "id": "tab-id-1",
      "label": "Home Automation",
      "node_count": 85,
      "groups": [
        {"id": "g1", "label": "Lighting Control", "node_count": 23},
        {"id": "g2", "label": "Climate", "node_count": 15}
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
| `name_or_id` | string | yes | Tab name (e.g., "Home Automation") or tab ID |

**Name resolution:** Case-insensitive partial match. "home" matches "Home Automation". If ambiguous → returns error with matching tab names.

**Returns:**
```json
{
  "tab": {"id": "...", "label": "Home Automation", "type": "tab", "info": ""},
  "nodes": [
    {"id": "abc123", "type": "function", "name": "Process sensor data", "z": "tab-id", "...":  "..."}
  ],
  "groups": [
    {"id": "g1", "label": "Lighting Control", "nodes": ["n1", "n2", "n3"]}
  ],
  "total_nodes": 85
}
```

---

## Tool 3: `nr_search_nodes`
**Purpose:** Search nodes by name, type, or function code content.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Search term (name, type, or code snippet) |
| `type` | string | no | Filter by node type (e.g., "function", "mqtt in") |
| `flow` | string | no | Filter by tab name or ID |
| `max_results` | int | no | Limit results (default: 20) |

**Search targets:** node.name, node.type, node.func (JS code), node.template, node.action, node.data

**Returns:**
```json
{
  "results": [
    {
      "id": "abc123",
      "name": "Process sensor data",
      "type": "function",
      "flow_id": "tab-id",
      "flow_label": "Home Automation",
      "match_in": "func",
      "snippet": "if (msg.payload.temperature > threshold) {..."
    }
  ],
  "total": 3,
  "truncated": false
}
```

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
  "name": "Process sensor data",
  "code": "// Full JS code here...",
  "outputs": 1,
  "initialize": "",
  "finalize": ""
}
```

**Error:** If node is not type "function" → returns error with actual type.

---

## Tool 5: `nr_get_node_config`
**Purpose:** Get full node configuration including wires and connections.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | yes | Any node ID |

**Returns:** Full node object as-is from Node-RED API, plus computed fields:
```json
{
  "...all node fields...": "...",
  "_flow_label": "Home Automation",
  "_group_label": "Lighting Control",
  "_downstream": ["node-id-1", "node-id-2"],
  "_upstream": ["node-id-3"]
}
```

- `_downstream` = nodes this node wires TO
- `_upstream` = nodes that wire TO this node
- `_group_label` = group containing this node (if any)

---

## Tool 6: `nr_get_flow_context`
**Purpose:** Read flow-level context variables.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | yes | Tab ID |
| `key` | string | no | Specific context key (null = list all keys) |

**Returns (all keys):**
```json
{"flow_id": "tab-id", "keys": ["config", "last_run", "counters"]}
```

**Returns (specific key):**
```json
{"flow_id": "tab-id", "key": "config", "value": {"threshold": 25, "enabled": true}}
```

---

## Tool 7: `nr_safe_deploy`
**Purpose:** Deploy changes to a node with optimistic locking. Uses GET→POST (never PUT). Preserves tab order.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | yes | ID of node to modify |
| `fields` | object | yes | Fields to update (patch, not replace) |
| `description` | string | no | Deploy description for logs |

**Immutable fields (cannot be changed):** `id`, `type`, `z`

**Returns (success):**
```json
{
  "success": true,
  "rev": "new-rev-hash",
  "deployed_at": "2026-03-25T14:23:45+00:00",
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
  "suggestion": "Retry \u2014 will fetch fresh state automatically"
}
```

---

## Tool 8: `nr_get_installed_modules`
**Purpose:** List installed Node-RED modules and their node types.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | no | Filter by module name or node type |

**Returns:**
```json
{
  "modules": [
    {
      "name": "node-red-contrib-home-assistant-websocket",
      "version": "0.72.2",
      "types": ["ha-sensor", "ha-entity-config", "ha-api"],
      "enabled": true
    }
  ],
  "total": 1,
  "query": "home-assistant"
}
```

---

## Tool 9: `nr_inject`
**Purpose:** Trigger an inject node to fire immediately.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | yes | ID of inject node to trigger |

**Returns:**
```json
{"success": true, "node_id": "abc123", "node_name": "Every 30min", "message": "Inject triggered"}
```

---

## Tool 10: `nr_create_nodes`
**Purpose:** Create one or more new nodes/groups in a single deploy.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `nodes` | list[dict] | yes | Node dicts with `id`, `type`, `z` (tab ID) |
| `description` | string | no | Optional deploy note |

**Returns:**
```json
{"success": true, "created": 2, "node_ids": ["node1", "node2"], "rev": "new-rev", "description": "Add API nodes"}
```

Safety: validates target tab exists, checks for ID collisions, retries once on 409.

---

## Tool 11: `nr_delete_nodes`
**Purpose:** Delete one or more nodes. Cleans up group.nodes and wires references.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `node_ids` | list[string] | yes | IDs of nodes to delete |
| `description` | string | no | Optional deploy note |

**Returns:**
```json
{"success": true, "deleted": 2, "node_ids": ["n1", "n2"], "rev": "new-rev"}
```

Safety: refuses to delete tabs, cleans up all references.

---

## Tool 12: `nr_install_module`
**Purpose:** Install a new Node-RED module (npm package).

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `module_name` | string | yes | npm package name |

**Returns:**
```json
{"success": true, "module": "node-red-dashboard", "version": "3.6.5", "types": ["ui_tab", "ui_group"], "message": "Module installed successfully"}
```

Note: Installation may take 30-60 seconds.

---

## Tool 13: `nr_get_debug_output`
**Purpose:** Read debug output from flow context.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `flow_id` | string | yes | Tab ID |
| `key` | string | no | Context key (null = list all keys) |

Same format as `nr_get_flow_context`. Useful with catch nodes that store errors to flow context.

---

## Error Responses

All errors are returned as JSON:
```json
{"error": "Description of what went wrong"}
```

| Scenario | Error message pattern |
|----------|----------------------|
| Bad credentials | `Authentication failed (401/403)` |
| Node not found | `Node not found: <id>` |
| Tab not found | `Tab not found: '<name>'` |
| Rev conflict | `Conflict: flow modified by another client` |
| Connection error | `Node-RED API error ...` |
| Immutable field | `Cannot modify immutable fields: {id, type, z}` |
