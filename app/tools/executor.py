"""Tool dispatcher for model function calls."""

from .k8s import (
    create_secret,
    describe_pod,
    list_namespaces,
    restart_deployment,
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

MUTATING_TOOLS = {"create_secret", "restart_deployment"}


def _approval_required(tool_name: str, args: dict) -> bool:
    return tool_name in MUTATING_TOOLS and not bool(args.get("approved"))


def _sanitize_args(args: dict) -> dict:
    safe_args = dict(args)
    safe_args.pop("approved", None)
    return safe_args


def execute_tool(tool_name: str, args: dict) -> dict | list:
    if _approval_required(tool_name, args):
        return {
            "status": "permission_required",
            "tool": tool_name,
            "message": (
                f"Tool '{tool_name}' changes cluster state. Ask user for approval and then call again with approved=true."
            ),
        }

    safe_args = _sanitize_args(args)

    if tool_name == "list_namespaces":
        return list_namespaces()
    if tool_name == "get_pods":
        return get_pods(**safe_args)
    if tool_name == "get_weather":
        return get_weather(safe_args["city"])
    if tool_name == "get_events":
        return get_events(**safe_args)
    if tool_name == "get_recent_events":
        return get_recent_events(**safe_args)
    if tool_name == "describe_pod":
        return describe_pod(**safe_args)
    if tool_name == "get_pod_logs":
        return get_pod_logs(**safe_args)
    if tool_name == "get_deployments_status":
        return get_deployments_status(**safe_args)
    if tool_name == "get_nodes_status":
        return get_nodes_status()
    if tool_name == "get_resource_usage":
        return get_resource_usage(**safe_args)
    if tool_name == "get_hpa_status":
        return get_hpa_status(**safe_args)
    if tool_name == "get_failed_pods":
        return get_failed_pods(**safe_args)
    if tool_name == "create_secret":
        return create_secret(**safe_args)
    if tool_name == "restart_deployment":
        return restart_deployment(**safe_args)
    return {"error": f"Unknown tool: {tool_name}"}
