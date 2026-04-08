"""Tool dispatcher for model function calls."""

from .k8s import (
    create_registry_secret,
    create_secret,
    delete_secret,
    describe_pod,
    get_deployment_images,
    list_namespaces,
    list_secrets,
    rollback_deployment,
    restart_deployment,
    set_deployment_image,
    set_deployment_env,
    set_probe_config,
    set_resource_limits,
    set_image_pull_secret,
    get_image_pull_secret_refs,
    get_rollout_history,
    validate_image_reference,
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
from .registry import TOOLS

MUTATING_TOOLS = {
    "create_secret",
    "delete_secret",
    "restart_deployment",
    "set_deployment_image",
    "set_deployment_env",
    "set_probe_config",
    "set_resource_limits",
    "rollback_deployment",
    "set_image_pull_secret",
    "create_registry_secret",
}

# Build set of available tool names from registry
AVAILABLE_TOOLS = {tool["name"] for tool in TOOLS}


def _approval_required(tool_name: str, args: dict) -> bool:
    return tool_name in MUTATING_TOOLS and not bool(args.get("approved"))


def _sanitize_args(args: dict) -> dict:
    safe_args = dict(args)
    safe_args.pop("approved", None)
    return safe_args


def execute_tool(tool_name: str, args: dict) -> dict | list:
    # Check if tool is available
    if tool_name not in AVAILABLE_TOOLS:
        return {
            "status": "tool_not_available",
            "tool": tool_name,
            "message": (
                f"Tool '{tool_name}' is not available. "
                f"Available tools: {sorted(AVAILABLE_TOOLS)}. "
                f"To use this tool, add it to app/tools/k8s.py (or weather.py), "
                f"import it in executor.py, add a dispatch case, and register it in registry.py."
            ),
        }
    
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
    if tool_name == "list_secrets":
        return list_secrets(**safe_args)
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
    if tool_name == "get_deployment_images":
        return get_deployment_images(**safe_args)
    if tool_name == "get_rollout_history":
        return get_rollout_history(**safe_args)
    if tool_name == "get_nodes_status":
        return get_nodes_status()
    if tool_name == "get_resource_usage":
        return get_resource_usage(**safe_args)
    if tool_name == "get_hpa_status":
        return get_hpa_status(**safe_args)
    if tool_name == "get_failed_pods":
        return get_failed_pods(**safe_args)
    if tool_name == "get_image_pull_secret_refs":
        return get_image_pull_secret_refs(**safe_args)
    if tool_name == "validate_image_reference":
        return validate_image_reference(**safe_args)
    if tool_name == "create_secret":
        return create_secret(**safe_args)
    if tool_name == "delete_secret":
        return delete_secret(**safe_args)
    if tool_name == "restart_deployment":
        return restart_deployment(**safe_args)
    if tool_name == "set_deployment_image":
        return set_deployment_image(**safe_args)
    if tool_name == "set_deployment_env":
        return set_deployment_env(**safe_args)
    if tool_name == "set_probe_config":
        return set_probe_config(**safe_args)
    if tool_name == "set_resource_limits":
        return set_resource_limits(**safe_args)
    if tool_name == "rollback_deployment":
        return rollback_deployment(**safe_args)
    if tool_name == "set_image_pull_secret":
        return set_image_pull_secret(**safe_args)
    if tool_name == "create_registry_secret":
        return create_registry_secret(**safe_args)
    return {"error": f"Unknown tool: {tool_name}"}
