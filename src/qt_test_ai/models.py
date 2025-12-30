from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


Severity = Literal["info", "warning", "error"]


@dataclass
class Finding:
    category: str
    severity: Severity
    title: str
    details: str = ""
    file: str | None = None
    line: int | None = None
    rule_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestRun:
    project_root: str
    exe_path: str | None
    created_at: datetime
    findings: list[Finding]
    meta: dict[str, Any] = field(default_factory=dict)

    def summary_counts(self) -> dict[str, int]:
        counts = {"info": 0, "warning": 0, "error": 0}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts
