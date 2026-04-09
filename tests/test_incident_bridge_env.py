"""Environment-level tests for Incident Bridge."""

from __future__ import annotations

from math import isclose

from incident_bridge_env.models import IncidentBridgeAction
from incident_bridge_env.server.incident_bridge_env_environment import IncidentBridgeEnvironment


TASK_EXPECTATIONS = {
    "queue_backlog_worker_hang": {
        "severity": "SEV-3",
        "diagnosis": "The notifications worker is stalled and causing an email queue backlog.",
        "mitigation_id": "restart_stuck_worker",
        "update": (
            "Notifications and receipts are delayed because a stuck worker created a backlog. "
            "We are restarting the worker and monitoring the queue drain."
        ),
    },
    "checkout_tls_expiry": {
        "severity": "SEV-2",
        "diagnosis": "Checkout payments are failing because an expired edge certificate broke the TLS handshake in us-east.",
        "mitigation_id": "failover_and_rotate_certificate",
        "update": (
            "Checkout payments in the us-east edge are degraded by a certificate issue. "
            "We have failed traffic to the secondary edge, are rotating the TLS certificate, and are monitoring recovery."
        ),
    },
    "identity_bad_rollout": {
        "severity": "SEV-1",
        "diagnosis": "A global identity configuration rollout introduced an issuer mismatch that broke JWT validation.",
        "mitigation_id": "rollback_identity_config",
        "update": (
            "Authentication is failing globally for dashboard logins and API token exchanges. "
            "We have rolled back the rollout and are monitoring recovery in all regions."
        ),
    },
}


def _run_perfect_episode(task_id: str):
    env = IncidentBridgeEnvironment()
    obs = env.reset(task_id=task_id)

    for artifact_id in obs.available_artifacts:
        obs = env.step(
            IncidentBridgeAction(action_type="open_artifact", artifact_id=artifact_id)
        )

    expected = TASK_EXPECTATIONS[task_id]
    obs = env.step(
        IncidentBridgeAction(action_type="set_severity", severity=expected["severity"])
    )
    obs = env.step(
        IncidentBridgeAction(
            action_type="record_diagnosis", diagnosis=expected["diagnosis"]
        )
    )
    obs = env.step(
        IncidentBridgeAction(
            action_type="choose_mitigation",
            mitigation_id=expected["mitigation_id"],
        )
    )
    obs = env.step(
        IncidentBridgeAction(action_type="draft_update", update=expected["update"])
    )
    obs = env.step(IncidentBridgeAction(action_type="submit_report"))
    return obs


def test_perfect_submissions_score_full_credit():
    for task_id in TASK_EXPECTATIONS:
        obs = _run_perfect_episode(task_id)
        assert obs.done is True
        assert isclose(obs.score, 1.0, rel_tol=0, abs_tol=1e-6)


def test_invalid_action_sets_last_action_error():
    env = IncidentBridgeEnvironment()
    obs = env.reset(task_id="queue_backlog_worker_hang")
    obs = env.step(IncidentBridgeAction(action_type="set_severity", severity="SEV-9"))

    assert obs.done is False
    assert obs.last_action_error == "invalid severity 'SEV-9'"
    assert obs.reward == 0.0


def test_incomplete_submission_gets_partial_credit():
    env = IncidentBridgeEnvironment()
    obs = env.reset(task_id="identity_bad_rollout")
    obs = env.step(
        IncidentBridgeAction(action_type="open_artifact", artifact_id="alert_page")
    )
    obs = env.step(IncidentBridgeAction(action_type="submit_report"))

    assert obs.done is True
    assert 0.0 < obs.score < 1.0
