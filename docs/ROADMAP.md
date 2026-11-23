# Roadmap: suggested next updates

Each item is sized to be one branch and one pull request. Start at the top.

## 1. Catch the after-hours attack (rules, about 1 hour)

The held-out `after_hours_sensitive` attack is almost never caught. Add a policy option so a pack can say
"escalate any action outside this agent's working hours that touches sensitivity-3 fields":

- Add `off_hours_sensitive_review: true` to `staff_assistant` in `banking.yaml`.
- In `policy.py`, step 10: if set, and the action is off-hours (`features.is_off_hours`) and
  `pack.field_sensitivity(action.fields) >= 2`, append a review reason.
- Add a test in `tests/test_policy.py`. Re-run `scripts/evaluate.py` and log the change.

## 2. Write fresh held-out attacks (a teammate, about 2 hours)

Ask someone who has not read `features.py` to add two new recipes to `simulate.py` with
`split="heldout"`. Ideas: a burst that pauses for an hour between batches; one record read many times;
a bulk agent exporting slightly under the review threshold over and over. Report the numbers, caught or not.

## 3. Add a third industry pack (about 1 hour)

Copy `healthcare.yaml` to `hr.yaml` (employee help agent, HR partner assistant, payroll report agent).
Restart the app: the new pack appears in the sidebar automatically.

## 4. Turn the gateway into a real API (FastAPI, about half a day)

Add `api.py` with `POST /actions` (agent proposes an action) and `POST /reviews/{action_id}`. This shows the
gateway as a network service the agent must go through, which makes the "no bypass" principle concrete.

## 5. Put it in front of a real agent (stretch)

Wrap the gateway as an MCP (Model Context Protocol) server that proxies tool calls, so any MCP-compatible
agent can only reach tools through Agent Under Watch.

## 6. Reviewer fatigue monitoring (governance)

Track approval rate and time-to-decision per reviewer in the audit log. Alert if someone approves nearly
everything in seconds.

## 7. Persist across restarts

Pass `audit_path="audit.db"` in `app.py` so the audit log survives restarts (keep `*.db` in `.gitignore`).
