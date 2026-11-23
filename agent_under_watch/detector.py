"""Anomaly detection, trained only on normal behaviour, one baseline per agent.

Two complementary checks:

1. Isolation Forest - catches unusual COMBINATIONS of features
   (e.g. a normal number of lookups, but at an odd speed and odd hour).

2. Baseline envelope - catches values far OUTSIDE anything the agent has done
   before. Isolation Forest is weak here: a point 40x beyond the training range
   can score no worse than an ordinary edge case, because the trees can only
   split within the range they were trained on. The envelope fixes that.

Each agent gets its own baseline, so "normal" means normal FOR THAT AGENT:
50 records is routine for a reporting agent and alarming for a chat assistant.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

from .features import FEATURE_NAMES, to_vector

# Features where "far above normal" is meaningful (binary flags excluded)
ENVELOPE_FEATURES = ["n_actions", "actions_per_min", "distinct_subjects", "log_total_records", "distinct_tools"]


@dataclass
class AgentModel:
    forest: IsolationForest
    threshold: float  # forest scores below this are anomalous
    median: float  # typical forest score for normal behaviour
    limits: dict[str, float]  # envelope: values above these are anomalous


class AnomalyDetector:
    def __init__(self, threshold_percentile: float = 0.5, envelope_margin: float = 1.5,
                 seed: int = 42) -> None:
        self.threshold_percentile = threshold_percentile
        self.envelope_margin = envelope_margin
        self.seed = seed
        self.models: dict[str, AgentModel] = {}

    def fit(self, rows_by_agent: dict[str, list[dict[str, float]]]) -> "AnomalyDetector":
        for agent_id, rows in rows_by_agent.items():
            if len(rows) < 20:
                continue  # not enough history to say what "normal" is
            X = np.array([[r[n] for n in FEATURE_NAMES] for r in rows], dtype=float)
            forest = IsolationForest(n_estimators=100, random_state=self.seed).fit(X)
            scores = forest.score_samples(X)
            limits = {}
            for name in ENVELOPE_FEATURES:
                p999 = float(np.percentile(X[:, FEATURE_NAMES.index(name)], 99.9))
                limits[name] = max(p999 * self.envelope_margin, p999 + 1)
            self.models[agent_id] = AgentModel(
                forest=forest,
                threshold=float(np.percentile(scores, self.threshold_percentile)),
                median=float(np.median(scores)),
                limits=limits,
            )
        return self

    def score(self, agent_id: str, features: dict[str, float]) -> dict:
        """Returns flagged, strength (0..1, feeds the risk score), and what drove it."""
        model = self.models.get(agent_id)
        if model is None:
            return {"flagged": False, "strength": 0.0, "drivers": [], "note": "no baseline for agent"}

        raw = float(model.forest.score_samples(to_vector(features))[0])
        span = max(model.median - model.threshold, 1e-6)
        forest_strength = float(np.clip((model.median - raw) / (2 * span), 0.0, 1.0))
        forest_flag = raw < model.threshold

        drivers, env_strength = [], 0.0
        for name, limit in model.limits.items():
            value = features[name]
            if value > limit:
                drivers.append(f"{name} {value:.3g} (normal limit {limit:.3g})")
                env_strength = max(env_strength, min(1.0, 0.5 + 0.5 * (value / limit - 1)))
        if forest_flag:
            drivers.append("unusual combination of behaviours (isolation forest)")

        return {
            "flagged": forest_flag or bool(drivers),
            "strength": round(max(forest_strength, env_strength), 3),
            "forest_score": round(raw, 4),
            "drivers": drivers,
        }
