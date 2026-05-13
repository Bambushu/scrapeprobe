"""Discovery path heuristics — classify likely traversal strategies for the target."""

from __future__ import annotations

import re
import time

import httpx
from bs4 import BeautifulSoup

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get


def run(
    ctx: ProbeContext,
    client: httpx.Client,
    sitemap_findings: dict | None = None,
) -> ProbeResult:
    started = time.monotonic()
    result = ProbeResult(name="discovery")

    resp = safe_get(client, ctx.target_url)
    if resp is None:
        result.status = "error"
        result.error = "Could not reach target for discovery probe"
        result.duration_s = time.monotonic() - started
        return result

    html = resp.text or ""
    soup = BeautifulSoup(html, "lxml")

    forms = _analyze_forms(soup)
    pagination = _detect_pagination(html, soup)
    id_enum = _detect_id_enum(html, soup, ctx.target_host)

    sitemap_urls = (sitemap_findings or {}).get("total_url_count_estimate", 0)

    strategies = []
    if sitemap_urls > 100:
        strategies.append(
            {
                "name": "sitemap_walk",
                "score": "high",
                "reason": f"Sitemap exposes ~{sitemap_urls} URLs. Cheapest, most polite path.",
            }
        )
    if forms["search_form"]:
        strategies.append(
            {
                "name": "search_form_traversal",
                "score": "medium",
                "reason": f"Search form detected at {forms['search_form']['action']}. "
                f"Inputs: {', '.join(forms['search_form']['input_names'])}.",
            }
        )
    if forms["has_alphabet_links"]:
        strategies.append(
            {
                "name": "alphabet_traversal",
                "score": "medium",
                "reason": "A-Z anchor links present. Classic alphabet-pagination directory.",
            }
        )
    if pagination["has_pagination"]:
        strategies.append(
            {
                "name": "category_pagination",
                "score": "medium",
                "reason": f"Pagination detected ({pagination['pattern']}). Walk page=1..N.",
            }
        )
    if id_enum["likely"]:
        strategies.append(
            {
                "name": "id_enumeration",
                "score": "medium",
                "reason": f"Sequential numeric IDs in URL pattern: {id_enum['example']}",
            }
        )
    if not strategies:
        strategies.append(
            {
                "name": "manual_inspection_required",
                "score": "unknown",
                "reason": "No obvious discovery primitive detected. Manual exploration needed.",
            }
        )

    result.findings = {
        "strategies": strategies,
        "forms": forms,
        "pagination": pagination,
        "id_enum": id_enum,
    }
    result.evidence.append(
        Evidence(url=ctx.target_url, status_code=resp.status_code, snippet=html[:200])
    )

    result.duration_s = time.monotonic() - started
    return result


def _analyze_forms(soup: BeautifulSoup) -> dict:
    forms = soup.find_all("form")
    search_form = None
    has_alphabet = False

    for form in forms:
        action = form.get("action", "") or ""
        inputs = form.find_all(["input", "select"])
        names = [i.get("name", "") for i in inputs if i.get("name")]
        types = [i.get("type", "") for i in inputs]
        joined = " ".join(names + [action]).lower()
        if any(
            k in joined for k in ("search", "query", "q=", "keyword", "suche", "zoek", "recherche")
        ):
            search_form = {
                "action": action,
                "method": (form.get("method") or "get").lower(),
                "input_names": names,
                "input_types": types,
            }
            break

    alphabet_anchors = soup.find_all("a", string=re.compile(r"^[A-Z]$"))
    if len(alphabet_anchors) >= 10:
        has_alphabet = True

    return {
        "form_count": len(forms),
        "search_form": search_form,
        "has_alphabet_links": has_alphabet,
    }


def _detect_pagination(html: str, soup: BeautifulSoup) -> dict:
    if not html:
        return {"has_pagination": False, "pattern": None}

    next_link = soup.find("a", string=re.compile(r"(?i)next|nächste|volgende|suivant|siguiente"))
    nav_classes = soup.find_all(class_=re.compile(r"(?i)pag(?:e|inat)"))
    rel_next = soup.find("link", rel="next") or soup.find("a", rel="next")

    if rel_next:
        return {"has_pagination": True, "pattern": "rel=next"}
    if next_link:
        return {"has_pagination": True, "pattern": "anchor:next"}
    if nav_classes:
        return {"has_pagination": True, "pattern": f"css-class:{nav_classes[0].get('class')}"}

    qs_pages = re.findall(r"[?&](?:page|p)=(\d+)", html)
    if qs_pages:
        return {"has_pagination": True, "pattern": "querystring:page="}

    return {"has_pagination": False, "pattern": None}


def _detect_id_enum(html: str, soup: BeautifulSoup, host: str) -> dict:
    if not html:
        return {"likely": False}

    same_host_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") or host in href:
            same_host_links.append(href)

    numeric_id_pattern = re.compile(r"(/[a-z_-]+/)(\d{2,8})(?:/|$|\?)")
    matches = []
    for href in same_host_links:
        m = numeric_id_pattern.search(href)
        if m:
            matches.append((m.group(1), int(m.group(2)), href))

    if len(matches) < 3:
        return {"likely": False}

    by_prefix: dict[str, list[int]] = {}
    examples: dict[str, str] = {}
    for prefix, n, full in matches:
        by_prefix.setdefault(prefix, []).append(n)
        examples.setdefault(prefix, full)

    best_prefix = max(by_prefix, key=lambda k: len(by_prefix[k]))
    nums = sorted(by_prefix[best_prefix])
    if len(nums) >= 3 and (nums[-1] - nums[0]) < 100000:
        return {
            "likely": True,
            "url_prefix": best_prefix,
            "min_id": nums[0],
            "max_id_seen": nums[-1],
            "sample_count": len(nums),
            "example": examples[best_prefix],
        }
    return {"likely": False}
