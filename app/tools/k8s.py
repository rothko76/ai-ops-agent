"""Kubernetes-related tools."""

from typing import Any, cast
from datetime import UTC, datetime
import base64
import json
import logging
from urllib.parse import parse_qs, urlparse

from kubernetes import client as k8s_client, config
from kubernetes.client.rest import ApiException
import requests
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)
RETRYABLE_K8S_STATUS_CODES = {0, 408, 409, 429, 500, 502, 503, 504}


def _is_retryable_k8s_error(exc: BaseException) -> bool:
    return isinstance(exc, ApiException) and getattr(exc, "status", None) in RETRYABLE_K8S_STATUS_CODES


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=8),
    retry=retry_if_exception(_is_retryable_k8s_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _k8s_call(func: Any, *args: Any, **kwargs: Any) -> Any:
    return func(*args, **kwargs)


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
        namespaces = cast(Any, _k8s_call(v1.list_namespace))
        return [ns.metadata.name for ns in namespaces.items]
    except ApiException as err:
        return {"error": f"Failed to list namespaces: {err.reason}"}


def list_secrets(namespace: str = "default") -> list[dict[str, Any]] | dict[str, str]:
    """List all secrets in a namespace with their type and keys."""
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        secrets = cast(Any, _k8s_call(v1.list_namespaced_secret, namespace=_safe_ns(namespace)))
        results: list[dict[str, Any]] = []
        for secret in cast(Any, secrets.items):
            results.append({
                "name": secret.metadata.name,
                "type": secret.type,
                "keys": list(secret.data.keys()) if secret.data else [],
            })
        return results
    except ApiException as err:
        return {"error": f"Failed to list secrets: {err.reason}"}


def get_pods(namespace: str = "default") -> list[dict[str, Any]] | dict[str, str]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        pods = cast(Any, _k8s_call(v1.list_namespaced_pod, namespace=_safe_ns(namespace)))
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
            _k8s_call(
            v1.list_namespaced_event,
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
        pod = cast(Any, _k8s_call(v1.read_namespaced_pod, name=pod_name, namespace=_safe_ns(namespace)))
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
        logs = _k8s_call(
            v1.read_namespaced_pod_log,
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
        deployments = cast(Any, _k8s_call(apps.list_namespaced_deployment, namespace=_safe_ns(namespace)))
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
        nodes = cast(Any, _k8s_call(v1.list_node))
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
            response = _k8s_call(
                custom_api.list_namespaced_custom_object,
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=_safe_ns(namespace),
                plural="pods",
            )
        else:
            response = _k8s_call(
                custom_api.list_cluster_custom_object,
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
        hpas = cast(Any, _k8s_call(autoscaling.list_namespaced_horizontal_pod_autoscaler, namespace=_safe_ns(namespace)))
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
        pods = cast(Any, _k8s_call(v1.list_namespaced_pod, namespace=_safe_ns(namespace)))
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


def _deployment_label_selector(deployment: Any) -> str:
    labels = cast(dict[str, str], deployment.spec.selector.match_labels or {})
    return ",".join(f"{k}={v}" for k, v in labels.items())


def _is_owned_by_deployment(replica_set: Any, deployment_name: str) -> bool:
    for owner in cast(Any, replica_set.metadata.owner_references or []):
        if owner.kind == "Deployment" and owner.name == deployment_name:
            return True
    return False


def _collect_container_images(template_spec: Any) -> dict[str, Any]:
    containers = [
        {"name": c.name, "image": c.image}
        for c in cast(Any, template_spec.containers or [])
    ]
    init_containers = [
        {"name": c.name, "image": c.image}
        for c in cast(Any, template_spec.init_containers or [])
    ]
    return {
        "containers": containers,
        "init_containers": init_containers,
    }


def get_deployment_images(namespace: str, name: str) -> dict[str, Any]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    try:
        deployment = cast(Any, _k8s_call(apps.read_namespaced_deployment, name=name, namespace=_safe_ns(namespace)))
        spec = deployment.spec.template.spec
        images = _collect_container_images(spec)
        image_pull_secrets = [s.name for s in cast(Any, spec.image_pull_secrets or [])]

        return {
            "namespace": deployment.metadata.namespace,
            "name": deployment.metadata.name,
            "images": images,
            "image_pull_secrets": image_pull_secrets,
        }
    except ApiException as err:
        return {"error": f"Failed to get deployment images for '{name}': {err.reason}"}


def get_rollout_history(namespace: str, name: str, limit: int = 10) -> dict[str, Any]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    try:
        deployment = cast(Any, _k8s_call(apps.read_namespaced_deployment, name=name, namespace=_safe_ns(namespace)))
        selector = _deployment_label_selector(deployment)
        if not selector:
            return {"error": f"Deployment '{name}' has no selector labels; cannot determine rollout history."}

        replica_sets = cast(
            Any,
            _k8s_call(apps.list_namespaced_replica_set, namespace=_safe_ns(namespace), label_selector=selector),
        )

        history: list[dict[str, Any]] = []
        for rs in cast(Any, replica_sets.items):
            if not _is_owned_by_deployment(rs, name):
                continue

            revision_str = (rs.metadata.annotations or {}).get("deployment.kubernetes.io/revision", "0")
            try:
                revision = int(revision_str)
            except ValueError:
                revision = 0

            images = _collect_container_images(rs.spec.template.spec)
            history.append(
                {
                    "replicaset": rs.metadata.name,
                    "revision": revision,
                    "created_at": str(rs.metadata.creation_timestamp),
                    "desired_replicas": rs.spec.replicas or 0,
                    "ready_replicas": rs.status.ready_replicas or 0,
                    "available_replicas": rs.status.available_replicas or 0,
                    "images": images,
                }
            )

        history.sort(key=lambda item: (item["revision"], item["created_at"]), reverse=True)
        current_revision = (deployment.metadata.annotations or {}).get("deployment.kubernetes.io/revision")

        return {
            "namespace": deployment.metadata.namespace,
            "name": deployment.metadata.name,
            "current_revision": current_revision,
            "history": history[: max(1, limit)],
        }
    except ApiException as err:
        return {"error": f"Failed to get rollout history for deployment '{name}': {err.reason}"}


def rollback_deployment(namespace: str, name: str, to_revision: int | None = None) -> dict[str, Any]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    try:
        deployment = cast(Any, _k8s_call(apps.read_namespaced_deployment, name=name, namespace=_safe_ns(namespace)))
        selector = _deployment_label_selector(deployment)
        if not selector:
            return {"error": f"Deployment '{name}' has no selector labels; cannot rollback."}

        replica_sets = cast(
            Any,
            _k8s_call(apps.list_namespaced_replica_set, namespace=_safe_ns(namespace), label_selector=selector),
        )

        by_revision: dict[int, Any] = {}
        for rs in cast(Any, replica_sets.items):
            if not _is_owned_by_deployment(rs, name):
                continue

            revision_str = (rs.metadata.annotations or {}).get("deployment.kubernetes.io/revision", "0")
            try:
                revision = int(revision_str)
            except ValueError:
                continue
            if revision <= 0:
                continue

            existing = by_revision.get(revision)
            if existing is None or str(rs.metadata.creation_timestamp) > str(existing.metadata.creation_timestamp):
                by_revision[revision] = rs

        if not by_revision:
            return {"error": f"No rollout revisions found for deployment '{name}'."}

        available = sorted(by_revision.keys(), reverse=True)

        if to_revision is None:
            current_str = (deployment.metadata.annotations or {}).get("deployment.kubernetes.io/revision")
            current_revision = int(current_str) if current_str and current_str.isdigit() else available[0]
            candidates = [rev for rev in available if rev < current_revision]
            if not candidates:
                return {
                    "error": (
                        f"No previous revision available for deployment '{name}'. "
                        f"Current/known revisions: {available}"
                    )
                }
            target_revision = candidates[0]
        else:
            if to_revision not in by_revision:
                return {
                    "error": (
                        f"Requested revision {to_revision} not found for deployment '{name}'. "
                        f"Available revisions: {available}"
                    )
                }
            target_revision = to_revision

        target_rs = by_revision[target_revision]
        target_spec = target_rs.spec.template.spec

        containers_patch = [
            {"name": c.name, "image": c.image}
            for c in cast(Any, target_spec.containers or [])
        ]
        init_patch = [
            {"name": c.name, "image": c.image}
            for c in cast(Any, target_spec.init_containers or [])
        ]
        if not containers_patch:
            return {"error": f"Target revision {target_revision} has no containers to restore."}

        patch_body: dict[str, Any] = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "ai-ops-agent/rolledBackAt": datetime.now(UTC).isoformat(),
                            "ai-ops-agent/rollbackTargetRevision": str(target_revision),
                        }
                    },
                    "spec": {
                        "containers": containers_patch,
                    },
                }
            }
        }
        if init_patch:
            patch_body["spec"]["template"]["spec"]["initContainers"] = init_patch

        _k8s_call(
            apps.patch_namespaced_deployment,
            name=name,
            namespace=_safe_ns(namespace),
            body=patch_body,
        )

        return {
            "status": "rolled_back",
            "namespace": _safe_ns(namespace),
            "name": name,
            "target_revision": target_revision,
            "images": _collect_container_images(target_spec),
        }
    except ApiException as err:
        return {"error": f"Failed to rollback deployment '{name}': {err.reason}"}


