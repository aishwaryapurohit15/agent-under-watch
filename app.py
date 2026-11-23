"""Agent Under Watch - Streamlit dashboard.

Run locally:   streamlit run app.py
Deploy:        share.streamlit.io -> New app -> pick this repo -> main file: app.py
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from agent_under_watch import Verdict, build_system, evaluate, list_packs, replay
from agent_under_watch.scenarios import SCENARIOS, run_scenario

st.set_page_config(page_title="Agent Under Watch", page_icon="🛡️", layout="wide")

BANNER = {"ALLOW": st.success, "BLOCK": st.error, "ESCALATE": st.warning}


@st.cache_resource(show_spinner=False)
def load(pack: str):
    system = build_system(pack, normal_per_agent=600, attacks_per_type=20)
    results = replay(system)
    metrics = evaluate(results, system.audit)
    return system, results, metrics


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🛡️ Agent Under Watch")
st.sidebar.caption("A governance gateway that checks every AI-agent action before it runs.")
pack = st.sidebar.selectbox("Policy pack (industry)", list_packs(), index=list_packs().index("banking"))
with st.spinner(f"Training baselines and replaying traffic for '{pack}'... (first load ~15s)"):
    system, results, metrics = load(pack)

llm_available = bool(os.environ.get("ANTHROPIC_API_KEY"))
system.gateway.use_llm = st.sidebar.toggle(
    "AI-written explanations", value=False, disabled=not llm_available,
    help="Needs ANTHROPIC_API_KEY. The AI only explains; it never changes a decision.",
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**All data is synthetic.**  \n"
    f"Domain: `{system.pack.domain}` · agents: {len(system.pack.agents)} · "
    f"pending reviews: {len(system.gateway.pending)}"
)

st.title("Agent Under Watch")
st.caption("Rules enforce. Machine learning raises scrutiny. Humans decide the grey areas. Everything is logged.")

tab_demo, tab_activity, tab_review, tab_audit, tab_eval, tab_policy = st.tabs(
    ["Demo scenarios", "Activity", "Review queue", "Audit log", "Evaluation", "Policy pack"]
)


def decision_card(action, decision) -> None:
    with st.container(border=True):
        BANNER[decision.verdict.value](f"**{decision.verdict.value}** · risk score {decision.risk_score}/100")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Agent**  \n{action.agent_id}")
        c2.markdown(f"**Tool**  \n{action.tool}")
        c3.markdown(f"**Record**  \n{action.subject_id or 'bulk'}")
        c4.markdown(f"**Records**  \n{action.record_count:,}")
        st.markdown(f"**Explanation**  \n{decision.explanation}")
        if decision.risk_components:
            st.caption("Risk components (0-1): " + ", ".join(
                f"{k} {v:.2f}" for k, v in decision.risk_components.items()))


# ---------------------------------------------------------------- demo
with tab_demo:
    key = st.radio("Scenario", list(SCENARIOS), horizontal=True,
                   format_func=lambda k: f"{k}: {SCENARIOS[k][0]}")
    title, story, expected = SCENARIOS[key]
    st.markdown(f"### {key}. {title}")
    st.write(story.format(subject=system.pack.subject_label))
    st.caption(f"Expected: {expected}")

    if st.button("Run scenario", type="primary"):
        st.session_state["demo"] = run_scenario(system, key)
    res = st.session_state.get("demo")
    if res is not None and res.key == key:
        s = res.summary
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Actions proposed", s["actions"])
        m2.metric("Allowed", s["ALLOW"])
        m3.metric("Blocked", s["BLOCK"])
        m4.metric("Escalated", s["ESCALATE"])
        if s["first_flagged_at_action"]:
            st.info(f"First flagged at action #{s['first_flagged_at_action']} of {s['actions']}.")
        flagged = [(a, d) for a, d in res.decisions if d.verdict != Verdict.ALLOW]
        decision_card(*(flagged[0] if flagged else res.decisions[-1]))
        with st.expander("Every action in this scenario"):
            st.dataframe(pd.DataFrame([{
                "#": i, "time": a.timestamp, "tool": a.tool, "record": a.subject_id,
                "records": a.record_count, "verdict": d.verdict.value, "risk": d.risk_score,
                "reasons": "; ".join(d.reasons),
            } for i, (a, d) in enumerate(res.decisions, 1)]), hide_index=True)

# ---------------------------------------------------------------- activity
with tab_activity:
    st.subheader("Replayed traffic: normal test sessions plus attacks")
    c1, c2 = st.columns(2)
    verdicts = c1.multiselect("Verdict", ["ALLOW", "BLOCK", "ESCALATE"], default=["BLOCK", "ESCALATE"])
    scenarios = c2.multiselect("Scenario", sorted(results["scenario"].unique()))
    view = results[results["verdict"].isin(verdicts)]
    if scenarios:
        view = view[view["scenario"].isin(scenarios)]
    st.caption(f"{len(view):,} of {len(results):,} actions")
    st.dataframe(view[["timestamp", "scenario", "agent_id", "tool", "subject_id", "record_count",
                       "verdict", "risk_score", "reasons"]].head(2000), hide_index=True)

# ---------------------------------------------------------------- review queue
with tab_review:
    st.subheader("Actions waiting for a human decision")
    pending = list(system.gateway.pending.items())
    if not pending:
        st.success("Nothing waiting for review.")
    else:
        reviewer = st.text_input("Your name (required - every approval is attributed)")
        labels = {aid: f"{a.agent_id} · {a.tool} · {a.record_count:,} records · risk {d.risk_score} · {aid}"
                  for aid, (a, d) in reversed(pending)}
        choice = st.selectbox(f"{len(pending)} pending", list(labels), format_func=labels.get)
        action, decision = system.gateway.pending[choice]
        decision_card(action, decision)
        note = st.text_input("Note (optional)")
        c1, c2 = st.columns(2)
        for col, approve, label in ((c1, True, "Approve and execute"), (c2, False, "Reject")):
            if col.button(label, disabled=not reviewer.strip(), key=f"rv-{approve}"):
                system.gateway.review(choice, reviewer, approve, note)
                st.toast(f"{'Approved' if approve else 'Rejected'} and logged.")
                st.rerun()

# ---------------------------------------------------------------- audit
with tab_audit:
    st.subheader("Append-only, hash-chained audit log")
    ok, bad = system.audit.verify_chain()
    (st.success if ok else st.error)(
        f"Hash chain {'intact' if ok else f'BROKEN at row {bad}'} · {system.audit.count():,} entries")
    rows = pd.DataFrame(system.audit.rows(limit=1000))
    st.dataframe(rows[["id", "ts", "event", "agent_id", "agent_owner", "authenticated_subject", "tool",
                       "target_subject", "record_count", "verdict", "risk_score", "reviewer", "reasons",
                       "hash"]], hide_index=True)

# ---------------------------------------------------------------- evaluation
with tab_eval:
    st.subheader("How well does it work? (synthetic data - see limitations)")
    c = st.columns(4)
    c[0].metric("Unauthorized actions executed", metrics["unauthorized_actions_executed"], help="Target: 0")
    c[1].metric("Designed attacks caught", f"{metrics['detection_rate_designed']:.0%}", help="Target: 95%+")
    c[2].metric("Held-out attacks caught", f"{metrics['detection_rate_heldout']:.0%}",
                help="Attacks the features were not designed for")
    c[3].metric("False-positive rate", f"{metrics['false_positive_rate_sessions']:.1%}", help="Target: <5%")
    st.bar_chart(pd.Series(metrics["by_scenario"], name="share of sessions flagged"), horizontal=True)
    st.caption("'normal' should be near 0; every attack row should be near 100%. "
               "A low held-out bar is an honest finding, not a bug to hide.")
    st.json(metrics, expanded=False)

# ---------------------------------------------------------------- policy
with tab_policy:
    st.subheader(f"Policy pack: {pack}")
    st.caption("Edit this YAML file in the repo to change what agents may do. No code changes needed.")
    with open(system.pack.source) as f:
        st.code(f.read(), language="yaml")
