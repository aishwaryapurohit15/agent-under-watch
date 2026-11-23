"""Core data types shared by every part of the system.

These are deliberately domain-neutral: a "subject" is whoever the data is about
(a bank customer, a patient, an employee). The policy pack decides what that means.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


@dataclass
class Session:
    """An authenticated session, created by the auth system - never by the agent."""

    session_id: str
    agent_id: str
    subject_id: str | None  # who is logged in; None for staff/back-office agents
    started_at: datetime
    step_up_verified: bool = False  # extra verification (e.g. one-time code) completed
    paused: bool = False  # set by the circuit breaker; only a human can resume


@dataclass
class ProposedAction:
    """What an agent asks the gateway to do. The agent never executes anything itself."""

    session_id: str
    agent_id: str
    tool: str
    timestamp: datetime
    subject_id: str | None = None  # the record the agent wants to touch (None for bulk)
    record_count: int = 1
    fields: list[str] = field(default_factory=list)
    purpose: str = ""
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class Decision:
    """The gateway's answer, with everything needed to explain and audit it."""

    action_id: str
    verdict: Verdict
    reasons: list[str]
    risk_score: int = 0
    risk_components: dict[str, float] = field(default_factory=dict)
    anomaly: dict[str, float | bool] = field(default_factory=dict)
    explanation: str = ""
    executed: bool = False
    result: object | None = None  # data returned to the agent when executed

    def to_row(self) -> dict:
        return {
            "action_id": self.action_id,
            "verdict": self.verdict.value,
            "risk_score": self.risk_score,
            "reasons": "; ".join(self.reasons),
            "explanation": self.explanation,
            "executed": self.executed,
        }
