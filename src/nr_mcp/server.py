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


def main():
    """Entry point for uv tool install."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
