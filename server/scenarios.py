"""Scenario catalog and scoring helpers for Incident Bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Sequence


def _kg(*options: str) -> tuple[str, ...]:
    return tuple(option.lower() for option in options)


@dataclass(frozen=True)
class Artifact:
    """A readable incident artifact that the agent can inspect."""

    artifact_id: str
    title: str
    kind: str
    content: str


@dataclass(frozen=True)
class IncidentTaskRubric:
    """Weighted rubric used to score a submitted incident report."""

    required_artifacts: tuple[str, ...]
    severity_scores: Mapping[str, float]
    diagnosis_groups: tuple[tuple[str, ...], ...]
    mitigation_scores: Mapping[str, float]
    update_groups: tuple[tuple[str, ...], ...]
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "evidence": 0.20,
            "severity": 0.15,
            "diagnosis": 0.20,
            "mitigation": 0.25,
            "update": 0.20,
        }
    )


@dataclass(frozen=True)
class IncidentTask:
    """Single incident-response benchmark task."""

    task_id: str
    title: str
    difficulty: str
    goal: str
    task_summary: str
    artifact_order: tuple[str, ...]
    artifacts: Dict[str, Artifact]
    mitigation_options: Dict[str, str]
    rubric: IncidentTaskRubric
    success_note: str


AVAILABLE_SEVERITIES: tuple[str, ...] = ("SEV-1", "SEV-2", "SEV-3", "SEV-4")

MITIGATION_OPTIONS: Dict[str, str] = {
    "restart_stuck_worker": "Recycle the unhealthy worker and verify the backlog starts draining.",
    "scale_consumers": "Add more consumers without removing the stuck worker.",
    "failover_and_rotate_certificate": "Route traffic to the healthy secondary edge, then rotate the expired certificate.",
    "rollback_identity_config": "Rollback the latest identity-proxy configuration and refresh signing metadata.",
    "clear_cache_only": "Clear caches without reverting the broken change.",
    "wait_for_auto_recovery": "Take no direct action and wait for the issue to self-heal.",
}


TASKS: Dict[str, IncidentTask] = {
    "queue_backlog_worker_hang": IncidentTask(
        task_id="queue_backlog_worker_hang",
        title="Delayed Notification Queue",
        difficulty="easy",
        goal="Restore the notifications pipeline after delayed emails and receipts began piling up.",
        task_summary=(
            "A single notifications worker stopped making forward progress. Customers are not "
            "receiving password resets and receipts, but the rest of the product is healthy."
        ),
        artifact_order=(
            "alert_page",
            "queue_metrics",
            "worker_logs",
            "notifications_runbook",
            "customer_report",
        ),
        artifacts={
            "alert_page": Artifact(
                artifact_id="alert_page",
                title="Pager Alert",
                kind="alert",
                content=(
                    "PagerDuty fired for notifications-latency-high. Queue age is 14 minutes, "
                    "and password-reset plus receipt emails are delayed. The alert started 12 "
                    "minutes after worker consumer-3 stopped heartbeating."
                ),
            ),
            "queue_metrics": Artifact(
                artifact_id="queue_metrics",
                title="Queue Metrics",
                kind="metrics",
                content=(
                    "notifications_queue depth climbed from 1.2k to 17.4k. Enqueue is stable at "
                    "1.2k jobs/min, dequeue dropped to 180 jobs/min. API latency, database CPU, "
                    "and SMTP dependency latency are all normal."
                ),
            ),
            "worker_logs": Artifact(
                artifact_id="worker_logs",
                title="Worker Logs",
                kind="logs",
                content=(
                    "consumer-3 heartbeat timeout after 300s. Last successful ack was on job "
                    "batch/send_receipt. No crash loop is present, but the worker is stalled and "
                    "not draining the queue."
                ),
            ),
            "notifications_runbook": Artifact(
                artifact_id="notifications_runbook",
                title="Notifications Runbook",
                kind="runbook",
                content=(
                    "If queue backlog rises while dependencies are healthy and one worker is "
                    "stalled, recycle the stuck worker first. Only scale the pool after the "
                    "stalled consumer is removed and backlog drain is confirmed."
                ),
            ),
            "customer_report": Artifact(
                artifact_id="customer_report",
                title="Customer Support Note",
                kind="support_note",
                content=(
                    "Support agents report delayed receipts and password reset emails. No message "
                    "loss has been confirmed. Customers can still complete product actions."
                ),
            ),
        },
        mitigation_options=MITIGATION_OPTIONS,
        rubric=IncidentTaskRubric(
            required_artifacts=("alert_page", "worker_logs", "notifications_runbook"),
            severity_scores={"SEV-3": 1.0, "SEV-2": 0.4},
            diagnosis_groups=(
                _kg("notification", "email", "receipt"),
                _kg("worker", "consumer"),
                _kg("stalled", "stuck", "heartbeat timeout", "hung"),
                _kg("queue", "backlog"),
            ),
            mitigation_scores={"restart_stuck_worker": 1.0, "scale_consumers": 0.2},
            update_groups=(
                _kg("delayed", "backlog"),
                _kg("emails", "notifications", "receipts"),
                _kg("restart", "recycle"),
                _kg("monitor", "draining", "drain"),
            ),
        ),
        success_note="A stalled worker caused the backlog. Restarting that worker should drain the queue quickly.",
    ),
    "checkout_tls_expiry": IncidentTask(
        task_id="checkout_tls_expiry",
        title="Checkout Edge Certificate Failure",
        difficulty="medium",
        goal="Stabilize checkout failures impacting card payments in one production edge cluster.",
        task_summary=(
            "Customers in one primary edge cluster cannot complete card payments because checkout "
            "requests are failing during the TLS handshake."
        ),
        artifact_order=(
            "alert_page",
            "synthetic_checks",
            "edge_logs",
            "tls_runbook",
            "status_context",
        ),
        artifacts={
            "alert_page": Artifact(
                artifact_id="alert_page",
                title="Checkout Error Alert",
                kind="alert",
                content=(
                    "checkout-error-rate is 38% in us-east edge. Failed requests are isolated to "
                    "card payments hitting pay-edge-us-east. Other checkout steps remain healthy."
                ),
            ),
            "synthetic_checks": Artifact(
                artifact_id="synthetic_checks",
                title="Synthetic Probes",
                kind="synthetic",
                content=(
                    "TLS handshake to pay-edge-us-east fails consistently. The same request routed "
                    "to pay-edge-us-west succeeds. Network reachability and DNS are healthy."
                ),
            ),
            "edge_logs": Artifact(
                artifact_id="edge_logs",
                title="Edge Logs",
                kind="logs",
                content=(
                    "nginx upstream error: certificate verify failed. Remote certificate expired "
                    "at 2026-04-09T08:15:00Z on the us-east payment edge gateway."
                ),
            ),
            "tls_runbook": Artifact(
                artifact_id="tls_runbook",
                title="TLS Rotation Runbook",
                kind="runbook",
                content=(
                    "For a regional edge certificate expiry, shift traffic to the warm secondary "
                    "gateway, rotate the expired certificate, then reintroduce the primary once "
                    "handshakes are healthy."
                ),
            ),
            "status_context": Artifact(
                artifact_id="status_context",
                title="Status Page Context",
                kind="status",
                content=(
                    "Customer-facing update should mention checkout impact, the affected region, "
                    "the failover in progress, and that engineers are monitoring payment recovery."
                ),
            ),
        },
        mitigation_options=MITIGATION_OPTIONS,
        rubric=IncidentTaskRubric(
            required_artifacts=("alert_page", "edge_logs", "tls_runbook"),
            severity_scores={"SEV-2": 1.0, "SEV-1": 0.7, "SEV-3": 0.2},
            diagnosis_groups=(
                _kg("checkout", "payment"),
                _kg("tls", "certificate", "cert"),
                _kg("expired", "expiry"),
                _kg("edge", "gateway", "us-east"),
            ),
            mitigation_scores={
                "failover_and_rotate_certificate": 1.0,
                "clear_cache_only": 0.0,
                "wait_for_auto_recovery": 0.0,
            },
            update_groups=(
                _kg("checkout", "payments"),
                _kg("us-east", "edge"),
                _kg("failover", "secondary"),
                _kg("certificate", "tls"),
                _kg("monitor", "recovery", "restoring"),
            ),
        ),
        success_note="The failure is isolated to a regional edge certificate. Fail over traffic and rotate the expired cert.",
    ),
    "identity_bad_rollout": IncidentTask(
        task_id="identity_bad_rollout",
        title="Global Identity Rollout Regression",
        difficulty="hard",
        goal="Restore login access after a bad identity-proxy rollout broke token validation globally.",
        task_summary=(
            "A fresh identity-proxy configuration rollout caused authentication failures in all "
            "regions. Dashboard logins and API token exchanges are both impacted."
        ),
        artifact_order=(
            "alert_page",
            "deploy_timeline",
            "auth_proxy_logs",
            "regional_metrics",
            "identity_runbook",
            "exec_brief",
        ),
        artifacts={
            "alert_page": Artifact(
                artifact_id="alert_page",
                title="Authentication Failure Alert",
                kind="alert",
                content=(
                    "login-success-rate dropped to 12% globally 11 minutes ago. Dashboard login "
                    "and API token exchange errors are both elevated. Traffic volume is normal."
                ),
            ),
            "deploy_timeline": Artifact(
                artifact_id="deploy_timeline",
                title="Deployment Timeline",
                kind="deploy",
                content=(
                    "identity-proxy config rollout completed 10 minutes ago in all regions. No "
                    "database schema changes or cache invalidations happened during the window."
                ),
            ),
            "auth_proxy_logs": Artifact(
                artifact_id="auth_proxy_logs",
                title="Auth Proxy Logs",
                kind="logs",
                content=(
                    "issuer mismatch for incoming tokens; JWKS signature validation failed after "
                    "config reload. Tokens minted before the rollout no longer pass validation."
                ),
            ),
            "regional_metrics": Artifact(
                artifact_id="regional_metrics",
                title="Regional Metrics",
                kind="metrics",
                content=(
                    "All regions show identical authentication errors. Database, cache, and "
                    "network layers are healthy. The blast radius is global and started at the "
                    "same minute as the identity rollout."
                ),
            ),
            "identity_runbook": Artifact(
                artifact_id="identity_runbook",
                title="Identity Rollback Runbook",
                kind="runbook",
                content=(
                    "If issuer mismatch or JWKS validation fails immediately after a config "
                    "rollout, rollback the identity-proxy config, refresh signing metadata, and "
                    "watch login success recover before reopening traffic changes."
                ),
            ),
            "exec_brief": Artifact(
                artifact_id="exec_brief",
                title="Executive Brief",
                kind="brief",
                content=(
                    "Enterprise customers cannot log in to the dashboard and API token exchanges "
                    "are failing. This is the highest-priority issue on the board."
                ),
            ),
        },
        mitigation_options=MITIGATION_OPTIONS,
        rubric=IncidentTaskRubric(
            required_artifacts=("alert_page", "deploy_timeline", "auth_proxy_logs", "identity_runbook"),
            severity_scores={"SEV-1": 1.0, "SEV-2": 0.3},
            diagnosis_groups=(
                _kg("login", "authentication", "identity"),
                _kg("rollout", "deploy", "configuration", "config"),
                _kg("issuer", "jwks", "signature", "token validation"),
                _kg("global", "all regions"),
            ),
            mitigation_scores={
                "rollback_identity_config": 1.0,
                "clear_cache_only": 0.2,
                "wait_for_auto_recovery": 0.0,
            },
            update_groups=(
                _kg("login", "authentication"),
                _kg("global", "all regions"),
                _kg("rollback", "rolled back", "reverted"),
                _kg("monitor", "recovery", "restoring"),
                _kg("dashboard", "api token", "api"),
            ),
        ),
        success_note="The rollout broke global token validation. Roll back the config before touching healthy dependencies.",
    ),
}

TASK_ORDER: tuple[str, ...] = (
    "queue_backlog_worker_hang",
    "checkout_tls_expiry",
    "identity_bad_rollout",
)


def _contains_any(text: str, options: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(option in lowered for option in options)


def _keyword_group_score(text: str, groups: Sequence[tuple[str, ...]]) -> float:
    if not groups:
        return 1.0
    if not text.strip():
        return 0.0
    matches = sum(1 for group in groups if _contains_any(text, group))
    return matches / len(groups)


def evaluate_progress(
    task: IncidentTask,
    opened_artifacts: Sequence[str],
    severity: str | None,
    diagnosis: str | None,
    mitigation_id: str | None,
    update: str | None,
) -> tuple[float, Dict[str, float]]:
    """Return the normalized score and weighted breakdown for the current report."""

    rubric = task.rubric
    opened = set(opened_artifacts)
    required = set(rubric.required_artifacts)

    evidence = len(opened & required) / len(required)
    severity_score = rubric.severity_scores.get(severity or "", 0.0)
    diagnosis_score = _keyword_group_score(diagnosis or "", rubric.diagnosis_groups)
    mitigation_score = rubric.mitigation_scores.get(mitigation_id or "", 0.0)
    update_score = _keyword_group_score(update or "", rubric.update_groups)

    weighted = {
        "evidence": round(evidence * rubric.weights["evidence"], 4),
        "severity": round(severity_score * rubric.weights["severity"], 4),
        "diagnosis": round(diagnosis_score * rubric.weights["diagnosis"], 4),
        "mitigation": round(mitigation_score * rubric.weights["mitigation"], 4),
        "update": round(update_score * rubric.weights["update"], 4),
    }
    total = round(sum(weighted.values()), 4)
    return total, weighted
