"""Pure-function tests for the techstack matcher."""

from scrapeprobe.probes.techstack import _detect, _meta_tags, _script_srcs


def test_meta_tags_extraction():
    html = """
    <html><head>
      <meta name="generator" content="WordPress 6.4.2">
      <meta name="description" content="An example site">
      <meta property="og:title" content="Example">
    </head></html>
    """
    meta = _meta_tags(html)
    assert meta["generator"].startswith("WordPress")
    assert meta["description"] == "An example site"
    assert meta["og:title"] == "Example"


def test_script_srcs_extraction():
    html = """
    <script src="/wp-content/themes/x.js"></script>
    <script src='https://cdn.shopify.com/x.js'></script>
    <script>inline()</script>
    """
    srcs = _script_srcs(html)
    assert any("wp-content" in s for s in srcs)
    assert any("shopify" in s for s in srcs)


def test_detect_wordpress_via_meta_generator():
    detected = _detect(
        headers={},
        cookies={},
        html="",
        meta={"generator": "WordPress 6.4.2"},
    )
    names = [d["name"] for d in detected]
    assert "WordPress" in names


def test_detect_cloudflare_via_headers():
    detected = _detect(
        headers={"server": "cloudflare", "cf-ray": "abc123-XYZ"},
        cookies={},
        html="",
        meta={},
    )
    names = [d["name"] for d in detected]
    assert "Cloudflare CDN" in names


def test_detect_nginx_via_server_header():
    detected = _detect(
        headers={"server": "nginx/1.24.0"},
        cookies={},
        html="",
        meta={},
    )
    names = [d["name"] for d in detected]
    assert "nginx" in names


def test_detect_nextjs_via_html_marker():
    html = '<script id="__NEXT_DATA__">{}</script><div id="__next"></div>'
    detected = _detect(headers={}, cookies={}, html=html, meta={})
    names = [d["name"] for d in detected]
    assert "Next.js" in names


def test_detect_angular_via_html():
    html = '<app-root ng-version="17.0.0"></app-root>'
    detected = _detect(headers={}, cookies={}, html=html, meta={})
    names = [d["name"] for d in detected]
    assert "Angular" in names


def test_detect_empty_when_nothing_matches():
    detected = _detect(headers={}, cookies={}, html="<html></html>", meta={})
    assert detected == []


def test_detect_recaptcha():
    html = '<script src="https://www.google.com/recaptcha/api.js"></script><div class="g-recaptcha"></div>'
    detected = _detect(headers={}, cookies={}, html=html, meta={})
    names = [d["name"] for d in detected]
    assert "reCAPTCHA" in names
