import json
import logging
from mcp.types import Tool, TextContent
from converter import ConfigConverter

logger = logging.getLogger(__name__)


def create_list_components_tool(adapter):
    return Tool(
        name="list_components",
        description="List all currently running RAN tester components. Returns component ID, type, and config file path for each running component. Use this first to see what's already running before starting new components.",
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


def create_usage_guide_tool():
    return Tool(
        name="get_usage_guide",
        description="""Get the complete usage guide for the RAN Tester UE MCP server.
Call this tool FIRST to understand how to use all available tools, component types,
configuration formats, validation rules, and example workflows.

This is the primary reference for agents learning how to operate the RAN testing system.""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )


async def handle_usage_guide(adapter, arguments):
    guide = """# RAN Tester UE MCP Server - Usage Guide

## Overview
This MCP server controls a 5G RAN (Radio Access Network) testing system. You can start, stop, monitor, and validate test components that interact with real or simulated radio hardware.

## Available Tools

### 1. list_components
Lists all currently running components. Use this first to see what's active.
- No parameters required
- Returns: Component ID, type, and config file path

### 2. start_component
Starts a new test component. Automatically validates and converts your JSON config.
- **component_type**: One of: rtue, sniffer, sni5gect, jammer, ssb_spoofer, uuagent
- **config_json**: JSON object with component configuration (must include "id" field)
- **rf_config**: RF hardware config, e.g., {"type": "b200"}

### 3. stop_component
Stops a running component.
- **component_id**: The ID of the component to stop

### 4. get_component_logs
Retrieves logs from a component.
- **component_id**: Component ID
- **component_type**: Component type (rtue, sniffer, etc.)

### 5. get_component_health
Checks if a component is running properly.
- **component_id**: Component ID

### 6. get_component_schema
Gets the JSON schema showing required fields for a component type.
- **component_type**: Component type
- Use this BEFORE creating configs to understand what fields are needed

### 7. validate_config
Validates a config without starting the component. Shows the converted config format.
- **component_type**: Component type
- **config_json**: Configuration to validate
- Use this to verify your config is correct before starting

### 8. list_available_configs
Lists existing configuration templates on the system.

## Component Types

| Type | Description | Output Format | Use Case |
|------|-------------|---------------|----------|
| rtue | RAN Tester UE | .conf (INI) | Simulates a 5G phone/device connecting to a network |
| sniffer | Packet sniffer | .toml | Captures and analyzes 5G radio traffic |
| sni5gect | Security testing | .yaml | Tests RAN security vulnerabilities |
| jammer | Jamming simulation | .yaml | Simulates RF jamming attacks |
| ssb_spoofer | SSB spoofing | .yaml | Spoofs synchronization signals |
| uuagent | UU interface | .conf (INI) | UU interface agent for testing |

## RF Hardware Types

| Type | Description |
|------|-------------|
| b200 | USRP B200/B210 software-defined radio (real hardware) |
| zmq | ZeroMQ for simulation/testing (no hardware needed) |
| none | No RF hardware |

**B200/B210 Device Limits:**
- Max frequency: 6 GHz (cannot use FR2 bands)
- Max sample rate: 61.44 MHz
- Max bandwidth: ~56 MHz

## Key 5G Concepts

### Frequency Bands
- n1: 2100 MHz (LTE/5G)
- n3: 1800 MHz (LTE/5G)
- n28: 700 MHz (5G)
- n41: 2.5 GHz (5G)
- n78: 3.5 GHz (5G - most common)
- n79: 4.9 GHz (5G)

### Frequency Ranges
- FR1 (Sub-6GHz): 410 MHz to 7.125 GHz
- FR2 (mmWave): 24.25 GHz to 52.6 GHz (requires specialized hardware, not B200)

### Sample Rates vs Bandwidth
| Sample Rate | Bandwidth | PRBs |
|-------------|-----------|------|
| 15.36 MHz | 10 MHz | 50 |
| 23.04 MHz | 20 MHz | 106 |
| 30.72 MHz | 20 MHz | 106 |
| 61.44 MHz | 100 MHz | 273 |

## Configuration Format Conversion
You provide JSON, the server converts it automatically:
- rtue/uuagent: JSON -> .conf (INI format with sections like [rf], [nas])
- sniffer: JSON -> .toml (with [sniffer] and [[pdcch]] sections)
- sni5gect/jammer/ssb_spoofer: JSON -> .yaml

## Validation Rules

### RTUE Required Fields
- id, rf_srate, rf_tx_gain, rf_rx_gain, rat_nr_bands, rat_nr_nof_prb, usim_imsi, nas_apn
- rf_tx_gain: 0-90
- rf_rx_gain: 0-90
- rf_srate: > 0
- usim_imsi: exactly 15 digits

### Sniffer Required Fields
- id, file_path, sample_rate, frequency, nid_1, ssb_numerology
- frequency: must be in FR1 (410e6-7.125e9) or FR2 (24.25e9-52.6e9)
- ssb_numerology: 0-4
- sample_rate: > 0

### Jammer Required Fields
- id, center_frequency, bandwidth, amplitude, sampling_freq, tx_gain, device_args
- center_frequency: FR1 or FR2 range
- amplitude: 0-1
- tx_gain: 0-90
- bandwidth: > 0
- sampling_freq: >= 2 * bandwidth (Nyquist)

## Example Workflows

### Workflow: Start a UE and Sniffer
1. Call get_component_schema for "rtue" to see required fields
2. Call start_component with rtue config
3. Call start_component with sniffer config
4. Call list_components to verify both running
5. Call get_component_logs to check operation

### Workflow: Run Security Test
1. Call validate_config with your jammer config first
2. Call start_component with jammer config
3. Call get_component_health to verify running
4. When done, call stop_component

### Workflow: Debug a Component
1. Call list_components to see what's running
2. Call get_component_health for the problem component
3. Call get_component_logs to see error messages
4. Fix config based on errors and restart

## Recommended Workflow
1. ALWAYS call get_component_schema first to understand required fields
2. Build your config JSON
3. Call validate_config to verify it's correct
4. Call start_component to launch it
5. Call get_component_logs to monitor operation"""

    return [TextContent(type="text", text=guide)]


def create_tools(adapter):
    return [
        create_usage_guide_tool(),
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
    "get_usage_guide": handle_usage_guide,
    "list_components": handle_list_components,
    "start_component": handle_start_component,
    "stop_component": handle_stop_component,
    "get_component_logs": handle_get_logs,
    "get_component_health": handle_health,
    "get_component_schema": handle_get_schema,
    "validate_config": handle_validate_config,
    "list_available_configs": handle_list_configs
}
