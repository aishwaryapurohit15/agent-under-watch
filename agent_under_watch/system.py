"""Wires everything together: build a system for a pack, train it, replay traffic, score it."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .audit import AuditLog
from .auth import AuthService
from .detector import AnomalyDetector
from .features import session_features
from .gateway import Gateway
from .mockdb import MockDatabase
from .models import Verdict
from .policy import PolicyPack, load_pack
from .simulate import SimSession, Simulator


@dataclass
class System:
    pack: PolicyPack
    gateway: Gateway
    auth: AuthService
    audit: AuditLog
    sessions: list[SimSession]


def train_detector(pack: PolicyPack, sessions: list[SimSession]) -> AnomalyDetector:
    """Fit one baseline per agent using ONLY normal training sessions."""
    rows_by_agent: dict[str, list[dict]] = {}
    for s in sessions:
        if s.split != "train":
            continue
        agent = pack.agents[s.agent_id]
        for i in range(len(s.actions)):
            rows_by_agent.setdefault(s.agent_id, []).append(
                session_features(s.actions[: i + 1], pack, agent)
            )
    pct = float(pack.anomaly.get("threshold_percentile", 0.5))
    return AnomalyDetector(threshold_percentile=pct).fit(rows_by_agent)


def build_system(pack_name: str = "banking", seed: int = 7, audit_path: str = ":memory:",
                 normal_per_agent: int = 1000, attacks_per_type: int = 25,
                 use_llm: bool = False) -> System:
    pack = load_pack(pack_name)
    sim = Simulator(pack, seed=seed)
    sessions = sim.dataset(normal_per_agent, attacks_per_type)
    detector = train_detector(pack, sessions)
    auth = AuthService()
    db = MockDatabase(sim.n_subjects, list(pack.sensitivity), seed=seed)
    audit = AuditLog(audit_path)
    gateway = Gateway(pack, auth, db, detector, audit, use_llm=use_llm)
    return System(pack, gateway, auth, audit, sessions)


def replay(system: System, splits: tuple[str, ...] = ("test", "designed", "heldout")) -> pd.DataFrame:
    """Send every action in the chosen splits through the gateway; return one row per action."""
    rows = []
    for s in system.sessions:
        if s.split not in splits:
            continue
        system.auth.start_session(s.agent_id, s.subject_id, s.actions[0].timestamp,
                                  step_up_verified=s.step_up, session_id=s.session_id)
        for a in s.actions:
            d = system.gateway.submit(a)
            rows.append({
                "timestamp": a.timestamp, "session_id": s.session_id, "scenario": s.scenario,
                "split": s.split, "label": s.label, "agent_id": a.agent_id, "tool": a.tool,
                "subject_id": a.subject_id, "record_count": a.record_count,
                "verdict": d.verdict.value, "risk_score": d.risk_score, "executed": d.executed,
                "unauthorized": a.action_id in s.unauthorized, "action_id": a.action_id,
                "reasons": "; ".join(d.reasons), "explanation": d.explanation,
            })
    return pd.DataFrame(rows)


def evaluate(results: pd.DataFrame, audit: AuditLog | None = None) -> dict:
    """Session-level metrics. A session counts as 'caught' if any action was blocked or escalated."""
    flagged = results["verdict"] != Verdict.ALLOW.value
    by_session = results.assign(flagged=flagged).groupby("session_id").agg(
        scenario=("scenario", "first"), split=("split", "first"), label=("label", "first"),
        flagged=("flagged", "any"),
    )

    def rate(mask) -> float:
        sub = by_session[mask]
        return round(float(sub["flagged"].mean()), 4) if len(sub) else float("nan")

    normal = results[results["label"] == "normal"]
    metrics = {
        "unauthorized_actions_executed": int((results["unauthorized"] & results["executed"]).sum()),
        "detection_rate_designed": rate((by_session.label == "attack") & (by_session.split == "designed")),
        "detection_rate_heldout": rate((by_session.label == "attack") & (by_session.split == "heldout")),
        "false_positive_rate_sessions": rate(by_session.label == "normal"),
        "escalations_per_1000_normal_actions": round(
            1000 * float((normal["verdict"] == Verdict.ESCALATE.value).mean()), 2) if len(normal) else 0.0,
        "legit_unusual_sent_to_review": rate(by_session.label == "legit_unusual"),
        "by_scenario": {
            sc: rate(by_session.scenario == sc) for sc in sorted(by_session.scenario.unique())
        },
    }
    if audit is not None:
        ok, bad_row = audit.verify_chain()
        metrics["audit_completeness"] = round(audit.count("decision") / max(len(results), 1), 4)
        metrics["audit_chain_intact"] = ok
    return metrics
