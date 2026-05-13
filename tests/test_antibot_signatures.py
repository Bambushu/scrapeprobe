"""Pure-function tests for the antibot signature matcher.

Builds a synthetic httpx.Response to drive _match_signatures without network IO.
"""

import httpx

from scrapeprobe.probes.antibot import _looks_like_challenge, _match_signatures


def _resp(*, status=200, text="", headers=None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers=headers or {},
        text=text,
        request=httpx.Request("GET", "https://example.com/"),
    )


def test_cloudflare_passive_detection():
    matches = _match_signatures(
        _resp(
            headers={"server": "cloudflare", "cf-ray": "abc123-AMS"},
            text="<html><body>Hello world</body></html>",
        )
    )
    names = [m["name"] for m in matches]
    assert "Cloudflare CDN (passive)" in names


def test_cloudflare_active_challenge():
    matches = _match_signatures(
        _resp(
            headers={"cf-mitigated": "challenge"},
            text="Just a moment...",
        )
    )
    names = [m["name"] for m in matches]
    assert "Cloudflare WAF (Pro+)" in names
    # The high-severity active one should be present
    severities = [m["severity"] for m in matches if m["name"] == "Cloudflare WAF (Pro+)"]
    assert "high" in severities


def test_imperva_detection():
    matches = _match_signatures(
        _resp(
            headers={"x-iinfo": "12345", "set-cookie": "visid_incap_abc=xyz; HttpOnly"},
        )
    )
    names = [m["name"] for m in matches]
    assert "Imperva / Incapsula" in names


def test_akamai_detection():
    matches = _match_signatures(
        _resp(
            headers={"set-cookie": "_abck=ABCD1234; ak_bmsc=XYZ"},
        )
    )
    names = [m["name"] for m in matches]
    assert "Akamai Bot Manager" in names


def test_no_matches_for_clean_response():
    matches = _match_signatures(_resp(headers={"server": "nginx"}, text="<html></html>"))
    assert matches == []


def test_looks_like_challenge_positive():
    assert _looks_like_challenge("Please enable JavaScript and cookies to continue")
    assert _looks_like_challenge("Just a moment... DDoS protection by Cloudflare")
    assert _looks_like_challenge("Verifying you are human")


def test_looks_like_challenge_negative():
    assert not _looks_like_challenge("Welcome to our normal website.")
    assert not _looks_like_challenge("")
