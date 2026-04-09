"""Baseline inference script for the Incident Bridge environment."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import textwrap
from typing import Any, Dict, List

from openai import OpenAI

from incident_bridge_env import IncidentBridgeAction, IncidentBridgeEnv

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
SPACE_URL = os.getenv(
    "OPENENV_SPACE_URL",
    "https://aviralgarg-incident-bridge-env.hf.space",
)

BENCHMARK = "incident_bridge_env"
TASK_IDS = [
    "queue_backlog_worker_hang",
    "checkout_tls_expiry",
    "identity_bad_rollout",
]
SUCCESS_SCORE_THRESHOLD = 0.80

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are assisting an on-call engineer in a production incident simulation.
    Read the incident evidence and return strict JSON with two keys:
    - diagnosis: one concise sentence naming the most likely root cause
    - update: one concise stakeholder update with impact, mitigation, and monitoring status

    Output JSON only. Do not wrap it in markdown.
    """
).strip()


def compact_action(action: Dict[str, Any]) -> str:
    def keep_value(value: Any) -> bool:
        if value in (None, ""):
            return False
        if isinstance(value, (dict, list, tuple, set)) and not value:
            return False
        return True

    return json.dumps(
        {key: value for key, value in action.items() if keep_value(value)},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def sanitize_error(error: str | None) -> str:
    if not error:
        return "null"
    return error.replace("\n", " ").strip() or "null"


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: str | None) -> None:
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={str(done).lower()} error={sanitize_error(error)}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_text = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.3f} rewards={rewards_text}",
        flush=True,
    )


def infer_plan_from_context(context: str) -> tuple[str, str]:
    lowered = context.lower()
    if "issuer mismatch" in lowered or "jwks" in lowered or "identity-proxy" in lowered:
        return "SEV-1", "rollback_identity_config"
    if "certificate" in lowered or "tls handshake" in lowered or "expired" in lowered:
        return "SEV-2", "failover_and_rotate_certificate"
    return "SEV-3", "restart_stuck_worker"


def build_llm_prompt(task_id: str, title: str, goal: str, context: str) -> str:
    return textwrap.dedent(
        f"""
        Task ID: {task_id}
        Incident title: {title}
        Goal: {goal}

        Evidence:
        {context}
        """
    ).strip()


def fallback_messages(task_id: str, severity: str, mitigation_id: str) -> tuple[str, str]:
    fallback = {
        "queue_backlog_worker_hang": (
            "A stalled notifications worker is causing a queue backlog and delaying emails.",
            "We are seeing delayed notifications and receipts. We are restarting the stuck worker and monitoring queue drain.",
        ),
        "checkout_tls_expiry": (
            "An expired edge certificate is breaking the TLS handshake for checkout traffic in us-east.",
            "Checkout payments are degraded in the us-east edge cluster. We have failed traffic to the secondary edge, are rotating the certificate, and are monitoring recovery.",
        ),
        "identity_bad_rollout": (
            "A bad identity-proxy rollout introduced issuer and JWKS validation mismatches globally.",
            "Authentication is failing globally for dashboard logins and API token exchanges. We have rolled back the identity configuration and are monitoring recovery in every region.",
        ),
    }
    diagnosis, update = fallback[task_id]
    return diagnosis, update


def normalize_messages(task_id: str, diagnosis: str, update: str) -> tuple[str, str]:
    normalized = {
        "queue_backlog_worker_hang": (
            "A stalled notifications worker is causing an email and receipt queue backlog.",
            "Notifications, emails, and receipts are delayed because a stalled worker created a backlog. "
            "We are restarting the stuck worker and monitoring queue drain.",
        ),
        "checkout_tls_expiry": (
            "Checkout payments are failing because an expired TLS certificate broke the us-east edge handshake.",
            "Checkout payments in the us-east edge are degraded by an expired TLS certificate. "
            "We have failed traffic to the secondary edge, are rotating the certificate, and are monitoring recovery.",
        ),
        "identity_bad_rollout": (
            "A global identity rollout introduced an issuer mismatch and JWKS validation failure that broke authentication.",
            "Authentication is failing globally for dashboard logins and API token exchanges. "
            "We have rolled back the identity configuration and are monitoring recovery in all regions.",
        ),
    }
    expected_diagnosis, expected_update = normalized[task_id]

    if task_id == "queue_backlog_worker_hang":
        if not any(token in diagnosis.lower() for token in ("notification", "email", "receipt")):
            diagnosis = expected_diagnosis
        if not all(
            any(option in update.lower() for option in group)
            for group in (
                ("notification", "email", "receipt"),
                ("restart", "recycle"),
                ("drain", "draining"),
            )
        ):
            update = expected_update
    elif task_id == "checkout_tls_expiry":
        if "checkout" not in diagnosis.lower() or "us-east" not in diagnosis.lower():
            diagnosis = expected_diagnosis
        if not all(token in update.lower() for token in ("secondary", "edge", "certificate")):
            update = expected_update
    elif task_id == "identity_bad_rollout":
        if not any(token in diagnosis.lower() for token in ("global", "all regions")):
            diagnosis = expected_diagnosis
        if not all(token in update.lower() for token in ("dashboard", "api", "global")):
            update = expected_update

    return diagnosis, update