def set_deployment_image(namespace: str, deployment: str, container: str, image: str) -> dict[str, str]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "ai-ops-agent/setImageAt": datetime.now(UTC).isoformat(),
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": container,
                            "image": image,
                        }
                    ]
                },
            }
        }
    }

    try:
        _k8s_call(
            apps.patch_namespaced_deployment,
            name=deployment,
            namespace=_safe_ns(namespace),
            body=patch_body,
        )
        return {
            "status": "image_updated",
            "namespace": _safe_ns(namespace),
            "deployment": deployment,
            "container": container,
            "image": image,
        }
    except ApiException as err:
        return {"error": f"Failed to set image for deployment '{deployment}': {err.reason}"}


def set_deployment_env(
    namespace: str,
    deployment: str,
    container: str,
    name: str,
    value: str,
) -> dict[str, str]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "ai-ops-agent/setEnvAt": datetime.now(UTC).isoformat(),
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": container,
                            "env": [
                                {
                                    "name": name,
                                    "value": value,
                                }
                            ],
                        }
                    ]
                },
            }
        }
    }

    try:
        _k8s_call(
            apps.patch_namespaced_deployment,
            name=deployment,
            namespace=_safe_ns(namespace),
            body=patch_body,
        )
        return {
            "status": "env_updated",
            "namespace": _safe_ns(namespace),
            "deployment": deployment,
            "container": container,
            "name": name,
            "value": value,
        }
    except ApiException as err:
        return {"error": f"Failed to set env for deployment '{deployment}': {err.reason}"}


