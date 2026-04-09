---
title: Incident Bridge Environment Server
emoji: 🚨
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
app_port: 7860
tags:
  - openenv
  - incident-response
  - sre
---

# Incident Bridge

Incident Bridge is a real-world OpenEnv benchmark for on-call incident response. Each episode asks an agent to stabilize a production issue by:

1. Inspecting evidence artifacts such as alerts, metrics, logs, and runbooks.
2. Setting the right severity.
3. Recording a diagnosis.
4. Choosing a mitigation.
5. Drafting a stakeholder update.
6. Submitting the final report.

The environment is designed for the Meta x PyTorch OpenEnv hackathon requirements:

- Real-world task, not a toy game
- At least three tasks with increasing difficulty
- Typed OpenEnv models and `step() / reset() / state()`
- Deterministic grader with normalized `0.0` to `1.0` score
- Lightweight enough for `2 vCPU / 8 GB`
- Reproducible `inference.py` baseline and local validation flow

## Task Catalog

| Task ID | Difficulty | Scenario | Expected Mitigation |
| --- | --- | --- | --- |
| `queue_backlog_worker_hang` | Easy | Delayed receipts and password-reset emails caused by a stuck worker | Restart the stuck worker |
| `checkout_tls_expiry` | Medium | Regional checkout failures caused by an expired edge certificate | Fail over traffic and rotate the certificate |
| `identity_bad_rollout` | Hard | Global login outage caused by a bad identity-proxy rollout | Roll back the identity config |

## Why This Should Score Well

- The workflow is clearly real-world and sequential.
- Each task has explicit evidence, one primary mitigation, and a rubric that grants partial credit.
- The observation format is readable enough for general LLM agents and strict enough for automated scoring.
- The baseline can be reproduced locally from Docker and emits validator-friendly stdout logs.

## Environment Interface

### Action

`IncidentBridgeAction` supports these workflow actions:

- `open_artifact`
- `set_severity`
- `record_diagnosis`
- `choose_mitigation`
- `draft_update`
- `submit_report`
- `noop`

### Observation

Every observation exposes:

- Task metadata: `task_id`, `title`, `difficulty`, `goal`, `task_summary`
- Navigation helpers: `available_artifacts`, `artifact_catalog`
- Current working memory: `current_severity`, `current_diagnosis`, `current_mitigation`, `current_update`
- Evidence context: `active_artifact_id`, `active_artifact_title`, `active_artifact_content`, `opened_artifacts`
- Score context: `score`, `score_breakdown`, `steps_remaining`
- Action feedback: `feedback`, `last_action_error`

### Reward

Reward is the positive delta in normalized rubric score after each action. Over a perfect episode, cumulative reward sums to `1.0`.

Rubric weights:

- Evidence gathered: `0.20`
- Severity choice: `0.15`
- Diagnosis quality: `0.20`
- Mitigation choice: `0.25`
- Stakeholder update quality: `0.20`

## Quick Start

### Install

```bash
uv sync --dev
```

### Run the server locally

```bash
uv run server --port 8000
```

### Build the Docker image

```bash
docker build -t incident-bridge-env:latest -f server/Dockerfile .
```

### Validate the environment

```bash
source .venv/bin/activate
openenv validate .
openenv validate --url http://localhost:8000
./scripts/validate-submission.sh http://localhost:8000 .
```

### Run the baseline agent

```bash
export HF_TOKEN=your_api_key
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export LOCAL_IMAGE_NAME=incident-bridge-env:latest

python inference.py
```

## Hugging Face Spaces Deployment

```bash
source .venv/bin/activate
openenv push --repo-id <your-username>/incident-bridge-env
```

The Space will expose:

- `/web` for interactive exploration
- `/docs` for API inspection
- `/health` for readiness checks
- `/ws` for low-latency client sessions

## Project Layout

```
incident_bridge_env/
├── __init__.py
├── client.py
├── docs/
│   └── competition_requirements.md
├── inference.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── scripts/
│   └── validate-submission.sh
├── server/
│   ├── app.py
│   ├── Dockerfile
│   ├── incident_bridge_env_environment.py
│   ├── requirements.txt
│   └── scenarios.py
└── tests/
    └── test_incident_bridge_env.py
```
