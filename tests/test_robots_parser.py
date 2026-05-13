from scrapeprobe.probes.robots import _parse_robots


def test_parse_robots_basic():
    text = """\
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /public/
Crawl-delay: 2

Sitemap: https://example.com/sitemap.xml
"""
    result = _parse_robots(text)
    assert result["user_agent_rules"]["*"]["disallow"] == ["/admin/", "/private/"]
    assert result["user_agent_rules"]["*"]["allow"] == ["/public/"]
    assert result["crawl_delay_s"] == 2.0
    assert "https://example.com/sitemap.xml" in result["sitemaps"]
    assert not result["disallow_all"]


def test_parse_robots_disallow_all():
    text = "User-agent: *\nDisallow: /\n"
    result = _parse_robots(text)
    assert result["disallow_all"]


def test_parse_robots_multiple_user_agents():
    text = """\
User-agent: googlebot
Disallow: /no-google/

User-agent: *
Disallow: /all-bots/
"""
    result = _parse_robots(text)
    assert result["user_agent_rules"]["googlebot"]["disallow"] == ["/no-google/"]
    assert result["user_agent_rules"]["*"]["disallow"] == ["/all-bots/"]


def test_parse_robots_handles_comments():
    text = """\
# This is a comment
User-agent: *  # inline comment
Disallow: /x/ # another
"""
    result = _parse_robots(text)
    assert "/x/" in result["user_agent_rules"]["*"]["disallow"]


def test_parse_robots_empty():
    result = _parse_robots("")
    assert result["user_agent_rules"] == {}
    assert result["sitemaps"] == []
    assert not result["disallow_all"]
