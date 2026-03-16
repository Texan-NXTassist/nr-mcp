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

**API endpoint:** `GET /flow/:id/context/:key` (this one is safe — it's a read-only GET, not the broken PUT).

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

## Error Codes (all tools)

| Code | Meaning |
|------|---------|
| `AUTH_ERROR` | Bad credentials (401/403) |
| `NOT_FOUND` | Node, flow, or key not found |
| `CONFLICT` | Rev mismatch on deploy (409) |
| `VALIDATION` | Invalid parameters or immutable field change |
| `CONNECTION` | Cannot reach Node-RED |
