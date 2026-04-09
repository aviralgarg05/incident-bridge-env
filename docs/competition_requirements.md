# Competition Notes

Verified on April 9, 2026 from the Scaler landing page, dashboard page, and the dashboard's published source bundles.

## Public Round 1 Prompt

The public dashboard exposes a single open-ended Round 1 task:

- Build a complete, real-world OpenEnv environment
- Use the standard `step() / reset() / state()` API
- Avoid game or toy environments

## Hard Requirements

- Implement typed OpenEnv models plus a valid `openenv.yaml`
- Provide at least 3 graded tasks with easy, medium, and hard difficulty
- Keep reward and scores normalized in the `0.0` to `1.0` range
- Include a reproducible `inference.py` in the project root
- Deploy a working Hugging Face Space
- Include a working Dockerfile
- Include a README with environment description, action/observation spaces, and setup steps

## Automated Validation Checks

These must pass before submission is accepted:

1. Hugging Face Space responds to `POST /reset` with HTTP `200`
2. OpenEnv spec compliance passes
3. Docker build succeeds
4. Baseline inference script runs without errors and produces scores
5. Tasks and graders exist and stay in the `0.0` to `1.0` score range

## Required `inference.py` Contract

- `inference.py` must live in the repository root
- Use the OpenAI client for all LLM calls
- Read these environment variables:
  - `API_BASE_URL`
  - `MODEL_NAME`
  - `HF_TOKEN`
  - `LOCAL_IMAGE_NAME` when using `from_docker_image()`
- Provide defaults only for `API_BASE_URL` and `MODEL_NAME`
- Emit validator-friendly stdout lines:
  - `[START] task=<task_name> env=<benchmark> model=<model_name>`
  - `[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>`
  - `[END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>`

## Infra Constraints

- Inference runtime must stay under 20 minutes
- The full environment plus inference path must fit inside:
  - `2 vCPU`
  - `8 GB RAM`

## Submission Details

- Only team leads can submit
- Submission window shown publicly: March 28, 2026 to April 12, 2026, 11:59 PM IST
- Support contact on the dashboard: `help_openenvhackathon@scaler.com`

## What Was Not Publicly Exposed

- The dashboard copy references “4-5 problem statements,” but the public page and public source bundle expose only the open-ended real-world OpenEnv prompt above
- No public authenticated API payload containing additional hidden tasks was available without account access
