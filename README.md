# AI DevOps Agent

An LLM-powered conversational agent that investigates and remediates Kubernetes incidents using the OpenAI Responses API and structured tool calling.

The agent follows a deliberate reasoning loop — **Observe → Hypothesis → Test → Evaluate → Decide** — and requires explicit user approval before making any cluster changes.

## How it works

```
User input
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Agent loop  (app/main.py)                          │
│                                                     │
│  1. Build message history (SessionMemory)           │
│  2. Call OpenAI Responses API with tool definitions │
│  3a. Model requests a tool call                     │
│      → Approval gate (mutating tools only)          │
│      → Execute tool  (app/tools/executor.py)        │
│      → Feed result back into messages               │
│      → Repeat                                       │
│  3b. Model returns a final answer → return to user  │
└─────────────────────────────────────────────────────┘
```

All outbound calls (OpenAI API, Kubernetes API, weather API) are wrapped with **tenacity** retry/backoff to handle transient failures gracefully.

## Project structure

```
ai-ops-agent/
├── app/
│   ├── main.py              # Agent loop, CLI entry point, retry logic
│   ├── memory.py            # Sliding-window session memory (8 turns)
│   ├── tools/
│   │   ├── registry.py      # Tool schemas (OpenAI JSON schema format)
│   │   ├── executor.py      # Tool dispatcher + approval gate
│   │   ├── k8s.py           # All Kubernetes tool implementations
│   │   └── weather.py       # Example external API tool
│   └── prompts/
│       └── system_prompt.txt
├── manifests/
│   └── labs/
│       └── scenarios/       # Runnable incident lab scenarios
│           ├── crashloop/
│           ├── bad-config-rollout/
│           ├── bad-upgrade-rollout/
│           ├── image-pull-backoff/
│           ├── missing-secret/
│           └── unschedulable/
├── tests/
├── .env
├── requirements.txt
└── Dockerfile
```

## Quickstart

**Prerequisites:** Python 3.11+, a running Kubernetes cluster (local or remote), `kubectl` configured.

```bash
# 1. Clone and create a virtual environment
git clone <repo-url> && cd ai-ops-agent
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your OpenAI API key
echo "OPENAI_API_KEY=sk-..." > .env
# Optional: override the model (default: gpt-4.1)
echo "OPENAI_MODEL=gpt-4.1" >> .env

# 4. Run the interactive CLI
python app/main.py
```

```
AI DevOps Agent ready. Type a question, or 'exit' to quit.
Commands: /clear (reset memory), /memory (show memory summary)

You> Why are pods in agent-lab-missing-secret crashing?
Agent> Step: Observe — fetching pods in agent-lab-missing-secret...
```

## Available tools

| Tool | Type | Description |
|---|---|---|
| `list_namespaces` | read | List all cluster namespaces |
| `get_pods` | read | Pod names, status, restart count |
| `get_failed_pods` | read | Pods in bad state across a namespace |
| `describe_pod` | read | Full pod conditions and container state |
| `get_pod_logs` | read | Container logs (current or previous crash) |
| `get_events` | read | Warning events, optionally filtered by object |
| `get_deployments_status` | read | Replica counts and rollout status |
| `get_nodes_status` | read | Node readiness and runtime info |
| `get_resource_usage` | read | CPU/memory from metrics-server |
| `get_hpa_status` | read | HorizontalPodAutoscaler current state |
| `list_secrets` | read | Secret names and keys in a namespace |
| `create_secret` | **mutating** | Create a Kubernetes secret *(requires approval)* |
| `delete_secret` | **mutating** | Delete a Kubernetes secret *(requires approval)* |
| `restart_deployment` | **mutating** | Rolling restart a deployment *(requires approval)* |

Mutating tools will never execute without explicit user confirmation in the conversation.

## Lab scenarios

Reproducible incident scenarios for testing and demos. Each has `start.sh` and `cleanup.sh`.

```bash
# Start a scenario
bash manifests/labs/scenarios/missing-secret/start.sh

# Then ask the agent about it
You> Investigate the pods in agent-lab-missing-secret

# Clean up afterwards
bash manifests/labs/scenarios/missing-secret/cleanup.sh
```

| Scenario | Namespace | Failure mode |
|---|---|---|
| `missing-secret` | `agent-lab-missing-secret` | Pod references a non-existent secret → `CreateContainerConfigError` |
| `crashloop` | `agent-lab-crashloop` | Container exits immediately → `CrashLoopBackOff` |
| `bad-config-rollout` | `agent-lab-bad-config` | Starts healthy, then bad env rollout causes app exit → `CrashLoopBackOff` |
| `image-pull-backoff` | `agent-lab-image-pull-backoff` | Invalid image reference → `ImagePullBackOff` |
| `bad-upgrade-rollout` | `agent-lab-bad-upgrade` | Starts healthy, then upgraded to invalid image → rollout breakage (`ImagePullBackOff`) |
| `unschedulable` | `agent-lab-unschedulable` | Impossible node selector → pod stuck in `Pending` |

You can also use the scenario runner:

```bash
bash manifests/labs/scenarios/run.sh start missing-secret
bash manifests/labs/scenarios/run.sh cleanup missing-secret
```

## Docker

```bash
docker build -t ai-ops-agent .
docker run --env-file .env ai-ops-agent
```

The image runs as a non-root user and uses a multi-stage build to keep the final image lean.
