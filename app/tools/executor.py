"""Tool dispatcher for model function calls."""

from .k8s import (
    describe_pod,
    list_namespaces,
    get_deployments_status,
    get_events,
    get_failed_pods,
    get_hpa_status,
    get_nodes_status,
    get_pod_logs,
    get_pods,
    get_recent_events,
    get_resource_usage,
)
from .weather import get_weather


def execute_tool(tool_name: str, args: dict) -> dict | list:
    if tool_name == "list_namespaces":
        return list_namespaces()
    if tool_name == "get_pods":
        return get_pods(**args)
    if tool_name == "get_weather":
        return get_weather(args["city"])
    if tool_name == "get_events":
        return get_events(**args)
    if tool_name == "get_recent_events":
        return get_recent_events(**args)
    if tool_name == "describe_pod":
        return describe_pod(**args)
    if tool_name == "get_pod_logs":
        return get_pod_logs(**args)
    if tool_name == "get_deployments_status":
        return get_deployments_status(**args)
    if tool_name == "get_nodes_status":
        return get_nodes_status()
    if tool_name == "get_resource_usage":
        return get_resource_usage(**args)
    if tool_name == "get_hpa_status":
        return get_hpa_status(**args)
    if tool_name == "get_failed_pods":
        return get_failed_pods(**args)
    return {"error": f"Unknown tool: {tool_name}"}
