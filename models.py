# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Typed models for the Incident Bridge environment."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field


class IncidentBridgeAction(Action):
    """Structured action for the incident-response workflow."""

    action_type: Literal[
        "open_artifact",
        "set_severity",
        "record_diagnosis",
        "choose_mitigation",
        "draft_update",
        "submit_report",
        "noop",
    ] = Field(
        ...,
        description="Workflow action to take in the incident-response environment.",
    )
    artifact_id: Optional[str] = Field(
        default=None,
        description="Artifact identifier to open when action_type is open_artifact.",
    )
    severity: Optional[str] = Field(
        default=None,
        description="Severity level to set when action_type is set_severity.",
    )
    diagnosis: Optional[str] = Field(
        default=None,
        description="Diagnosis text to record when action_type is record_diagnosis.",
    )
    mitigation_id: Optional[str] = Field(
        default=None,
        description="Mitigation option identifier when action_type is choose_mitigation.",
    )
    update: Optional[str] = Field(
        default=None,
        description="Stakeholder update text when action_type is draft_update.",
    )


class IncidentBridgeObservation(Observation):
    """Observation emitted after each workflow action."""

    task_id: str = Field(default="", description="Canonical task identifier.")
    title: str = Field(default="", description="Human-friendly incident title.")
    difficulty: str = Field(default="", description="Task difficulty label.")
    goal: str = Field(default="", description="Primary goal for the current episode.")
    task_summary: str = Field(
        default="",
        description="Short summary of the simulated incident and expected workflow.",
    )
    available_artifacts: List[str] = Field(
        default_factory=list,
        description="Artifact ids that can be opened for additional evidence.",
    )
    artifact_catalog: Dict[str, str] = Field(
        default_factory=dict,
        description="Artifact id to title mapping for quick navigation.",
    )
    active_artifact_id: Optional[str] = Field(
        default=None,
        description="Artifact currently displayed in the observation panel.",
    )
    active_artifact_title: Optional[str] = Field(
        default=None,
        description="Title for the currently displayed artifact.",
    )
    active_artifact_content: str = Field(
        default="",
        description="Full content for the currently displayed artifact.",
    )
    opened_artifacts: List[str] = Field(
        default_factory=list,
        description="Artifacts opened so far in this episode.",
    )
    available_severities: List[str] = Field(
        default_factory=list,
        description="Valid severity levels for this incident.",
    )
    available_mitigations: Dict[str, str] = Field(
        default_factory=dict,
        description="Mitigation options exposed to the agent.",
    )
    current_severity: Optional[str] = Field(
        default=None,
        description="Severity selected by the agent so far.",
    )
    current_diagnosis: Optional[str] = Field(
        default=None,
        description="Diagnosis recorded by the agent so far.",
    )
    current_mitigation: Optional[str] = Field(
        default=None,
        description="Mitigation option selected by the agent so far.",
    )
    current_update: Optional[str] = Field(
        default=None,
        description="Current stakeholder update drafted by the agent.",
    )
    steps_remaining: int = Field(
        default=0,
        description="Number of actions left before the episode auto-closes.",
    )
    score: float = Field(
        default=0.0,
        description="Current normalized progress score in the 0.0 to 1.0 range.",
    )
    score_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Weighted score breakdown for evidence, severity, diagnosis, mitigation, and update quality.",
    )
    feedback: str = Field(
        default="",
        description="Human-readable feedback about the last action or submission result.",
    )
    last_action_error: Optional[str] = Field(
        default=None,
        description="Last action validation error, or null when the action succeeded.",
    )


class IncidentBridgeState(State):
    """Environment state tracked across the episode."""

    task_id: str = Field(default="", description="Current task identifier.")
    progress_score: float = Field(
        default=0.0,
        description="Current normalized progress score in the 0.0 to 1.0 range.",
    )
    opened_artifacts: List[str] = Field(
        default_factory=list,
        description="Artifacts opened so far in the current episode.",
    )
    current_severity: Optional[str] = Field(
        default=None,
        description="Severity chosen so far.",
    )
    current_mitigation: Optional[str] = Field(
        default=None,
        description="Mitigation chosen so far.",
    )
    submitted: bool = Field(
        default=False,
        description="Whether the agent already submitted the incident report.",
    )
    max_steps: int = Field(
        default=12,
        description="Maximum number of actions allowed for the episode.",
    )