def set_probe_config(
    namespace: str,
    deployment: str,
    container: str,
    probe_type: str,
    path: str,
    port: int,
    initial_delay_seconds: int = 10,
    period_seconds: int = 10,
    timeout_seconds: int = 1,
    success_threshold: int = 1,
    failure_threshold: int = 3,
    scheme: str = "HTTP",
) -> dict[str, Any]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    probe_key_map = {
        "liveness": "livenessProbe",
        "readiness": "readinessProbe",
        "startup": "startupProbe",
    }
    probe_key = probe_key_map.get(probe_type.strip().lower())
    if not probe_key:
        return {
            "error": "Invalid probe_type. Use one of: liveness, readiness, startup."
        }

    probe_body = {
        "httpGet": {
            "path": path,
            "port": int(port),
            "scheme": scheme,
        },
        "initialDelaySeconds": max(0, int(initial_delay_seconds)),
        "periodSeconds": max(1, int(period_seconds)),
        "timeoutSeconds": max(1, int(timeout_seconds)),
        "successThreshold": max(1, int(success_threshold)),
        "failureThreshold": max(1, int(failure_threshold)),
    }

    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "ai-ops-agent/setProbeAt": datetime.now(UTC).isoformat(),
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": container,
                            probe_key: probe_body,
                        }
                    ]
                },
            }
        }
    }

    try:
        _k8s_call(
            apps.patch_namespaced_deployment,
            name=deployment,
            namespace=_safe_ns(namespace),
            body=patch_body,
        )
        return {
            "status": "probe_updated",
            "namespace": _safe_ns(namespace),
            "deployment": deployment,
            "container": container,
            "probe_type": probe_type,
            "probe": probe_body,
        }
    except ApiException as err:
        return {"error": f"Failed to set probe for deployment '{deployment}': {err.reason}"}


