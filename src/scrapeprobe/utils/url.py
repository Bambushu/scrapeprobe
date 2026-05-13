"""URL normalization helpers."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

import tldextract


def normalize_url(url: str) -> str:
    """Ensure scheme + lowercase host. Strip trailing slash on bare hosts only."""
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def host_of(url: str) -> str:
    return urlsplit(url).netloc.lower()


def scheme_of(url: str) -> str:
    return urlsplit(url).scheme.lower()


def join(base: str, path: str) -> str:
    return urljoin(base, path)


def country_from_tld(host: str) -> str | None:
    """Return a best-guess ISO country code based on the public-suffix TLD.
    Returns None for generic TLDs (.com, .org, .io, .ai, etc.)."""
    extracted = tldextract.extract(host)
    suffix = extracted.suffix.lower()
    # Multi-part suffixes like 'co.uk', 'gov.at'
    parts = suffix.split(".")
    last = parts[-1]
    cc_map = {
        "at": "AT",
        "de": "DE",
        "nl": "NL",
        "be": "BE",
        "uk": "UK",
        "fr": "FR",
        "it": "IT",
        "es": "ES",
        "se": "SE",
        "no": "NO",
        "dk": "DK",
        "fi": "FI",
        "ch": "CH",
        "ie": "IE",
        "pt": "PT",
        "pl": "PL",
        "cz": "CZ",
        "us": "US",
        "ca": "CA",
        "au": "AU",
        "nz": "NZ",
        "eu": "EU",
        "lu": "LU",
        "gr": "GR",
        "ro": "RO",
        "hu": "HU",
        "sk": "SK",
        "si": "SI",
        "hr": "HR",
        "bg": "BG",
        "ee": "EE",
        "lv": "LV",
        "lt": "LT",
        "is": "IS",
        "mt": "MT",
        "cy": "CY",
    }
    if last in cc_map:
        return cc_map[last]
    # Common multipart like .gov.at → AT
    if len(parts) > 1 and parts[-1] in cc_map:
        return cc_map[parts[-1]]
    return None


def is_same_host(url_a: str, url_b: str) -> bool:
    return host_of(url_a) == host_of(url_b)


def looks_like_url(s: str) -> bool:
    try:
        p = urlparse(s)
        return bool(p.scheme) and bool(p.netloc)
    except Exception:
        return False
