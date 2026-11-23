"""End-to-end behaviour of the gateway, scenarios, human review and audit log."""
import sqlite3

import pytest

from agent_under_watch import Verdict, evaluate, replay
from agent_under_watch.scenarios import run_scenario


def test_demo_scenarios_behave_as_expected(system_factory):
    system = system_factory()
    verdicts = lambda key: [d.verdict for _, d in run_scenario(system, key).decisions]  # noqa: E731

    assert verdicts("A") == [Verdict.ALLOW]
    assert verdicts("B")[-1] == Verdict.BLOCK
    assert verdicts("C")[-1] == Verdict.BLOCK
    d = verdicts("D")
    assert Verdict.ESCALATE in d[:20], "burst should be flagged within the first 20 lookups"
    assert d[-1] == Verdict.BLOCK, "circuit breaker should have paused the session"
    assert verdicts("E") == [Verdict.ESCALATE]


def test_blocked_actions_never_execute(system_factory):
    system = system_factory()
    for key in "BCD":
        for _, decision in run_scenario(system, key).decisions:
            if decision.verdict != Verdict.ALLOW:
                assert decision.executed is False
                assert decision.result is None


def test_human_review_requires_a_name_and_is_logged(system_factory):
    system = system_factory()
    action, decision = run_scenario(system, "E").decisions[0]
    assert action.action_id in system.gateway.pending
    with pytest.raises(ValueError):
        system.gateway.review(action.action_id, reviewer="  ", approve=True)
    approved = system.gateway.review(action.action_id, reviewer="J. Rivera", approve=True, note="Q3 audit")
    assert approved.executed and approved.verdict == Verdict.ALLOW
    assert system.audit.count("review") == 1


def test_audit_log_is_append_only_and_tamper_evident(system_factory):
    system = system_factory()
    run_scenario(system, "B")
    with pytest.raises(sqlite3.DatabaseError):
        system.audit.conn.execute("DELETE FROM audit_log")
    with pytest.raises(sqlite3.DatabaseError):
        system.audit.conn.execute("UPDATE audit_log SET verdict = 'ALLOW'")
    assert system.audit.verify_chain() == (True, None)

    # Simulate someone editing the file directly, bypassing the triggers
    system.audit.conn.execute("DROP TRIGGER audit_no_update")
    system.audit.conn.execute("UPDATE audit_log SET verdict = 'ALLOW' WHERE verdict = 'BLOCK'")
    ok, bad_row = system.audit.verify_chain()
    assert ok is False and bad_row is not None


def test_evaluation_targets(system_factory):
    system = system_factory()
    results = replay(system)
    m = evaluate(results, system.audit)
    assert m["unauthorized_actions_executed"] == 0
    assert m["detection_rate_designed"] >= 0.95
    assert m["false_positive_rate_sessions"] < 0.10  # looser than the 5% target: small test sample
    assert m["audit_completeness"] == 1.0 and m["audit_chain_intact"]