def set_resource_limits(
    namespace: str,
    deployment: str,
    container: str,
    requests_cpu: str | None = None,
    requests_memory: str | None = None,
    limits_cpu: str | None = None,
    limits_memory: str | None = None,
) -> dict[str, Any]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()

    requests_obj: dict[str, str] = {}
    limits_obj: dict[str, str] = {}
    if requests_cpu:
        requests_obj["cpu"] = requests_cpu
    if requests_memory:
        requests_obj["memory"] = requests_memory
    if limits_cpu:
        limits_obj["cpu"] = limits_cpu
    if limits_memory:
        limits_obj["memory"] = limits_memory

    if not requests_obj and not limits_obj:
        return {
            "error": "Provide at least one resource field: requests_cpu, requests_memory, limits_cpu, limits_memory."
        }

    resources_patch: dict[str, Any] = {}
    if requests_obj:
        resources_patch["requests"] = requests_obj
    if limits_obj:
        resources_patch["limits"] = limits_obj

    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "ai-ops-agent/setResourcesAt": datetime.now(UTC).isoformat(),
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": container,
                            "resources": resources_patch,
                        }
                    ]
                },
            }
        }
    }

    try:
        _k8s_call(
            apps.patch_namespaced_deployment,
            name=deployment,
            namespace=_safe_ns(namespace),
            body=patch_body,
        )
        return {
            "status": "resources_updated",
            "namespace": _safe_ns(namespace),
            "deployment": deployment,
            "container": container,
            "resources": resources_patch,
        }
    except ApiException as err:
        return {"error": f"Failed to set resources for deployment '{deployment}': {err.reason}"}


def get_image_pull_secret_refs(namespace: str, deployment: str) -> dict[str, Any]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()
    v1 = k8s_client.CoreV1Api()

    try:
        dep = cast(Any, _k8s_call(apps.read_namespaced_deployment, name=deployment, namespace=_safe_ns(namespace)))
        pod_secret_refs = [s.name for s in cast(Any, dep.spec.template.spec.image_pull_secrets or [])]
        service_account_name = dep.spec.template.spec.service_account_name or "default"

        service_account = cast(
            Any,
            _k8s_call(v1.read_namespaced_service_account, name=service_account_name, namespace=_safe_ns(namespace)),
        )
        service_account_refs = [s.name for s in cast(Any, service_account.image_pull_secrets or [])]

        return {
            "namespace": _safe_ns(namespace),
            "deployment": deployment,
            "service_account": service_account_name,
            "pod_spec_image_pull_secrets": pod_secret_refs,
            "service_account_image_pull_secrets": service_account_refs,
            "effective_image_pull_secrets": sorted(set(pod_secret_refs + service_account_refs)),
        }
    except ApiException as err:
        return {"error": f"Failed to get imagePullSecrets for deployment '{deployment}': {err.reason}"}


