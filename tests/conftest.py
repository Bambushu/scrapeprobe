"""Shared fixtures for ScrapeProbe tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult, Report


@pytest.fixture
def sample_ctx() -> ProbeContext:
    return ProbeContext(
        target_url="https://example.com/",
        target_host="example.com",
        target_scheme="https",
        user_agent="ScrapeProbe/test",
        polite_delay_s=0.0,
        timeout_s=2.0,
        output_dir="/tmp/scrapeprobe-test",
    )


@pytest.fixture
def synthetic_report() -> Report:
    """A fully populated report for the markdown renderer to chew on."""
    now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
    return Report(
        target_url="https://example.com/",
        target_host="example.com",
        started_at=now,
        finished_at=now,
        duration_s=4.2,
        scrapeprobe_version="0.1.0",
        probes={
            "robots": _stub_probe(
                "robots",
                {
                    "present": True,
                    "http_status": 200,
                    "size_bytes": 200,
                    "user_agent_rules": {
                        "*": {"allow": ["/public/"], "disallow": ["/private/", "/admin/"]}
                    },
                    "sitemaps": ["https://example.com/sitemap.xml"],
                    "disallow_all": False,
                    "crawl_delay_s": 2.0,
                },
            ),
            "antibot": _stub_probe(
                "antibot",
                {
                    "wafw00f": {
                        "detected": True,
                        "identified": ["Cloudflare (CloudFlare Inc.)"],
                        "generic_signal": False,
                    },
                    "signature_matches": [
                        {
                            "name": "Cloudflare CDN (passive)",
                            "severity": "low",
                            "matched_on": ["header:cf-ray"],
                            "note": None,
                        }
                    ],
                    "overall_severity": "low",
                    "looks_blocked_on_recon": False,
                    "response_status": 200,
                },
            ),
            "techstack": _stub_probe(
                "techstack",
                {
                    "detected": [
                        {
                            "name": "WordPress",
                            "categories": ["cms"],
                            "matched_on": ["meta:generator"],
                            "website": "https://wordpress.org",
                        },
                        {
                            "name": "nginx",
                            "categories": ["server"],
                            "matched_on": ["header:server"],
                            "website": "https://nginx.org",
                        },
                    ],
                    "by_category": {"cms": ["WordPress"], "server": ["nginx"]},
                    "detection_count": 2,
                },
            ),
            "sitemap": _stub_probe(
                "sitemap",
                {
                    "sitemaps_found": [
                        {
                            "url": "https://example.com/sitemap.xml",
                            "kind": "sitemap",
                            "url_count_estimate": 1234,
                            "child_sitemap_count": 0,
                            "size_bytes": 50000,
                            "http_status": 200,
                        },
                    ],
                    "sitemap_count": 1,
                    "total_url_count_estimate": 1234,
                    "has_rss_feed": False,
                },
            ),
            "bulkdata": _stub_probe(
                "bulkdata",
                {
                    "on_site_endpoints": [],
                    "national_registry_hits": [],
                    "any_bulkdata_signal": False,
                    "highest_value_finding": None,
                    "note": "No obvious bulk-data endpoint.",
                },
            ),
            "discovery": _stub_probe(
                "discovery",
                {
                    "strategies": [
                        {
                            "name": "sitemap_walk",
                            "score": "high",
                            "reason": "Sitemap exposes ~1234 URLs.",
                        },
                    ],
                    "forms": {"form_count": 1, "search_form": None, "has_alphabet_links": False},
                    "pagination": {"has_pagination": False, "pattern": None},
                    "id_enum": {"likely": False},
                },
            ),
            "sampling": _stub_probe(
                "sampling",
                {
                    "attempted": True,
                    "sample_size_planned": 10,
                    "successes": 10,
                    "polite_delay_s_used": 1.0,
                    "median_latency_ms": 420.0,
                    "avg_latency_ms": 510.0,
                    "avg_bytes_per_record": 15000,
                    "sampled_urls": [
                        {
                            "url": "https://example.com/p/1",
                            "status": 200,
                            "latency_ms": 400,
                            "outcome": "ok",
                            "size_bytes": 15000,
                        },
                    ],
                },
            ),
            "tos": _stub_probe(
                "tos",
                {
                    "pages_found": [
                        {"url": "https://example.com/terms", "http_status": 200, "chars": 8000}
                    ],
                    "scraping_keywords_hit": [
                        {
                            "url": "https://example.com/terms",
                            "language": "en",
                            "pattern": "scrap[ei]",
                            "matched": "scrape",
                            "context": "...you may not scrape or crawl our website without consent...",
                        }
                    ],
                    "scraping_keyword_hit_count": 1,
                    "languages_detected": ["en"],
                },
            ),
            "jurisdiction": _stub_probe(
                "jurisdiction",
                {
                    "tld_country": None,
                    "header_country": None,
                    "effective_country_guess": None,
                    "is_eu_eea": False,
                    "gdpr_applies_heuristic": False,
                    "has_consent_banner_markers": False,
                    "consent_banner_markers": [],
                    "note": "Non-EU TLD, no consent banner detected.",
                },
            ),
        },
    )


def _stub_probe(name: str, findings: dict[str, Any]) -> ProbeResult:
    return ProbeResult(
        name=name,
        status="ok",
        findings=findings,
        evidence=[Evidence(url=f"https://example.com/{name}", status_code=200, snippet="")],
        duration_s=0.5,
    )
