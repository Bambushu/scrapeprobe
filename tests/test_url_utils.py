from scrapeprobe.utils.url import (
    country_from_tld,
    host_of,
    is_same_host,
    normalize_url,
    origin_of,
)


def test_normalize_url_adds_scheme():
    assert normalize_url("example.com").startswith("https://")


def test_normalize_url_lowercases_host():
    assert normalize_url("https://Example.COM/Path") == "https://example.com/Path"


def test_normalize_url_strips_fragment():
    assert "#fragment" not in normalize_url("https://example.com/page#fragment")


def test_origin_of():
    assert origin_of("https://example.com/some/path?q=1") == "https://example.com"


def test_host_of():
    assert host_of("https://www.example.co.uk/x") == "www.example.co.uk"


def test_is_same_host():
    assert is_same_host("https://example.com/a", "https://example.com/b")
    assert not is_same_host("https://example.com/a", "https://other.example.com/a")


def test_country_from_tld():
    assert country_from_tld("firmen.wko.at") == "AT"
    assert country_from_tld("apps.cra-arc.gc.ca") == "CA"
    assert country_from_tld("example.de") == "DE"
    assert country_from_tld("example.com") is None
    assert country_from_tld("example.io") is None
