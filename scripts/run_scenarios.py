"""Run the six demo scenarios in the terminal.

    python scripts/run_scenarios.py                 # banking
    python scripts/run_scenarios.py --pack healthcare
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_under_watch import build_system, list_packs  # noqa: E402
from agent_under_watch.scenarios import SCENARIOS, run_scenario  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="banking", choices=list_packs())
    args = parser.parse_args()

    print(f"Training baselines for the '{args.pack}' pack...")
    system = build_system(args.pack, normal_per_agent=600)
    for key in SCENARIOS:
        res = run_scenario(system, key)
        s = res.summary
        print(f"\n[{key}] {res.title}\n    {res.story}\n    expected: {res.expected}")
        print(f"    result:   {s['ALLOW']} allowed, {s['BLOCK']} blocked, {s['ESCALATE']} escalated "
              f"(first flag at action {s['first_flagged_at_action']})")
        flagged = [d for _, d in res.decisions if d.verdict.value != "ALLOW"]
        print("    " + (flagged[0] if flagged else res.decisions[-1][1]).explanation)
    ok, _ = system.audit.verify_chain()
    print(f"\nAudit log: {system.audit.count()} entries, hash chain intact: {ok}")


if __name__ == "__main__":
    main()