def set_image_pull_secret(
    namespace: str,
    secret_name: str,
    deployment: str | None = None,
    service_account: str | None = None,
) -> dict[str, Any]:
    _load_kube_config()
    apps = k8s_client.AppsV1Api()
    v1 = k8s_client.CoreV1Api()

    if not deployment and not service_account:
        return {"error": "Provide at least one target: deployment or service_account."}

    updated_targets: list[str] = []

    try:
        if deployment:
            dep = cast(Any, _k8s_call(apps.read_namespaced_deployment, name=deployment, namespace=_safe_ns(namespace)))
            existing = [s.name for s in cast(Any, dep.spec.template.spec.image_pull_secrets or [])]
            if secret_name not in existing:
                existing.append(secret_name)

            dep_patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "imagePullSecrets": [{"name": n} for n in existing],
                        }
                    }
                }
            }
            _k8s_call(
                apps.patch_namespaced_deployment,
                name=deployment,
                namespace=_safe_ns(namespace),
                body=dep_patch,
            )
            updated_targets.append(f"deployment/{deployment}")

        if service_account:
            sa = cast(
                Any,
                _k8s_call(v1.read_namespaced_service_account, name=service_account, namespace=_safe_ns(namespace)),
            )
            existing = [s.name for s in cast(Any, sa.image_pull_secrets or [])]
            if secret_name not in existing:
                existing.append(secret_name)

            sa_patch = {
                "imagePullSecrets": [{"name": n} for n in existing],
            }
            _k8s_call(
                v1.patch_namespaced_service_account,
                name=service_account,
                namespace=_safe_ns(namespace),
                body=sa_patch,
            )
            updated_targets.append(f"serviceaccount/{service_account}")

        return {
            "status": "image_pull_secret_set",
            "namespace": _safe_ns(namespace),
            "secret_name": secret_name,
            "targets": updated_targets,
        }
    except ApiException as err:
        return {"error": f"Failed to set imagePullSecret '{secret_name}': {err.reason}"}


def create_registry_secret(
    namespace: str,
    name: str,
    server: str,
    username: str,
    password: str,
    email: str | None = None,
) -> dict[str, str]:
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    auth = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    docker_cfg = {
        "auths": {
            server: {
                "username": username,
                "password": password,
                "auth": auth,
            }
        }
    }
    if email:
        docker_cfg["auths"][server]["email"] = email

    dockerconfigjson = base64.b64encode(json.dumps(docker_cfg).encode("utf-8")).decode("utf-8")
    body = k8s_client.V1Secret(
        metadata=k8s_client.V1ObjectMeta(name=name, namespace=_safe_ns(namespace)),
        data={".dockerconfigjson": dockerconfigjson},
        type="kubernetes.io/dockerconfigjson",
    )

    try:
        _k8s_call(v1.create_namespaced_secret, namespace=_safe_ns(namespace), body=body)
        return {
            "status": "created",
            "namespace": _safe_ns(namespace),
            "name": name,
            "type": "kubernetes.io/dockerconfigjson",
        }
    except ApiException as err:
        if err.status == 409:
            return {
                "status": "already_exists",
                "namespace": _safe_ns(namespace),
                "name": name,
            }
        return {"error": f"Failed to create registry secret '{name}': {err.reason}"}


def _split_image_reference(image: str) -> tuple[str, str, str]:
    normalized = image.strip()
    if not normalized:
        raise ValueError("Image reference is empty")

    reference = "latest"
    if "@" in normalized:
        normalized, reference = normalized.rsplit("@", 1)
    else:
        last_slash = normalized.rfind("/")
        last_colon = normalized.rfind(":")
        if last_colon > last_slash:
            normalized, reference = normalized.rsplit(":", 1)

    first_segment, _, remainder = normalized.partition("/")
    if "." in first_segment or ":" in first_segment or first_segment == "localhost":
        registry = first_segment
        repository = remainder
    else:
        registry = "registry-1.docker.io"
        repository = normalized

    if not repository:
        raise ValueError(f"Invalid image reference: '{image}'")
    if registry == "registry-1.docker.io" and "/" not in repository:
        repository = f"library/{repository}"

    return registry, repository, reference


