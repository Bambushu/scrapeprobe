from scrapeprobe.probes.sitemap import _classify, _extract_locs

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com/a</loc></url>
<url><loc>https://example.com/b</loc></url>
<url><loc>https://example.com/c</loc></url>
</urlset>"""

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
<sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>"""

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Item 1</title></item>
<item><title>Item 2</title></item>
</channel></rss>"""


def test_classify_urlset():
    kind, count, children = _classify(URLSET, "application/xml")
    assert kind == "sitemap"
    assert count == 3
    assert children == []


def test_classify_sitemap_index():
    kind, count, children = _classify(SITEMAP_INDEX, "application/xml")
    assert kind == "sitemap_index"
    assert len(children) == 2
    assert "https://example.com/sitemap-1.xml" in children


def test_classify_rss():
    kind, count, children = _classify(RSS, "application/rss+xml")
    assert kind == "rss"
    assert count == 2


def test_classify_empty():
    kind, count, children = _classify("", "")
    assert kind == "empty"
    assert count == 0


def test_extract_locs_handles_namespaces():
    body = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap>
        <loc>https://example.com/a.xml</loc>
        <lastmod>2026-01-01</lastmod>
      </sitemap>
      <sitemap><loc>https://example.com/b.xml</loc></sitemap>
    </sitemapindex>
    """
    locs = _extract_locs(body, "sitemap")
    assert locs == ["https://example.com/a.xml", "https://example.com/b.xml"]
