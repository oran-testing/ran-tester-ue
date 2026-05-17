import json
import logging
from mcp.types import Resource

logger = logging.getLogger(__name__)


def create_component_status_resource(adapter):
    return Resource(
        uri="component://{component_id}/status",
        name="Component Status",
        description="Current status of a running component",
        mimeType="application/json"
    )


async def handle_component_status(adapter, uri, component_id):
    success, result = adapter.get_health(component_id)
    if success:
        return result
    return {"error": result.get("error", "Unknown error")}


def create_schema_resource(adapter):
    return Resource(
        uri="schema://{component_type}",
        name="Component Schema",
        description="JSON schema for component configuration",
        mimeType="application/json"
    )


async def handle_schema_resource(adapter, uri, component_type):
    success, result = adapter.get_schema(component_type)
    if success:
        return result
    return {"error": result.get("error", "Unknown error")}


def create_config_template_resource(adapter):
    return Resource(
        uri="template://{config_name}",
        name="Config Template",
        description="Configuration template file",
        mimeType="text/yaml"
    )


async def handle_config_template_resource(adapter, uri, config_name):
    success, result = adapter.get_config_template(config_name)
    if success:
        return result
    return f"Error: {result}"


def create_component_logs_resource(adapter):
    return Resource(
        uri="log://{component_id}",
        name="Component Logs",
        description="Recent logs from a component",
        mimeType="application/json"
    )


async def handle_component_logs_resource(adapter, uri, component_id):
    success, components = adapter.list_components()
    if not success:
        return {"error": "Failed to list components"}

    component_type = None
    for comp in components.get("running", []):
        if comp["id"] == component_id:
            component_type = comp["type"]
            break

    if not component_type:
        return {"error": f"Component {component_id} not found"}

    success, result = adapter.get_logs(component_id, component_type)
    if success:
        return result
    return {"error": result.get("error", "Unknown error")}


def create_resources(adapter):
    return [
        create_component_status_resource(adapter),
        create_schema_resource(adapter),
        create_config_template_resource(adapter),
        create_component_logs_resource(adapter)
    ]


RESOURCE_HANDLERS = {
    "component://": handle_component_status,
    "schema://": handle_schema_resource,
    "template://": handle_config_template_resource,
    "log://": handle_component_logs_resource
}
