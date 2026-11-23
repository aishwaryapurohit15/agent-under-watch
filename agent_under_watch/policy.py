"""Policy packs and the deterministic policy engine.

A policy pack is a YAML file describing one domain (banking, healthcare, ...):
which agents exist, who owns them, which tools they may use, and with what limits.
Swapping the pack is all it takes to point the system at a new industry.

The policy engine only ever returns BLOCK, ESCALATE or "passed". No model,
score or LLM can turn a BLOCK from here into an ALLOW.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import ProposedAction, Session, Verdict

PACK_DIR = Path(__file__).resolve().parent.parent / "policy_packs"


@dataclass
class ToolRule:
    name: str
    max_records: int = 1
    review_above: int | None = None  # records above this go to a human
    allowed_fields: list[str] = field(default_factory=list)  # empty = any field
    requires_step_up: bool = False  # session must have completed extra verification


@dataclass
class AgentProfile:
    agent_id: str
    owner: str
    purpose: str
    session_bound: bool
    tools: dict[str, ToolRule]
    working_hours: tuple[int, int] = (0, 24)
    normal: dict = field(default_factory=dict)  # used only by the data simulator


@dataclass
class PolicyPack:
    domain: str
    subject_label: str
    agents: dict[str, AgentProfile]
    prohibited_tools: set[str]
    sensitivity: dict[str, int]
    risk: dict
    anomaly: dict
    simulation: dict
    source: str = ""

    def field_sensitivity(self, fields: list[str]) -> int:
        return max((self.sensitivity.get(f, 1) for f in fields), default=0)


def list_packs() -> list[str]:
    return sorted(p.stem for p in PACK_DIR.glob("*.yaml"))


def load_pack(name_or_path: str) -> PolicyPack:
    path = Path(name_or_path)
    if not path.suffix:
        path = PACK_DIR / f"{name_or_path}.yaml"
    raw = yaml.safe_load(path.read_text())

    agents = {}
    for agent_id, a in raw["agents"].items():
        tools = {t: ToolRule(name=t, **(rule or {})) for t, rule in a["tools"].items()}
        agents[agent_id] = AgentProfile(
            agent_id=agent_id,
            owner=a["owner"],
            purpose=a["purpose"],
            session_bound=a.get("session_bound", False),
            tools=tools,
            working_hours=tuple(a.get("working_hours", [0, 24])),
            normal=a.get("normal", {}),
        )
    return PolicyPack(
        domain=raw["domain"],
        subject_label=raw.get("subject_label", "subject"),
        agents=agents,
        prohibited_tools=set(raw.get("prohibited_tools", [])),
        sensitivity=raw.get("sensitivity", {}),
        risk=raw.get("risk", {}),
        anomaly=raw.get("anomaly", {}),
        simulation=raw.get("simulation", {}),
        source=str(path),
    )


@dataclass
class PolicyResult:
    verdict: Verdict | None  # BLOCK, ESCALATE, or None when every hard rule passed
    reasons: list[str]
    checks: dict[str, bool]


def check_policy(pack: PolicyPack, action: ProposedAction, session: Session | None) -> PolicyResult:
    """Run the hard rules in order. The first BLOCK wins; ESCALATE rules collect."""
    checks: dict[str, bool] = {}
    label = pack.subject_label

    def block(check: str, reason: str) -> PolicyResult:
        checks[check] = False
        return PolicyResult(Verdict.BLOCK, [reason], checks)

    # 1. The session must exist and belong to this agent (issued by the auth system).
    if session is None or session.agent_id != action.agent_id:
        return block("valid_session", "No valid session for this agent; the auth system did not issue it.")
    checks["valid_session"] = True

    # 2. The circuit breaker may have paused this session.
    if session.paused:
        return block("session_active", "Session is paused pending human review after repeated anomalies.")
    checks["session_active"] = True

    # 3. The agent must be registered, with a named owner.
    agent = pack.agents.get(action.agent_id)
    if agent is None:
        return block("registered_agent", f"Agent '{action.agent_id}' is not in the agent registry.")
    checks["registered_agent"] = True

    # 4. Some tools are off-limits to every agent.
    if action.tool in pack.prohibited_tools:
        return block("not_prohibited", f"'{action.tool}' is prohibited for all AI agents.")
    checks["not_prohibited"] = True

    # 5. The tool must be on this agent's allow-list.
    rule = agent.tools.get(action.tool)
    if rule is None:
        return block("tool_allowed", f"{action.agent_id} is not permitted to use '{action.tool}'.")
    checks["tool_allowed"] = True

    # 6. Session binding: a session-bound agent may only touch the logged-in subject.
    if agent.session_bound:
        if action.subject_id is None or action.subject_id != session.subject_id:
            return block(
                "session_binding",
                f"Requested {label} {action.subject_id} is not the authenticated {label} "
                f"{session.subject_id}.",
            )
    checks["session_binding"] = True

    # 7. Hard volume limit.
    if action.record_count > rule.max_records:
        return block(
            "within_record_limit",
            f"{action.record_count:,} records requested; the limit for this agent and tool is "
            f"{rule.max_records:,}.",
        )
    checks["within_record_limit"] = True

    # 8. Field allow-list (data minimisation).
    if rule.allowed_fields:
        extra = sorted(set(action.fields) - set(rule.allowed_fields))
        if extra:
            return block("fields_allowed", f"Fields not permitted for this tool: {', '.join(extra)}.")
    checks["fields_allowed"] = True

    # 9. Step-up verification for sensitive changes.
    if rule.requires_step_up and not session.step_up_verified:
        return block("step_up", f"'{action.tool}' requires step-up verification, which is missing.")
    checks["step_up"] = True

    # 10. Rules that do not forbid an action but require a human to approve it.
    reasons = []
    if rule.review_above is not None and action.record_count > rule.review_above:
        reasons.append(
            f"{action.record_count:,} records is above the {rule.review_above:,}-record review threshold."
        )
    checks["no_mandatory_review"] = not reasons
    return PolicyResult(Verdict.ESCALATE if reasons else None, reasons, checks)
