import ipaddress

import httpx
import pytest

from app import fetcher
from app.fetcher import (
    BlockedAddressError,
    FetchError,
    InvalidURLError,
    NotHTMLError,
    fetch_page,
    is_public_ip,
    resolve_public_ips,
    validate_url,
)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254",
        "100.64.0.1", "0.0.0.0", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "224.0.0.1",
    ],
)
def test_private_and_reserved_ips_are_blocked(ip):
    assert not is_public_ip(ipaddress.ip_address(ip))


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_ips_are_allowed(ip):
    assert is_public_ip(ipaddress.ip_address(ip))


@pytest.mark.parametrize(
    "url,error",
    [
        ("ftp://example.com", InvalidURLError),
        ("file:///etc/passwd", InvalidURLError),
        ("http://user:pass@example.com", InvalidURLError),
        ("http://localhost:8000", BlockedAddressError),
        ("http://db.internal/", BlockedAddressError),
    ],
)
def test_validate_url_rejects(url, error):
    with pytest.raises(error):
        validate_url(url)


async def test_ip_literal_is_checked():
    with pytest.raises(BlockedAddressError):
        await resolve_public_ips("127.0.0.1", 80)
    with pytest.raises(BlockedAddressError):
        await resolve_public_ips("[::1]", 80)


async def test_hostname_resolving_to_private_ip_is_blocked(monkeypatch):
    async def fake_lookup(host, port):
        return ["93.184.215.14", "10.1.2.3"]  # one public, one private: must still block

    monkeypatch.setattr(fetcher, "_dns_lookup", fake_lookup)
    with pytest.raises(BlockedAddressError):
        await resolve_public_ips("evil.example", 80)


@pytest.fixture
def public_dns(monkeypatch):
    async def ok(host, port):
        return ["93.184.215.14"]

    monkeypatch.setattr(fetcher, "resolve_public_ips", ok)


async def test_rejects_non_html(public_dns):
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
    )
    with pytest.raises(NotHTMLError):
        await fetch_page("https://example.com/file.pdf", transport=transport)


async def test_follows_redirects_and_returns_final_url(public_dns):
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<h1>hi</h1>")

    page = await fetch_page("https://example.com/old", transport=httpx.MockTransport(handler))
    assert page.final_url == "https://example.com/new"
    assert page.html == b"<h1>hi</h1>"
    assert page.encoding == "utf-8"


async def test_http_error_status_is_reported(public_dns):
    transport = httpx.MockTransport(lambda r: httpx.Response(404, headers={"content-type": "text/html"}))
    with pytest.raises(FetchError, match="404"):
        await fetch_page("https://example.com/missing", transport=transport)


async def test_guarded_backend_blocks_redirect_to_private_ip():
    # The real transport: a redirect to 127.0.0.1 must be refused at connect time.
    backend = fetcher.GuardedNetworkBackend()
    with pytest.raises(BlockedAddressError):
        await backend.connect_tcp("127.0.0.1", 80)
