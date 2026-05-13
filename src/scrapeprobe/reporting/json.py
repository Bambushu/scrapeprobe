"""JSON report renderer for programmatic consumption."""

from __future__ import annotations

import json

from scrapeprobe.models import Report


def render(report: Report, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), indent=indent, ensure_ascii=False, default=str)
