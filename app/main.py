from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError, InternalServerError, RateLimitError
from typing import Any, cast
import json
import logging
import os
from datetime import date, datetime
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

try:
    from app.memory import SessionMemory
    from app.tools.executor import execute_tool
    from app.tools.registry import TOOLS
except ModuleNotFoundError:
    # Support running as `python app/main.py` where `app` package isn't on sys.path.
    from memory import SessionMemory
    from tools.executor import execute_tool
    from tools.registry import TOOLS

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

client = OpenAI()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")


def _json_safe_default(value: Any) -> str:
    """Convert common non-JSON-native objects into stable string values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _is_retryable_openai_error(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
        return True
    if isinstance(exc, APIStatusError):
        return getattr(exc, "status_code", None) in {408, 409, 429, 500, 502, 503, 504}
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=8),
    retry=retry_if_exception(_is_retryable_openai_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _create_response(messages: list[Any]) -> Any:
    return client.responses.create(
        model=OPENAI_MODEL,
        input=cast(Any, messages),
        tools=cast(list, TOOLS),
    )

SYSTEM_PROMPT = (
    "You are a DevOps assistant. Use tools when needed, be concise, and reuse chat context "
    "from previous turns when the user references earlier questions.\n\n"
    "When debugging incidents, always follow this loop:\n"
    "1) Observe: Gather evidence with tools. Do not propose fixes yet.\n"
    "2) Hypothesis: State the most likely root cause from observed evidence.\n"
    "3) Test: Use tools to confirm or refute the hypothesis.\n"
    "4) Evaluate: Say whether hypothesis is supported or rejected.\n"
    "5) Decide: Either continue investigating or propose a remediation.\n\n"
    "Response format requirement:\n"
    "Start each diagnostic reply with 'Step: <Observe|Hypothesis|Test|Evaluate|Decide>' so "
    "the user can track your reasoning.\n\n"
    "MUTATING TOOLS (create_secret, restart_deployment) REQUIRE APPROVAL:\n"
    "1) If a tool call returns {\"status\": \"permission_required\"}, explain exactly what "
    "you plan to change and ask for confirmation.\n"
    "2) If the user confirms (yes/approved/go ahead), immediately retry the same tool call with "
    "approved=true and do not ask for confirmation again.\n"
    "3) Do not execute mutating actions before at least one Observe->Hypothesis->Test cycle.\n"
    "4) After any remediation, always verify outcome with follow-up tool calls before concluding.\n"
    "5) For missing secret incidents, after create_secret succeeds, also restart_deployment (with "
    "approval) to force pods to pick up the new secret quickly."
)

def ask_agent(question: str, memory: SessionMemory) -> str:
    messages: list[Any] = memory.build_messages(SYSTEM_PROMPT, question)
    logger.debug(f"Starting agent with question: {question!r}")

    while True:
        logger.debug(f"Sending {len(messages)} messages to model")
        try:
            response = _create_response(messages)
        except (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError, APIStatusError):
            logger.exception("OpenAI request failed after retries")
            return "I could not reach the model service after multiple retries. Please try again."

        output = response.output[0]
        logger.debug(f"Response output type: {output.type}")

        # 🧠 CASE 1: model wants to call a tool
        if output.type == "function_call":
            tool_name = output.name
            args = json.loads(output.arguments)
            logger.debug(f"Tool call requested: {tool_name}({args})")

            result = execute_tool(tool_name, args)

            logger.debug(f"Tool result: {result}")

            # Check if tool is unavailable (missing tool awareness)
            if isinstance(result, dict) and result.get("status") == "tool_not_available":
                logger.warning(f"Tool not available: {tool_name}")
                msg = result.get("message", "Unknown tool")
                return f"⚠️  {msg}"

            # send tool result back
            messages.append(output)  # the tool call
            messages.append({
                "type": "function_call_output",
                "call_id": output.call_id,
                "output": json.dumps(result, default=_json_safe_default)
            })

        # 🧠 CASE 2: final answer
        else:
            logger.debug("Final answer received")
            answer = response.output_text
            memory.add_turn(question, answer)
            return answer
        

# def classify(notification):
#     response = client.responses.create(
#         model="gpt-4.1-mini",
#         temperature=0,
#         messages=[
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user", "content": f"Notification:\n{notification}"}
#         ],
#     )

#     usage = response.usage
#     print("TOKENS:", usage)

#     return response.choices[0].message.content

# if __name__ == "__main__":
#     notification = "You have a meeting at 3 PM with your team."
#     category = classify(notification)
#     print("Category:", category)

if __name__ == "__main__":
    memory = SessionMemory(max_turns=8)
    logger.debug("Interactive session started")
    print("AI DevOps Agent ready. Type a question, or 'exit' to quit.")
    print("Commands: /clear (reset memory), /memory (show memory summary)")

    while True:
        try:
            question = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            print("Exiting.")
            break
        if question.lower() == "/clear":
            memory.clear()
            print("Memory cleared.")
            continue
        if question.lower() == "/memory":
            print(memory.preview())
            continue

        answer = ask_agent(question, memory)
        print(f"Agent> {answer}")