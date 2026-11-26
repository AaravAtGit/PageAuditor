import pytest
import respx

from app import fetcher
from app.fetcher import FetchError, check_host_is_public, fetch_html


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost:8000/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "ftp://example.com/",
    ],
)
async def test_blocks_private_and_non_http_urls(url):
    with pytest.raises(FetchError):
        await check_host_is_public(url)


async def test_allows_public_ip():
    await check_host_is_public("http://8.8.8.8/")


@pytest.fixture
def only_localhost_blocked(monkeypatch):
    async def fake_check(url):
        if "127.0.0.1" in url:
            raise FetchError("private")
        return "93.184.216.34"

    monkeypatch.setattr(fetcher, "check_host_is_public", fake_check)


@respx.mock
async def test_follows_redirects(only_localhost_blocked):
    respx.get("https://93.184.216.34:443/old").respond(301, headers={"location": "/new"})
    respx.get("https://93.184.216.34:443/new").respond(200, headers={"content-type": "text/html"}, text="<h1>hi</h1>")
    assert await fetch_html("https://example.com/old") == ("https://example.com/new", "<h1>hi</h1>")


@respx.mock
async def test_blocks_redirect_to_private_ip(only_localhost_blocked):
    respx.get("https://93.184.216.34:443/").respond(302, headers={"location": "http://127.0.0.1/admin"})
    with pytest.raises(FetchError):
        await fetch_html("https://example.com/")


@respx.mock
async def test_rejects_non_html(only_localhost_blocked):
    respx.get("https://93.184.216.34:443/a.pdf").respond(200, headers={"content-type": "application/pdf"})
    with pytest.raises(FetchError) as exc:
        await fetch_html("https://example.com/a.pdf")
    assert exc.value.status_code == 415


@respx.mock
async def test_connects_to_checked_ip_not_a_fresh_lookup(monkeypatch):
    # DNS rebinding: if httpx resolved the name again it could get a private IP.
    # The request must go to the IP we checked, with the real name in Host and SNI.
    async def fake_check(url):
        return "93.184.216.34"

    monkeypatch.setattr(fetcher, "check_host_is_public", fake_check)
    route = respx.get("https://93.184.216.34:443/page").respond(200, headers={"content-type": "text/html"}, text="ok")

    assert await fetch_html("https://rebind.example/page") == ("https://rebind.example/page", "ok")
    request = route.calls.last.request
    assert request.headers["host"] == "rebind.example"
    assert request.extensions["sni_hostname"] == "rebind.example"


async def test_check_returns_ipv4_first(monkeypatch):
    async def fake_getaddrinfo(host, port):
        return [(0, 0, 0, "", ("2a04:4e42::223", port, 0, 0)), (0, 0, 0, "", ("151.101.0.223", port))]

    monkeypatch.setattr(fetcher.asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)
    assert await check_host_is_public("https://python.org/") == "151.101.0.223"
