"""Bulk-data probe — highest-value possible finding.

Checks national open-data registries (data.gv.X, data.europa.eu, data.gov.X) AND
on-site paths likely to expose a public dataset (CKAN, OData, JSON API, RSS, etc.).
"""

from __future__ import annotations

import json
import time
from importlib import resources
from urllib.parse import quote_plus

import httpx

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get
from scrapeprobe.utils.url import country_from_tld, join

_PATTERNS: dict | None = None


def _load() -> dict:
    global _PATTERNS
    if _PATTERNS is None:
        ref = resources.files("scrapeprobe.data").joinpath("bulkdata_patterns.json")
        _PATTERNS = json.loads(ref.read_text(encoding="utf-8"))
    return _PATTERNS


def run(ctx: ProbeContext, client: httpx.Client) -> ProbeResult:
    started = time.monotonic()
    patterns = _load()
    result = ProbeResult(name="bulkdata")

    onsite_hits = _check_onsite_paths(ctx, client, patterns["on_site_paths"])
    registry_hits = _check_national_registries(ctx, client, patterns["national_registries"])

    has_any = bool(onsite_hits) or any(r.get("appears_listed") for r in registry_hits)

    result.findings = {
        "on_site_endpoints": onsite_hits,
        "national_registry_hits": registry_hits,
        "any_bulkdata_signal": has_any,
        "highest_value_finding": _summarize(onsite_hits, registry_hits),
    }
    for hit in onsite_hits:
        result.evidence.append(
            Evidence(url=hit["url"], status_code=hit["http_status"], snippet=hit.get("snippet", ""))
        )
    if not has_any:
        result.status = "partial"
        result.findings["note"] = (
            "No obvious bulk-data endpoint or registry listing. Manual confirmation recommended for high-value targets."
        )

    result.duration_s = time.monotonic() - started
    return result


def _check_onsite_paths(ctx: ProbeContext, client: httpx.Client, paths: list[str]) -> list[dict]:
    hits = []
    for path in paths:
        url = join(ctx.origin, path)
        resp = safe_get(client, url)
        if resp is None:
            continue
        if resp.status_code in (200, 202):
            ct = resp.headers.get("content-type", "").lower()
            if not _is_useful_response(resp.text, ct, url):
                continue
            snippet = (resp.text or "")[:200].replace("\n", " ")
            hits.append(
                {
                    "url": url,
                    "http_status": resp.status_code,
                    "content_type": ct,
                    "size_bytes": len(resp.content),
                    "looks_like": _what_does_it_look_like(resp.text, ct),
                    "snippet": snippet,
                }
            )
    return hits


def _check_national_registries(
    ctx: ProbeContext, client: httpx.Client, registries: dict[str, list[str]]
) -> list[dict]:
    """For the country implied by the TLD, probe its open-data portal search.
    Returns a list of {country, query_url, appears_listed, hit_count_hint}.

    We are intentionally conservative — listing presence is a hint, not proof.
    """
    hits = []
    cc = country_from_tld(ctx.target_host)
    candidates = []
    if cc and cc in registries:
        candidates.extend(registries[cc])
    # Always also check EU portal for any European TLD
    if cc and cc != "EU":
        candidates.extend(registries.get("EU", []))

    host_query = ctx.target_host
    short = host_query.replace("www.", "").split(".")[0]

    for tmpl in candidates[:4]:  # cap probes — registries can be slow
        url = tmpl.replace("{host}", quote_plus(short))
        resp = safe_get(client, url)
        if resp is None or resp.status_code >= 400:
            continue
        text = resp.text or ""
        appears = _registry_hit_heuristic(text, ctx.target_host, short)
        hits.append(
            {
                "country": cc,
                "registry_search_url": url,
                "http_status": resp.status_code,
                "appears_listed": appears,
                "note": "Heuristic match in search results. Manual confirmation recommended."
                if appears
                else "No clear match in search results.",
            }
        )
    return hits


def _registry_hit_heuristic(html: str, host: str, short: str) -> bool:
    if not html:
        return False
    h = host.lower()
    s = short.lower()
    body = html.lower()
    # Two-out-of-three: domain mentioned, short-name mentioned, and a result-page marker
    markers = [
        "dataset" in body or "data set" in body,
        h in body or f"//{h}" in body,
        s in body and len(s) >= 4,
    ]
    return sum(markers) >= 2


def _is_useful_response(text: str, ct: str, url: str = "") -> bool:
    """A response counts as 'bulk data' only if it has structured-data content type
    or its URL clearly points to structured data. HTML alone is not enough — many
    sites return a generic HTML page (or WAF block) for unknown paths."""
    if not text:
        return False
    if any(k in ct for k in ("json", "xml", "csv", "rss", "atom", "text/plain")):
        # Still reject if it's actually an HTML page mislabelled
        head = text[:200].lstrip().lower()
        return not (head.startswith("<!doctype html") or head.startswith("<html"))
    # Path-based whitelist: if the URL ends in a data extension, trust it
    url_lower = url.lower()
    if any(
        url_lower.endswith(ext) for ext in (".json", ".xml", ".csv", ".tsv", ".rss", ".atom", ".gz")
    ):
        head = text[:200].lstrip().lower()
        return not (head.startswith("<!doctype html") or head.startswith("<html"))
    # Plain HTML pages do not count as bulk data, even if structured-data markers are present
    return False


def _what_does_it_look_like(text: str, ct: str) -> str:
    sample = (text or "")[:400].lstrip().lower()
    if "json" in ct or sample.startswith("{") or sample.startswith("["):
        return "json"
    if "xml" in ct or sample.startswith("<?xml") or "<feed" in sample or "<rss" in sample:
        return "xml/rss/atom"
    if "csv" in ct:
        return "csv"
    if "<html" in sample[:80]:
        return "html"
    return "unknown"


def _summarize(onsite: list[dict], registry: list[dict]) -> str | None:
    if onsite:
        kinds = sorted({h["looks_like"] for h in onsite})
        sample = onsite[0]["url"]
        return f"On-site bulk-data endpoint(s) responded with structured data ({', '.join(kinds)}). Example: {sample}"
    listed = [r for r in registry if r.get("appears_listed")]
    if listed:
        return f"Possible listing in national open-data registry ({listed[0].get('country')}). Manual verification recommended."
    return None
