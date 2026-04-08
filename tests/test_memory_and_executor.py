from app.memory import SessionMemory
from app.tools import executor


def test_session_memory_keeps_recent_turns_only() -> None:
    memory = SessionMemory(max_turns=2)
    memory.add_turn("u1", "a1")
    memory.add_turn("u2", "a2")
    memory.add_turn("u3", "a3")

    messages = memory.build_messages("system", "latest")
    assert messages == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
        {"role": "user", "content": "latest"},
    ]


def test_session_memory_clear_and_preview() -> None:
    memory = SessionMemory(max_turns=2)
    assert memory.preview() == "(memory is empty)"
    assert memory.is_empty()

    memory.add_turn("hello", "world")
    assert "Stored turns: 1" in memory.preview()

    memory.clear()
    assert memory.is_empty()


def test_execute_tool_returns_tool_not_available_for_unknown() -> None:
    result = executor.execute_tool("not_a_real_tool", {})
    assert result["status"] == "tool_not_available"
    assert result["tool"] == "not_a_real_tool"


def test_execute_tool_requires_approval_for_mutating_tool() -> None:
    result = executor.execute_tool("create_secret", {"namespace": "ns", "name": "s", "data": {"k": "v"}})
    assert result["status"] == "permission_required"
    assert result["tool"] == "create_secret"


def test_execute_tool_strips_approved_flag_before_dispatch(monkeypatch) -> None:
    captured: dict = {}

    def fake_create_secret(**kwargs):
        captured.update(kwargs)
        return {"status": "created"}

    monkeypatch.setattr(executor, "create_secret", fake_create_secret)

    result = executor.execute_tool(
        "create_secret",
        {"namespace": "ns", "name": "s", "data": {"k": "v"}, "approved": True},
    )

    assert result == {"status": "created"}
    assert captured == {"namespace": "ns", "name": "s", "data": {"k": "v"}}


def test_execute_tool_weather_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(executor, "get_weather", lambda city: {"city": city, "temperature_c": 20.0, "windspeed_kmh": 10.0})
    result = executor.execute_tool("get_weather", {"city": "Tel Aviv"})
    assert result["city"] == "Tel Aviv"
