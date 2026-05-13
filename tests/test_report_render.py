"""End-to-end render test — the markdown renderer must not raise on a realistic Report."""

import json

from scrapeprobe.reporting import json as json_renderer
from scrapeprobe.reporting import markdown as md_renderer


def test_markdown_renderer_full_pipeline(synthetic_report):
    md = md_renderer.render(synthetic_report)
    assert md.startswith("# ScrapeProbe Report")
    # Every numbered section must be present.
    for needle in (
        "## Executive summary",
        "## 1. Bulk-data finding",
        "## 2. Anti-bot stack fingerprint",
        "## 3. Tech stack fingerprint",
        "## 4. Robots.txt analysis",
        "## 5. Sitemap discovery",
        "## 6. Discovery path heuristics",
        "## 7. Sample scrape attempt",
        "## 8. Full-run projection",
        "## 9. Terms-of-Service posture",
        "## 10. Jurisdiction & GDPR posture",
    ):
        assert needle in md, f"missing section: {needle!r}"


def test_markdown_renderer_mentions_target(synthetic_report):
    md = md_renderer.render(synthetic_report)
    assert "example.com" in md


def test_json_renderer_is_valid_json(synthetic_report):
    out = json_renderer.render(synthetic_report)
    parsed = json.loads(out)
    assert parsed["target_url"] == "https://example.com/"
    assert "robots" in parsed["probes"]
    assert parsed["probes"]["robots"]["findings"]["present"] is True


def test_markdown_renderer_handles_blocked_sampling(synthetic_report):
    """When sample-scrape is blocked, the report must still render cleanly."""
    synthetic_report.probes["sampling"].findings = {
        "attempted": False,
        "reason": "Anti-bot probe reported the homepage is blocked.",
        "latency_per_record_ms": None,
    }
    synthetic_report.probes["sampling"].status = "blocked"
    md = md_renderer.render(synthetic_report)
    assert "blocked" in md.lower() or "Not attempted" in md


def test_markdown_renderer_handles_missing_robots(synthetic_report):
    """If robots probe found no robots.txt, render still works."""
    synthetic_report.probes["robots"].findings = {
        "present": False,
        "http_status": 404,
        "user_agent_rules": {},
        "sitemaps": [],
        "disallow_all": False,
        "crawl_delay_s": None,
    }
    md = md_renderer.render(synthetic_report)
    assert "No `/robots.txt` found" in md
