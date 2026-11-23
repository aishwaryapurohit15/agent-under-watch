"""Transparent risk score from 0 to 100.

Every component is between 0 and 1 and every weight lives in the policy pack,
so a reviewer (or a regulator) can see exactly why a score came out as it did.
The score can only ESCALATE an action; it can never allow a blocked one.
"""
from __future__ import annotations

import math

from .models import ProposedAction
from .policy import PolicyPack

DEFAULT_WEIGHTS = {"volume": 30, "sensitivity": 25, "anomaly": 35, "off_hours": 10}


def risk_score(
    pack: PolicyPack, action: ProposedAction, anomaly_strength: float, off_hours: bool
) -> tuple[int, dict[str, float]]:
    weights = {**DEFAULT_WEIGHTS, **pack.risk.get("weights", {})}
    max_level = max(pack.sensitivity.values(), default=3)
    components = {
        # 1 record -> 0, 10 -> 0.33, 100 -> 0.67, 1,000+ -> 1
        "volume": min(1.0, math.log10(max(action.record_count, 1)) / 3),
        "sensitivity": pack.field_sensitivity(action.fields) / max_level,
        "anomaly": anomaly_strength,
        "off_hours": 1.0 if off_hours else 0.0,
    }
    total = sum(weights.values())
    score = round(100 * sum(weights[k] * components[k] for k in components) / total)
    return score, {k: round(v, 3) for k, v in components.items()}
