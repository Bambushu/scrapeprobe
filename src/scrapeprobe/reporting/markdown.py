"""Markdown report renderer — the primary deliverable."""

from __future__ import annotations

import textwrap

from scrapeprobe.models import Report


def render(report: Report) -> str:
    """Return a complete REPORT.md as a string."""
    sections = [
        _header(report),
        _executive_summary(report),
        _bulkdata_section(report),
        _antibot_section(report),
        _techstack_section(report),
        _robots_section(report),
        _sitemap_section(report),
        _discovery_section(report),
        _sampling_section(report),
        _projection_section(report),
        _tos_section(report),
        _jurisdiction_section(report),
        _footer(report),
    ]
    return "\n\n".join(s for s in sections if s).rstrip() + "\n"


def _header(report: Report) -> str:
    return textwrap.dedent(f"""\
    # ScrapeProbe Report

    **Target:** `{report.target_url}`
    **Host:** `{report.target_host}`
    **Probed at:** {report.started_at.isoformat()}
    **Duration:** {report.duration_s:.1f}s
    **ScrapeProbe:** v{report.scrapeprobe_version}
    """).rstrip()


def _executive_summary(report: Report) -> str:
    p = report.probes
    bulkdata = p.get("bulkdata")
    antibot = p.get("antibot")
    techstack = p.get("techstack")
    sitemap = p.get("sitemap")

    headline = []

    if bulkdata and bulkdata.findings.get("any_bulkdata_signal"):
        hv = bulkdata.findings.get("highest_value_finding") or "Bulk-data signal detected."
        headline.append(f"- **Bulk data:** {hv}")
    else:
        headline.append(
            "- **Bulk data:** No obvious open dataset detected — scraping likely required."
        )

    if antibot:
        sev = antibot.findings.get("overall_severity", "unknown")
        wafw = antibot.findings.get("wafw00f", {})
        identified = ", ".join(wafw.get("identified") or []) or "—"
        blocked = (
            " 🛑 already blocked on recon" if antibot.findings.get("looks_blocked_on_recon") else ""
        )
        headline.append(f"- **Anti-bot:** severity `{sev}`, identified: `{identified}`{blocked}")

    if techstack:
        count = techstack.findings.get("detection_count", 0)
        cats = techstack.findings.get("by_category", {})
        cat_str = ", ".join(f"{k}: {', '.join(v[:3])}" for k, v in cats.items() if v) or "—"
        headline.append(f"- **Tech stack:** {count} signal(s). {cat_str}")

    if sitemap:
        total = sitemap.findings.get("total_url_count_estimate", 0)
        smc = sitemap.findings.get("sitemap_count", 0)
        if smc:
            headline.append(f"- **Sitemap:** {smc} file(s), ~{total:,} URLs total.")
        else:
            headline.append("- **Sitemap:** none found at common paths.")

    sampling = p.get("sampling")
    if sampling:
        f = sampling.findings
        if f.get("attempted"):
            if f.get("successes", 0) > 0:
                median = f.get("median_latency_ms")
                headline.append(
                    f"- **Sample scrape:** {f['successes']}/{f['sample_size_planned']} succeeded, median {median} ms/record."
                )
            else:
                headline.append(f"- **Sample scrape:** blocked. {f.get('reason') or ''}")
        else:
            headline.append(f"- **Sample scrape:** not attempted. {f.get('reason') or ''}")

    return "## Executive summary\n\n" + "\n".join(headline)


