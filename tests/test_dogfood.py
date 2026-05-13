"""Dogfood log helper tests. Uses tmp_path to keep $HOME untouched."""

from __future__ import annotations

from pathlib import Path

import pytest

from scrapeprobe import dogfood


@pytest.fixture(autouse=True)
def isolate_log(monkeypatch, tmp_path):
    """Redirect DOGFOOD_DIR / LOG_PATH onto tmp_path for every test."""
    fake_dir = tmp_path / "scrapeprobe-dogfood"
    fake_log = fake_dir / "log.md"
    monkeypatch.setattr(dogfood, "DOGFOOD_DIR", fake_dir)
    monkeypatch.setattr(dogfood, "LOG_PATH", fake_log)
    return fake_log


def test_ensure_log_creates_dir_and_header(isolate_log: Path):
    dogfood.ensure_log_exists()
    assert isolate_log.exists()
    content = isolate_log.read_text(encoding="utf-8")
    assert content.startswith("# ScrapeProbe dogfood log")


def test_append_stub_writes_entry(isolate_log: Path):
    report = Path("/tmp/scrapeprobe-run/REPORT.md")
    log_path = dogfood.append_stub(
        gig="Test Client / Example Directory",
        target_url="https://example.com/",
        report_path=report,
    )
    assert log_path == isolate_log
    content = isolate_log.read_text(encoding="utf-8")
    assert "Test Client / Example Directory" in content
    assert "https://example.com/" in content
    assert str(report) in content
    assert "Verdict:** pending" in content


def test_append_stub_appends_multiple_entries(isolate_log: Path):
    dogfood.append_stub("Gig One", "https://a.example/", Path("/tmp/a/REPORT.md"))
    dogfood.append_stub("Gig Two", "https://b.example/", Path("/tmp/b/REPORT.md"))
    content = isolate_log.read_text(encoding="utf-8")
    assert content.count("## ") == 2
    # Header section stays put
    assert content.startswith("# ScrapeProbe dogfood log")


def test_list_gigs_oldest_first(isolate_log: Path):
    dogfood.append_stub("Gig One", "https://a.example/", Path("/tmp/a/REPORT.md"))
    dogfood.append_stub("Gig Two", "https://b.example/", Path("/tmp/b/REPORT.md"))
    titles = dogfood.list_gigs()
    assert len(titles) == 2
    assert "Gig One" in titles[0]
    assert "Gig Two" in titles[1]


def test_list_gigs_empty_when_no_log(isolate_log: Path):
    # Don't create the log
    assert dogfood.list_gigs() == []


def test_print_log_runs_without_error(isolate_log: Path, capsys):
    dogfood.append_stub("Gig X", "https://x.example/", Path("/tmp/x/REPORT.md"))
    dogfood.print_log()
    captured = capsys.readouterr()
    assert "Gig X" in captured.out


def test_open_in_editor_falls_back_when_no_editor(isolate_log: Path, monkeypatch, capsys):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    rc = dogfood.open_in_editor()
    assert rc == 0
    captured = capsys.readouterr()
    assert "No $EDITOR set" in captured.out
