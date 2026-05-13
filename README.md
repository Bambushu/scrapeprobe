# ScrapeProbe

> The first 60 minutes of every web-scraping gig, codified.

ScrapeProbe is an open-source Python CLI that produces a proposal-ready recon
report on a target URL's scraping characteristics. Hand it a URL, get a
`REPORT.md` covering bulk-data endpoints, anti-bot stack, tech stack,
robots/sitemap analysis, discovery heuristics, a sample scrape attempt, full-run
projections, TOS posture, and GDPR/jurisdiction flags.

It's a **recon tool**, not a bypass tool. If the target blocks a polite
identifying request, ScrapeProbe reports that as a finding instead of trying to
evade it.

## What it tells you in five minutes

- **Is there a bulk dataset?** Open-data registries, CKAN endpoints, public
  APIs, OData, RSS, sitemaps, GraphQL. Highest-value finding by far. If the data
  is downloadable, you don't need to scrape.
- **Will scraping actually work?** wafw00f + an in-tree signature DB identify
  Cloudflare WAF, Imperva/Incapsula, Akamai Bot Manager, DataDome,
  PerimeterX/HUMAN, Kasada, F5 BIG-IP, AWS WAF, Sucuri, and 200+ more.
- **What's the stack?** ~50 hand-curated fingerprints across CMS, JS frameworks,
  e-commerce, CDN, server, analytics, anti-bot, and forms.
- **How big is this thing?** Sitemap walker estimates URL count (gzipped sitemaps
  too) and projects sequential / parallel wall-time at the observed latency.
- **What does the TOS actually say?** Fetches Terms / Nutzungsbedingungen /
  Conditions and greps for scraping-relevant keywords across EN / DE / NL / FR /
  ES / IT.
- **Does GDPR apply?** TLD + response-header + consent-banner heuristics flag
  EU/EEA targets.

## Install

```bash
# Recommended — isolated tool install
pipx install scrapeprobe
# or
uv tool install scrapeprobe

# Or in an existing venv
pip install scrapeprobe
```

## Use

```bash
# Basic
scrapeprobe https://firmen.wko.at/

# Custom output directory
scrapeprobe https://example.com/ --out ./recon/example/

# Faster polite delay (default is 1.0s between requests)
scrapeprobe https://example.com/ --delay 0.5

# Suppress the progress UI
scrapeprobe https://example.com/ --quiet
```

Output: a directory `scrapeprobe-<host>-<YYYYMMDD>/` containing `REPORT.md`
(human-readable, Markdown) and `report.json` (machine-readable, the same
findings).

## Example reports

Three real-world runs against very different targets, illustrating what the
report looks like:

- [`firmen.wko.at`](examples/sample-reports/firmen-wko-at/REPORT.md) —
  Austrian Chamber of Commerce business directory. WordPress + GTM, gzipped
  sitemap exposing ~361k URLs, generic WAF, no obvious bulk-data endpoint.
- [`apps.cra-arc.gc.ca`](examples/sample-reports/cra-charity-registry/REPORT.md) —
  Canadian Charity Registry (Angular SPA). F5 BIG-IP AppSec, hCaptcha, no
  sitemap. Sample-scrape declines politely; the report tells you the real cost
  of going further.
- [`opentender.eu`](examples/sample-reports/opentender-eu/REPORT.md) —
  EU public procurement aggregator. Cloudflare WAF in active-challenge mode,
  recon returns 403, ScrapeProbe correctly reports the block instead of trying
  to evade it.

## Politeness

ScrapeProbe identifies itself in every request:

```
User-Agent: ScrapeProbe/0.1.0 (+https://github.com/Bambushu/scrapeprobe)
```

It honors `Crawl-delay` from robots.txt, caps sample scrapes at 10 records, and
aborts on the first 429/403. It does **not** rotate proxies, spoof TLS
fingerprints, solve captchas, or render JavaScript. That's the bypass layer;
this is the recon layer.

## What's in the report

Every report has these ten sections, in this order:

1. **Bulk-data finding** — the high-value swing. Probes ~30 on-site paths and
   the country's national open-data registry (data.gv.at, data.europa.eu,
   data.gov.uk, data.gov, data.canada.ca, etc).
2. **Anti-bot stack fingerprint** — wafw00f + our DB, severity-graded.
3. **Tech stack fingerprint** — CMS, JS framework, CDN, server, analytics,
   forms, search.
4. **Robots.txt analysis** — declared sitemaps, disallow paths, crawl-delay,
   user-agent-specific rules.
5. **Sitemap discovery** — common paths + robots-declared, sub-sitemap walking,
   gzipped sitemap support, URL-count estimate.
6. **Discovery path heuristics** — sitemap-walk, search form, alphabet
   traversal, pagination, ID enumeration. One scored recommendation per
   strategy.
7. **Sample scrape attempt** — 5-10 records from same-host links. Median
   per-record latency, average bytes, full per-URL trace.
8. **Full-run projection** — sequential and 10-parallel wall-time estimates
   based on observed latency × sitemap URL count.
9. **TOS posture** — fetches Terms / legal / Nutzungsbedingungen, greps for
   scraping-relevant keywords across six languages, snippets each hit in
   context.
10. **Jurisdiction & GDPR** — TLD-implied country, HTTP-header geo signals,
    consent-banner markers, GDPR-applies heuristic.

## Why I built this

I run [Overtell.io](https://overtell.io), which means I bid on a lot of web-scraping
gigs. The first 60-90 minutes of every gig is always the same: "what's behind
this URL? Cloudflare? hCaptcha? Bulk download available? What discovery path
even works?" I was doing this manually for every bid, badly and inconsistently.

ScrapeProbe is that workflow as code. It runs in five minutes, produces a
report I can paste into a proposal, and gives me a defensible number on the
scope.

It's also a small contribution to the recon ecosystem. There are great tools for
individual sections — [wafw00f](https://github.com/EnableSecurity/wafw00f) for
WAF detection, [Wappalyzer-next](https://github.com/s0md3v/wappalyzer-next) for
tech stack — but I couldn't find one tool that did all of the above in a single
pass with a single report. Now there is one.

— Maikel Slomp

## See also

- **[Scrapling](https://github.com/D4Vinci/Scrapling)** — once recon is done and
  you've decided to scrape, Scrapling's adaptive fetcher (with anti-bot bypass)
  is what you graduate to.
- **[wafw00f](https://github.com/EnableSecurity/wafw00f)** — does the heavy
  lifting in ScrapeProbe's anti-bot section. Standalone if all you want is WAF
  identification.
- **[Wappalyzer-next](https://github.com/s0md3v/wappalyzer-next)** — for
  Wappalyzer-grade (3000+ fingerprint) tech detection. Heavier dep (Playwright)
  but much wider coverage than ScrapeProbe's 50.

## Contributing

PRs welcome — especially fingerprints, registry endpoints for under-represented
countries, and TOS keyword patterns for languages not yet covered. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the design, [`RESEARCH.md`](RESEARCH.md)
for the dep-or-build decisions, and `tests/` for the test patterns.

## License

MIT. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

ScrapeProbe is a recon tool. The findings it produces are best-effort
heuristics, not legal advice. Always verify a high-stakes finding manually
before betting a project on it.
