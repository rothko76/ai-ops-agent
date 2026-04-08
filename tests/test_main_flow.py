import os
from datetime import date, datetime, UTC

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.memory import SessionMemory
from app import main


class _Obj:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_json_safe_default_for_datetime_date_and_other() -> None:
    dt = datetime(2026, 4, 3, 12, 0, tzinfo=UTC)
    d = date(2026, 4, 3)

    assert main._json_safe_default(dt) == "2026-04-03T12:00:00+00:00"
    assert main._json_safe_default(d) == "2026-04-03"
    assert main._json_safe_default(123) == "123"


def test_ask_agent_returns_final_answer_and_stores_turn(monkeypatch) -> None:
    memory = SessionMemory(max_turns=8)

    final_response = _Obj(output=[_Obj(type="message")], output_text="Step: Decide - done")
    monkeypatch.setattr(main, "_create_response", lambda messages: final_response)

    answer = main.ask_agent("status?", memory)

    assert answer == "Step: Decide - done"
    preview = memory.preview()
    assert "Stored turns: 1" in preview
    assert "U: status?" in preview


def test_ask_agent_handles_tool_not_available(monkeypatch) -> None:
    memory = SessionMemory(max_turns=8)

    function_call = _Obj(
        type="function_call",
        name="unknown_tool",
        arguments="{}",
        call_id="c1",
    )
    tool_response = _Obj(output=[function_call], output_text="")

    monkeypatch.setattr(main, "_create_response", lambda messages: tool_response)
    monkeypatch.setattr(
        main,
        "execute_tool",
        lambda name, args: {"status": "tool_not_available", "message": "Tool missing"},
    )

    answer = main.ask_agent("use tool", memory)
    assert answer == "⚠️  Tool missing"


def test_ask_agent_serializes_tool_result_then_returns_final(monkeypatch) -> None:
    memory = SessionMemory(max_turns=8)

    call = _Obj(
        type="function_call",
        name="describe_pod",
        arguments='{"namespace":"ns","pod_name":"p1"}',
        call_id="c1",
    )
    first = _Obj(output=[call], output_text="")
    second = _Obj(output=[_Obj(type="message")], output_text="Step: Evaluate - complete")

    seen_messages = []

    def fake_create_response(messages):
        seen_messages.append(messages)
        return first if len(seen_messages) == 1 else second

    monkeypatch.setattr(main, "_create_response", fake_create_response)
    monkeypatch.setattr(
        main,
        "execute_tool",
        lambda name, args: {"finished_at": datetime(2026, 4, 3, 12, 0, tzinfo=UTC)},
    )

    answer = main.ask_agent("diagnose", memory)

    assert answer == "Step: Evaluate - complete"
    last_messages = seen_messages[-1]
    tool_output = last_messages[-1]
    assert tool_output["type"] == "function_call_output"
    assert "2026-04-03T12:00:00+00:00" in tool_output["output"]
