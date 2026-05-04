import json
import logging
from mcp.types import Tool, TextContent
from converter import ConfigConverter

logger = logging.getLogger(__name__)


def create_list_components_tool(adapter):
    return Tool(
        name="list_components",
        description="List all running RAN tester components",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )


async def handle_list_components(adapter, arguments):
    success, result = adapter.list_components()
    if success:
        return [TextContent(
            type="text",
            text=f"Running components:\n{json.dumps(result, indent=2)}"
        )]
    return [TextContent(
        type="text",
        text=f"Error listing components: {result.get('error', 'Unknown error')}"
    )]


def create_start_component_tool(adapter):
    return Tool(
        name="start_component",
        description="""Start a RAN testing component with JSON configuration.

Supported component types:
- rtue: RAN Tester UE (.conf format)
- sniffer: Packet sniffer (.toml format)
- sni5gect: Security testing framework (.yaml format)
- jammer: Jamming simulation (.yaml format)
- ssb_spoofer: SSB spoofing (.yaml format)
- uuagent: UU interface agent (.conf format)

RF types:
- b200: USRP B200/B210 hardware
- zmq: ZeroMQ for simulation
- none: No RF hardware""",
        inputSchema={
            "type": "object",
            "properties": {
                "component_type": {
                    "type": "string",
                    "enum": ["rtue", "sniffer", "sni5gect", "jammer", "ssb_spoofer", "uuagent"],
                    "description": "Type of component to start"
                },
                "config_json": {
                    "type": "object",
                    "description": "Component configuration as JSON object"
                },
                "rf_config": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["b200", "zmq", "none"],
                            "description": "RF hardware type"
                        }
                    },
                    "required": ["type"]
                }
            },
            "required": ["component_type", "config_json", "rf_config"]
        }
    )


async def handle_start_component(adapter, arguments):
    component_type = arguments["component_type"]
    config_json = arguments["config_json"]
    rf_config = arguments["rf_config"]

    if "id" not in config_json:
        return [TextContent(
            type="text",
            text="Error: 'id' field required in config_json"
        )]

    payload = {
        "id": config_json["id"],
        "type": component_type,
        "config_json": config_json,
        "rf": rf_config
    }

    success, result = adapter.start_component(payload)

    if success:
        return [TextContent(
            type="text",
            text=f"Component started successfully:\n{json.dumps(result, indent=2)}"
        )]
    else:
        error_msg = result.get('error', 'Unknown error')
        details = result.get('details', '')
        response_text = f"Failed to start component:\n{error_msg}"
        if details:
            response_text += f"\n\nDetails: {details}"
        return [TextContent(
            type="text",
            text=response_text
        )]


def create_stop_component_tool(adapter):
    return Tool(
        name="stop_component",
        description="Stop a running component by its ID",
        inputSchema={
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "string",
                    "description": "ID of the component to stop"
                }
            },
            "required": ["component_id"]
        }
    )


async def handle_stop_component(adapter, arguments):
    component_id = arguments["component_id"]
    success, result = adapter.stop_component(component_id)

    if success:
        return [TextContent(
            type="text",
            text=f"Component stopped successfully:\n{json.dumps(result, indent=2)}"
        )]
    return [TextContent(
        type="text",
        text=f"Failed to stop component:\n{result.get('error', 'Unknown error')}"
    )]


def create_get_logs_tool(adapter):
    return Tool(
        name="get_component_logs",
        description="Retrieve logs from a specific component",
        inputSchema={
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "string",
                    "description": "ID of the component"
                },
                "component_type": {
                    "type": "string",
                    "description": "Type of the component"
                }
            },
            "required": ["component_id", "component_type"]
        }
    )


async def handle_get_logs(adapter, arguments):
    component_id = arguments["component_id"]
    component_type = arguments["component_type"]

    success, result = adapter.get_logs(component_id, component_type)

    if success:
        logs = result.get("logs", [])
        if not logs:
            return [TextContent(
                type="text",
                text="No logs found for this component"
            )]

        log_text = "\n".join([
            f"[{log['time']}] {log['message']}"
            for log in logs[:50]
        ])

        return [TextContent(
            type="text",
            text=f"Logs for {component_id}:\n{log_text}"
        )]

    return [TextContent(
        type="text",
        text=f"Error getting logs: {result.get('error', 'Unknown error')}"
    )]


