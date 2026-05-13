"""Dogfood log helper.

Goal: pre-build the "what 5 real gigs taught me" case-study narrative as you go,
not reconstruct it from memory at v0.2 launch time.

Each `scrapeprobe URL --gig NAME` run appends a stub entry to
~/scrapeprobe-dogfood/log.md. Open the log in $EDITOR via `scrapeprobe-log`
and fill in the verdict + what-was-wrong / what-was-right lines after reviewing
the report.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

DOGFOOD_DIR = Path.home() / "scrapeprobe-dogfood"
LOG_PATH = DOGFOOD_DIR / "log.md"

LOG_HEADER = """# ScrapeProbe dogfood log

One entry per real gig. Filled in after reviewing each REPORT.md.
Used to build the v0.2 public-launch case-study narrative.

---
"""


def ensure_log_exists() -> None:
    DOGFOOD_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text(LOG_HEADER, encoding="utf-8")


def append_stub(gig: str, target_url: str, report_path: Path) -> Path:
    """Append a stub markdown entry for a fresh probe run. Returns the log path."""
    ensure_log_exists()
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"""
## {today} — {gig}

- **Target:** `{target_url}`
- **Report:** `{report_path}`
- **Verdict:** pending
- **What was wrong:**
- **What was right:**
- **Would I bid?:**

"""
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)
    return LOG_PATH


def open_in_editor() -> int:
    """Open the log file in $EDITOR / $VISUAL. Falls back to printing the path
    if no editor is configured. Returns the editor's exit code, or 0 if printed."""
    ensure_log_exists()
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        print(f"No $EDITOR set. Log is at: {LOG_PATH}")
        return 0
    return subprocess.call([editor, str(LOG_PATH)])


def print_log() -> None:
    ensure_log_exists()
    print(LOG_PATH.read_text(encoding="utf-8"))


def list_gigs() -> list[str]:
    """Return the gig titles found in the log, oldest first."""
    if not LOG_PATH.exists():
        return []
    titles = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and " — " in line:
            titles.append(line[3:].strip())
    return titles
