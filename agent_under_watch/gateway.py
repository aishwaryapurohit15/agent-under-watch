"""The gateway: the only route from an AI agent to real systems.

    agent --proposes--> Gateway --checks--> ALLOW (gateway executes)
                                        --> BLOCK (nothing happens)
                                        --> ESCALATE (held until a named human decides)

Order matters:
  1. Hard rules (policy.py). A BLOCK here is final; no model is even consulted.
  2. Behaviour (anomaly detector) and the risk score. These can only add scrutiny.
  3. Circuit breaker: repeated anomalies pause the whole session.
Every step is written to the audit log.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .audit import AuditLog
from .auth import AuthService
from .detector import AnomalyDetector
from .explainer import explain
from .features import is_off_hours, session_features
from .mockdb import MockDatabase
from .models import Decision, ProposedAction, Verdict
from .policy import PolicyPack, check_policy
from .risk import risk_score


class Gateway:
    def __init__(
        self,
        pack: PolicyPack,
        auth: AuthService,
        db: MockDatabase,
        detector: AnomalyDetector,
        audit: AuditLog,
        use_llm: bool = False,
    ) -> None:
        self.pack = pack
        self.auth = auth
        self._db = db  # private: agents never get this reference
        self.detector = detector
        self.audit = audit
        self.use_llm = use_llm
        self.escalate_at = int(pack.risk.get("escalate_at", 50))
        self.pause_after = int(pack.anomaly.get("pause_after", 3))
        self._history: dict[str, list[ProposedAction]] = defaultdict(list)
        self._anomaly_count: Counter[str] = Counter()
        self.pending: dict[str, tuple[ProposedAction, Decision]] = {}

    # ------------------------------------------------------------------ submit
    def submit(self, action: ProposedAction) -> Decision:
        session = self.auth.get(action.session_id)
        policy = check_policy(self.pack, action, session)

        if policy.verdict == Verdict.BLOCK:
            decision = Decision(action.action_id, Verdict.BLOCK, policy.reasons)
        else:
            decision = self._assess_behaviour(action, policy.reasons)

        if session is not None:
            self._history[action.session_id].append(action)

        if decision.verdict == Verdict.ALLOW:
            decision.result = self._execute(action)
            decision.executed = True
        elif decision.verdict == Verdict.ESCALATE:
            self.pending[action.action_id] = (action, decision)

        decision.explanation = explain(action, decision, self.use_llm)
        self._log("decision", action, decision, session)
        return decision

    def _assess_behaviour(self, action: ProposedAction, policy_reasons: list[str]) -> Decision:
        agent = self.pack.agents[action.agent_id]
        history = self._history[action.session_id] + [action]
        features = session_features(history, self.pack, agent)
        anomaly = self.detector.score(action.agent_id, features)
        off_hours = is_off_hours(agent, action)
        score, components = risk_score(self.pack, action, anomaly["strength"], off_hours)

        reasons = list(policy_reasons)
        if anomaly["flagged"]:
            reasons.append(
                "Session behaviour is unusual for this agent: " + "; ".join(anomaly["drivers"]) + "."
            )
            self._anomaly_count[action.session_id] += 1
            if self._anomaly_count[action.session_id] >= self.pause_after:
                self.auth.pause(action.session_id)
                reasons.append(
                    f"Circuit breaker: session paused after {self.pause_after} anomalous actions."
                )
        if score >= self.escalate_at:
            reasons.append(f"Risk score {score} is at or above the review threshold of {self.escalate_at}.")

        return Decision(
            action.action_id,
            Verdict.ESCALATE if reasons else Verdict.ALLOW,
            reasons,
            risk_score=score,
            risk_components=components,
            anomaly={**anomaly, "features": {k: round(v, 3) for k, v in features.items()}},
        )

    # ------------------------------------------------------------------ human review
    def review(self, action_id: str, reviewer: str, approve: bool, note: str = "") -> Decision:
        """A named human approves or rejects an escalated action."""
        if not reviewer.strip():
            raise ValueError("A reviewer name is required; anonymous approvals are not accepted.")
        if action_id not in self.pending:
            raise KeyError(f"No pending escalation with id {action_id}")
        action, original = self.pending.pop(action_id)
        verdict = Verdict.ALLOW if approve else Verdict.BLOCK
        decision = Decision(
            action_id,
            verdict,
            [f"{'Approved' if approve else 'Rejected'} by {reviewer}." + (f" Note: {note}" if note else "")],
            risk_score=original.risk_score,
            risk_components=original.risk_components,
            anomaly=original.anomaly,
        )
        if approve:
            decision.result = self._execute(action)
            decision.executed = True
        decision.explanation = decision.reasons[0]
        self._log("review", action, decision, self.auth.get(action.session_id), reviewer, note)
        return decision

    def resume_session(self, session_id: str, reviewer: str) -> None:
        if not reviewer.strip():
            raise ValueError("A reviewer name is required.")
        self.auth.resume(session_id)
        self._anomaly_count[session_id] = 0

    # ------------------------------------------------------------------ internals
    def _execute(self, action: ProposedAction):
        return self._db.execute(action.tool, action.subject_id, action.record_count, action.fields)

    def _log(self, event, action, decision, session, reviewer=None, note=None) -> None:
        agent = self.pack.agents.get(action.agent_id)
        self.audit.append(
            ts=action.timestamp.isoformat(),
            event=event,
            action_id=action.action_id,
            session_id=action.session_id,
            agent_id=action.agent_id,
            agent_owner=agent.owner if agent else None,
            authenticated_subject=session.subject_id if session else None,
            tool=action.tool,
            target_subject=action.subject_id,
            record_count=action.record_count,
            fields=action.fields,
            purpose=action.purpose,
            verdict=decision.verdict.value,
            reasons=decision.reasons,
            risk_score=decision.risk_score,
            risk_components=decision.risk_components,
            anomaly=decision.anomaly,
            executed=decision.executed,
            reviewer=reviewer,
            note=note,
        )
