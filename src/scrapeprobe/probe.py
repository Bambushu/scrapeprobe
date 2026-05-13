"""Orchestrator — runs all probes against a target URL and assembles a Report."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from scrapeprobe import __version__
from scrapeprobe.models import ProbeContext, Report
from scrapeprobe.probes import (
    antibot,
    bulkdata,
    discovery,
    jurisdiction,
    robots,
    sampling,
    sitemap,
    techstack,
    tos,
)
from scrapeprobe.utils.http import DEFAULT_UA, build_client
from scrapeprobe.utils.url import host_of, normalize_url, scheme_of


def probe_target(
    target_url: str,
    *,
    output_dir: str,
    polite_delay_s: float = 1.0,
    timeout_s: float = 15.0,
    user_agent: str = DEFAULT_UA,
    progress_cb=None,
) -> Report:
    """Run every probe against target_url and assemble a Report.

    progress_cb is an optional callable(probe_name: str, phase: str) used to drive
    the CLI status spinner. phase is 'start' or 'done'.
    """
    url = normalize_url(target_url)
    ctx = ProbeContext(
        target_url=url,
        target_host=host_of(url),
        target_scheme=scheme_of(url),
        user_agent=user_agent,
        polite_delay_s=polite_delay_s,
        timeout_s=timeout_s,
        output_dir=output_dir,
    )

    started_at = datetime.now(UTC)
    t_start = time.monotonic()

    report = Report(
        target_url=url,
        target_host=ctx.target_host,
        started_at=started_at,
        finished_at=started_at,  # placeholder, overwritten below
        duration_s=0.0,
        scrapeprobe_version=__version__,
    )

    with build_client(user_agent=user_agent, timeout=timeout_s) as client:
        # Phase 1: robots — its findings inform downstream sitemap probe
        _emit(progress_cb, "robots", "start")
        report.probes["robots"] = robots.run(ctx, client)
        _emit(progress_cb, "robots", "done")

        # Phase 2: antibot + techstack + jurisdiction (homepage reads, parallelizable)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for name in ("antibot", "techstack", "jurisdiction"):
                _emit(progress_cb, name, "start")
            fut_antibot = pool.submit(antibot.run, ctx, client)
            fut_tech = pool.submit(techstack.run, ctx, client)
            fut_juris = pool.submit(jurisdiction.run, ctx, client)
            report.probes["antibot"] = fut_antibot.result()
            report.probes["techstack"] = fut_tech.result()
            report.probes["jurisdiction"] = fut_juris.result()
        for name in ("antibot", "techstack", "jurisdiction"):
            _emit(progress_cb, name, "done")

        # Phase 3: sitemap (depends on robots for seed)
        _emit(progress_cb, "sitemap", "start")
        seed_sitemaps = report.probes["robots"].findings.get("sitemaps", [])
        report.probes["sitemap"] = sitemap.run(ctx, client, seed_sitemaps=seed_sitemaps)
        _emit(progress_cb, "sitemap", "done")

        # Phase 4: bulkdata + tos (parallelizable, both hit distinct endpoints)
        with ThreadPoolExecutor(max_workers=2) as pool:
            _emit(progress_cb, "bulkdata", "start")
            _emit(progress_cb, "tos", "start")
            fut_bulk = pool.submit(bulkdata.run, ctx, client)
            fut_tos = pool.submit(tos.run, ctx, client)
            report.probes["bulkdata"] = fut_bulk.result()
            report.probes["tos"] = fut_tos.result()
        _emit(progress_cb, "bulkdata", "done")
        _emit(progress_cb, "tos", "done")

        # Phase 5: discovery (uses sitemap result)
        _emit(progress_cb, "discovery", "start")
        report.probes["discovery"] = discovery.run(
            ctx, client, sitemap_findings=report.probes["sitemap"].findings
        )
        _emit(progress_cb, "discovery", "done")

        # Phase 6: sampling (uses antibot + sitemap)
        _emit(progress_cb, "sampling", "start")
        report.probes["sampling"] = sampling.run(
            ctx,
            client,
            sitemap_findings=report.probes["sitemap"].findings,
            antibot_findings=report.probes["antibot"].findings,
        )
        _emit(progress_cb, "sampling", "done")

    finished_at = datetime.now(UTC)
    report.finished_at = finished_at
    report.duration_s = time.monotonic() - t_start
    return report


def _emit(cb, name: str, phase: str) -> None:
    if cb is not None:
        try:
            cb(name, phase)
        except Exception:
            pass
