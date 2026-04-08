from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
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


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/agent/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
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
def clear_session(req: SessionClearRequest) -> SessionClearResponse:
    cleared = _sessions.clear(req.session_id)
    return SessionClearResponse(session_id=req.session_id, cleared=cleared)
