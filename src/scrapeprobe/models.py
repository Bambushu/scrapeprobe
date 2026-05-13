"""Typed result containers shared by all probes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ProbeStatus = Literal["ok", "partial", "blocked", "skipped", "error"]


@dataclass
class Evidence:
    """A single observation that backs a finding."""

    url: str
    status_code: int | None = None
    snippet: str = ""
    note: str = ""


@dataclass
class ProbeResult:
    """Standard envelope every probe returns. Probes must NEVER raise."""

    name: str
    status: ProbeStatus = "ok"
    findings: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    error: str | None = None
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "findings": self.findings,
            "evidence": [
                {"url": e.url, "status_code": e.status_code, "snippet": e.snippet, "note": e.note}
                for e in self.evidence
            ],
            "error": self.error,
            "duration_s": round(self.duration_s, 3),
        }


@dataclass
class ProbeContext:
    """Shared state passed to every probe."""

    target_url: str
    target_host: str
    target_scheme: str
    user_agent: str
    polite_delay_s: float
    timeout_s: float
    output_dir: str
    disallow_paths: list[str] = field(default_factory=list)
    crawl_delay_s: float | None = None

    @property
    def origin(self) -> str:
        return f"{self.target_scheme}://{self.target_host}"


@dataclass
class Report:
    """Full report payload, assembled by orchestrator and passed to renderers."""

    target_url: str
    target_host: str
    started_at: datetime
    finished_at: datetime
    duration_s: float
    probes: dict[str, ProbeResult] = field(default_factory=dict)
    scrapeprobe_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_url": self.target_url,
            "target_host": self.target_host,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_s": round(self.duration_s, 3),
            "scrapeprobe_version": self.scrapeprobe_version,
            "probes": {k: v.to_dict() for k, v in self.probes.items()},
        }
