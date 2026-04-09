from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
import os

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.main import ask_agent
from app.memory import SessionMemory


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


app = FastAPI(
    title="AI Ops Agent API",
    version="1.0.0",
    description="HTTP wrapper for the AI DevOps agent with session-based memory.",
)

_sessions = SessionStore(max_turns=8)


def _require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    expected_token = os.getenv("AGENT_API_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server auth is not configured (AGENT_API_TOKEN is missing).",
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    scheme, _, provided = authorization.partition(" ")
    if scheme.lower() != "bearer" or not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use: Bearer <token>",
        )

    if provided != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
        )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/agent/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _: None = Depends(_require_bearer_token)) -> ChatResponse:
    memory = _sessions.get_or_create(req.session_id)

    try:
        answer = ask_agent(req.message, memory)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {err}") from err

    return ChatResponse(
        session_id=req.session_id,
        answer=answer,
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.post("/v1/agent/session/clear", response_model=SessionClearResponse)
def clear_session(req: SessionClearRequest, _: None = Depends(_require_bearer_token)) -> SessionClearResponse:
    cleared = _sessions.clear(req.session_id)
    return SessionClearResponse(session_id=req.session_id, cleared=cleared)
