# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Incident-response environment used for the hackathon submission."""

from __future__ import annotations

from uuid import uuid4

from openenv.core.env_server.interfaces import Environment

try:
    from ..models import (
        IncidentBridgeAction,
        IncidentBridgeObservation,
        IncidentBridgeState,
    )
    from .scenarios import AVAILABLE_SEVERITIES, TASK_ORDER, TASKS, evaluate_progress
except ImportError:
    from models import IncidentBridgeAction, IncidentBridgeObservation, IncidentBridgeState
    from server.scenarios import AVAILABLE_SEVERITIES, TASK_ORDER, TASKS, evaluate_progress


class IncidentBridgeEnvironment(Environment):
    """Production-style incident-response workflow with rubric scoring."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    MAX_STEPS: int = 12
    SCORE_EPSILON: float = 0.001

    def __init__(self):
        self._task_cursor = 0
        self._current_task = None
        self._state = IncidentBridgeState(
            episode_id=str(uuid4()),
            step_count=0,
            max_steps=self.MAX_STEPS,
        )
        self._opened_artifacts: list[str] = []
        self._current_severity: str | None = None
        self._current_diagnosis: str | None = None
        self._current_mitigation: str | None = None
        self._current_update: str | None = None
        self._active_artifact_id: str | None = None
        self._submitted = False
        self._progress_score = 0.0

    def _exposed_score(self, raw_score: float) -> float:
        """Keep externally visible scores strictly inside (0, 1)."""

        return min(max(raw_score, self.SCORE_EPSILON), 1.0 - self.SCORE_EPSILON)

    def reset(
        self,
        task_id: str | None = None,
        episode_id: str | None = None,
    ) -> IncidentBridgeObservation:
        """Reset the environment onto a task and return the initial observation."""

        if task_id is None:
            task_id = TASK_ORDER[self._task_cursor % len(TASK_ORDER)]
            self._task_cursor += 1
        if task_id not in TASKS:
            raise ValueError(f"Unknown task_id '{task_id}'. Available: {', '.join(TASK_ORDER)}")

        self._current_task = TASKS[task_id]
        self._state = IncidentBridgeState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=task_id,
            progress_score=self._exposed_score(0.0),
            opened_artifacts=[],
            current_severity=None,
            current_mitigation=None,
            submitted=False,
            max_steps=self.MAX_STEPS,
        )
        self._opened_artifacts = []
        self._current_severity = None
        self._current_diagnosis = None
        self._current_mitigation = None
        self._current_update = None
        self._active_artifact_id = None
        self._submitted = False
        self._progress_score = 0.0

        return self._build_observation(
            feedback=(
                "Incident loaded. Inspect the evidence, set severity, record a diagnosis, "
                "choose a mitigation, draft a stakeholder update, then submit the report."
            ),
            reward=0.0,
            done=False,
            last_action_error=None,
        )

    def step(self, action: IncidentBridgeAction) -> IncidentBridgeObservation:  # type: ignore[override]
        """Apply a workflow action and return the updated incident state."""

        if self._current_task is None:
            raise RuntimeError("reset() must be called before step().")
        if self._submitted:
            return self._build_observation(
                feedback="The incident report has already been submitted. Reset to start a new task.",
                reward=0.0,
                done=True,
                last_action_error="report already submitted",
            )

        self._state.step_count += 1
        previous_score = self._progress_score
        feedback = ""
        last_action_error: str | None = None
        requested_done = False

        if action.action_type == "open_artifact":
            artifact_id = (action.artifact_id or "").strip()
            if artifact_id not in self._current_task.artifacts:
                last_action_error = f"unknown artifact_id '{artifact_id}'"
            else:
                self._active_artifact_id = artifact_id
                if artifact_id not in self._opened_artifacts:
                    self._opened_artifacts.append(artifact_id)
                artifact = self._current_task.artifacts[artifact_id]
                feedback = f"Opened {artifact.title}. Use the evidence to guide your next decision."
        elif action.action_type == "set_severity":
            severity = (action.severity or "").strip().upper()
            if severity not in AVAILABLE_SEVERITIES:
                last_action_error = f"invalid severity '{severity}'"
            else:
                self._current_severity = severity
                feedback = f"Severity set to {severity}."
        elif action.action_type == "record_diagnosis":
            diagnosis = (action.diagnosis or "").strip()
            if not diagnosis:
                last_action_error = "diagnosis text is required"
            else:
                self._current_diagnosis = diagnosis
                feedback = "Diagnosis recorded."
        elif action.action_type == "choose_mitigation":
            mitigation_id = (action.mitigation_id or "").strip()
            if mitigation_id not in self._current_task.mitigation_options:
                last_action_error = f"unknown mitigation_id '{mitigation_id}'"
            else:
                self._current_mitigation = mitigation_id
                feedback = (
                    f"Mitigation selected: {self._current_task.mitigation_options[mitigation_id]}"
                )
        elif action.action_type == "draft_update":
            update = (action.update or "").strip()
            if not update:
                last_action_error = "stakeholder update text is required"
            else:
                self._current_update = update
                feedback = "Stakeholder update drafted."
        elif action.action_type == "submit_report":
            requested_done = True
        elif action.action_type == "noop":
            feedback = "No-op recorded. Continue the workflow."
        else:
            last_action_error = f"unsupported action_type '{action.action_type}'"

        score, breakdown = evaluate_progress(
            task=self._current_task,
            opened_artifacts=self._opened_artifacts,
            severity=self._current_severity,
            diagnosis=self._current_diagnosis,
            mitigation_id=self._current_mitigation,
            update=self._current_update,
        )
        self._progress_score = score
        self._sync_state()

        done = requested_done or self._state.step_count >= self.MAX_STEPS
        reward = max(score - previous_score, 0.0)

        if requested_done:
            self._submitted = True
            self._state.submitted = True
            if score >= 0.9:
                feedback = (
                    f"Report submitted. Score {score:.2f}. {self._current_task.success_note}"
                )
            elif score >= 0.7:
                feedback = (
                    f"Report submitted with score {score:.2f}. Solid recovery path, but a few "
                    "details are still weak."
                )
            else:
                feedback = (
                    f"Report submitted with score {score:.2f}. The report is incomplete; revisit "
                    "the evidence, mitigation, or communication next time."
                )
        elif done:
            self._submitted = True
            self._state.submitted = True
            feedback = (
                f"Step budget exhausted. Episode closed with score {score:.2f}. Submit faster on the next run."
            )

        if last_action_error and not feedback:
            feedback = "Action rejected. See last_action_error for the exact issue."

        return self._build_observation(
            feedback=feedback,
            reward=reward,
            done=done,
            last_action_error=last_action_error,
            score_breakdown=breakdown,
        )

    def _sync_state(self) -> None:
        self._state.progress_score = self._exposed_score(self._progress_score)
        self._state.opened_artifacts = list(self._opened_artifacts)
        self._state.current_severity = self._current_severity
        self._state.current_mitigation = self._current_mitigation

    def _build_observation(
        self,
        feedback: str,
        reward: float,
        done: bool,
        last_action_error: str | None,
        score_breakdown: dict[str, float] | None = None,
    ) -> IncidentBridgeObservation:
        if self._current_task is None:
            raise RuntimeError("No active task loaded.")

        active_artifact = self._current_task.artifacts.get(self._active_artifact_id or "")
        breakdown = score_breakdown or evaluate_progress(
            task=self._current_task,
            opened_artifacts=self._opened_artifacts,
            severity=self._current_severity,
            diagnosis=self._current_diagnosis,
            mitigation_id=self._current_mitigation,
            update=self._current_update,
        )[1]

        return IncidentBridgeObservation(
            task_id=self._current_task.task_id,
            title=self._current_task.title,
            difficulty=self._current_task.difficulty,
            goal=self._current_task.goal,
            task_summary=self._current_task.task_summary,
            available_artifacts=list(self._current_task.artifact_order),
            artifact_catalog={
                artifact_id: self._current_task.artifacts[artifact_id].title
                for artifact_id in self._current_task.artifact_order
            },
            active_artifact_id=active_artifact.artifact_id if active_artifact else None,
            active_artifact_title=active_artifact.title if active_artifact else None,
            active_artifact_content=active_artifact.content if active_artifact else "",
            opened_artifacts=list(self._opened_artifacts),
            available_severities=list(AVAILABLE_SEVERITIES),
            available_mitigations=dict(self._current_task.mitigation_options),
            current_severity=self._current_severity,
            current_diagnosis=self._current_diagnosis,
            current_mitigation=self._current_mitigation,
            current_update=self._current_update,
            steps_remaining=max(self.MAX_STEPS - self._state.step_count, 0),
            score=self._exposed_score(self._progress_score),
            score_breakdown=breakdown,
            feedback=feedback,
            last_action_error=last_action_error,
            done=done,
            reward=reward,
            metadata={
                "opened_artifact_count": len(self._opened_artifacts),
                "submitted": self._submitted,
                "step_count": self._state.step_count,
            },
        )

    @property
    def state(self) -> IncidentBridgeState:
        """Return the current state snapshot."""

        return self._state
