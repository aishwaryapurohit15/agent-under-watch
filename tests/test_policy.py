"""Hard rules: these must hold no matter what the ML or the LLM says."""
from datetime import datetime

from agent_under_watch import ProposedAction, Verdict, list_packs, load_pack
from agent_under_watch.auth import AuthService
from agent_under_watch.policy import check_policy

T = datetime(2026, 11, 2, 10, 0)


def _setup(pack_name):
    pack = load_pack(pack_name)
    roles = pack.simulation["roles"]
    auth = AuthService()
    return pack, roles, auth


def test_every_pack_loads_and_every_agent_has_an_owner():
    for name in list_packs():
        pack = load_pack(name)
        assert pack.agents
        for agent in pack.agents.values():
            assert agent.owner.strip(), f"{name}:{agent.agent_id} has no accountable owner"


def test_session_binding_blocks_other_subject():
    for name in list_packs():
        pack, r, auth = _setup(name)
        s = auth.start_session(r["bound_agent"], "1024", T)
        a = ProposedAction(s.session_id, r["bound_agent"], r["read_tool"], T, "1025", 1, r["bound_fields"])
        result = check_policy(pack, a, s)
        assert result.verdict == Verdict.BLOCK
        assert result.checks["session_binding"] is False


def test_agent_cannot_choose_its_own_session_subject():
    """A made-up session id is rejected: identity comes from the auth system only."""
    pack, r, auth = _setup("banking")
    a = ProposedAction("forged-session", r["bound_agent"], r["read_tool"], T, "1025", 1, r["bound_fields"])
    assert check_policy(pack, a, auth.get("forged-session")).verdict == Verdict.BLOCK


def test_prohibited_tool_always_blocked():
    for name in list_packs():
        pack, r, auth = _setup(name)
        s = auth.start_session(r["bulk_agent"], None, T)
        a = ProposedAction(s.session_id, r["bulk_agent"], r["forbidden_tool"], T, None, 1, [])
        assert check_policy(pack, a, s).verdict == Verdict.BLOCK


def test_record_limit_and_field_allow_list():
    pack, r, auth = _setup("banking")
    s = auth.start_session(r["bulk_agent"], None, T)
    too_many = ProposedAction(s.session_id, r["bulk_agent"], r["export_tool"], T, None, 5000, r["bulk_fields"])
    assert check_policy(pack, too_many, s).verdict == Verdict.BLOCK
    bad_field = ProposedAction(s.session_id, r["bulk_agent"], r["export_tool"], T, None, 10, ["ssn"])
    assert check_policy(pack, bad_field, s).verdict == Verdict.BLOCK


def test_review_threshold_escalates():
    pack, r, auth = _setup("banking")
    s = auth.start_session(r["bulk_agent"], None, T)
    a = ProposedAction(s.session_id, r["bulk_agent"], r["export_tool"], T, None, 500, r["bulk_fields"])
    assert check_policy(pack, a, s).verdict == Verdict.ESCALATE


def test_step_up_required_for_contact_change():
    pack, r, auth = _setup("banking")
    s = auth.start_session(r["bound_agent"], "1024", T, step_up_verified=False)
    a = ProposedAction(s.session_id, r["bound_agent"], "update_contact", T, "1024", 1, ["phone"])
    assert check_policy(pack, a, s).verdict == Verdict.BLOCK
    s2 = auth.start_session(r["bound_agent"], "1024", T, step_up_verified=True)
    a2 = ProposedAction(s2.session_id, r["bound_agent"], "update_contact", T, "1024", 1, ["phone"])
    assert check_policy(pack, a2, s2).verdict is None
