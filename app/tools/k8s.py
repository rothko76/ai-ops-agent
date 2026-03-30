"""Kubernetes-related tools."""

from typing import Any, cast
from datetime import UTC, datetime

from kubernetes import client as k8s_client, config
from kubernetes.client.rest import ApiException


def _load_kube_config() -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


def _safe_ns(namespace: str | None) -> str:
    return namespace or "default"


def _event_timestamp(event: Any) -> str:
    return str(event.last_timestamp or event.event_time or event.first_timestamp or "")


def list_namespaces() -> list[str] | dict[str, str]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        namespaces = cast(Any, v1.list_namespace())
        return [ns.metadata.name for ns in namespaces.items]
    except ApiException as err:
        return {"error": f"Failed to list namespaces: {err.reason}"}


def get_pods(namespace: str = "default") -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        pods = cast(Any, v1.list_namespaced_pod(namespace=_safe_ns(namespace)))
        results: list[dict[str, Any]] = []
        for pod in cast(Any, pods.items):
            restarts = sum((cs.restart_count or 0) for cs in (pod.status.container_statuses or []))
            results.append(
                {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "restarts": restarts,
                    "node": pod.spec.node_name,
                }
            )
        return results
    except ApiException as err:
        return {"error": f"Failed to list pods: {err.reason}"}


def get_events(
    namespace: str = "default",
    involved_object: str | None = None,
    warnings_only: bool = True,
    limit: int = 100,
) -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    filter_object = involved_object if involved_object else None
    try:
        events = cast(
            Any,
            v1.list_namespaced_event(
            namespace=_safe_ns(namespace),
            field_selector=f"involvedObject.name={filter_object}" if filter_object else "",
            ),
        )

        filtered = [
            {
                "reason": e.reason,
                "message": e.message,
                "count": e.count,
                "object": e.involved_object.name,
                "type": e.type,
                "last_seen": _event_timestamp(e),
            }
            for e in cast(Any, events.items)
            if (not warnings_only or e.type == "Warning")
        ]
        filtered.sort(key=lambda item: item.get("last_seen", ""), reverse=True)
        return filtered[: max(1, limit)]
    except ApiException as err:
        return {"error": f"Failed to list events: {err.reason}"}


def get_recent_events(namespace: str = "default", limit: int = 100, warnings_only: bool = True) -> list[dict[str, Any]] | dict[str, str]:
    return get_events(namespace=namespace, warnings_only=warnings_only, limit=limit)


def describe_pod(namespace: str, pod_name: str) -> dict[str, Any]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        pod = cast(Any, v1.read_namespaced_pod(name=pod_name, namespace=_safe_ns(namespace)))
        container_statuses = []
        for c in cast(Any, pod.status.container_statuses or []):
            state = c.state.to_dict() if c.state else {}
            container_statuses.append(
                {
                    "name": c.name,
                    "ready": c.ready,
                    "restarts": c.restart_count,
                    "state": state,
                    "image": c.image,
                }
            )

        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "pod_ip": pod.status.pod_ip,
            "start_time": str(pod.status.start_time),
            "labels": pod.metadata.labels or {},
            "conditions": [
                {
                    "type": cond.type,
                    "status": cond.status,
                    "reason": cond.reason,
                    "message": cond.message,
                }
                for cond in cast(Any, (pod.status.conditions or []))
            ],
            "containers": container_statuses,
        }
    except ApiException as err:
        return {"error": f"Failed to describe pod '{pod_name}': {err.reason}"}


def get_pod_logs(
    namespace: str,
    pod_name: str,
    container: str | None = None,
    previous: bool = False,
    tail: int = 200,
) -> dict[str, Any]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=_safe_ns(namespace),
            container=container,
            previous=previous,
            tail_lines=max(1, tail),
        )
        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "container": container,
            "previous": previous,
            "tail": tail,
            "logs": logs,
        }
    except ApiException as err:
        return {"error": f"Failed to fetch logs for pod '{pod_name}': {err.reason}"}


def get_deployments_status(namespace: str = "default") -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    try:
        deployments = cast(Any, apps.list_namespaced_deployment(namespace=_safe_ns(namespace)))
        return [
            {
                "name": d.metadata.name,
                "namespace": d.metadata.namespace,
                "desired_replicas": d.spec.replicas,
                "ready_replicas": d.status.ready_replicas or 0,
                "available_replicas": d.status.available_replicas or 0,
                "updated_replicas": d.status.updated_replicas or 0,
                "unavailable_replicas": d.status.unavailable_replicas or 0,
            }
            for d in cast(Any, deployments.items)
        ]
    except ApiException as err:
        return {"error": f"Failed to list deployments: {err.reason}"}


