from bs4 import BeautifulSoup

from scrapeprobe.probes.discovery import _analyze_forms, _detect_id_enum, _detect_pagination


def test_analyze_forms_finds_search_form():
    html = """
    <form action="/search" method="get">
      <input name="q" type="text">
      <input name="submit" type="submit">
    </form>
    """
    soup = BeautifulSoup(html, "lxml")
    forms = _analyze_forms(soup)
    assert forms["search_form"]["action"] == "/search"
    assert "q" in forms["search_form"]["input_names"]


def test_analyze_forms_finds_alphabet_links():
    anchors = "".join(f'<a href="/letter/{c}">{c}</a>' for c in "ABCDEFGHIJKLMNOP")
    soup = BeautifulSoup(anchors, "lxml")
    forms = _analyze_forms(soup)
    assert forms["has_alphabet_links"]


def test_detect_pagination_via_rel_next():
    html = '<link rel="next" href="/page/2">'
    soup = BeautifulSoup(html, "lxml")
    result = _detect_pagination(html, soup)
    assert result["has_pagination"]
    assert result["pattern"] == "rel=next"


def test_detect_pagination_via_querystring():
    html = '<a href="/items?page=2">Next</a>'
    soup = BeautifulSoup(html, "lxml")
    result = _detect_pagination(html, soup)
    assert result["has_pagination"]


def test_detect_pagination_none():
    html = "<div>no pagination here</div>"
    soup = BeautifulSoup(html, "lxml")
    result = _detect_pagination(html, soup)
    assert not result["has_pagination"]


def test_detect_id_enum_positive():
    html = """
    <a href="/items/100">A</a>
    <a href="/items/101">B</a>
    <a href="/items/102">C</a>
    <a href="/items/103">D</a>
    """
    soup = BeautifulSoup(html, "lxml")
    result = _detect_id_enum(html, soup, "example.com")
    assert result["likely"]
    assert result["url_prefix"] == "/items/"
    assert result["sample_count"] == 4


def test_detect_id_enum_negative():
    html = '<a href="/page-1">A</a><a href="/about">B</a>'
    soup = BeautifulSoup(html, "lxml")
    result = _detect_id_enum(html, soup, "example.com")
    assert not result["likely"]
