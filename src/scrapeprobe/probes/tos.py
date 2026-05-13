"""Terms-of-Service probe — find the TOS page, grep for scraping-relevant keywords.

We surface what's there; we do NOT legal-opine.
"""

from __future__ import annotations

import json
import re
import time
from importlib import resources

import httpx
from bs4 import BeautifulSoup

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get
from scrapeprobe.utils.url import is_same_host, join

_DATA: dict | None = None


def _load() -> dict:
    global _DATA
    if _DATA is None:
        ref = resources.files("scrapeprobe.data").joinpath("tos_keywords.json")
        _DATA = json.loads(ref.read_text(encoding="utf-8"))
    return _DATA


def run(ctx: ProbeContext, client: httpx.Client) -> ProbeResult:
    started = time.monotonic()
    data = _load()
    result = ProbeResult(name="tos")

    # Candidate URL pool: from data + homepage footer links
    pool: list[str] = [join(ctx.origin, p) for p in data["candidate_paths"]]
    pool.extend(_homepage_footer_candidates(ctx, client))
    pool = _dedupe_preserve(pool)

    found_pages = []
    for url in pool[:8]:  # cap to keep probe under budget
        resp = safe_get(client, url)
        if resp is None or resp.status_code >= 400:
            continue
        if "html" not in resp.headers.get("content-type", "").lower():
            continue
        text = _extract_text(resp.text or "")
        if len(text) < 400:
            continue  # too short to be a real TOS page
        found_pages.append({"url": url, "http_status": resp.status_code, "text": text[:50_000]})
        result.evidence.append(Evidence(url=url, status_code=resp.status_code, snippet=text[:200]))
        if len(found_pages) >= 2:
            break

    if not found_pages:
        result.status = "partial"
        result.findings = {
            "pages_found": [],
            "scraping_keywords_hit": [],
            "languages_detected": [],
            "note": "No TOS / Terms / legal page found at common paths.",
        }
        result.duration_s = time.monotonic() - started
        return result

    hits = []
    langs_detected: set[str] = set()
    for page in found_pages:
        for lang, patterns in data["keywords"].items():
            for pat in patterns:
                for match in re.finditer(pat, page["text"], re.IGNORECASE):
                    snippet = _context_snippet(page["text"], match.start(), match.end())
                    hits.append(
                        {
                            "url": page["url"],
                            "language": lang,
                            "pattern": pat,
                            "matched": match.group(0),
                            "context": snippet,
                        }
                    )
                    langs_detected.add(lang)

    result.findings = {
        "pages_found": [
            {"url": p["url"], "http_status": p["http_status"], "chars": len(p["text"])}
            for p in found_pages
        ],
        "scraping_keywords_hit": hits[:25],
        "scraping_keyword_hit_count": len(hits),
        "languages_detected": sorted(langs_detected),
    }
    result.duration_s = time.monotonic() - started
    return result


def _homepage_footer_candidates(ctx: ProbeContext, client: httpx.Client) -> list[str]:
    resp = safe_get(client, ctx.target_url)
    if resp is None or resp.status_code >= 400:
        return []
    soup = BeautifulSoup(resp.text or "", "lxml")
    # Look in footer or in links matching TOS-ish anchor text
    candidates = []
    needles = (
        "terms",
        "tos",
        "legal",
        "impressum",
        "agb",
        "voorwaard",
        "conditions",
        "mentions",
        "datenschutz",
        "termin",
        "condizioni",
        "privacy",
    )
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip().lower()
        href = a["href"]
        if any(n in text for n in needles) or any(n in href.lower() for n in needles):
            absu = join(ctx.target_url, href)
            if is_same_host(absu, ctx.target_url):
                candidates.append(absu)
    return candidates


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        norm = item.rstrip("/").lower()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(item)
    return out


def _extract_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _context_snippet(text: str, start: int, end: int, width: int = 80) -> str:
    s = max(0, start - width)
    e = min(len(text), end + width)
    return text[s:e].replace("\n", " ").strip()
