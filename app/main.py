from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
import json
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from kubernetes import client as k8s_client, config

try:
    config.load_incluster_config()   # running inside a pod
except config.ConfigException:
    config.load_kube_config()        # running locally

def get_events(namespace: str = "default", involved_object: str | None = None) -> list:
    config.load_kube_config()
    v1 = k8s_client.CoreV1Api()

    # treat empty string the same as None
    filter_object = involved_object if involved_object else None
    events = v1.list_namespaced_event(
        namespace=namespace,
        field_selector=f"involvedObject.name={filter_object}" if filter_object else ""
    )

    return [
        {
            "reason": e.reason,
            "message": e.message,
            "count": e.count,
            "object": e.involved_object.name,
            "type": e.type,           # "Normal" or "Warning"
            "last_seen": str(e.last_timestamp),
        }
        for e in events.items
        if e.type == "Warning"        # filter to only problems
    ]

def get_pods():
    return [
        {"name": "api-1", "status": "Running"},
        {"name": "worker-1", "status": "CrashLoopBackOff"}
    ]


import requests

def get_weather(city: str) -> dict:
    # Step 1: geocode city → lat/lon
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1}
    ).json()
    loc = geo["results"][0]

    # Step 2: fetch current temperature
    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current_weather": True
        }
    ).json()

    return {
        "city": city,
        "temperature_c": weather["current_weather"]["temperature"],
        "windspeed_kmh": weather["current_weather"]["windspeed"],
    }

client = OpenAI()

SYSTEM_PROMPT = "Say Hi to the user and classify the notification into one of the following categories: 'social', 'work', 'personal', 'other'. Only return the category without any explanation."

tools = [
    {
        "type": "function",
        "name": "get_pods",
        "description": "Get list of Kubernetes pods and their status",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
    "type": "function",
    "name": "get_weather",
    "description": "Get the current weather for a given city",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "The name of the city, e.g. 'Tel Aviv'"
            }
        },
        "required": ["city"]
    }
},
    {
        "type": "function",
        "name": "get_events",
        "description": "Get Kubernetes warning events in a namespace, optionally filtered to a specific pod or object",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "The Kubernetes namespace to query. Defaults to 'default'."
                },
                "involved_object": {
                    "type": "string",
                    "description": "Optional pod or object name to filter events for."
                }
            },
            "required": []
        }
    }
]

def ask_agent(question):
    messages = [
        {"role": "system", "content": "You are a DevOps assistant."},
        {"role": "user", "content": question}
    ]
    logger.debug(f"Starting agent with question: {question!r}")

    while True:
        logger.debug(f"Sending {len(messages)} messages to model")
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=messages,
            tools=tools
        )

        output = response.output[0]
        logger.debug(f"Response output type: {output.type}")

        # 🧠 CASE 1: model wants to call a tool
        if output.type == "function_call":
            tool_name = output.name
            args = json.loads(output.arguments)
            logger.debug(f"Tool call requested: {tool_name}({args})")

            if tool_name == "get_pods":
                result = get_pods()
            elif tool_name == "get_weather":
                result = get_weather(args["city"])
            elif tool_name == "get_events":
                result = get_events(**args)

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
            return response.output_text
        

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
 #   question = "Which pods are failing?"
    question = "What warnings are there in the ingress-nginx namespace?"
    logger.debug("Script started")
    answer = ask_agent(question)
    print("Answer:", answer)