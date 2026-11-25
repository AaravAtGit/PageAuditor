"""Safe page fetching.

Protections required by the brief:
- timeout on every request
- follow redirects (bounded)
- reject non-HTML responses
- block private / loopback / link-local / reserved IP ranges (SSRF)

The SSRF check happens in two places:
1. `validate_url` gives a fast, friendly error before any network call.
2. `GuardedNetworkBackend` re-resolves and re-checks the IP at the moment a
   TCP connection is opened, then connects to that exact IP. That covers
   redirects to internal hosts and DNS rebinding (a hostname that resolves
   to a public IP during the first check and to 127.0.0.1 a moment later).
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpcore
import httpx

from app.config import get_settings

HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
USER_AGENT = "AEOPageAuditor/0.1 (+on-page audit bot)"


class FetchError(Exception):
    """Base class. `status_code` is the HTTP status our API should return."""

    status_code = 502
    code = "fetch_failed"


class InvalidURLError(FetchError):
    status_code = 422
    code = "invalid_url"


class BlockedAddressError(FetchError):
    status_code = 422
    code = "blocked_address"


class NotHTMLError(FetchError):
    status_code = 415
    code = "not_html"


@dataclass
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    html: bytes
    encoding: str | None
    truncated: bool


def is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # "::ffff:127.0.0.1" is IPv4 loopback in disguise; check the embedded v4 address.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # is_global is False for private, loopback, link-local (169.254/16, incl. cloud
    # metadata endpoints), CGNAT, reserved and documentation ranges.
    return ip.is_global and not ip.is_multicast


async def _dns_lookup(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        results = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve host '{host}'.") from exc
    return list(dict.fromkeys(r[4][0] for r in results))  # unique, order kept


async def resolve_public_ips(host: str, port: int) -> list[str]:
    """Resolve `host` and return its IPs, raising if ANY of them is non-public."""
    try:
        infos = [str(ipaddress.ip_address(host.strip("[]")))]  # already an IP literal
    except ValueError:
        infos = await _dns_lookup(host, port)

    for addr in infos:
        if not is_public_ip(ipaddress.ip_address(addr.split("%")[0])):
            raise BlockedAddressError(
                f"'{host}' resolves to a private or reserved address; refusing to fetch it."
            )
    return infos


def validate_url(url: str) -> str:
    """Syntactic checks. Returns the URL stripped of whitespace."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise InvalidURLError("Only http:// and https:// URLs are supported.")
    if not parts.hostname:
        raise InvalidURLError("The URL has no hostname.")
    if parts.username or parts.password:
        raise InvalidURLError("URLs with embedded credentials are not allowed.")
    if parts.hostname.lower() in ("localhost",) or parts.hostname.lower().endswith(
        (".localhost", ".local", ".internal")
    ):
        raise BlockedAddressError("Local hostnames are not allowed.")
    return url


class GuardedNetworkBackend(httpcore.AsyncNetworkBackend):
    """Wraps httpcore's default backend: every TCP connect is to a vetted public IP."""

    def __init__(self) -> None:
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        ips = await resolve_public_ips(host, port)
        # Connect to the IP we just checked, not the hostname, so DNS can't change
        # underneath us. TLS still uses the original hostname for SNI/cert checks,
        # because httpcore passes the request's host to start_tls separately.
        return await self._inner.connect_tcp(
            ips[0], port, timeout=timeout, local_address=local_address, socket_options=socket_options
        )

    async def connect_unix_socket(self, *args, **kwargs):
        raise BlockedAddressError("Unix sockets are not allowed.")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class GuardedTransport(httpx.AsyncHTTPTransport):
    def __init__(self) -> None:
        # trust_env=False: ignore HTTP(S)_PROXY env vars, which would bypass the guard.
        super().__init__(trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(),
            network_backend=GuardedNetworkBackend(),
        )


def _is_html(content_type: str) -> bool:
    return content_type.split(";")[0].strip().lower() in HTML_CONTENT_TYPES


async def fetch_page(url: str, transport: httpx.AsyncBaseTransport | None = None) -> FetchedPage:
    settings = get_settings()
    url = validate_url(url)
    parts = urlsplit(url)
    # Early, friendly check; the transport re-checks on every connection anyway.
    await resolve_public_ips(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))

    async with httpx.AsyncClient(
        transport=transport or GuardedTransport(),
        follow_redirects=True,
        max_redirects=settings.fetch_max_redirects,
        timeout=httpx.Timeout(settings.fetch_timeout_seconds),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    ) as client:
        try:
            async with client.stream("GET", url) as response:
                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400:
                    raise FetchError(f"The page returned HTTP {response.status_code}.")
                if not _is_html(content_type):
                    raise NotHTMLError(
                        f"Expected an HTML page but got '{content_type or 'unknown'}'."
                    )

                # Read at most fetch_max_bytes so a huge page can't exhaust memory.
                body = bytearray()
                truncated = False
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > settings.fetch_max_bytes:
                        del body[settings.fetch_max_bytes :]
                        truncated = True
                        break

                return FetchedPage(
                    requested_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    html=bytes(body),
                    encoding=response.charset_encoding,
                    truncated=truncated,
                )
        except FetchError:
            raise
        except httpx.TooManyRedirects as exc:
            raise FetchError("Too many redirects.") from exc
        except httpx.TimeoutException as exc:
            raise FetchError(
                f"Timed out after {settings.fetch_timeout_seconds:.0f}s fetching the page."
            ) from exc
        except httpx.HTTPError as exc:
            raise FetchError(f"Could not fetch the page: {exc.__class__.__name__}.") from exc
