"""A fake system of record (core banking, EHR, HR system...).

Only the gateway holds a reference to this object. Agents get a gateway client,
so there is no code path from an agent to the data that skips the checks.
All data is synthetic.
"""
from __future__ import annotations

import random


class MockDatabase:
    def __init__(self, n_subjects: int, fields: list[str], seed: int = 7) -> None:
        self.rng = random.Random(seed)
        self.fields = fields
        self.n_subjects = n_subjects

    def subject_ids(self) -> list[str]:
        return [str(1000 + i) for i in range(self.n_subjects)]

    def _fake_value(self, subject_id: str, field: str) -> str:
        # Deterministic fake value so the same record always looks the same.
        r = random.Random(f"{subject_id}:{field}")
        return f"<synthetic {field} #{r.randint(1000, 9999)}>"

    def execute(self, tool: str, subject_id: str | None, record_count: int, fields: list[str]) -> dict:
        """Pretend to run the tool. Returns a small summary rather than bulk data."""
        if subject_id is not None:
            return {"subject_id": subject_id, **{f: self._fake_value(subject_id, f) for f in fields}}
        return {"tool": tool, "records_returned": record_count, "fields": fields}
