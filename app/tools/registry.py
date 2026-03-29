"""Tool definitions for the OpenAI Responses API."""

TOOLS = [
    {
        "type": "function",
        "name": "list_namespaces",
        "description": "List all namespaces in the Kubernetes cluster",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_pods",
        "description": "Get list of Kubernetes pods and their status",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The Kubernetes namespace to query. Defaults to 'default'.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get the current weather for a given city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The name of the city, e.g. 'Tel Aviv'",
                }
            },
            "required": ["city"],
        },
    },
    {
        "type": "function",
        "name": "get_events",
        "description": "Get Kubernetes warning events in a namespace, optionally filtered to a specific pod or object",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The Kubernetes namespace to query. Defaults to 'default'.",
                },
                "involved_object": {
                    "type": "string",
                    "description": "Optional pod or object name to filter events for.",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_recent_events",
        "description": "Get recent Kubernetes events in a namespace with optional warning-only filter",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The namespace to query. Defaults to 'default'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of events to return. Defaults to 100.",
                },
                "warnings_only": {
                    "type": "boolean",
                    "description": "If true, only return warning events. Defaults to true.",
                },
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "describe_pod",
        "description": "Describe pod status, conditions, and container state",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The namespace containing the pod.",
                },
                "pod_name": {
                    "type": "string",
                    "description": "The pod name to describe.",
                },
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "type": "function",
        "name": "get_pod_logs",
        "description": "Fetch logs from a pod container",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The namespace containing the pod.",
                },
                "pod_name": {
                    "type": "string",
                    "description": "The pod name to fetch logs from.",
                },
                "container": {
                    "type": "string",
                    "description": "Optional container name for multi-container pods.",
                },
                "previous": {
                    "type": "boolean",
                    "description": "If true, return logs from the previous crashed container instance.",
                },
                "tail": {
                    "type": "integer",
                    "description": "Number of log lines from the end. Defaults to 200.",
                },
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "type": "function",
        "name": "get_deployments_status",
        "description": "Get rollout and replica status for deployments in a namespace",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The namespace to inspect. Defaults to 'default'.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_nodes_status",
        "description": "Get readiness and runtime information for cluster nodes",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_resource_usage",
        "description": "Get pod CPU and memory usage from metrics-server",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Optional namespace filter. If omitted, returns cluster-wide pod metrics.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_hpa_status",
        "description": "Get HorizontalPodAutoscaler status and scaling targets in a namespace",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The namespace to inspect. Defaults to 'default'.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "get_failed_pods",
        "description": "List pods likely in a bad state (failed phase, waiting errors, or frequent restarts)",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The namespace to inspect. Defaults to 'default'.",
                }
            },
            "required": [],
        },
    },
]
