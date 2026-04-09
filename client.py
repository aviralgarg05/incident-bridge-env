# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Client for the Incident Bridge incident-response environment."""

from __future__ import annotations

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

try:
    from .models import (
        IncidentBridgeAction,
        IncidentBridgeObservation,
        IncidentBridgeState,
    )
except ImportError:
    from models import IncidentBridgeAction, IncidentBridgeObservation, IncidentBridgeState


class IncidentBridgeEnv(
    EnvClient[IncidentBridgeAction, IncidentBridgeObservation, IncidentBridgeState]
):
    """Persistent client for the incident-response environment."""

    def _step_payload(self, action: IncidentBridgeAction) -> Dict:
        return {
            "action_type": action.action_type,
            "artifact_id": action.artifact_id,
            "severity": action.severity,
            "diagnosis": action.diagnosis,
            "mitigation_id": action.mitigation_id,
            "update": action.update,
        }

    def _parse_result(self, payload: Dict) -> StepResult[IncidentBridgeObservation]:
        obs_data = payload.get("observation", {})
        observation = IncidentBridgeObservation(
            task_id=obs_data.get("task_id", ""),
            title=obs_data.get("title", ""),
            difficulty=obs_data.get("difficulty", ""),
            goal=obs_data.get("goal", ""),
            task_summary=obs_data.get("task_summary", ""),
            available_artifacts=obs_data.get("available_artifacts", []),
            artifact_catalog=obs_data.get("artifact_catalog", {}),
            active_artifact_id=obs_data.get("active_artifact_id"),
            active_artifact_title=obs_data.get("active_artifact_title"),
            active_artifact_content=obs_data.get("active_artifact_content", ""),
            opened_artifacts=obs_data.get("opened_artifacts", []),
            available_severities=obs_data.get("available_severities", []),
            available_mitigations=obs_data.get("available_mitigations", {}),
            current_severity=obs_data.get("current_severity"),
            current_diagnosis=obs_data.get("current_diagnosis"),
            current_mitigation=obs_data.get("current_mitigation"),
            current_update=obs_data.get("current_update"),
            steps_remaining=obs_data.get("steps_remaining", 0),
            score=obs_data.get("score", 0.0),
            score_breakdown=obs_data.get("score_breakdown", {}),
            feedback=obs_data.get("feedback", ""),
            last_action_error=obs_data.get("last_action_error"),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> IncidentBridgeState:
        return IncidentBridgeState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id", ""),
            progress_score=payload.get("progress_score", 0.0),
            opened_artifacts=payload.get("opened_artifacts", []),
            current_severity=payload.get("current_severity"),
            current_mitigation=payload.get("current_mitigation"),
            submitted=payload.get("submitted", False),
            max_steps=payload.get("max_steps", 12),
        )