def validate_image_reference(image: str, timeout_seconds: int = 8) -> dict[str, Any]:
    try:
        registry, repository, reference = _split_image_reference(image)
    except ValueError as err:
        return {"image": image, "valid": False, "status": "invalid_reference", "message": str(err)}

    url = f"https://{registry}/v2/{repository}/manifests/{reference}"
    accept_header = (
        "application/vnd.oci.image.manifest.v1+json,"
        "application/vnd.docker.distribution.manifest.v2+json,"
        "application/vnd.docker.distribution.manifest.list.v2+json"
    )
    headers = {"Accept": accept_header}

    try:
        response = requests.get(url, headers=headers, timeout=max(1, timeout_seconds))
    except requests.RequestException as err:
        return {
            "image": image,
            "registry": registry,
            "repository": repository,
            "reference": reference,
            "valid": False,
            "status": "registry_unreachable",
            "message": str(err),
        }

    if response.status_code == 200:
        return {
            "image": image,
            "registry": registry,
            "repository": repository,
            "reference": reference,
            "valid": True,
            "status": "exists",
        }

    if response.status_code == 404:
        return {
            "image": image,
            "registry": registry,
            "repository": repository,
            "reference": reference,
            "valid": False,
            "status": "not_found",
        }

    if response.status_code == 401:
        auth_header = response.headers.get("Www-Authenticate") or response.headers.get("WWW-Authenticate")
        if auth_header and auth_header.lower().startswith("bearer "):
            auth_fields = auth_header[7:]
            auth_parts: dict[str, str] = {}
            for part in auth_fields.split(","):
                key, sep, value = part.strip().partition("=")
                if sep:
                    auth_parts[key] = value.strip('"')

            realm = auth_parts.get("realm")
            service = auth_parts.get("service")
            scope = auth_parts.get("scope")
            if realm and service and scope:
                try:
                    token_response = requests.get(
                        realm,
                        params={"service": service, "scope": scope},
                        timeout=max(1, timeout_seconds),
                    )
                    token_response.raise_for_status()
                    token = token_response.json().get("token")
                    if token:
                        retry_response = requests.get(
                            url,
                            headers={**headers, "Authorization": f"Bearer {token}"},
                            timeout=max(1, timeout_seconds),
                        )
                        if retry_response.status_code == 200:
                            return {
                                "image": image,
                                "registry": registry,
                                "repository": repository,
                                "reference": reference,
                                "valid": True,
                                "status": "exists",
                            }
                        if retry_response.status_code == 404:
                            return {
                                "image": image,
                                "registry": registry,
                                "repository": repository,
                                "reference": reference,
                                "valid": False,
                                "status": "not_found",
                            }
                except requests.RequestException:
                    pass

        return {
            "image": image,
            "registry": registry,
            "repository": repository,
            "reference": reference,
            "valid": False,
            "status": "authentication_required",
        }

    if response.status_code == 429:
        return {
            "image": image,
            "registry": registry,
            "repository": repository,
            "reference": reference,
            "valid": False,
            "status": "rate_limited",
        }

    return {
        "image": image,
        "registry": registry,
        "repository": repository,
        "reference": reference,
        "valid": False,
        "status": "registry_error",
        "http_status": response.status_code,
    }


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


def delete_secret(namespace: str, name: str) -> dict[str, str]:
    """Delete a Kubernetes secret from a namespace."""
    _load_kube_config()
    v1 = k8s_client.CoreV1Api()

    try:
        v1.delete_namespaced_secret(name=name, namespace=_safe_ns(namespace))
        return {
            "status": "deleted",
            "namespace": _safe_ns(namespace),
            "name": name,
        }
    except ApiException as err:
        if err.status == 404:
            return {
                "status": "not_found",
                "namespace": _safe_ns(namespace),
                "name": name,
            }
        return {"error": f"Failed to delete secret '{name}': {err.reason}"}
