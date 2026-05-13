"""Robots.txt probe — fetch, parse, expose disallow paths + crawl-delay for downstream probes."""

from __future__ import annotations

import re
import time

import httpx

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get
from scrapeprobe.utils.url import join


def run(ctx: ProbeContext, client: httpx.Client) -> ProbeResult:
    started = time.monotonic()
    url = join(ctx.origin, "/robots.txt")
    result = ProbeResult(name="robots")

    resp = safe_get(client, url)
    if resp is None:
        result.status = "error"
        result.error = "Could not reach /robots.txt (network failure)"
        result.duration_s = time.monotonic() - started
        return result

    result.evidence.append(Evidence(url=url, status_code=resp.status_code, snippet=resp.text[:240]))

    if resp.status_code >= 400:
        result.status = "partial"
        result.findings = {
            "present": False,
            "http_status": resp.status_code,
            "user_agent_rules": {},
            "sitemaps": [],
            "disallow_all": False,
            "crawl_delay_s": None,
        }
        result.duration_s = time.monotonic() - started
        return result

    parsed = _parse_robots(resp.text)
    result.findings = {
        "present": True,
        "http_status": resp.status_code,
        "size_bytes": len(resp.content),
        **parsed,
    }

    # Propagate hints to context for downstream probes.
    star_rules = parsed["user_agent_rules"].get("*", {})
    ctx.disallow_paths = star_rules.get("disallow", [])
    if parsed["crawl_delay_s"] is not None:
        ctx.crawl_delay_s = parsed["crawl_delay_s"]

    result.duration_s = time.monotonic() - started
    return result


def _parse_robots(text: str) -> dict:
    user_agent_rules: dict[str, dict[str, list[str]]] = {}
    sitemaps: list[str] = []
    current_uas: list[str] = []
    crawl_delays: dict[str, float] = {}

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        directive, value = line.split(":", 1)
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            if not current_uas or _previous_block_had_rules(user_agent_rules, current_uas):
                current_uas = [value.lower()]
            else:
                current_uas.append(value.lower())
            for ua in current_uas:
                user_agent_rules.setdefault(ua, {"allow": [], "disallow": []})
        elif directive in ("allow", "disallow") and current_uas:
            for ua in current_uas:
                user_agent_rules.setdefault(ua, {"allow": [], "disallow": []})
                user_agent_rules[ua][directive].append(value)
        elif directive == "crawl-delay" and current_uas:
            try:
                d = float(value)
                for ua in current_uas:
                    crawl_delays[ua] = d
            except ValueError:
                pass
        elif directive == "sitemap":
            sitemaps.append(value)

    star_rules = user_agent_rules.get("*", {"allow": [], "disallow": []})
    disallow_all = any(_normalize_path(p) == "/" for p in star_rules.get("disallow", []))
    star_delay = crawl_delays.get("*")

    return {
        "user_agent_rules": user_agent_rules,
        "sitemaps": sitemaps,
        "disallow_all": disallow_all,
        "crawl_delay_s": star_delay,
        "crawl_delays_all_agents": crawl_delays,
    }


def _previous_block_had_rules(rules: dict, uas: list[str]) -> bool:
    for ua in uas:
        if rules.get(ua) and (rules[ua]["allow"] or rules[ua]["disallow"]):
            return True
    return False


def _normalize_path(path: str) -> str:
    path = path.strip()
    if not path:
        return ""
    return re.sub(r"\s+", "", path)
