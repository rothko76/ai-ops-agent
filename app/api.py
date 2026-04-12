from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import UTC, datetime
import hashlib
import json
import logging
import os
from secrets import compare_digest
from threading import BoundedSemaphore, Lock
from time import monotonic
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.main import ask_agent
from app.memory import SessionMemory


logger = logging.getLogger("aiops.api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    timestamp: str


class SessionClearRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)


class SessionClearResponse(BaseModel):
    session_id: str
    cleared: bool


class SessionStore:
    """In-memory session store keyed by session_id for multi-turn API chats."""

    def __init__(self, max_turns: int = 8):
        self._max_turns = max_turns
        self._lock = Lock()
        self._sessions: dict[str, SessionMemory] = {}

    def get_or_create(self, session_id: str) -> SessionMemory:
        with self._lock:
            memory = self._sessions.get(session_id)
            if memory is None:
                memory = SessionMemory(max_turns=self._max_turns)
                self._sessions[session_id] = memory
            return memory

    def clear(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float):
        self._max_requests = max(1, int(max_requests))
        self._window_seconds = max(1.0, float(window_seconds))
        self._lock = Lock()
        self._buckets: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self._window_seconds

        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._max_requests:
                return False

            bucket.append(now)
            return True


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _structured_log(event: str, level: int = logging.INFO, **fields: object) -> None:
    payload = {
        "timestamp": _utc_timestamp(),
        "event": event,
        **fields,
    }
    logger.log(level, json.dumps(payload, default=str, sort_keys=True))


app = FastAPI(
    title="AI Ops Agent API",
    version="1.0.0",
    description="HTTP wrapper for the AI DevOps agent with session-based memory.",
)

_sessions = SessionStore(max_turns=8)
_RATE_LIMIT_MAX_REQUESTS = _env_int("AGENT_RATE_LIMIT_MAX_REQUESTS", 30)
_RATE_LIMIT_WINDOW_SECONDS = _env_float("AGENT_RATE_LIMIT_WINDOW_SECONDS", 60.0)
_MAX_CONCURRENT_REQUESTS = _env_int("AGENT_MAX_CONCURRENT_REQUESTS", 8)
_CHAT_TIMEOUT_SECONDS = _env_float("AGENT_CHAT_TIMEOUT_SECONDS", 90.0)

_request_limiter = SlidingWindowRateLimiter(
    max_requests=_RATE_LIMIT_MAX_REQUESTS,
    window_seconds=_RATE_LIMIT_WINDOW_SECONDS,
)
_chat_semaphore = BoundedSemaphore(value=max(1, _MAX_CONCURRENT_REQUESTS))
_chat_executor = ThreadPoolExecutor(max_workers=max(4, _MAX_CONCURRENT_REQUESTS))


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    request_start = monotonic()

    try:
        response = await call_next(request)
    except Exception:
        latency_ms = round((monotonic() - request_start) * 1000.0, 2)
        _structured_log(
            "http_request_failed",
            level=logging.ERROR,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            latency_ms=latency_ms,
        )
        raise

    response.headers["X-Request-ID"] = request_id
    latency_ms = round((monotonic() - request_start) * 1000.0, 2)
    _structured_log(
        "http_request_complete",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    return response


def _require_bearer_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> tuple[str, str]:
    request_id = getattr(request.state, "request_id", None)
    expected_token = os.getenv("AGENT_API_TOKEN")
    if not expected_token:
        _structured_log(
            "auth_server_not_configured",
            level=logging.ERROR,
            request_id=request_id,
            path=request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server auth is not configured (AGENT_API_TOKEN is missing).",
        )

    if not authorization:
        _structured_log(
            "auth_missing_header",
            level=logging.WARNING,
            request_id=request_id,
            path=request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    scheme, _, provided = authorization.partition(" ")
    if scheme.lower() != "bearer" or not provided:
        _structured_log(
            "auth_invalid_header_format",
            level=logging.WARNING,
            request_id=request_id,
            path=request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use: Bearer <token>",
        )

    if not compare_digest(provided, expected_token):
        _structured_log(
            "auth_invalid_token",
            level=logging.WARNING,
            request_id=request_id,
            path=request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
        )

    client_ip = request.client.host if request.client else "unknown"
    token_fingerprint = hashlib.sha256(provided.encode("utf-8")).hexdigest()[:16]
    _structured_log(
        "auth_success",
        request_id=request_id,
        path=request.url.path,
        client_ip=client_ip,
        token_fingerprint=token_fingerprint,
    )
    return token_fingerprint, client_ip


@app.get("/healthz")
def healthz() -> dict[str, str]:
    _structured_log("healthz_checked")
    return {"status": "ok"}


@app.post("/v1/agent/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    request: Request,
    auth_ctx: tuple[str, str] = Depends(_require_bearer_token),
) -> ChatResponse:
    token_fingerprint, client_ip = auth_ctx
    request_id = getattr(request.state, "request_id", None)
    chat_started = monotonic()
    rate_key = f"{token_fingerprint}:{client_ip}"
    if not _request_limiter.allow(rate_key):
        _structured_log(
            "chat_rate_limited",
            level=logging.WARNING,
            request_id=request_id,
            session_id=req.session_id,
            client_ip=client_ip,
            token_fingerprint=token_fingerprint,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry shortly.",
        )

    if not _chat_semaphore.acquire(blocking=False):
        _structured_log(
            "chat_concurrency_rejected",
            level=logging.WARNING,
            request_id=request_id,
            session_id=req.session_id,
            client_ip=client_ip,
            token_fingerprint=token_fingerprint,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Server is handling too many concurrent requests. Please retry shortly.",
        )

    memory = _sessions.get_or_create(req.session_id)

    try:
        future = _chat_executor.submit(ask_agent, req.message, memory)
        answer = future.result(timeout=max(1.0, _CHAT_TIMEOUT_SECONDS))
        _structured_log(
            "chat_completed",
            request_id=request_id,
            session_id=req.session_id,
            client_ip=client_ip,
            token_fingerprint=token_fingerprint,
            latency_ms=round((monotonic() - chat_started) * 1000.0, 2),
            answer_length=len(answer),
        )
    except FuturesTimeoutError as err:
        _structured_log(
            "chat_timed_out",
            level=logging.WARNING,
            request_id=request_id,
            session_id=req.session_id,
            client_ip=client_ip,
            token_fingerprint=token_fingerprint,
            timeout_seconds=_CHAT_TIMEOUT_SECONDS,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Agent request timed out before completion.",
        ) from err
    except Exception as err:
        _structured_log(
            "chat_failed",
            level=logging.ERROR,
            request_id=request_id,
            session_id=req.session_id,
            client_ip=client_ip,
            token_fingerprint=token_fingerprint,
            error=str(err),
        )
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {err}") from err
    finally:
        _chat_semaphore.release()

    return ChatResponse(
        session_id=req.session_id,
        answer=answer,
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.post("/v1/agent/session/clear", response_model=SessionClearResponse)
def clear_session(
    req: SessionClearRequest,
    request: Request,
    _: tuple[str, str] = Depends(_require_bearer_token),
) -> SessionClearResponse:
    cleared = _sessions.clear(req.session_id)
    _structured_log(
        "session_cleared",
        request_id=getattr(request.state, "request_id", None),
        session_id=req.session_id,
        cleared=cleared,
    )
    return SessionClearResponse(session_id=req.session_id, cleared=cleared)
