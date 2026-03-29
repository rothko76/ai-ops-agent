"""In-process session memory for interactive chat turns."""

from __future__ import annotations


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
