"""Plain-language explanations for human reviewers.

Default: a deterministic template built from the structured decision record.
Optional: if the `anthropic` package is installed and ANTHROPIC_API_KEY is set,
an LLM rewrites the summary. The LLM:
  * only ever sees structured fields (never raw documents or agent prompts),
    so text injected into customer documents cannot reach it;
  * is advisory only - its output never changes the verdict.
"""
from __future__ import annotations

import json
import os

from .models import Decision, ProposedAction, Verdict

VERB = {
    Verdict.ALLOW: "Allowed",
    Verdict.BLOCK: "Blocked",
    Verdict.ESCALATE: "Held for human review",
}


def template_explanation(action: ProposedAction, decision: Decision) -> str:
    parts = [f"{VERB[decision.verdict]}: {action.agent_id} asked to run '{action.tool}'"]
    target = f" on record {action.subject_id}" if action.subject_id else ""
    parts[0] += f"{target} ({action.record_count:,} record{'s' if action.record_count != 1 else ''})."
    if decision.reasons:
        parts.append("Why: " + " ".join(decision.reasons))
    if decision.verdict != Verdict.BLOCK:
        top = sorted(decision.risk_components.items(), key=lambda kv: -kv[1])[:2]
        drivers = ", ".join(f"{k} {v:.0%}" for k, v in top if v > 0) or "none"
        parts.append(f"Risk score {decision.risk_score}/100 (main drivers: {drivers}).")
    if decision.verdict == Verdict.BLOCK:
        parts.append("Nothing was executed and no data was returned.")
    return " ".join(parts)


def llm_explanation(action: ProposedAction, decision: Decision) -> str | None:
    """Optional LLM summary. Returns None if no LLM is configured or the call fails."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # optional dependency
    except ImportError:
        return None
    record = {
        "agent": action.agent_id,
        "tool": action.tool,
        "record_count": action.record_count,
        "fields": action.fields,
        "verdict": decision.verdict.value,
        "rule_reasons": decision.reasons,
        "risk_score": decision.risk_score,
        "risk_components": decision.risk_components,
        "anomaly": decision.anomaly,
    }
    prompt = (
        "You explain AI-agent governance decisions to a bank risk reviewer. Using ONLY the JSON "
        "record below, write two plain sentences: what the agent tried and why the system decided "
        "as it did. Do not recommend a different decision.\n\n" + json.dumps(record)
    )
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.environ.get("AUW_LLM_MODEL", "claude-haiku-5-5"),
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return "[AI summary, advisory only] " + msg.content[0].text.strip()
    except Exception:
        return None


def explain(action: ProposedAction, decision: Decision, use_llm: bool = False) -> str:
    if use_llm:
        text = llm_explanation(action, decision)
        if text:
            return text
    return template_explanation(action, decision)
