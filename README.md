# Agent Under Watch

![tests](https://github.com/aishwaryapurohit15/agent-under-watch/actions/workflows/ci.yml/badge.svg)

**A governance gateway that checks every action an AI agent proposes, before it runs.**

**Live demo:** https://agent-under-watch.streamlit.app

AI agents now read customer records, update data and start workflows. Agent Under Watch sits between
an agent and the systems it touches and decides, for every single action:

| Decision | Meaning |
| --- | --- |
| **ALLOW** | Safe and authorized. The gateway executes it. |
| **BLOCK** | Breaks a hard rule. Nothing runs, no data returns. |
| **ESCALATE** | Allowed in principle but risky or unusual. Held until a *named* human approves or rejects it. |

Every decision is explained and written to a tamper-evident audit log.

> All data in this project is synthetic. No real customer, patient or bank data is used.

## How a decision is made

```
Customer / user ──► AI agent ──proposes action──► AGENT UNDER WATCH ──► ALLOW → gateway executes
                   (no credentials)                │                ├─► BLOCK → nothing happens
Auth system ──verified identity──────────────────►│                └─► ESCALATE → human reviewer
                                                    ▼
          1. Session binding   2. Permissions   3. Anomaly check   4. Risk score
                                                    ▼
                                 Append-only, hash-chained audit log
```

1. **Hard rules first** (`policy.py`). Registered agent with a named owner, prohibited tools, per-agent
   tool allow-list, record limits, field allow-list, step-up verification, and **session binding**: an
   agent serving a logged-in customer can only touch *that* customer, because identity comes from the
   auth system, never from the agent. A BLOCK here is final; no model is consulted.
2. **Behaviour** (`features.py`, `detector.py`). Session-level features scored against each agent's own
   baseline with an Isolation Forest plus a "baseline envelope" for values far outside anything seen.
3. **Risk score** (`risk.py`). Transparent 0-100 score; weights live in the policy pack.
4. **Circuit breaker**. Repeated anomalies pause the whole session until a human resumes it.
5. **Explanation** (`explainer.py`). Template by default; optional LLM summary that only sees structured
   fields and can never change a decision.

## Works for any industry: policy packs

The engine is domain-neutral. Everything industry-specific lives in one YAML file in `policy_packs/`:

| Pack | Session-bound agent | Lookup agent | Bulk agent |
| --- | --- | --- | --- |
| `banking.yaml` | customer_service_bot | staff_assistant | reporting_agent |
| `healthcare.yaml` | patient_portal_assistant | clinician_assistant | billing_report_agent |

Add a new industry by copying a pack and editing it. No code changes are needed.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

pytest -q                            # 17 tests
python scripts/run_scenarios.py      # the six demo scenarios in the terminal
python scripts/evaluate.py --all     # full metrics, saved to results/
streamlit run app.py                 # the dashboard at http://localhost:8501
```

Full GitHub and deployment steps are in **[docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md)**.

## Demo scenarios

| # | Scenario | Caught by | Decision |
| --- | --- | --- | --- |
| A | Normal request | nothing | ALLOW |
| B | Prompt injection: export 5,000 records | permissions | BLOCK |
| C | Prompt injection: read someone else's single record | session binding | BLOCK |
| D | 300 permitted single lookups in two minutes | anomaly detection | ESCALATE at action 4, then circuit breaker |
| E | Reporting agent exports 500 records for an audit | review threshold | ESCALATE to a named reviewer |
| F | Slow exfiltration, 3 lookups an hour for 24 h | anomaly envelope | ESCALATE at action 13 |

## Current results (seed 7)

| Metric | Target | Banking | Healthcare |
| --- | --- | --- | --- |
| Unauthorized actions executed | 0 | 0 | 0 |
| Designed attacks caught | ≥ 95% | 100% | 100% |
| Held-out attacks caught | report | 50% | 54% |
| Normal sessions flagged (false positives) | < 5% | 2.0% | 1.6% |
| Audit completeness | 100% | 100% | 100% |

**Honest notes**

- The held-out **after-hours sensitive lookup** attack is almost never caught (0% banking, 8% healthcare).
  Fixing it is the first item on the roadmap.
- The baseline envelope was added after a demo run showed Isolation Forest missing scenario D. The
  held-out attacks were visible at that point, so they are no longer fully "unseen". Write new held-out
  attacks (roadmap) before reporting final numbers.
- Synthetic normal behaviour is cleaner than real behaviour; real false-positive rates would be higher.

## Governance framework mapping

See **[docs/FRAMEWORK_MAPPING.md](docs/FRAMEWORK_MAPPING.md)** for how each component maps to the NIST AI RMF,
EU AI Act (Articles 9, 12-15, 26), ISO/IEC 42001, Singapore's Model AI Governance Framework for Agentic AI,
and the OWASP Top 10 for Agentic Applications 2026.

## Project layout

```
agent_under_watch/
  models.py       data types (ProposedAction, Decision, Session)
  policy.py       policy packs + hard rules
  auth.py         stand-in auth system (source of truth for identity)
  gateway.py      the decision pipeline, execution, human review
  features.py     session behaviour features
  detector.py     Isolation Forest + baseline envelope, per agent
  risk.py         transparent 0-100 risk score
  explainer.py    template / optional LLM explanations
  audit.py        append-only, hash-chained SQLite audit log
  mockdb.py       fake system of record (synthetic)
  simulate.py     synthetic normal traffic and attacks
  scenarios.py    demo scenarios A-F
  system.py       wiring, training, replay, evaluation
policy_packs/     banking.yaml, healthcare.yaml
scripts/          run_scenarios.py, evaluate.py
tests/            pytest suite (runs on every push via GitHub Actions)
app.py            Streamlit dashboard
```

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).
