"""Tool implementations for nr-mcp.

All tools fetch fresh data on each call (no caching).
"""

from .client import NRClient, NRError, NRNotFoundError, NRConflictError


async def get_flow_summary(client: NRClient) -> dict:
    """Overview of all tabs with node counts and groups."""
    flows, _ = await client.get_flows()

    tabs = [f for f in flows if f.get("type") == "tab"]
    groups = [f for f in flows if f.get("type") == "group"]
    nodes = [f for f in flows if f.get("type") not in ("tab", "group", "subflow", "comment") and "z" in f]

    tab_map = {}
    for tab in tabs:
        tab_map[tab["id"]] = {
            "id": tab["id"],
            "label": tab.get("label", ""),
            "node_count": 0,
            "groups": [],
        }

    for node in nodes:
        z = node.get("z", "")
        if z in tab_map:
            tab_map[z]["node_count"] += 1

    for group in groups:
        z = group.get("z", "")
        if z in tab_map:
            tab_map[z]["groups"].append({
                "id": group["id"],
                "label": group.get("name", group.get("label", "")),
                "node_count": len(group.get("nodes", [])),
            })

    return {
        "total_nodes": len(nodes),
        "total_tabs": len(tabs),
        "tabs": list(tab_map.values()),
    }


async def get_flow(client: NRClient, name_or_id: str) -> dict:
    """Get single tab by name or ID with all nodes and groups."""
    flows, _ = await client.get_flows()
    tabs = [f for f in flows if f.get("type") == "tab"]

    # Find tab by ID or name (case-insensitive partial match)
    tab = None
    query_lower = name_or_id.lower()
    for t in tabs:
        if t["id"] == name_or_id:
            tab = t
            break
    if not tab:
        matches = [t for t in tabs if query_lower in t.get("label", "").lower()]
        if len(matches) == 1:
            tab = matches[0]
        elif len(matches) > 1:
            names = [m.get("label") for m in matches]
            raise NRNotFoundError(f"Ambiguous tab name '{name_or_id}'. Matches: {names}")
        else:
            raise NRNotFoundError(f"Tab not found: '{name_or_id}'")

    tab_id = tab["id"]
    nodes = [f for f in flows if f.get("z") == tab_id and f.get("type") != "group"]
    groups = [f for f in flows if f.get("z") == tab_id and f.get("type") == "group"]

    return {
        "tab": {"id": tab["id"], "label": tab.get("label", ""), "type": "tab", "info": tab.get("info", "")},
        "nodes": nodes,
        "groups": [{"id": g["id"], "label": g.get("name", ""), "nodes": g.get("nodes", [])} for g in groups],
        "total_nodes": len(nodes),
    }


async def search_nodes(client: NRClient, query: str, node_type: str | None = None,
                        flow: str | None = None, max_results: int = 20) -> dict:
    """Search nodes by name, type, or function code content."""
    flows, _ = await client.get_flows()

    tabs = {f["id"]: f.get("label", "") for f in flows if f.get("type") == "tab"}
    nodes = [f for f in flows if "z" in f and f.get("type") not in ("tab", "group")]

    query_lower = query.lower()
    results = []

    for node in nodes:
        if node_type and node.get("type") != node_type:
            continue
        if flow:
            flow_lower = flow.lower()
            z = node.get("z", "")
            if z != flow and flow_lower not in tabs.get(z, "").lower():
                continue

        # Search in name, type, func, template, action
        match_in = None
        snippet = ""
        for field in ("name", "type", "func", "template", "action", "data"):
            val = node.get(field, "")
            if isinstance(val, str) and query_lower in val.lower():
                match_in = field
                snippet = val[:200]
                break

        if match_in:
            results.append({
                "id": node["id"],
                "name": node.get("name", ""),
                "type": node.get("type", ""),
                "flow_id": node.get("z", ""),
                "flow_label": tabs.get(node.get("z", ""), ""),
                "match_in": match_in,
                "snippet": snippet,
            })
            if len(results) >= max_results:
                break

    return {
        "results": results,
        "total": len(results),
        "truncated": len(results) >= max_results,
    }


