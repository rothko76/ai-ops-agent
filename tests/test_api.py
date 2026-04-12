from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app import api


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _chat_payload(session_id: str = "demo-1", message: str = "hello") -> dict[str, str]:
    return {"session_id": session_id, "message": message}


def test_healthz_no_auth_required(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    client = TestClient(api.app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_requires_auth_header(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    client = TestClient(api.app)

    response = client.post("/v1/agent/chat", json=_chat_payload())

    assert response.status_code == 401
    assert "Missing Authorization" in response.json()["detail"]


def test_chat_rejects_wrong_bearer_format(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    client = TestClient(api.app)

    response = client.post(
        "/v1/agent/chat",
        json=_chat_payload(),
        headers={"Authorization": "Token test-token"},
    )

    assert response.status_code == 401
    assert "Invalid Authorization header format" in response.json()["detail"]


def test_chat_rejects_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    client = TestClient(api.app)

    response = client.post(
        "/v1/agent/chat",
        json=_chat_payload(),
        headers=_auth_header("wrong-token"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API token."


def test_chat_rejects_when_server_token_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    client = TestClient(api.app)

    response = client.post("/v1/agent/chat", json=_chat_payload(), headers=_auth_header("any"))

    assert response.status_code == 500
    assert "AGENT_API_TOKEN" in response.json()["detail"]


def test_chat_success_with_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    monkeypatch.setattr(api, "ask_agent", lambda message, memory: "Step: Observe - ok")
    client = TestClient(api.app)

    response = client.post(
        "/v1/agent/chat",
        json=_chat_payload("session-a", "investigate"),
        headers=_auth_header("test-token"),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-a"
    assert data["answer"] == "Step: Observe - ok"
    assert "T" in data["timestamp"]


def test_chat_keeps_session_memory_across_calls(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    seen_previews: list[str] = []

    def fake_ask_agent(message, memory):
        seen_previews.append(memory.preview())
        memory.add_turn(message, f"echo:{message}")
        return f"echo:{message}"

    monkeypatch.setattr(api, "ask_agent", fake_ask_agent)
    client = TestClient(api.app)

    first = client.post(
        "/v1/agent/chat",
        json=_chat_payload("session-memory", "one"),
        headers=_auth_header("test-token"),
    )
    second = client.post(
        "/v1/agent/chat",
        json=_chat_payload("session-memory", "two"),
        headers=_auth_header("test-token"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert seen_previews[0] == "(memory is empty)"
    assert "Stored turns: 1" in seen_previews[1]


def test_clear_session_resets_memory(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    monkeypatch.setattr(api, "ask_agent", lambda message, memory: "ok")
    client = TestClient(api.app)

    create = client.post(
        "/v1/agent/chat",
        json=_chat_payload("session-clear", "hello"),
        headers=_auth_header("test-token"),
    )
    clear_first = client.post(
        "/v1/agent/session/clear",
        json={"session_id": "session-clear"},
        headers=_auth_header("test-token"),
    )
    clear_second = client.post(
        "/v1/agent/session/clear",
        json={"session_id": "session-clear"},
        headers=_auth_header("test-token"),
    )

    assert create.status_code == 200
    assert clear_first.status_code == 200
    assert clear_first.json() == {"session_id": "session-clear", "cleared": True}
    assert clear_second.status_code == 200
    assert clear_second.json() == {"session_id": "session-clear", "cleared": False}


def test_chat_rate_limit_exceeded(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    monkeypatch.setattr(api, "_request_limiter", api.SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0))
    monkeypatch.setattr(api, "ask_agent", lambda message, memory: "ok")
    client = TestClient(api.app)

    first = client.post(
        "/v1/agent/chat",
        json=_chat_payload("rate-limit", "first"),
        headers=_auth_header("test-token"),
    )
    second = client.post(
        "/v1/agent/chat",
        json=_chat_payload("rate-limit", "second"),
        headers=_auth_header("test-token"),
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Rate limit exceeded" in second.json()["detail"]


def test_chat_times_out(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    monkeypatch.setattr(api, "_request_limiter", api.SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0))
    monkeypatch.setattr(api, "_CHAT_TIMEOUT_SECONDS", 1.0)

    def slow_ask_agent(message, memory):
        time.sleep(1.2)
        return "late"

    monkeypatch.setattr(api, "ask_agent", slow_ask_agent)
    client = TestClient(api.app)

    response = client.post(
        "/v1/agent/chat",
        json=_chat_payload("timeout", "hello"),
        headers=_auth_header("test-token"),
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"]


def test_chat_rejects_when_concurrency_limit_reached(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    monkeypatch.setattr(api, "_request_limiter", api.SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0))
    monkeypatch.setattr(api, "ask_agent", lambda message, memory: "ok")

    # Simulate all slots consumed by replacing semaphore with one that cannot be acquired.
    sem = api.BoundedSemaphore(value=1)
    assert sem.acquire(blocking=False)
    monkeypatch.setattr(api, "_chat_semaphore", sem)

    client = TestClient(api.app)
    response = client.post(
        "/v1/agent/chat",
        json=_chat_payload("busy", "hello"),
        headers=_auth_header("test-token"),
    )

    assert response.status_code == 429
    assert "concurrent requests" in response.json()["detail"]


def test_healthz_adds_generated_request_id_header(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    client = TestClient(api.app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_chat_echoes_incoming_request_id_header(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_sessions", api.SessionStore(max_turns=8))
    monkeypatch.setattr(api, "_request_limiter", api.SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0))
    monkeypatch.setattr(api, "ask_agent", lambda message, memory: "ok")
    client = TestClient(api.app)

    req_id = "req-test-123"
    response = client.post(
        "/v1/agent/chat",
        json=_chat_payload("reqid", "hello"),
        headers={**_auth_header("test-token"), "X-Request-ID": req_id},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == req_id
