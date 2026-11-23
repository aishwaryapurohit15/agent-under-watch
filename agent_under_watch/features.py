"""Behavioural features, computed over the whole session so far.

Looking at one action alone misses the interesting cases: 300 single-record
reads are each harmless, but together they look like someone scraping data.
So every feature describes the session up to and including the current action.
"""
from __future__ import annotations

import math

import numpy as np

from .models import ProposedAction
from .policy import AgentProfile, PolicyPack

FEATURE_NAMES = [
    "n_actions",
    "actions_per_min",
    "distinct_subjects",
    "log_total_records",
    "max_sensitivity",
    "distinct_tools",
    "off_hours",
    "log_median_gap_s",
]


def is_off_hours(agent: AgentProfile, action: ProposedAction) -> bool:
    start, end = agent.working_hours
    return not (start <= action.timestamp.hour < end)


def session_features(
    history: list[ProposedAction], pack: PolicyPack, agent: AgentProfile
) -> dict[str, float]:
    """history = every action in the session so far, oldest first, current one last."""
    current = history[-1]
    times = [a.timestamp for a in history]
    elapsed_min = (times[-1] - times[0]).total_seconds() / 60
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    subjects = {a.subject_id for a in history if a.subject_id is not None}
    return {
        "n_actions": len(history),
        "actions_per_min": len(history) / max(elapsed_min, 1.0),
        "distinct_subjects": len(subjects),
        "log_total_records": math.log1p(sum(a.record_count for a in history)),
        "max_sensitivity": max(pack.field_sensitivity(a.fields) for a in history),
        "distinct_tools": len({a.tool for a in history}),
        "off_hours": float(is_off_hours(agent, current)),
        "log_median_gap_s": math.log1p(float(np.median(gaps))) if gaps else 0.0,
    }


def to_vector(features: dict[str, float]) -> np.ndarray:
    return np.array([[features[name] for name in FEATURE_NAMES]], dtype=float)
