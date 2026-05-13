"""Jurisdiction / GDPR heuristic probe.

Surfaces:
- TLD-implied country
- Response header `country` / `cf-ipcountry` if present
- Whether the page sets EU-style cookie-consent banners (markers only, not blocking)

This is NOT legal advice. Just flags."""

from __future__ import annotations

import re
import time

import httpx

from scrapeprobe.models import Evidence, ProbeContext, ProbeResult
from scrapeprobe.utils.http import safe_get
from scrapeprobe.utils.url import country_from_tld

EU_EEA = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
    "IS",
    "LI",
    "NO",
    "EU",
}


def run(ctx: ProbeContext, client: httpx.Client) -> ProbeResult:
    started = time.monotonic()
    result = ProbeResult(name="jurisdiction")

    cc = country_from_tld(ctx.target_host)
    resp = safe_get(client, ctx.target_url)

    header_cc = None
    has_consent_banner = False
    consent_signals: list[str] = []

    if resp is not None:
        header_cc = (
            resp.headers.get("cf-ipcountry")
            or resp.headers.get("country")
            or resp.headers.get("x-country-code")
        )
        text = resp.text or ""
        consent_signals = _consent_signals(text)
        has_consent_banner = bool(consent_signals)
        result.evidence.append(
            Evidence(url=ctx.target_url, status_code=resp.status_code, snippet=text[:200])
        )

    effective_cc = (header_cc or cc or "").upper() or None
    is_eu = effective_cc in EU_EEA if effective_cc else False

    result.findings = {
        "tld_country": cc,
        "header_country": header_cc,
        "effective_country_guess": effective_cc,
        "is_eu_eea": is_eu,
        "gdpr_applies_heuristic": is_eu or bool(consent_signals),
        "has_consent_banner_markers": has_consent_banner,
        "consent_banner_markers": consent_signals,
        "note": (
            "EU/EEA jurisdiction likely. Scraping plans should consider GDPR (legitimate-interest analysis, "
            "data minimization, no personal data collection without lawful basis)."
            if (is_eu or has_consent_banner)
            else "Non-EU TLD and no EU consent banner detected. GDPR may still apply if EU residents' "
            "data is collected. Confirm before scraping personal data."
        ),
    }
    if not effective_cc and not has_consent_banner:
        result.status = "partial"

    result.duration_s = time.monotonic() - started
    return result


def _consent_signals(html: str) -> list[str]:
    if not html:
        return []
    needles = {
        "cookiebot": r"\bcookiebot\b",
        "onetrust": r"\bonetrust\b|optanon",
        "cookieyes": r"\bcookieyes\b",
        "complianz": r"\bcomplianz\b",
        "didomi": r"\bdidomi\b",
        "iubenda": r"\biubenda\b",
        "trustarc": r"\btrustarc\b",
        "klaro": r"\bklaro\b",
        "tarteaucitron": r"\btarteaucitron\b",
        "borlabs": r"\bborlabs\b",
        "generic-gdpr-banner": r"gdpr[-_]?(?:notice|banner|consent)|cookie[-_]?(?:notice|banner|consent)",
    }
    found = []
    for label, pat in needles.items():
        if re.search(pat, html, re.IGNORECASE):
            found.append(label)
    return found