def _bulkdata_section(report: Report) -> str:
    pr = report.probes.get("bulkdata")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 1. Bulk-data finding\n"]
    if f.get("any_bulkdata_signal"):
        lines.append(f"**Highest-value finding:** {f.get('highest_value_finding')}\n")
    else:
        lines.append(
            "**No bulk-data endpoint or registry listing detected.** Scraping is the path.\n"
        )

    onsite = f.get("on_site_endpoints", [])
    if onsite:
        lines.append("### On-site endpoints that responded with structured data")
        lines.append("| URL | Status | Content-Type | Size | Looks like |")
        lines.append("|---|---|---|---|---|")
        for h in onsite[:15]:
            lines.append(
                f"| `{h['url']}` | {h['http_status']} | `{h.get('content_type', '')}` | {h.get('size_bytes', 0):,} B | {h.get('looks_like')} |"
            )

    registry = f.get("national_registry_hits", [])
    if registry:
        lines.append("\n### National open-data registry probes")
        for h in registry:
            mark = "✓ possible listing" if h.get("appears_listed") else "✗ no clear match"
            lines.append(f"- {mark} — `{h['registry_search_url']}` (HTTP {h['http_status']})")

    if note := f.get("note"):
        lines.append(f"\n> {note}")
    return "\n".join(lines)


def _antibot_section(report: Report) -> str:
    pr = report.probes.get("antibot")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 2. Anti-bot stack fingerprint\n"]
    lines.append(f"**Overall severity:** `{f.get('overall_severity', 'unknown')}`  ")
    lines.append(f"**Recon response HTTP status:** `{f.get('response_status')}`  ")
    if f.get("looks_blocked_on_recon"):
        lines.append(
            "🛑 **The target returned a block/challenge to ScrapeProbe's polite recon.** Scraping will need engineered countermeasures (residential proxies, browser automation, or both).  "
        )

    wafw = f.get("wafw00f", {})
    lines.append("\n### wafw00f")
    if wafw.get("error"):
        lines.append(f"- error: {wafw['error']}")
    else:
        ident = wafw.get("identified") or []
        if ident:
            lines.append(f"- Identified: {', '.join(f'`{i}`' for i in ident)}")
        if wafw.get("generic_signal"):
            lines.append("- Generic WAF signals detected (unidentified product).")
        if not ident and not wafw.get("generic_signal"):
            lines.append("- No WAF identified by wafw00f.")

    matches = f.get("signature_matches", [])
    if matches:
        lines.append("\n### ScrapeProbe signatures")
        lines.append("| Product | Severity | Matched on |")
        lines.append("|---|---|---|")
        for m in matches:
            lines.append(f"| {m['name']} | `{m['severity']}` | {', '.join(m['matched_on'])} |")

    if f.get("note"):
        lines.append(f"\n> {f['note']}")
    return "\n".join(lines)


def _techstack_section(report: Report) -> str:
    pr = report.probes.get("techstack")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 3. Tech stack fingerprint\n"]
    by_cat = f.get("by_category", {})
    if not by_cat:
        lines.append(
            "No known fingerprints matched. Target may use a custom stack or aggressive HTML obfuscation."
        )
        return "\n".join(lines)

    for cat, techs in sorted(by_cat.items()):
        lines.append(f"### {cat}")
        for t in techs:
            lines.append(f"- {t}")
        lines.append("")

    if f.get("note"):
        lines.append(f"> {f['note']}")
    return "\n".join(lines)


def _robots_section(report: Report) -> str:
    pr = report.probes.get("robots")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 4. Robots.txt analysis\n"]
    if not f.get("present"):
        lines.append(f"No `/robots.txt` found (HTTP {f.get('http_status')}).")
        return "\n".join(lines)

    lines.append(f"`/robots.txt` present ({f.get('size_bytes', 0):,} bytes).")
    if f.get("disallow_all"):
        lines.append(
            "\n🛑 **Disallow: / for `User-agent: *`** — site asks not to be crawled at all."
        )
    if f.get("crawl_delay_s"):
        lines.append(f"- Declared crawl delay: `{f['crawl_delay_s']}s` for `User-agent: *`.")
    if f.get("sitemaps"):
        lines.append(f"- Sitemap directive(s): {', '.join(f'`{s}`' for s in f['sitemaps'])}")

    rules = f.get("user_agent_rules", {})
    star = rules.get("*", {})
    if star.get("disallow"):
        lines.append("\n### Disallowed paths for `User-agent: *`")
        for p in star["disallow"][:30]:
            lines.append(f"- `{p}`")
    if star.get("allow"):
        lines.append("\n### Explicitly allowed paths for `User-agent: *`")
        for p in star["allow"][:20]:
            lines.append(f"- `{p}`")
    return "\n".join(lines)