async def get_function_code(client: NRClient, node_id: str) -> dict:
    """Extract JS code from a function node."""
    flows, _ = await client.get_flows()
    node = next((f for f in flows if f.get("id") == node_id), None)
    if not node:
        raise NRNotFoundError(f"Node not found: {node_id}")
    if node.get("type") != "function":
        return {"error": f"Node {node_id} is type '{node.get('type')}', not 'function'"}

    return {
        "node_id": node_id,
        "name": node.get("name", ""),
        "code": node.get("func", ""),
        "outputs": node.get("outputs", 1),
        "initialize": node.get("initialize", ""),
        "finalize": node.get("finalize", ""),
    }


async def get_node_config(client: NRClient, node_id: str) -> dict:
    """Get full node config including computed upstream/downstream."""
    flows, _ = await client.get_flows()
    node = next((f for f in flows if f.get("id") == node_id), None)
    if not node:
        raise NRNotFoundError(f"Node not found: {node_id}")

    tabs = {f["id"]: f.get("label", "") for f in flows if f.get("type") == "tab"}
    groups = [f for f in flows if f.get("type") == "group"]

    # Compute downstream (nodes this node wires to)
    downstream = []
    for wire_list in node.get("wires", []):
        downstream.extend(wire_list)

    # Compute upstream (nodes that wire to this node)
    upstream = []
    for f in flows:
        for wire_list in f.get("wires", []):
            if node_id in wire_list:
                upstream.append(f["id"])

    # Find group
    group_label = None
    for g in groups:
        if node_id in g.get("nodes", []):
            group_label = g.get("name", g.get("label", ""))
            break

    result = dict(node)
    result["_flow_label"] = tabs.get(node.get("z", ""), "")
    result["_group_label"] = group_label
    result["_downstream"] = downstream
    result["_upstream"] = upstream
    return result


async def get_flow_context(client: NRClient, flow_id: str, key: str | None = None) -> dict:
    """Read flow context. API returns {memory: {key: {msg: value, format: type}}}."""
    data = await client.get_context(flow_id)
    memory = data.get("memory", {})

    if key:
        if key not in memory:
            raise NRNotFoundError(f"Context key not found: '{key}'")
        value = memory[key].get("msg")
        return {"flow_id": flow_id, "key": key, "value": value}
    return {"flow_id": flow_id, "keys": list(memory.keys())}


async def safe_deploy(client: NRClient, node_id: str, fields: dict,
                       description: str | None = None) -> dict:
    """Deploy changes with GET→modify→POST and optimistic locking.

    NEVER uses PUT /flow/:id (which reorders tabs).
    """
    IMMUTABLE_FIELDS = {"id", "type", "z"}
    bad_fields = set(fields.keys()) & IMMUTABLE_FIELDS
    if bad_fields:
        return {"success": False, "error": f"Cannot modify immutable fields: {bad_fields}"}

    flows, rev = await client.get_flows()

    # Find node
    node_idx = None
    for i, f in enumerate(flows):
        if f.get("id") == node_id:
            node_idx = i
            break

    if node_idx is None:
        raise NRNotFoundError(f"Node not found: {node_id}")

    # Apply field patches (merge, don't replace)
    for key, value in fields.items():
        flows[node_idx][key] = value

    # Deploy
    from datetime import datetime, timezone
    try:
        new_rev = await client.post_flows(flows, rev)
    except NRConflictError:
        return {
            "success": False,
            "error": "Conflict: flow modified by another client (rev mismatch)",
            "suggestion": "Retry — will fetch fresh state automatically",
        }

    return {
        "success": True,
        "rev": new_rev,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "node_id": node_id,
        "fields_updated": list(fields.keys()),
        "tab_order_preserved": True,
    }


async def get_installed_modules(client: NRClient, query: str | None) -> dict:
    """List installed Node-RED modules and their node types."""
    raw = await client.get_nodes()

    modules = []
    for mod in raw:
        name = mod.get("name", mod.get("id", "unknown"))
        version = mod.get("version", "?")
        types = mod.get("types", [])

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
            "enabled": mod.get("enabled", True),
        })

    return {
        "modules": modules,
        "total": len(modules),
        "query": query,
    }


