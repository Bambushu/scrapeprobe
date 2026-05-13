"""Anti-bot / WAF probe — wraps wafw00f and adds our own signature DB."""

from __future__ import annotations

import json
import re
import time
from importlib import resources

import httpx

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get

_SIGNATURES: dict | None = None


def _load_signatures() -> dict:
    global _SIGNATURES
    if _SIGNATURES is None:
        ref = resources.files("scrapeprobe.data").joinpath("antibot_signatures.json")
        _SIGNATURES = json.loads(ref.read_text(encoding="utf-8"))
    return _SIGNATURES


def run(ctx: ProbeContext, client: httpx.Client) -> ProbeResult:
    started = time.monotonic()
    result = ProbeResult(name="antibot")

    resp = safe_get(client, ctx.target_url)
    if resp is None:
        result.status = "error"
        result.error = "Could not reach target for anti-bot probe"
        result.duration_s = time.monotonic() - started
        return result

    result.evidence.append(
        Evidence(url=ctx.target_url, status_code=resp.status_code, snippet=resp.text[:200])
    )

    matches = _match_signatures(resp)
    wafw00f_result = _run_wafw00f(ctx.target_url)

    severities = [m["severity"] for m in matches] + (
        ["high"] if wafw00f_result.get("detected") else []
    )
    overall = (
        "high"
        if "high" in severities
        else ("medium" if "medium" in severities else ("low" if "low" in severities else "none"))
    )

    blocked = resp.status_code in (403, 406, 429, 503) or _looks_like_challenge(resp.text)

    result.findings = {
        "wafw00f": wafw00f_result,
        "signature_matches": matches,
        "overall_severity": overall,
        "looks_blocked_on_recon": blocked,
        "response_status": resp.status_code,
    }

    if blocked:
        result.status = "blocked"
    elif not matches and not wafw00f_result.get("detected"):
        result.status = "partial"
        result.findings["note"] = (
            "No anti-bot signatures detected. May still have rate limits or downstream WAF rules."
        )

    result.duration_s = time.monotonic() - started
    return result


def _match_signatures(resp: httpx.Response) -> list[dict]:
    sigs = _load_signatures()
    matches = []
    text = resp.text or ""
    for name, sig in sigs.items():
        if name.startswith("_"):
            continue
        hit_reasons = []
        if "match_headers" in sig:
            for header, pattern in sig["match_headers"].items():
                # set-cookie may have multiple values; httpx joins them in headers dict, raw is preserved
                hval = resp.headers.get(header, "")
                if not hval and header.lower() == "set-cookie":
                    hval = "\n".join(
                        v for k, v in resp.headers.multi_items() if k.lower() == "set-cookie"
                    )
                if hval and re.search(pattern, hval, re.IGNORECASE):
                    hit_reasons.append(f"header:{header}")
        if "match_html" in sig and re.search(sig["match_html"], text, re.IGNORECASE):
            hit_reasons.append("html")
        if "match_html_negative" in sig and re.search(
            sig["match_html_negative"], text, re.IGNORECASE
        ):
            hit_reasons = []  # negative match cancels this signature
            continue
        if "match_scripts" in sig and re.search(sig["match_scripts"], text, re.IGNORECASE):
            hit_reasons.append("script")
        if hit_reasons:
            matches.append(
                {
                    "name": name,
                    "severity": sig.get("severity", "medium"),
                    "matched_on": hit_reasons,
                    "note": sig.get("note"),
                }
            )
    return matches


def _looks_like_challenge(html: str) -> bool:
    if not html:
        return False
    needles = (
        "Just a moment",
        "Checking your browser",
        "challenge-platform",
        "enable JavaScript and cookies",
        "DDoS protection",
        "Verifying you are human",
        "captcha-delivery",
    )
    return any(n.lower() in html.lower() for n in needles)


def _run_wafw00f(url: str) -> dict:
    try:
        from wafw00f.main import WAFW00F
    except Exception as exc:  # pragma: no cover
        return {"detected": False, "error": f"wafw00f import failed: {exc}"}
    try:
        scanner = WAFW00F(url, debuglevel=0, followredirect=True)
        scanner.normalRequest()
        identified = scanner.identwaf(findall=False)
        generic = scanner.genericdetect()
        return {
            "detected": bool(identified) or bool(generic),
            "identified": _flatten_waf_names(identified),
            "generic_signal": bool(generic),
        }
    except Exception as exc:
        return {"detected": False, "error": f"wafw00f raised: {exc.__class__.__name__}: {exc}"}


def _flatten_waf_names(raw) -> list[str]:
    """wafw00f.identwaf can return strings, tuples, nested lists, or odd structures
    depending on version. Be defensive: keep only printable WAF-name-looking strings."""
    if not raw:
        return []
    out: list[str] = []
    for item in raw:
        candidate = None
        if isinstance(item, str):
            candidate = item.strip()
        elif isinstance(item, (list, tuple)) and item:
            first = item[0]
            if isinstance(first, str):
                candidate = first.strip()
        if not candidate:
            continue
        # Reject obvious non-names (URLs, query strings, payloads)
        if (
            candidate.startswith(("http://", "https://"))
            or "%3C" in candidate
            or "%20" in candidate
        ):
            continue
        if len(candidate) > 80:
            continue
        out.append(candidate)
    return out
