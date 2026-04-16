"""In-process session memory for interactive chat turns."""

from __future__ import annotations

import json
import logging
import os
from threading import Lock

logger = logging.getLogger(__name__)


class SessionMemory:
    def __init__(self, max_turns: int = 8):
        self.max_turns = max_turns
        self._turns: list[dict[str, str]] = []

    def add_turn(self, user: str, assistant: str) -> None:
        self._turns.append({"user": user, "assistant": assistant})
        # Keep only the most recent turns to control token growth.
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns :]

    def clear(self) -> None:
        self._turns.clear()

    def is_empty(self) -> bool:
        return not self._turns

    def build_messages(self, system_prompt: str, latest_user_input: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        for turn in self._turns:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})

        messages.append({"role": "user", "content": latest_user_input})
        return messages

    def preview(self) -> str:
        if not self._turns:
            return "(memory is empty)"

        lines = [f"Stored turns: {len(self._turns)}"]
        for idx, turn in enumerate(self._turns, start=1):
            user_preview = turn["user"][:100]
            assistant_preview = turn["assistant"][:100]
            lines.append(f"{idx}. U: {user_preview}")
            lines.append(f"   A: {assistant_preview}")
        return "\n".join(lines)


class SessionStore:
    """Session store: Redis-backed when REDIS_URL is set, in-memory fallback otherwise.

    Redis keys: ``session:<session_id>`` — stored as a JSON array of turn dicts.
    TTL is applied on every save so active sessions never expire mid-use.
    """

    def __init__(self, max_turns: int = 8, ttl_seconds: int = 86400):
        self._max_turns = max_turns
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._local: dict[str, SessionMemory] = {}
        self._redis = None

        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis as _redis_lib
                client = _redis_lib.from_url(redis_url, decode_responses=True)
                client.ping()
                self._redis = client
                logger.info("SessionStore: connected to Redis at %s", redis_url)
            except Exception as exc:
                logger.warning("Redis unavailable (%s); falling back to in-memory sessions.", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_create(self, session_id: str) -> SessionMemory:
        if self._redis is not None:
            return self._load_from_redis(session_id)
        with self._lock:
            if session_id not in self._local:
                self._local[session_id] = SessionMemory(max_turns=self._max_turns)
            return self._local[session_id]

    def save(self, session_id: str, memory: SessionMemory) -> None:
        """Persist turns to Redis. No-op for in-memory store."""
        if self._redis is None:
            return
        try:
            self._redis.set(
                f"session:{session_id}",
                json.dumps(memory._turns),
                ex=self._ttl,
            )
        except Exception as exc:
            logger.warning("Failed to save session %r to Redis: %s", session_id, exc)

    def clear(self, session_id: str) -> bool:
        if self._redis is not None:
            try:
                return bool(self._redis.delete(f"session:{session_id}"))
            except Exception as exc:
                logger.warning("Failed to clear session %r from Redis: %s", session_id, exc)
                return False
        with self._lock:
            return self._local.pop(session_id, None) is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_from_redis(self, session_id: str) -> SessionMemory:
        memory = SessionMemory(max_turns=self._max_turns)
        try:
            raw = self._redis.get(f"session:{session_id}")
            if raw:
                turns = json.loads(raw)
                memory._turns = turns[-self._max_turns:]
        except Exception as exc:
            logger.warning("Failed to load session %r from Redis: %s", session_id, exc)
        return memory

