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


def default_port(parts) -> int:
    return parts.port or (443 if parts.scheme == "https" else 80)


async def check_host_is_public(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http(s) URLs are supported.")

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, default_port(parts))
    except socket.gaierror:
        raise FetchError(f"Could not resolve {parts.hostname}.")

    ips = [ipaddress.ip_address(info[4][0]) for info in infos]
    for ip in ips:
        if not ip.is_global:
            raise FetchError(f"{parts.hostname} points to a private address ({ip}); refusing to fetch it.")

    # prefer IPv4, plenty of networks (docker included) have no IPv6 route
    return str(next((ip for ip in ips if ip.version == 4), ips[0]))


async def get_pinned(client: httpx.AsyncClient, url: str, ip: str) -> httpx.Response:
    # connect to the IP we checked, so DNS can't hand httpx a different one (DNS rebinding)
    parts = urlsplit(url)
    host = f"[{ip}]" if ":" in ip else ip
    pinned = parts._replace(netloc=f"{host}:{default_port(parts)}").geturl()
    return await client.get(
        pinned,
        headers={"Host": parts.netloc.rpartition("@")[2]},
        extensions={"sni_hostname": parts.hostname},
    )


async def fetch_html(url: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "AEOPageAuditor/1.0"}) as client:
        # follow redirects ourselves so every hop gets the IP check
        for _ in range(MAX_REDIRECTS + 1):
            ip = await check_host_is_public(url)
            try:
                response = await get_pinned(client, url, ip)
            except httpx.HTTPError as exc:
                raise FetchError(f"Could not fetch the page ({exc.__class__.__name__}).", 502)

            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            if response.status_code >= 400:
                raise FetchError(f"The page returned HTTP {response.status_code}.", 502)
            if "html" not in response.headers.get("content-type", ""):
                raise FetchError("That URL is not an HTML page.", 415)
            return url, response.text

    raise FetchError("Too many redirects.", 502)
