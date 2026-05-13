"""Sitemap discovery probe — sitemap.xml, sitemap_index.xml, RSS feeds; estimate URL count."""

from __future__ import annotations

import gzip
import re
import time
from xml.etree import ElementTree as ET

import httpx

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get
from scrapeprobe.utils.url import join

CANDIDATE_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap1.xml",
    "/sitemaps.xml",
    "/wp-sitemap.xml",
    "/sitemap.xml.gz",
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/atom.xml",
]

MAX_SUB_SITEMAPS_TO_PROBE = 8


def run(
    ctx: ProbeContext,
    client: httpx.Client,
    seed_sitemaps: list[str] | None = None,
) -> ProbeResult:
    started = time.monotonic()
    result = ProbeResult(name="sitemap")
    found: list[dict] = []

    candidates = list(seed_sitemaps or [])
    candidates.extend(join(ctx.origin, p) for p in CANDIDATE_PATHS)
    seen = set()

    for url in candidates:
        if url in seen:
            continue
        seen.add(url)

        resp = safe_get(client, url)
        if resp is None or resp.status_code >= 400:
            continue

        body = resp.text
        # Some sites ship sitemap files as .gz literal payload (not HTTP gzip Content-Encoding).
        # httpx already decoded any Content-Encoding gzip — anything still .gz here is in-file.
        if url.lower().endswith(".gz"):
            try:
                body = gzip.decompress(resp.content).decode("utf-8", errors="replace")
            except (OSError, EOFError):
                pass  # leave as-is; classifier will mark non_xml and we'll skip it
        kind, url_count, child_sitemaps = _classify(body, resp.headers.get("content-type", ""))
        if kind in ("non_xml", "unknown_xml", "empty"):
            # Avoid surfacing the site's generic HTML 404 page as a "sitemap".
            continue
        found.append(
            {
                "url": url,
                "kind": kind,
                "url_count_estimate": url_count,
                "child_sitemap_count": len(child_sitemaps),
                "size_bytes": len(resp.content),
                "http_status": resp.status_code,
            }
        )
        result.evidence.append(
            Evidence(url=url, status_code=resp.status_code, snippet=resp.text[:200], note=kind)
        )

        # For sitemap indexes, peek at a few children to estimate scale.
        if kind == "sitemap_index" and child_sitemaps:
            for child in child_sitemaps[:MAX_SUB_SITEMAPS_TO_PROBE]:
                if child in seen:
                    continue
                seen.add(child)
                cresp = safe_get(client, child)
                if cresp is None or cresp.status_code >= 400:
                    continue
                cbody = cresp.text
                if child.lower().endswith(".gz"):
                    try:
                        cbody = gzip.decompress(cresp.content).decode("utf-8", errors="replace")
                    except (OSError, EOFError):
                        pass
                ckind, c_url_count, _ = _classify(cbody, cresp.headers.get("content-type", ""))
                found.append(
                    {
                        "url": child,
                        "kind": ckind,
                        "url_count_estimate": c_url_count,
                        "child_sitemap_count": 0,
                        "size_bytes": len(cresp.content),
                        "http_status": cresp.status_code,
                        "parent": url,
                    }
                )

    total_urls = sum(f["url_count_estimate"] for f in found if f["url_count_estimate"])
    result.findings = {
        "sitemaps_found": found,
        "sitemap_count": len(found),
        "total_url_count_estimate": total_urls,
        "has_rss_feed": any("rss" in f["kind"] or "atom" in f["kind"] for f in found),
    }
    if not found:
        result.status = "partial"
        result.findings["note"] = "No sitemap or RSS feed detected at common paths."

    result.duration_s = time.monotonic() - started
    return result


def _classify(body: str, content_type: str) -> tuple[str, int, list[str]]:
    """Return (kind, url_count_estimate, child_sitemap_urls)."""
    ct = (content_type or "").lower()
    if not body:
        return "empty", 0, []

    head = body[:1024].lower()
    is_xml = "<?xml" in head or "xml" in ct
    if "<rss" in head:
        return "rss", body.lower().count("<item"), []
    if "<feed" in head and "atom" in head:
        return "atom", body.lower().count("<entry"), []
    if "<sitemapindex" in head:
        children = _extract_locs(body, "sitemap")
        return "sitemap_index", 0, children
    if "<urlset" in head:
        # Cheap count — number of <url> / <loc> pairs.
        return "sitemap", body.lower().count("<url>"), []
    if is_xml:
        # Try to parse for tag clues
        try:
            root = ET.fromstring(body)
            tag = root.tag.split("}")[-1].lower()
            if tag == "sitemapindex":
                return "sitemap_index", 0, _extract_locs(body, "sitemap")
            if tag == "urlset":
                return "sitemap", body.lower().count("<url>"), []
        except ET.ParseError:
            pass
    return "unknown_xml" if is_xml else "non_xml", 0, []


def _extract_locs(body: str, parent_tag: str) -> list[str]:
    """Quick regex pull of <loc> inside <sitemap> entries. Avoids namespace headaches."""
    pattern = rf"<{parent_tag}>\s*<loc>([^<]+)</loc>"
    return [m.strip() for m in re.findall(pattern, body, re.IGNORECASE)]