def create_health_tool(adapter):
    return Tool(
        name="get_component_health",
        description="Check the health status of a running component",
        inputSchema={
            "type": "object",
            "properties": {
                "component_id": {
                    "type": "string",
                    "description": "ID of the component to check"
                }
            },
            "required": ["component_id"]
        }
    )


async def handle_health(adapter, arguments):
    component_id = arguments["component_id"]
    success, result = adapter.get_health(component_id)

    if success:
        return [TextContent(
            type="text",
            text=f"Health status for {component_id}:\n{json.dumps(result, indent=2)}"
        )]
    return [TextContent(
        type="text",
        text=f"Error checking health: {result.get('error', 'Unknown error')}"
    )]


def create_get_schema_tool(adapter):
    return Tool(
        name="get_component_schema",
        description="Get the JSON schema for a component type. Use this to understand required fields and validation rules before creating configurations.",
        inputSchema={
            "type": "object",
            "properties": {
                "component_type": {
                    "type": "string",
                    "enum": ["rtue", "sniffer", "sni5gect", "jammer", "ssb_spoofer", "uuagent"],
                    "description": "Component type to get schema for"
                }
            },
            "required": ["component_type"]
        }
    )


async def handle_get_schema(adapter, arguments):
    component_type = arguments["component_type"]
    success, result = adapter.get_schema(component_type)

    if success:
        return [TextContent(
            type="text",
            text=f"Schema for {component_type}:\n{json.dumps(result, indent=2)}"
        )]
    return [TextContent(
        type="text",
        text=f"Error getting schema: {result.get('error', 'Unknown error')}"
    )]


def create_validate_config_tool(adapter):
    return Tool(
        name="validate_config",
        description="Validate a JSON configuration without starting the component. Returns validation errors if any.",
        inputSchema={
            "type": "object",
            "properties": {
                "component_type": {
                    "type": "string",
                    "enum": ["rtue", "sniffer", "sni5gect", "jammer", "ssb_spoofer", "uuagent"]
                },
                "config_json": {
                    "type": "object",
                    "description": "Configuration to validate"
                }
            },
            "required": ["component_type", "config_json"]
        }
    )


async def handle_validate_config(adapter, arguments):
    component_type = arguments["component_type"]
    config_json = arguments["config_json"]

    try:
        config_str, file_ext = ConfigConverter.convert(component_type, config_json)
        return [TextContent(
            type="text",
            text=f"Configuration is valid!\nFile extension: .{file_ext}\n\nConverted config:\n{config_str}"
        )]
    except ValueError as e:
        return [TextContent(
            type="text",
            text=f"Validation failed:\n{str(e)}"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error during validation: {str(e)}"
        )]


def create_list_configs_tool(adapter):
    return Tool(
        name="list_available_configs",
        description="List all available configuration templates",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )


async def handle_list_configs(adapter, arguments):
    success, result = adapter.list_available_configs()

    if success:
        if not result:
            return [TextContent(
                type="text",
                text="No configuration templates found"
            )]

        config_list = "\n".join([
            f"- {cfg['name']}"
            for cfg in result
        ])

        return [TextContent(
            type="text",
            text=f"Available configurations:\n{config_list}"
        )]

    return [TextContent(
        type="text",
        text=f"Error listing configs: {result[0].get('error', 'Unknown error')}"
    )]


def create_tools(adapter):
    return [
        create_list_components_tool(adapter),
        create_start_component_tool(adapter),
        create_stop_component_tool(adapter),
        create_get_logs_tool(adapter),
        create_health_tool(adapter),
        create_get_schema_tool(adapter),
        create_validate_config_tool(adapter),
        create_list_configs_tool(adapter)
    ]


TOOL_HANDLERS = {
    "list_components": handle_list_components,
    "start_component": handle_start_component,
    "stop_component": handle_stop_component,
    "get_component_logs": handle_get_logs,
    "get_component_health": handle_health,
    "get_component_schema": handle_get_schema,
    "validate_config": handle_validate_config,
    "list_available_configs": handle_list_configs
}
