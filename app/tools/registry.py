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
        "name": "list_secrets",
        "description": "List all secrets in a Kubernetes namespace with their type and keys",
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
    {
        "type": "function",
        "name": "get_deployment_images",
        "description": "Get current container image references and imagePullSecrets from a deployment",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "name": {
                    "type": "string",
                    "description": "Deployment name.",
                },
            },
            "required": ["namespace", "name"],
        },
    },
    {
        "type": "function",
        "name": "get_rollout_history",
        "description": "Get rollout revision history for a deployment based on ReplicaSets",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "name": {
                    "type": "string",
                    "description": "Deployment name.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum revisions to return. Defaults to 10.",
                },
            },
            "required": ["namespace", "name"],
        },
    },
    {
        "type": "function",
        "name": "get_image_pull_secret_refs",
        "description": "Inspect imagePullSecrets used by a deployment pod spec and its service account",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "deployment": {
                    "type": "string",
                    "description": "Deployment name.",
                },
            },
            "required": ["namespace", "deployment"],
        },
    },
    {
        "type": "function",
        "name": "validate_image_reference",
        "description": "Validate whether a container image reference exists in a registry",
        "parameters": {
            "type": "object",
            "properties": {
                "image": {
                    "type": "string",
                    "description": "Image reference such as nginx:1.25 or ghcr.io/org/app:tag.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Network timeout for registry checks. Defaults to 8 seconds.",
                },
            },
            "required": ["image"],
        },
    },
    {
        "type": "function",
        "name": "create_secret",
        "description": "Create a Kubernetes secret in a namespace. Always include the 'data' field with the key-value pairs for the secret. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace where the secret will be created.",
                },
                "name": {
                    "type": "string",
                    "description": "Secret name.",
                },
                "data": {
                    "type": "object",
                    "description": "Required. Key/value pairs for the secret (e.g. {\"token\": \"mysecretvalue\"}). Must always be provided.",
                    "additionalProperties": {"type": "string"},
                },
                "secret_type": {
                    "type": "string",
                    "description": "Kubernetes secret type. Defaults to Opaque.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "name", "data"],
        },
    },
    {
        "type": "function",
        "name": "create_registry_secret",
        "description": "Create a docker-registry secret (kubernetes.io/dockerconfigjson). This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace where the secret will be created.",
                },
                "name": {
                    "type": "string",
                    "description": "Secret name.",
                },
                "server": {
                    "type": "string",
                    "description": "Registry host, for example index.docker.io or ghcr.io.",
                },
                "username": {
                    "type": "string",
                    "description": "Registry username.",
                },
                "password": {
                    "type": "string",
                    "description": "Registry password or token.",
                },
                "email": {
                    "type": "string",
                    "description": "Optional email field in docker config.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "name", "server", "username", "password"],
        },
    },
    {
        "type": "function",
        "name": "delete_secret",
        "description": "Delete a Kubernetes secret from a namespace. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the secret.",
                },
                "name": {
                    "type": "string",
                    "description": "Secret name to delete.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "name"],
        },
    },
    {
        "type": "function",
        "name": "set_deployment_image",
        "description": "Patch a deployment container image to a specified value. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "deployment": {
                    "type": "string",
                    "description": "Deployment name.",
                },
                "container": {
                    "type": "string",
                    "description": "Container name inside the deployment.",
                },
                "image": {
                    "type": "string",
                    "description": "Target image reference.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "deployment", "container", "image"],
        },
    },
    {
        "type": "function",
        "name": "set_deployment_env",
        "description": "Set or update an environment variable in a deployment container. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "deployment": {
                    "type": "string",
                    "description": "Deployment name.",
                },
                "container": {
                    "type": "string",
                    "description": "Container name inside the deployment.",
                },
                "name": {
                    "type": "string",
                    "description": "Environment variable name.",
                },
                "value": {
                    "type": "string",
                    "description": "Environment variable value.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "deployment", "container", "name", "value"],
        },
    },
    {
        "type": "function",
        "name": "set_probe_config",
        "description": "Configure an HTTP liveness/readiness/startup probe for a deployment container. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "deployment": {
                    "type": "string",
                    "description": "Deployment name.",
                },
                "container": {
                    "type": "string",
                    "description": "Container name inside the deployment.",
                },
                "probe_type": {
                    "type": "string",
                    "description": "Probe type: liveness, readiness, or startup.",
                },
                "path": {
                    "type": "string",
                    "description": "HTTP path to probe, for example /healthz.",
                },
                "port": {
                    "type": "integer",
                    "description": "HTTP port to probe.",
                },
                "initial_delay_seconds": {
                    "type": "integer",
                    "description": "Initial delay before probing starts.",
                },
                "period_seconds": {
                    "type": "integer",
                    "description": "Probe interval in seconds.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Probe timeout in seconds.",
                },
                "success_threshold": {
                    "type": "integer",
                    "description": "Minimum consecutive successes for success.",
                },
                "failure_threshold": {
                    "type": "integer",
                    "description": "Consecutive failures before action.",
                },
                "scheme": {
                    "type": "string",
                    "description": "HTTP scheme, usually HTTP or HTTPS.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "deployment", "container", "probe_type", "path", "port"],
        },
    },
    {
        "type": "function",
        "name": "set_resource_limits",
        "description": "Set CPU/memory requests and limits on a deployment container. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "deployment": {
                    "type": "string",
                    "description": "Deployment name.",
                },
                "container": {
                    "type": "string",
                    "description": "Container name inside the deployment.",
                },
                "requests_cpu": {
                    "type": "string",
                    "description": "CPU request, for example 100m.",
                },
                "requests_memory": {
                    "type": "string",
                    "description": "Memory request, for example 128Mi.",
                },
                "limits_cpu": {
                    "type": "string",
                    "description": "CPU limit, for example 500m.",
                },
                "limits_memory": {
                    "type": "string",
                    "description": "Memory limit, for example 512Mi.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "deployment", "container"],
        },
    },
    {
        "type": "function",
        "name": "rollback_deployment",
        "description": "Rollback deployment container images to a previous rollout revision. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "name": {
                    "type": "string",
                    "description": "Deployment name.",
                },
                "to_revision": {
                    "type": "integer",
                    "description": "Optional revision number. If omitted, rollback uses the previous revision.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "name"],
        },
    },
    {
        "type": "function",
        "name": "set_image_pull_secret",
        "description": "Attach an existing imagePullSecret to a deployment and/or service account. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing targets.",
                },
                "secret_name": {
                    "type": "string",
                    "description": "Existing secret name to attach.",
                },
                "deployment": {
                    "type": "string",
                    "description": "Optional deployment name target.",
                },
                "service_account": {
                    "type": "string",
                    "description": "Optional service account target.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "secret_name"],
        },
    },
    {
        "type": "function",
        "name": "restart_deployment",
        "description": "Restart a deployment rollout by patching a restart annotation. This mutating action requires explicit approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace containing the deployment.",
                },
                "name": {
                    "type": "string",
                    "description": "Deployment name.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "Set true only after user explicitly approves this change.",
                },
            },
            "required": ["namespace", "name"],
        },
    },
]
