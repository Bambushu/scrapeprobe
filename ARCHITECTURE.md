# Architecture

Design decisions for ScrapeProbe v0.1.0. Locked 2026-05-13.

## Stack

| Decision | Choice | Why |
|---|---|---|
| **Language** | Python 3.11+ | 3.11 is the oldest with `tomllib` in stdlib + mature `asyncio.TaskGroup`. Mike's machine runs 3.14 so dev/test happens there. CI matrix can cover 3.11-3.14 later. |
| **Build backend** | `hatchling` | `uv` default. Pure Python, no surprises. PEP 621 metadata in `pyproject.toml`. |
| **Dep manager** | `uv` for dev, but the package itself installs cleanly with `pip` or `pipx` | `uv` is faster but we don't force it on users. Standard `pyproject.toml` works everywhere. |
| **CLI framework** | `click` | Older + more stable than Typer. Mike's tooling uses Click patterns. Better grouping/composition for future subcommands. |
| **HTTP client** | `httpx` (sync) | HTTP/2 + connection pooling out of the box. Sync API is simpler than async for a one-shot probe — async would buy ~3-5s on a 60s total budget, not worth the complexity. |
| **HTML parser** | `beautifulsoup4` + `lxml` | Standard, fast, regex-friendly. |
| **Terminal UX** | `rich` | Live status spinner during the 5-minute probe so the user sees progress per section. |
| **Tests** | `pytest` + `pytest-httpx` | Mock HTTP responses for deterministic unit tests. Real-target integration tests are run manually and saved to `examples/`. |

## Distribution

```
# End user install
pipx install scrapeprobe        # isolated tool install, the recommended path
uv tool install scrapeprobe     # uv equivalent
pip install scrapeprobe         # if pipx/uv unavailable
```

PyInstaller binary is YAGNI for v1.

## Project layout

```
~/scrapeprobe/
  pyproject.toml                # PEP 621, hatchling
  README.md                     # public-facing
  RESEARCH.md                   # OSS landscape (this dir)
  ARCHITECTURE.md               # this file
  LICENSE                       # MIT
  NOTICE                        # attributions for bundled MIT data
  src/scrapeprobe/
    __init__.py                 # __version__
    __main__.py                 # python -m scrapeprobe
    cli.py                      # Click commands + main()
    probe.py                    # Orchestrator: calls probes in parallel where safe
    models.py                   # dataclasses for probe results
    probes/
      __init__.py
      antibot.py                # wafw00f wrapper + manual header/script signatures
      techstack.py              # HTTPArchive Wappalyzer matcher
      robots.py                 # robots.txt parse + sitemap discovery
      sitemap.py                # sitemap.xml walker, URL count estimate
      bulkdata.py               # open-data endpoint heuristics (data.gv.X, /opendata/, CKAN, etc.)
      discovery.py              # discovery path classifier (alphabet, postal, ID enum, sitemap)
      sampling.py               # 5-10 record sample fetch + latency
      tos.py                    # TOS / Terms / Nutzungsbedingungen fetcher + keyword grep
      jurisdiction.py           # TLD + HTTP header heuristics for GDPR/EU flagging
    reporting/
      __init__.py
      markdown.py               # REPORT.md generator
      json.py                   # JSON output
    data/
      techstack.json            # ~50 hand-curated MIT-clean tech fingerprints
      antibot_signatures.json   # manual WAF/bot signatures complementary to wafw00f
      bulkdata_patterns.json    # known open-data endpoint patterns per TLD
      tos_keywords.json         # multilingual TOS keyword lists (en/de/nl/fr/es)
    utils/
      __init__.py
      http.py                   # httpx wrapper: polite UA, retries, timeout, no automatic bypass
      url.py                    # URL normalization, path joining
  tests/
    conftest.py
    test_antibot.py
    test_techstack.py
    test_robots.py
    test_bulkdata.py
    test_report.py
    fixtures/                   # sample HTML/headers
  examples/
    sample-reports/             # real recon outputs
    README.md                   # index
  .gitignore
```

## Probe contract

Every probe in `src/scrapeprobe/probes/` exposes:

```python
def run(ctx: ProbeContext) -> ProbeResult:
    """Synchronous, returns a typed dataclass. Must not raise on network errors —
    caller catches and records as 'probe failed' in the report."""
```

`ProbeContext` carries the normalized URL, a shared `httpx.Client`, the user-agent string, the polite-delay budget, and an output dir for cached responses. `ProbeResult` is a typed `@dataclass` with `status`, `findings`, `evidence` (list of `(url, status_code, snippet)` tuples), and an optional `error`.

The orchestrator runs probes sequentially in dependency order:

1. `robots.run()` → publishes `disallow_paths` for subsequent probes to respect.
2. `antibot.run()` + `techstack.run()` in parallel (read-only HEAD/GET of root URL).
3. `sitemap.run()` (depends on robots).
4. `bulkdata.run()` + `jurisdiction.run()` + `tos.run()` in parallel.
5. `discovery.run()` (uses sitemap result).
6. `sampling.run()` (uses discovery + antibot result for sane back-off).

Parallelism via `concurrent.futures.ThreadPoolExecutor(max_workers=4)`. Async is overkill here.

## Politeness contract

- User agent: `ScrapeProbe/0.1.0 (+https://github.com/Bambushu/scrapeprobe)`. Self-identifying, **not** browser-impersonating.
- Honors `Crawl-delay` in robots.txt if present, else 1.0s between requests to the same host.
- Sampling cap: 10 records max per target. Aborts on first 429/403.
- No retries on 4xx. One retry on 5xx + connection errors.
- Total wall-time budget per run: 5 minutes (configurable via `--timeout`).

## Output formats

- `REPORT.md` is the primary deliverable. Sections in the order the chip spec defines: bulk-data first (highest-value finding), then WAF, tech stack, robots/sitemap, discovery, sample, latency, projection, TOS, GDPR.
- `--json` flag writes `report.json` alongside `REPORT.md` for programmatic consumption.
- `--out DIR` defaults to `./scrapeprobe-<host>-<YYYYMMDD>/` to keep multi-run output tidy.

## What we explicitly will NOT do

- **No captcha/WAF bypass.** Self-identifying UA, no TLS spoofing, no proxy rotation, no JS challenge solving. This is recon. If the target blocks us, that IS the report.
- **No credential filling, no login flows.** Public surfaces only.
- **No sustained load.** Sample cap is hard. Aborts on rate-limit signals.
- **No subdomain enumeration.** ScrapeProbe probes a single URL.
- **No DNS history / WHOIS deep-dive.** Jurisdiction heuristics use TLD + response headers only. WHOIS is a v0.2 nicety.
