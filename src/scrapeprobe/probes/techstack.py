"""Tech stack fingerprint probe — applies the in-tree MIT-clean fingerprint DB."""

from __future__ import annotations

import json
import re
import time
from importlib import resources

import httpx
from bs4 import BeautifulSoup

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get

_FINGERPRINTS: dict | None = None


def _load_fingerprints() -> dict:
    global _FINGERPRINTS
    if _FINGERPRINTS is None:
        ref = resources.files("scrapeprobe.data").joinpath("techstack.json")
        _FINGERPRINTS = json.loads(ref.read_text(encoding="utf-8"))
    return _FINGERPRINTS


def run(ctx: ProbeContext, client: httpx.Client) -> ProbeResult:
    started = time.monotonic()
    result = ProbeResult(name="techstack")

    resp = safe_get(client, ctx.target_url)
    if resp is None:
        result.status = "error"
        result.error = "Could not reach target for techstack probe"
        result.duration_s = time.monotonic() - started
        return result

    headers = {k.lower(): v for k, v in resp.headers.items()}
    text = resp.text or ""
    meta = _meta_tags(text)
    cookies = _cookies_from_headers(resp)

    detected = _detect(headers, cookies, text, meta)
    by_category = _group_by_category(detected)

    result.findings = {
        "detected": detected,
        "by_category": by_category,
        "detection_count": len(detected),
    }
    result.evidence.append(
        Evidence(url=ctx.target_url, status_code=resp.status_code, snippet=text[:200])
    )
    if not detected:
        result.status = "partial"
        result.findings["note"] = (
            "No known fingerprints matched. Target may use a custom stack or aggressive HTML obfuscation."
        )

    result.duration_s = time.monotonic() - started
    return result


def _meta_tags(html: str) -> dict[str, str]:
    if not html:
        return {}
    soup = BeautifulSoup(html, "lxml")
    meta = {}
    for tag in soup.find_all("meta"):
        name = (tag.get("name") or tag.get("property") or "").lower()
        if name and tag.get("content"):
            meta[name] = tag["content"]
    return meta


def _cookies_from_headers(resp: httpx.Response) -> dict[str, str]:
    """Return the raw Set-Cookie strings keyed by cookie name."""
    cookies = {}
    for k, v in resp.headers.multi_items():
        if k.lower() != "set-cookie":
            continue
        # Cookie name is everything up to the first '='
        name = v.split("=", 1)[0].strip()
        if name:
            cookies[name] = v
    return cookies


def _detect(headers: dict, cookies: dict, html: str, meta: dict) -> list[dict]:
    fps = _load_fingerprints()
    out = []
    for name, sig in fps.items():
        if name.startswith("_"):
            continue
        reasons = _match(sig, headers, cookies, html, meta)
        if reasons:
            out.append(
                {
                    "name": name,
                    "categories": sig.get("cats", []),
                    "matched_on": reasons,
                    "website": sig.get("website"),
                }
            )
    return out


def _match(sig: dict, headers: dict, cookies: dict, html: str, meta: dict) -> list[str]:
    reasons = []
    if "headers" in sig:
        for h, pattern in sig["headers"].items():
            val = headers.get(h.lower(), "")
            if val and re.search(pattern, val, re.IGNORECASE):
                reasons.append(f"header:{h}")
    if "cookies" in sig:
        for c, pattern in sig["cookies"].items():
            # Match against cookie name OR raw set-cookie line for the cookie
            for cname, craw in cookies.items():
                if re.search(c, cname, re.IGNORECASE) and re.search(pattern, craw, re.IGNORECASE):
                    reasons.append(f"cookie:{c}")
                    break
    if "html" in sig and re.search(sig["html"], html, re.IGNORECASE):
        reasons.append("html")
    if "scripts" in sig:
        scripts = _script_srcs(html)
        joined = "\n".join(scripts) + "\n" + html
        if re.search(sig["scripts"], joined, re.IGNORECASE):
            reasons.append("scripts")
    if "meta" in sig:
        for m, pattern in sig["meta"].items():
            val = meta.get(m.lower(), "")
            if val and re.search(pattern, val, re.IGNORECASE):
                reasons.append(f"meta:{m}")
    return reasons


def _script_srcs(html: str) -> list[str]:
    if not html:
        return []
    # Lightweight regex, avoids re-parsing
    return re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)


def _group_by_category(detected: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for tech in detected:
        for cat in tech.get("categories") or ["uncategorized"]:
            out.setdefault(cat, []).append(tech["name"])
    return out
