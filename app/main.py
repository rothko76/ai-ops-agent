from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from typing import Any, cast
import json
import logging

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

SYSTEM_PROMPT = (
    "You are a DevOps assistant. Use tools when needed, be concise, and reuse chat context "
    "from previous turns when the user references earlier questions."
)

def ask_agent(question: str, memory: SessionMemory) -> str:
    messages: list[Any] = memory.build_messages(SYSTEM_PROMPT, question)
    logger.debug(f"Starting agent with question: {question!r}")

    while True:
        logger.debug(f"Sending {len(messages)} messages to model")
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=cast(Any, messages),
            tools=cast(list, TOOLS)
        )

        output = response.output[0]
        logger.debug(f"Response output type: {output.type}")

        # 🧠 CASE 1: model wants to call a tool
        if output.type == "function_call":
            tool_name = output.name
            args = json.loads(output.arguments)
            logger.debug(f"Tool call requested: {tool_name}({args})")

            result = execute_tool(tool_name, args)

            logger.debug(f"Tool result: {result}")

            # send tool result back
            messages.append(output)  # the tool call
            messages.append({
                "type": "function_call_output",
                "call_id": output.call_id,
                "output": json.dumps(result)
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