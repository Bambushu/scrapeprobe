"""HTTPX client wrapper with polite defaults. No bypass, no impersonation."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx

from scrapeprobe import __version__

DEFAULT_UA = f"ScrapeProbe/{__version__} (+https://github.com/Bambushu/scrapeprobe)"


def build_client(
    *,
    user_agent: str = DEFAULT_UA,
    timeout: float = 15.0,
    follow_redirects: bool = True,
    http2: bool = True,
) -> httpx.Client:
    """Construct a single httpx.Client shared by all probes for a single run."""
    return httpx.Client(
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,de;q=0.7,nl;q=0.7,fr;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
        },
        timeout=timeout,
        follow_redirects=follow_redirects,
        http2=http2,
        verify=True,
    )


@contextmanager
def polite(delay_s: float) -> Iterator[None]:
    """Sleep AFTER the protected block so back-to-back fetches are spaced out."""
    try:
        yield
    finally:
        if delay_s > 0:
            time.sleep(delay_s)


def safe_get(
    client: httpx.Client,
    url: str,
    *,
    allow_status: tuple[int, ...] | None = None,
    timeout: float | None = None,
) -> httpx.Response | None:
    """GET that never raises. Returns None on connect failure, the response otherwise."""
    try:
        return client.get(url, timeout=timeout) if timeout else client.get(url)
    except (
        httpx.ConnectError,
        httpx.ReadError,
        httpx.WriteError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.UnsupportedProtocol,
        httpx.RemoteProtocolError,
        httpx.LocalProtocolError,
    ):
        return None
    except httpx.HTTPError:
        return None


def safe_head(
    client: httpx.Client,
    url: str,
    *,
    timeout: float | None = None,
) -> httpx.Response | None:
    try:
        return client.head(url, timeout=timeout) if timeout else client.head(url)
    except httpx.HTTPError:
        return None
