"""MCP server entry point for nr-mcp."""

import json

from mcp.server.fastmcp import FastMCP

from .client import NRClient, NRError
from . import tools


mcp = FastMCP("nr-mcp", json_response=True)
client = NRClient()


def _handle_result(result: dict) -> str:
    """Return JSON string for FastMCP (wraps in TextContent automatically)."""
    return json.dumps(result, indent=2, ensure_ascii=False)


def _error(msg: str) -> str:
    """Return error JSON string."""
    return _handle_result({"error": msg})


@mcp.tool()
async def nr_get_flow_summary() -> str:
    """Quick overview of all Node-RED tabs with node counts and groups."""
    try:
        result = await tools.get_flow_summary(client)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_get_flow(name_or_id: str) -> str:
    """Get a single Node-RED tab with all its nodes and groups. Accepts tab name (case-insensitive) or tab ID."""
    try:
        result = await tools.get_flow(client, name_or_id)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_search_nodes(
    query: str,
    type: str | None = None,
    flow: str | None = None,
    max_results: int = 20,
) -> str:
    """Search Node-RED nodes by name, type, or function code content. Searches in: name, type, func, template, action fields."""
    try:
        result = await tools.search_nodes(
            client,
            query,
            node_type=type,
            flow=flow,
            max_results=max_results,
        )
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_get_function_code(node_id: str) -> str:
    """Extract full JavaScript code from a Node-RED function node."""
    try:
        result = await tools.get_function_code(client, node_id)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_get_node_config(node_id: str) -> str:
    """Get full node configuration including wires, upstream/downstream connections, and group membership."""
    try:
        result = await tools.get_node_config(client, node_id)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_get_flow_context(flow_id: str, key: str | None = None) -> str:
    """Read Node-RED flow context (e.g. SLC factors, PV targets). Pass key=null to list all keys."""
    try:
        result = await tools.get_flow_context(client, flow_id, key)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_safe_deploy(
    node_id: str,
    fields: dict,
    description: str | None = None,
) -> str:
    """Deploy changes to a Node-RED node with optimistic locking. Uses correct GET→POST pattern (never PUT). Preserves tab order."""
    try:
        result = await tools.safe_deploy(
            client,
            node_id,
            fields,
            description=description,
        )
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_get_installed_modules(query: str | None = None) -> str:
    """List installed Node-RED modules and their node types. Optionally filter by module name or node type containing `query` string. Returns module name, version, and list of node types provided."""
    try:
        result = await tools.get_installed_modules(client, query)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_inject(node_id: str) -> str:
    """Trigger an inject node to fire immediately. Use nr_search_nodes to find inject nodes first. The node must be of type 'inject'."""
    try:
        result = await tools.inject_node(client, node_id)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_create_nodes(
    nodes: list[dict],
    description: str | None = None,
) -> str:
    """Create one or more new nodes/groups in a single deploy. Each node dict must include 'id', 'type', and 'z' (target tab ID). Groups need 'type': 'group'. Config nodes (e.g. ha-entity-config) use 'z': '' for global scope."""
    try:
        result = await tools.create_nodes(client, nodes, description)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_delete_nodes(
    node_ids: list[str],
    description: str | None = None,
) -> str:
    """Delete one or more nodes by ID. Also cleans up references: removes deleted IDs from group.nodes arrays and from other nodes' wires arrays."""
    try:
        result = await tools.delete_nodes(client, node_ids, description)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_install_module(module_name: str) -> str:
    """Install a new Node-RED module (npm package) from the registry. Use nr_get_installed_modules to check what's already installed first. Installation may take 30-60 seconds."""
    try:
        result = await tools.install_module(client, module_name)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


@mcp.tool()
async def nr_get_debug_output(flow_id: str, key: str | None = None) -> str:
    """Read debug output from flow context. Use when a flow has a catch node that stores errors/debug data to flow context (e.g. key 'debug_messages'). Pass key=null to list all context keys. Requires flow_id (tab ID). Trigger flow with nr_inject first, then read this."""
    try:
        result = await tools.get_debug_output(client, flow_id, key)
        return _handle_result(result)
    except NRError as e:
        return _error(str(e))
    except Exception as e:
        return _error(f"Unexpected error: {type(e).__name__}: {e}")


def main():
    """Entry point for uv tool install."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
