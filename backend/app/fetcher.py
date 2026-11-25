"""Fetch a page safely: timeout, redirects, HTML only, no private/localhost IPs."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 5


class FetchError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


async def check_host_is_public(url: str) -> None:
    """Resolve the URL's host and refuse it if any of its IPs is private, loopback, etc."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http(s) URLs are supported.")

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or 443)
    except socket.gaierror:
        raise FetchError(f"Could not resolve {parts.hostname}.")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        # is_global is False for private, loopback, link-local (incl. 169.254.169.254) and reserved ranges.
        if not ip.is_global:
            raise FetchError(f"{parts.hostname} points to a private address ({ip}); refusing to fetch it.")


async def fetch_html(url: str) -> tuple[str, str]:
    """Return (final_url, html). Redirects are followed by hand so every hop is checked."""
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "AEOPageAuditor/1.0"}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await check_host_is_public(url)
            try:
                response = await client.get(url)
            except httpx.HTTPError as exc:
                raise FetchError(f"Could not fetch the page ({exc.__class__.__name__}).", 502)

            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            if response.status_code >= 400:
                raise FetchError(f"The page returned HTTP {response.status_code}.", 502)
            if "html" not in response.headers.get("content-type", ""):
                raise FetchError("That URL is not an HTML page.", 415)
            return str(response.url), response.text

    raise FetchError("Too many redirects.", 502)
