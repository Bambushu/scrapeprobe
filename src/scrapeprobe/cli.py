"""Click CLI entry point."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.table import Table

from scrapeprobe import __version__
from scrapeprobe.dogfood import LOG_PATH, append_stub, list_gigs, open_in_editor, print_log
from scrapeprobe.probe import probe_target
from scrapeprobe.reporting import json as json_renderer
from scrapeprobe.reporting import markdown as md_renderer
from scrapeprobe.utils.http import DEFAULT_UA
from scrapeprobe.utils.url import host_of, normalize_url

PROBE_ORDER = [
    "robots",
    "antibot",
    "techstack",
    "jurisdiction",
    "sitemap",
    "bulkdata",
    "tos",
    "discovery",
    "sampling",
]


@click.command()
@click.argument("target", required=True)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(),
    default=None,
    help="Output directory (default: ./scrapeprobe-<host>-<YYYYMMDD>/).",
)
@click.option(
    "--json",
    "want_json",
    is_flag=True,
    default=True,
    help="Also write report.json alongside REPORT.md. (Default: on.)",
)
@click.option("--no-json", "want_json", flag_value=False)
@click.option(
    "--delay",
    "polite_delay",
    type=float,
    default=1.0,
    help="Polite delay in seconds between requests to the same host. Default 1.0.",
)
@click.option(
    "--timeout", type=float, default=15.0, help="Per-request HTTP timeout in seconds. Default 15."
)
@click.option(
    "--user-agent",
    "user_agent",
    default=DEFAULT_UA,
    show_default=True,
    help="User-Agent string. Default is self-identifying.",
)
@click.option("--quiet", is_flag=True, help="Suppress progress UI; only print final report path.")
@click.option(
    "--gig",
    "gig",
    default=None,
    help='Label this run as a real gig (e.g. --gig "Julianne / WKO Firmen") '
    "and append a stub entry to ~/scrapeprobe-dogfood/log.md.",
)
@click.version_option(version=__version__, prog_name="scrapeprobe")
def main(
    target: str,
    out_dir: str | None,
    want_json: bool,
    polite_delay: float,
    timeout: float,
    user_agent: str,
    quiet: bool,
    gig: str | None,
) -> None:
    """Probe TARGET URL and produce a proposal-ready recon report.

    \b
    Example:
        scrapeprobe https://firmen.wko.at/
        scrapeprobe https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyAdvncdSrch --out ./recon/cra/
    """
    target_url = normalize_url(target)
    host = host_of(target_url)
    out_path = (
        Path(out_dir)
        if out_dir
        else Path(f"./scrapeprobe-{host}-{datetime.now().strftime('%Y%m%d')}")
    )
    out_path.mkdir(parents=True, exist_ok=True)

    console = Console(stderr=True)
    if not quiet:
        console.print(
            f"[bold]ScrapeProbe v{__version__}[/bold] — probing [cyan]{target_url}[/cyan]"
        )
        console.print(f"Output: {out_path}\n")

    state = {name: "pending" for name in PROBE_ORDER}

    def _render_table() -> Table:
        table = Table(show_header=False, padding=(0, 2))
        for name in PROBE_ORDER:
            s = state[name]
            icon = {"pending": "·", "running": "⏳", "done": "✓"}.get(s, "?")
            color = {"pending": "dim", "running": "yellow", "done": "green"}.get(s, "")
            table.add_row(f"[{color}]{icon} {name}[/{color}]")
        return table

    def progress_cb(name: str, phase: str) -> None:
        if phase == "start":
            state[name] = "running"
        elif phase == "done":
            state[name] = "done"
        if not quiet and live is not None:
            live.update(_render_table())

    started = datetime.now(UTC)
    live = None
    try:
        if quiet:
            report = probe_target(
                target_url,
                output_dir=str(out_path),
                polite_delay_s=polite_delay,
                timeout_s=timeout,
                user_agent=user_agent,
                progress_cb=None,
            )
        else:
            with Live(_render_table(), console=console, refresh_per_second=8) as live_ctx:
                live = live_ctx
                report = probe_target(
                    target_url,
                    output_dir=str(out_path),
                    polite_delay_s=polite_delay,
                    timeout_s=timeout,
                    user_agent=user_agent,
                    progress_cb=progress_cb,
                )
    except KeyboardInterrupt:
        console.print("[red]Aborted by user.[/red]")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001 — top-level catch keeps the CLI helpful
        console.print(f"[red]Probe failed: {exc.__class__.__name__}: {exc}[/red]")
        raise

    md_path = out_path / "REPORT.md"
    md_path.write_text(md_renderer.render(report), encoding="utf-8")

    if want_json:
        json_path = out_path / "report.json"
        json_path.write_text(json_renderer.render(report), encoding="utf-8")

    finished = datetime.now(UTC)
    elapsed = (finished - started).total_seconds()

    if gig:
        log_path = append_stub(gig=gig, target_url=target_url, report_path=md_path)
        if not quiet:
            console.print(f"DOGFOOD: appended stub for [bold]{gig}[/bold] to {log_path}")

    if not quiet:
        console.print(f"\n[green]Done in {elapsed:.1f}s.[/green]")
        console.print(f"REPORT: {md_path}")
        if want_json:
            console.print(f"JSON:   {out_path / 'report.json'}")
    else:
        click.echo(str(md_path))


@click.group(invoke_without_command=True)
@click.option("--cat", is_flag=True, help="Print the log to stdout instead of opening in $EDITOR.")
@click.option("--list", "list_only", is_flag=True, help="List gig titles in the log, oldest first.")
@click.pass_context
def log_command(ctx: click.Context, cat: bool, list_only: bool) -> None:
    """Open the dogfood log (~/scrapeprobe-dogfood/log.md) in $EDITOR.

    Use --cat to print, --list to see gig titles only.
    """
    if ctx.invoked_subcommand is not None:
        return
    if list_only:
        titles = list_gigs()
        if not titles:
            click.echo(f"(No gigs logged yet. Log lives at {LOG_PATH}.)")
            return
        for t in titles:
            click.echo(t)
        return
    if cat:
        print_log()
        return
    open_in_editor()
