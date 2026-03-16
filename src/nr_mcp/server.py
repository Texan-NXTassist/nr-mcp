"""MCP server entry point for nr-mcp."""

import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .client import NRClient, NRError
from . import tools


server = Server("nr-mcp")
client = NRClient()


def _json_result(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]


def _error_result(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": msg}, indent=2))]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="nr_get_flow_summary",
            description="Quick overview of all Node-RED tabs with node counts and groups",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="nr_get_flow",
            description="Get a single Node-RED tab with all its nodes and groups. Accepts tab name (case-insensitive) or tab ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name_or_id": {"type": "string", "description": "Tab name (e.g. 'AC DC') or tab ID"},
                },
                "required": ["name_or_id"],
            },
        ),
        Tool(
            name="nr_search_nodes",
            description="Search Node-RED nodes by name, type, or function code content. Searches in: name, type, func, template, action fields.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "type": {"type": "string", "description": "Filter by node type (e.g. 'function', 'api-call-service')"},
                    "flow": {"type": "string", "description": "Filter by tab name or ID"},
                    "max_results": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="nr_get_function_code",
            description="Extract full JavaScript code from a Node-RED function node",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Function node ID"},
                },
                "required": ["node_id"],
            },
        ),
        Tool(
            name="nr_get_node_config",
            description="Get full node configuration including wires, upstream/downstream connections, and group membership",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Any node ID"},
                },
                "required": ["node_id"],
            },
        ),
        Tool(
            name="nr_get_flow_context",
            description="Read Node-RED flow context (e.g. SLC factors, PV targets). Pass key=null to list all keys.",
            inputSchema={
                "type": "object",
                "properties": {
                    "flow_id": {"type": "string", "description": "Tab ID"},
                    "key": {"type": "string", "description": "Context key (omit to list all)"},
                },
                "required": ["flow_id"],
            },
        ),
        Tool(
            name="nr_safe_deploy",
            description="Deploy changes to a Node-RED node with optimistic locking. Uses correct GET→POST pattern (never PUT). Preserves tab order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "ID of node to modify"},
                    "fields": {"type": "object", "description": "Fields to update (patch). Cannot change: id, type, z."},
                    "description": {"type": "string", "description": "Deploy description for logs"},
                },
                "required": ["node_id", "fields"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "nr_get_flow_summary":
            result = await tools.get_flow_summary(client)
        elif name == "nr_get_flow":
            result = await tools.get_flow(client, arguments["name_or_id"])
        elif name == "nr_search_nodes":
            result = await tools.search_nodes(
                client,
                arguments["query"],
                node_type=arguments.get("type"),
                flow=arguments.get("flow"),
                max_results=arguments.get("max_results", 20),
            )
        elif name == "nr_get_function_code":
            result = await tools.get_function_code(client, arguments["node_id"])
        elif name == "nr_get_node_config":
            result = await tools.get_node_config(client, arguments["node_id"])
        elif name == "nr_get_flow_context":
            result = await tools.get_flow_context(client, arguments["flow_id"], arguments.get("key"))
        elif name == "nr_safe_deploy":
            result = await tools.safe_deploy(
                client,
                arguments["node_id"],
                arguments["fields"],
                description=arguments.get("description"),
            )
        else:
            return _error_result(f"Unknown tool: {name}")

        return _json_result(result)
    except NRError as e:
        return _error_result(str(e))
    except Exception as e:
        return _error_result(f"Unexpected error: {type(e).__name__}: {e}")


def main():
    """Entry point for uv tool install."""
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
