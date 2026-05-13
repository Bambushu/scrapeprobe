"""Sample-scrape probe — try to extract 5-10 records from the most accessible discovery path.

Polite by default: max 10 requests, aborts on first 4xx that looks like a block.
"""

from __future__ import annotations

import time
from statistics import median

import httpx

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import polite, safe_get
from scrapeprobe.utils.url import is_same_host, join

MAX_SAMPLES = 10


def run(
    ctx: ProbeContext,
    client: httpx.Client,
    sitemap_findings: dict | None = None,
    antibot_findings: dict | None = None,
) -> ProbeResult:
    started = time.monotonic()
    result = ProbeResult(name="sampling")
    delay = max(ctx.crawl_delay_s or 0.0, ctx.polite_delay_s)

    if antibot_findings and antibot_findings.get("looks_blocked_on_recon"):
        result.status = "blocked"
        result.findings = {
            "attempted": False,
            "reason": "Anti-bot probe reported the homepage is blocked. Sample-scrape aborted to stay polite.",
            "latency_per_record_ms": None,
        }
        result.duration_s = time.monotonic() - started
        return result

    sample_urls = _pick_sample_urls(ctx, client, sitemap_findings)
    if not sample_urls:
        result.status = "skipped"
        result.findings = {
            "attempted": False,
            "reason": "No sample URLs available from sitemap or homepage links.",
            "latency_per_record_ms": None,
        }
        result.duration_s = time.monotonic() - started
        return result

    timings = []
    statuses = []
    successes = 0
    bytes_total = 0
    blocked = False

    for url in sample_urls[:MAX_SAMPLES]:
        with polite(delay):
            t0 = time.monotonic()
            resp = safe_get(client, url, timeout=ctx.timeout_s)
            dt = (time.monotonic() - t0) * 1000.0
        if resp is None:
            statuses.append(
                {"url": url, "status": None, "latency_ms": dt, "outcome": "network_error"}
            )
            continue
        statuses.append(
            {
                "url": url,
                "status": resp.status_code,
                "latency_ms": round(dt, 1),
                "outcome": "ok" if 200 <= resp.status_code < 300 else "non_2xx",
                "size_bytes": len(resp.content),
            }
        )
        if 200 <= resp.status_code < 300:
            successes += 1
            bytes_total += len(resp.content)
            timings.append(dt)
            result.evidence.append(
                Evidence(url=url, status_code=resp.status_code, snippet=resp.text[:160])
            )
        elif resp.status_code in (403, 429, 503):
            blocked = True
            break

    if blocked or successes == 0:
        result.status = "blocked"
    elif successes < len(sample_urls[:MAX_SAMPLES]):
        result.status = "partial"

    median_ms = median(timings) if timings else None
    avg_ms = (sum(timings) / len(timings)) if timings else None

    result.findings = {
        "attempted": True,
        "sample_size_planned": min(len(sample_urls), MAX_SAMPLES),
        "successes": successes,
        "polite_delay_s_used": delay,
        "median_latency_ms": round(median_ms, 1) if median_ms else None,
        "avg_latency_ms": round(avg_ms, 1) if avg_ms else None,
        "avg_bytes_per_record": (bytes_total // successes) if successes else None,
        "sampled_urls": statuses,
    }
    result.duration_s = time.monotonic() - started
    return result


def _pick_sample_urls(
    ctx: ProbeContext, client: httpx.Client, sitemap_findings: dict | None
) -> list[str]:
    """Same-host hrefs from the homepage. v0.2 may sample real entries from the sitemap."""
    return _homepage_links(ctx, client)


def _homepage_links(ctx: ProbeContext, client: httpx.Client) -> list[str]:
    """Re-fetch the homepage (cheap, shared connection pool) and pull same-host hrefs."""
    import re

    resp = safe_get(client, ctx.target_url, timeout=ctx.timeout_s)
    if resp is None or resp.status_code >= 400:
        return []

    hrefs = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
    out = []
    seen = set()
    for href in hrefs:
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absu = join(ctx.target_url, href)
        if not is_same_host(absu, ctx.target_url):
            continue
        if any(
            absu.lower().endswith(ext)
            for ext in (".css", ".js", ".png", ".jpg", ".svg", ".webp", ".ico")
        ):
            continue
        if absu in seen:
            continue
        seen.add(absu)
        out.append(absu)
        if len(out) >= MAX_SAMPLES * 2:
            break
    return out
