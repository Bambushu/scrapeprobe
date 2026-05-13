# OSS Landscape Research

Decisions for ScrapeProbe v0.1.0. Reviewed 2026-05-13.

## Verdict at a glance

| Tool | License | Decision | Why |
|---|---|---|---|
| **wafw00f** | BSD-3-Clause | **Use as dep** | Active (Jan 2026 release), 200+ WAFs, permissive license, importable. Core for anti-bot probe. |
| **HTTPArchive/wappalyzer fingerprints** | GPL-3.0 | **Pass** | Originally believed MIT (per `wappalyzergo` README). Verified GPL-3.0 on the source repo — both HTTPArchive and enthec forks are GPL. Cannot bundle in an MIT project. |
| **Hand-curated fingerprint DB** | MIT (ours) | **Build in-tree** | ~50 hand-curated patterns covering CMS, JS frameworks, e-commerce, CDN, server, analytics, anti-bot, forms. Smaller than Wappalyzer's 3000+, but covers the scraping-relevant 90% and is legally clean. |
| **builtwith (Python)** | Unclear | **Pass** | No license clarity, no recent releases, smaller signal coverage. |
| **wappalyzer-next** | GPL-3.0 | **Pass** | Copyleft would contaminate MIT licensing. Also pulls Playwright + Chromium. |
| **python-Wappalyzer (chorsley)** | n/a | **Pass** | Archived, no longer maintained. |
| **wap (blackarrowsec)** | LGPL-3.0 | **Pass** | Copyleft. Same data we'd get from HTTPArchive anyway. |
| **wappalyzergo (projectdiscovery)** | MIT | **Pass for code (Go)** | Go binary, not Python. Confirmed fingerprint source is HTTPArchive — we'll go straight to the source. |
| **curl-cffi** | MIT | **Pass for v1** | TLS fingerprint spoofing is bypass-adjacent. Honest recon uses a self-identifying UA so blocks become findings, not obstacles. Revisit in v0.2 if the "would Chrome get through?" question becomes interesting. |
| **cloudscraper** | MIT | **Pass** | Bypass tool, out of scope. ScrapeProbe is recon, not evasion. |
| **playwright + playwright-stealth** | Apache-2.0 + MIT | **Pass for v1** | Heavy dependency for sample scrape. v1 uses httpx + bs4. v0.2 can add `--render` flag for SPAs. |
| **scrapy** | BSD-3 | **Pass** | Wrong abstraction — we're a one-shot probe, not a long-running crawler. Mention in README "see also" so users know where to graduate to. |
| **fierce / subfinder / recon-ng** | various | **Pass** | Subdomain enumeration is out of scope. ScrapeProbe probes a known URL. |
| **whatweb (Ruby)** | GPL-2.0 | **Pass** | Wrong language; signatures borrowable but redundant with HTTPArchive DB. |
| **builtwith.com API** | proprietary | **Pass** | API-key paid service. Not OSS, not local. |

## Existing tools that already do this?

Searched GitHub (`scrapeprobe`, `scraping recon`, `scraper reconnaissance`, recon topics). **No existing OSS tool covers the full ScrapeProbe scope.** Closest neighbors:

- **wafw00f** — WAF only, one section of our report.
- **wappalyzer-next** — tech stack only, one section of our report, and Playwright-heavy.
- **Scrapling (D4Vinci)** — adaptive scraper with anti-bot fetcher. Different abstraction: it's a scraper, not a probe. Worth a README "see also" for users who want to graduate from recon to execution.
- **whatweb** — Ruby tech-stack fingerprinter, no bulk-data or sitemap analysis.

**Conclusion:** ScrapeProbe is novel as a single-shot, multi-section recon report aimed specifically at scraping-gig sizing. Not a wrapper, not redundant.

## Direct dependencies (v0.1.0)

1. **`httpx`** — sync HTTP with HTTP/2 + connection pooling. Workhorse for all probes.
2. **`beautifulsoup4`** — HTML parsing for tech-stack regexes and TOS keyword grep.
3. **`click`** — CLI framework. Stable, boring, well-documented.
4. **`rich`** — colored terminal progress + Markdown rendering for `--preview` flag.
5. **`wafw00f`** — anti-bot WAF fingerprinting (200+ products).
6. **`tldextract`** — robust TLD/domain parsing for GDPR / EU-jurisdiction heuristics.

## In-tree data

- **`src/scrapeprobe/data/techstack.json`** — ~50 hand-curated tech fingerprints under MIT (own work). Format intentionally close to Wappalyzer's schema (cats / headers / cookies / scripts / html / meta regexes) so a future v0.2 migration to a GPL-free upstream DB is easy. Original author: Maikel Slomp.
- **`src/scrapeprobe/data/antibot_signatures.json`** — complementary signals to `wafw00f` for products that wafw00f misses or under-reports.
- **`src/scrapeprobe/data/bulkdata_patterns.json`** — open-data endpoint patterns per TLD (data.gv.at, data.europa.eu, data.gov.uk, etc.).
- **`src/scrapeprobe/data/tos_keywords.json`** — multilingual TOS keyword lists (en/de/nl/fr/es).

## Open questions for v0.2

- Should `--render` add a Playwright fallback for SPA targets (CRA Charity Registry, Angular apps)? Today the report flags "Angular SPA detected → sample scrape may underperform" and stops. Rendering would unlock real samples but doubles install footprint.
- Should we ship a `--proxy` / `--from-country` flag for geo-fenced targets? Today we honestly note "site appears geo-fenced, recon ran from $LOCAL_IP." Bypass-adjacent — needs more thought.
- WHOIS lookups for jurisdiction analysis — `python-whois` is unmaintained-but-works. RDAP via `whoisit` is cleaner. Defer to v0.2.