async def inject_node(client: NRClient, node_id: str) -> dict:
    """Trigger an inject node to fire immediately."""
    flows, _ = await client.get_flows()
    node = next((f for f in flows if f["id"] == node_id), None)
    if not node:
        raise NRNotFoundError(f"Node '{node_id}' not found")
    if node.get("type") != "inject":
        raise NRError(f"Node '{node_id}' is type '{node.get('type')}', not 'inject'")

    await client.inject(node_id)

    return {
        "success": True,
        "node_id": node_id,
        "node_name": node.get("name", ""),
        "message": "Inject triggered",
    }


async def create_nodes(client: NRClient, nodes: list[dict], description: str | None) -> dict:
    """Create one or more new nodes/groups in a single deploy."""
    for n in nodes:
        if not n.get("id") or not n.get("type"):
            raise NRError(f"Node missing required 'id' or 'type': {n}")
        if "z" not in n and n["type"] not in ("tab", "subflow"):
            raise NRError(f"Node '{n['id']}' missing 'z' (target tab ID)")

    flows, rev = await client.get_flows()

    tab_ids = {f["id"] for f in flows if f.get("type") == "tab"}
    for n in nodes:
        z = n.get("z", "")
        if z and z not in tab_ids and n["type"] not in ("tab", "subflow"):
            raise NRError(f"Target tab '{z}' not found for node '{n['id']}'")

    existing_ids = {f["id"] for f in flows}
    for n in nodes:
        if n["id"] in existing_ids:
            raise NRError(f"Node ID '{n['id']}' already exists")

    modified_flows = flows + nodes

    try:
        new_rev = await client.post_flows(modified_flows, rev)
    except NRConflictError:
        flows, rev = await client.get_flows()
        existing_ids = {f["id"] for f in flows}
        for n in nodes:
            if n["id"] in existing_ids:
                raise NRError(f"Node ID '{n['id']}' already exists (after conflict retry)")
        modified_flows = flows + nodes
        new_rev = await client.post_flows(modified_flows, rev)

    return {
        "success": True,
        "created": len(nodes),
        "node_ids": [n["id"] for n in nodes],
        "rev": new_rev,
        "description": description,
    }


async def delete_nodes(client: NRClient, node_ids: list[str], description: str | None) -> dict:
    """Delete one or more nodes by ID. Cleans up group.nodes and wires references."""
    flows, rev = await client.get_flows()

    ids_to_delete = set(node_ids)
    existing_ids = {f["id"] for f in flows}

    missing = ids_to_delete - existing_ids
    if missing:
        raise NRError(f"Nodes not found: {missing}")

    for f in flows:
        if f["id"] in ids_to_delete and f.get("type") == "tab":
            raise NRError(f"Refusing to delete tab '{f['id']}'. Remove all nodes first.")

    new_flows = [f for f in flows if f["id"] not in ids_to_delete]

    for f in new_flows:
        if f.get("type") == "group" and "nodes" in f:
            f["nodes"] = [nid for nid in f["nodes"] if nid not in ids_to_delete]

    for f in new_flows:
        if "wires" in f:
            f["wires"] = [
                [w for w in output if w not in ids_to_delete]
                for output in f["wires"]
            ]

    try:
        new_rev = await client.post_flows(new_flows, rev)
    except NRConflictError:
        flows, rev = await client.get_flows()
        ids_to_delete = set(node_ids)
        new_flows = [f for f in flows if f["id"] not in ids_to_delete]
        for f in new_flows:
            if f.get("type") == "group" and "nodes" in f:
                f["nodes"] = [nid for nid in f["nodes"] if nid not in ids_to_delete]
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
        "rev": new_rev,
    }


async def install_module(client: NRClient, module_name: str) -> dict:
    """Install a new Node-RED module from the registry."""
    if not module_name or " " in module_name:
        raise NRError(f"Invalid module name: '{module_name}'")

    result = await client.install_module(module_name)

    return {
        "success": True,
        "module": module_name,
        "version": result.get("version", "unknown"),
        "types": result.get("types", []),
        "message": f"Module '{module_name}' installed successfully",
    }


async def get_debug_output(client: NRClient, flow_id: str, key: str | None = None) -> dict:
    """Read debug output from flow context (v1). Use when a flow has a catch node
    that stores errors/debug data to flow context. Pass key=None to list all keys."""
    return await get_flow_context(client, flow_id, key)
