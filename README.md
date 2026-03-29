# AI DevOps Agent

An LLM-powered agent that monitors and diagnoses Kubernetes clusters using OpenAI function calling.

## Project structure

```
ai-devops-agent/
├── app/
│   ├── main.py              # Entry point — CLI or FastAPI server
│   ├── agent.py             # Orchestrator loop (core brain)
│   ├── llm_client.py        # OpenAI async wrapper
│   ├── memory.py            # Session memory (messages + state)
│   ├── config.py            # Settings loaded from .env
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py      # Tool definitions (OpenAI JSON schema)
│   │   ├── k8s.py           # get_pods()
│   │   ├── logs.py          # get_logs()
│   │   └── executor.py      # Dispatches tool_call → function
│   ├── prompts/
│   │   └── system_prompt.txt
│   └── utils/
│       └── logger.py
├── tests/
│   └── test_agent.py
├── .env
├── requirements.txt
├── Dockerfile
└── README.md
```

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env .env.local   # edit OPENAI_API_KEY and cluster settings

# 3. Run as CLI
python -m app.main --task "Are all pods in the default namespace healthy?"

# 4. Run as HTTP server
uvicorn app.main:app --reload
# POST /run  {"task": "List all pods in kube-system"}
```

## Running tests

```bash
pytest tests/
```

## Docker

```bash
docker build -t ai-devops-agent .
docker run --env-file .env -p 8000:8000 ai-devops-agent
```