def _sitemap_section(report: Report) -> str:
    pr = report.probes.get("sitemap")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 5. Sitemap discovery\n"]
    sms = f.get("sitemaps_found", [])
    if not sms:
        lines.append("No sitemap or RSS feed found at common paths.")
        if note := f.get("note"):
            lines.append(f"\n> {note}")
        return "\n".join(lines)

    lines.append(f"**Sitemaps found:** {len(sms)}  ")
    lines.append(f"**Total URL count estimate:** ~{f.get('total_url_count_estimate', 0):,}\n")
    lines.append("| URL | Kind | URLs | Bytes |")
    lines.append("|---|---|---|---|")
    for sm in sms:
        lines.append(
            f"| `{sm['url']}` | {sm['kind']} | {sm.get('url_count_estimate', 0):,} | {sm.get('size_bytes', 0):,} |"
        )
    return "\n".join(lines)


def _discovery_section(report: Report) -> str:
    pr = report.probes.get("discovery")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 6. Discovery path heuristics\n"]
    for s in f.get("strategies", []):
        lines.append(f"- **{s['name']}** (`{s['score']}`) — {s['reason']}")

    forms = f.get("forms", {})
    if forms.get("search_form"):
        sf = forms["search_form"]
        lines.append("\n### Search form details")
        lines.append(f"- action: `{sf['action']}`, method: `{sf['method']}`")
        lines.append(f"- inputs: `{', '.join(sf['input_names'])}`")

    ide = f.get("id_enum", {})
    if ide.get("likely"):
        lines.append("\n### ID enumeration signals")
        lines.append(f"- prefix: `{ide['url_prefix']}`")
        lines.append(
            f"- observed ID range: `{ide['min_id']}` to `{ide['max_id_seen']}` (n={ide['sample_count']})"
        )
        lines.append(f"- example: `{ide['example']}`")
    return "\n".join(lines)


def _sampling_section(report: Report) -> str:
    pr = report.probes.get("sampling")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 7. Sample scrape attempt\n"]
    if not f.get("attempted"):
        lines.append(f"**Not attempted.** {f.get('reason')}")
        return "\n".join(lines)

    lines.append(f"- Planned sample size: {f.get('sample_size_planned')}")
    lines.append(f"- Successful fetches: **{f.get('successes')}**")
    lines.append(f"- Polite delay used: {f.get('polite_delay_s_used')}s")
    if f.get("median_latency_ms"):
        lines.append(f"- Median per-record latency: **{f['median_latency_ms']} ms**")
    if f.get("avg_bytes_per_record"):
        lines.append(f"- Avg bytes per record: {f['avg_bytes_per_record']:,}")
    lines.append("")

    statuses = f.get("sampled_urls", [])
    if statuses:
        lines.append("### Per-URL trace (first 10)")
        lines.append("| # | URL | Status | Latency | Outcome |")
        lines.append("|---|---|---|---|---|")
        for i, s in enumerate(statuses[:10], 1):
            lines.append(
                f"| {i} | `{s['url']}` | {s.get('status', '—')} | {s.get('latency_ms', '—')} ms | {s['outcome']} |"
            )
    return "\n".join(lines)