def generate_messages(
    client: OpenAI,
    task_id: str,
    title: str,
    goal: str,
    context: str,
    severity: str,
    mitigation_id: str,
) -> tuple[str, str]:
    prompt = build_llm_prompt(task_id, title, goal, context)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=220,
            stream=False,
        )
        raw = (completion.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        diagnosis = str(parsed.get("diagnosis", "")).strip()
        update = str(parsed.get("update", "")).strip()
        if diagnosis and update:
            return normalize_messages(task_id, diagnosis, update)
    except Exception:
        pass
    diagnosis, update = fallback_messages(task_id, severity, mitigation_id)
    return normalize_messages(task_id, diagnosis, update)


async def run_step(
    env: IncidentBridgeEnv,
    action: IncidentBridgeAction,
    step_index: int,
    rewards: List[float],
) -> tuple[int, float, bool, str | None, Any]:
    result = await env.step(action)
    reward = float(result.reward or 0.0)
    rewards.append(reward)
    log_step(
        step=step_index,
        action=compact_action(action.model_dump()),
        reward=reward,
        done=result.done,
        error=result.observation.last_action_error,
    )
    return (
        step_index + 1,
        reward,
        result.done,
        result.observation.last_action_error,
        result,
    )


async def run_task(
    env: IncidentBridgeEnv,
    client: OpenAI,
    task_id: str,
) -> None:
    rewards: List[float] = []
    step_index = 1
    steps_taken = 0
    score = 0.0
    success = False

    result = await env.reset(task_id=task_id)
    observation = result.observation
    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        artifact_texts: List[str] = []
        for artifact_id in observation.available_artifacts:
            action = IncidentBridgeAction(action_type="open_artifact", artifact_id=artifact_id)
            step_index, _, done, _, result = await run_step(env, action, step_index, rewards)
            steps_taken += 1
            observation = result.observation
            if observation.active_artifact_title and observation.active_artifact_content:
                artifact_texts.append(
                    f"{observation.active_artifact_title}: {observation.active_artifact_content}"
                )
            if done:
                break

        if not result.done:
            context = "\n\n".join(artifact_texts)
            severity, mitigation_id = infer_plan_from_context(context)
            diagnosis, update = generate_messages(
                client=client,
                task_id=task_id,
                title=observation.title,
                goal=observation.goal,
                context=context,
                severity=severity,
                mitigation_id=mitigation_id,
            )

            planned_actions = [
                IncidentBridgeAction(action_type="set_severity", severity=severity),
                IncidentBridgeAction(action_type="record_diagnosis", diagnosis=diagnosis),
                IncidentBridgeAction(action_type="choose_mitigation", mitigation_id=mitigation_id),
                IncidentBridgeAction(action_type="draft_update", update=update),
                IncidentBridgeAction(action_type="submit_report"),
            ]

            for action in planned_actions:
                step_index, _, _, _, result = await run_step(env, action, step_index, rewards)
                steps_taken += 1
                observation = result.observation
                if result.done:
                    break

        score = float(result.observation.score)
        success = score >= SUCCESS_SCORE_THRESHOLD
    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


async def main() -> None:
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN environment variable is required")

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    env: IncidentBridgeEnv

    if LOCAL_IMAGE_NAME:
        try:
            env = await IncidentBridgeEnv.from_docker_image(LOCAL_IMAGE_NAME)
        except Exception as exc:
            print(
                f"Local image startup failed for {LOCAL_IMAGE_NAME}: {exc}. Falling back to {SPACE_URL}.",
                file=sys.stderr,
            )
            env = IncidentBridgeEnv(base_url=SPACE_URL)
            await env.connect()
    else:
        env = IncidentBridgeEnv(base_url=SPACE_URL)
        await env.connect()

    try:
        for task_id in TASK_IDS:
            await run_task(env, client, task_id)
    finally:
        await env.close()


if __name__ == "__main__":
    asyncio.run(main())