def get_nodes_status() -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        nodes = cast(Any, v1.list_node())
        results: list[dict[str, Any]] = []
        for node in cast(Any, nodes.items):
            ready_condition = next((c for c in (node.status.conditions or []) if c.type == "Ready"), None)
            if ready_condition:
                ready_status = ready_condition.status
                ready_reason = ready_condition.reason
            else:
                ready_status = "Unknown"
                ready_reason = None
            results.append(
                {
                    "name": node.metadata.name,
                    "ready": ready_status,
                    "ready_reason": ready_reason,
                    "kubelet_version": node.status.node_info.kubelet_version,
                    "os_image": node.status.node_info.os_image,
                    "container_runtime": node.status.node_info.container_runtime_version,
                }
            )
        return results
    except ApiException as err:
        return {"error": f"Failed to list nodes: {err.reason}"}


def get_resource_usage(namespace: str | None = None) -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    custom_api = k8s_client.CustomObjectsApi()

    try:
        if namespace:
            response = custom_api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=_safe_ns(namespace),
                plural="pods",
            )
        else:
            response = custom_api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods",
            )
            response = cast(Any, response)
    except ApiException as err:
        return {
            "error": (
                "Failed to query pod metrics. Ensure metrics-server is installed in the cluster. "
                f"API error: {err.reason}"
            )
        }

    items = response.get("items", [])
    return [
        {
            "name": item.get("metadata", {}).get("name"),
            "namespace": item.get("metadata", {}).get("namespace"),
            "containers": [
                {
                    "name": c.get("name"),
                    "cpu": c.get("usage", {}).get("cpu"),
                    "memory": c.get("usage", {}).get("memory"),
                }
                for c in item.get("containers", [])
            ],
        }
        for item in items
    ]


def get_hpa_status(namespace: str = "default") -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    autoscaling = k8s_client.AutoscalingV2Api()

    try:
        hpas = cast(Any, autoscaling.list_namespaced_horizontal_pod_autoscaler(namespace=_safe_ns(namespace)))
        results: list[dict[str, Any]] = []
        for hpa in cast(Any, hpas.items):
            metrics = []
            for metric in cast(Any, hpa.status.current_metrics or []):
                metrics.append(metric.to_dict())

            results.append(
                {
                    "name": hpa.metadata.name,
                    "namespace": hpa.metadata.namespace,
                    "target": {
                        "kind": hpa.spec.scale_target_ref.kind,
                        "name": hpa.spec.scale_target_ref.name,
                    },
                    "min_replicas": hpa.spec.min_replicas,
                    "max_replicas": hpa.spec.max_replicas,
                    "current_replicas": hpa.status.current_replicas,
                    "desired_replicas": hpa.status.desired_replicas,
                    "current_metrics": metrics,
                }
            )
        return results
    except ApiException as err:
        return {"error": f"Failed to list HPAs: {err.reason}"}


def get_failed_pods(namespace: str = "default") -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        pods = cast(Any, v1.list_namespaced_pod(namespace=_safe_ns(namespace)))
        failed: list[dict[str, Any]] = []

        for pod in cast(Any, pods.items):
            phase = pod.status.phase or "Unknown"
            container_statuses = pod.status.container_statuses or []
            restart_count = sum((cs.restart_count or 0) for cs in container_statuses)

            waiting_reasons = [
                cs.state.waiting.reason
                for cs in container_statuses
                if cs.state and cs.state.waiting and cs.state.waiting.reason
            ]

            if phase in {"Failed", "Unknown", "Pending"} or waiting_reasons or restart_count > 0:
                failed.append(
                    {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "phase": phase,
                        "node": pod.spec.node_name,
                        "restarts": restart_count,
                        "waiting_reasons": waiting_reasons,
                    }
                )

        failed.sort(key=lambda item: item.get("restarts", 0), reverse=True)
        return failed
    except ApiException as err:
        return {"error": f"Failed to list failed pods: {err.reason}"}


def create_secret(
    namespace: str,
    name: str,
    data: dict[str, str] | None = None,
    secret_type: str = "Opaque",
) -> dict[str, str]:
    if data is None:
        data = {}
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    body = k8s_client.V1Secret(
        metadata=k8s_client.V1ObjectMeta(name=name, namespace=_safe_ns(namespace)),
        string_data=data,
        type=secret_type,
    )

    try:
        v1.create_namespaced_secret(namespace=_safe_ns(namespace), body=body)
        return {
            "status": "created",
            "namespace": _safe_ns(namespace),
            "name": name,
            "type": secret_type,
        }
    except ApiException as err:
        if err.status == 409:
            return {
                "status": "already_exists",
                "namespace": _safe_ns(namespace),
                "name": name,
            }
        return {"error": f"Failed to create secret '{name}': {err.reason}"}


def restart_deployment(namespace: str, name: str) -> dict[str, str]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    restarted_at = datetime.now(UTC).isoformat()
    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": restarted_at,
                    }
                }
            }
        }
    }

    try:
        apps.patch_namespaced_deployment(
            name=name,
            namespace=_safe_ns(namespace),
            body=patch_body,
        )
        return {
            "status": "restarted",
            "namespace": _safe_ns(namespace),
            "name": name,
            "restarted_at": restarted_at,
        }
    except ApiException as err:
        return {"error": f"Failed to restart deployment '{name}': {err.reason}"}
