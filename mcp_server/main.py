import os
import logging
import json
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from dotenv import load_dotenv

from tools import create_tools, TOOL_HANDLERS
from resources import create_resources, RESOURCE_HANDLERS
from adapter import ControllerAdapter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

CONTROLLER_URL = os.getenv("CONTROLLER_URL", "http://controller:1343")
CONTROLLER_TOKEN = os.getenv("CONTROLLER_TOKEN")
CONFIGS_DIR = os.getenv("CONFIGS_DIR", "/host/configs")

if not CONTROLLER_TOKEN:
    raise ValueError("CONTROLLER_TOKEN environment variable is required")

server = Server("ran-tester-ue-mcp")

controller_adapter = ControllerAdapter(
    url=CONTROLLER_URL,
    token=CONTROLLER_TOKEN,
    configs_dir=CONFIGS_DIR
)

tools = create_tools(controller_adapter)
resources = create_resources(controller_adapter)


@server.list_tools()
async def list_tools():
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    logger.info(f"Tool called: {name}")
    handler = TOOL_HANDLERS.get(name)
    if handler:
        return await handler(controller_adapter, arguments)
    raise ValueError(f"Unknown tool: {name}")


@server.list_resources()
async def list_resources():
    return resources


@server.read_resource()
async def read_resource(uri: str):
    logger.info(f"Resource read: {uri}")
    for prefix, handler in RESOURCE_HANDLERS.items():
        if uri.startswith(prefix):
            parts = uri[len(prefix):].split('/')
            return await handler(controller_adapter, uri, *parts)
    raise ValueError(f"Unknown resource: {uri}")




async def main():
    logger.info("Starting RAN Tester UE MCP Server")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
