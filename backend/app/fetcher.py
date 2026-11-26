import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

class FetchError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


async def resolve_public_ip(hostname: str) -> str:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(hostname, None, family=socket.AF_INET)
    except socket.gaierror:
        raise FetchError(f"Could not resolve {hostname}.")

    ip = ipaddress.ip_address(infos[0][4][0])
    if not ip.is_global:
        raise FetchError(f"{hostname} points to a private address ({ip}); refusing to fetch it.")
    return str(ip)


async def fetch_html(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http(s) URLs are supported.")

    # connect to the IP we checked, not the hostname, so DNS can't switch it on us
    ip = await resolve_public_ip(parts.hostname)
    pinned = parts._replace(netloc=f"{ip}:{parts.port}" if parts.port else ip).geturl()
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "AEOPageAuditor/1.0"}) as client:
            response = await client.get(
                pinned, headers={"Host": parts.netloc}, extensions={"sni_hostname": parts.hostname}
            )
    except httpx.HTTPError as exc:
        raise FetchError(f"Could not fetch the page ({exc.__class__.__name__}).", 502)

    if response.is_redirect:
        location = urljoin(url, response.headers["location"])
        raise FetchError(f"That URL redirects to {location}. Audit that URL instead.")
    if response.status_code >= 400:
        raise FetchError(f"The page returned HTTP {response.status_code}.", 502)
    if "html" not in response.headers.get("content-type", ""):
        raise FetchError("That URL is not an HTML page.", 415)
    return response.text