def _projection_section(report: Report) -> str:
    """Project full-run cost from sampling latency. Always renders Section 8 — even
    when projection is impossible — so the numbering doesn't gap."""
    sampling = report.probes.get("sampling")
    sm = report.probes.get("sitemap")

    median_ms = sampling.findings.get("median_latency_ms") if sampling else None
    total_urls = sm.findings.get("total_url_count_estimate", 0) if sm else 0
    delay = (sampling.findings.get("polite_delay_s_used") if sampling else None) or 1.0

    if not median_ms or not total_urls:
        reason = []
        if not median_ms:
            reason.append("no sample scrape latency available")
        if not total_urls:
            reason.append("no URL count estimate from sitemap")
        return (
            "## 8. Full-run projection\n\n"
            f"Projection not available ({', '.join(reason)}). Once a successful sample scrape and a "
            "sitemap URL count exist, this section estimates sequential + parallel wall-time."
        )

    per_req_s = (median_ms / 1000.0) + delay
    seq_seconds = per_req_s * total_urls
    parallel10_seconds = seq_seconds / 10

    lines = ["## 8. Full-run projection\n"]
    lines.append(
        f"Based on observed median latency ({median_ms} ms/req) and polite delay ({delay}s):\n"
    )
    lines.append("| Scale | Workers | Estimated wall-time |")
    lines.append("|---|---|---|")
    lines.append(f"| Sequential, polite (single IP) | 1 | {_fmt_duration(seq_seconds)} |")
    lines.append(f"| Production, 10 parallel workers | 10 | {_fmt_duration(parallel10_seconds)} |")
    lines.append(
        "\n> Projection ignores rate-limiting, retries, and discovery overhead. Real-world adds 30-100%."
    )
    return "\n".join(lines)


def _tos_section(report: Report) -> str:
    pr = report.probes.get("tos")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 9. Terms-of-Service posture\n"]
    pages = f.get("pages_found", [])
    if not pages:
        lines.append("No TOS / legal page found at common paths.")
        if note := f.get("note"):
            lines.append(f"\n> {note}")
        return "\n".join(lines)

    lines.append(f"**TOS pages found:** {len(pages)}  ")
    for p in pages:
        lines.append(f"- `{p['url']}` ({p['chars']:,} chars)")

    hits = f.get("scraping_keywords_hit", [])
    if hits:
        lines.append(f"\n**Scraping-relevant keyword hits:** {f.get('scraping_keyword_hit_count')}")
        lines.append(f"**Languages detected:** {', '.join(f.get('languages_detected') or [])}\n")
        lines.append("| Lang | Pattern | Match | Context |")
        lines.append("|---|---|---|---|")
        for h in hits[:12]:
            ctx_text = h["context"].replace("|", "/")[:160]
            lines.append(
                f"| {h['language']} | `{h['pattern'][:40]}` | `{h['matched'][:30]}` | …{ctx_text}… |"
            )
    else:
        lines.append(
            "\nNo scraping-relevant keywords matched. The site's TOS may still cover this — read it."
        )

    lines.append(
        "\n> ScrapeProbe surfaces what's in the TOS. It does NOT provide legal advice. Consult counsel before relying on this."
    )
    return "\n".join(lines)


def _jurisdiction_section(report: Report) -> str:
    pr = report.probes.get("jurisdiction")
    if not pr:
        return ""
    f = pr.findings
    lines = ["## 10. Jurisdiction & GDPR posture\n"]
    lines.append(f"- TLD-implied country: `{f.get('tld_country') or '—'}`")
    if f.get("header_country"):
        lines.append(f"- HTTP-header country: `{f['header_country']}`")
    lines.append(f"- Effective country guess: `{f.get('effective_country_guess') or 'unknown'}`")
    lines.append(f"- EU/EEA: `{'yes' if f.get('is_eu_eea') else 'no'}`")
    lines.append(
        f"- GDPR likely applies: `{'yes' if f.get('gdpr_applies_heuristic') else 'unclear'}`"
    )
    if markers := f.get("consent_banner_markers"):
        lines.append(f"- Consent-banner markers: {', '.join(markers)}")
    if note := f.get("note"):
        lines.append(f"\n> {note}")
    return "\n".join(lines)


def _footer(report: Report) -> str:
    return textwrap.dedent(f"""\
    ---

    *Generated by [ScrapeProbe](https://github.com/Bambushu/scrapeprobe) v{report.scrapeprobe_version}.
    Not legal advice. Findings are best-effort heuristics — verify before staking a bid on them.*
    """).rstrip()


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    if seconds < 86_400:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 86_400:.1f} d"
