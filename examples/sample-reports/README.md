# Sample Reports

Three real ScrapeProbe runs against public targets, kept here as a what-to-expect reference. They were generated with `scrapeprobe <url> --out <dir>` and are unedited except for redacting timestamps in this README.

| Target | Headline | Run duration |
|---|---|---|
| [`firmen.wko.at`](firmen-wko-at/REPORT.md) | WordPress directory, gzipped sitemap exposes ~361k URLs, generic WAF, sitemap-walk is the cheap path. | ~37s |
| [`apps.cra-arc.gc.ca/ebci/hacc/...`](cra-charity-registry/REPORT.md) | Angular SPA, F5 BIG-IP AppSec Manager + hCaptcha, no sitemap. Recon completes; real scraping needs browser automation + captcha solving. | ~49s |
| [`opentender.eu`](opentender-eu/REPORT.md) | Cloudflare WAF in active-challenge mode, recon returns HTTP 403. ScrapeProbe declines to sample politely; the report tells you what you'd need. | ~5s |

## What you don't get

These reports are recon, not penetration tests. You won't find:

- Credentials or API keys
- Captcha solutions or WAF bypasses
- Personal data of any individual
- Subdomain / DNS / certificate enumeration
- Sustained-load behavior

If a target has a paid bulk-data API, that's the right path. ScrapeProbe surfaces it.
