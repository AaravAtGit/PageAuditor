import pytest
import respx

from app import fetcher
from app.fetcher import FetchError, fetch_html, resolve_public_ip


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "10.0.0.5", "192.168.1.1", "169.254.169.254"])
async def test_blocks_private_ips(host):
    with pytest.raises(FetchError):
        await resolve_public_ip(host)


async def test_allows_public_ip():
    assert await resolve_public_ip("8.8.8.8") == "8.8.8.8"


@pytest.mark.parametrize("url", ["ftp://example.com/", "http://[::1]/", "not a url"])
async def test_rejects_bad_urls(url):
    with pytest.raises(FetchError):
        await fetch_html(url)


@pytest.fixture
def fake_dns(monkeypatch):
    async def fake_resolve(hostname):
        if hostname == "127.0.0.1":
            raise FetchError("private")
        return "93.184.216.34"

    monkeypatch.setattr(fetcher, "resolve_public_ip", fake_resolve)


@respx.mock
async def test_connects_to_checked_ip(fake_dns):
    route = respx.get("https://93.184.216.34/page").respond(200, headers={"content-type": "text/html"}, text="ok")
    assert await fetch_html("https://example.com/page") == ("https://example.com/page", "ok")
    request = route.calls.last.request
    assert request.headers["host"] == "example.com"
    assert request.extensions["sni_hostname"] == "example.com"


@respx.mock
async def test_follows_redirects(fake_dns):
    respx.get("https://93.184.216.34/old").respond(301, headers={"location": "/new"})
    respx.get("https://93.184.216.34/new").respond(200, headers={"content-type": "text/html"}, text="<h1>hi</h1>")
    assert await fetch_html("https://example.com/old") == ("https://example.com/new", "<h1>hi</h1>")


@respx.mock
async def test_blocks_redirect_to_private_ip(fake_dns):
    respx.get("https://93.184.216.34/").respond(302, headers={"location": "http://127.0.0.1/admin"})
    with pytest.raises(FetchError):
        await fetch_html("https://example.com/")


@respx.mock
async def test_rejects_non_html(fake_dns):
    respx.get("https://93.184.216.34/a.pdf").respond(200, headers={"content-type": "application/pdf"})
    with pytest.raises(FetchError) as exc:
        await fetch_html("https://example.com/a.pdf")
    assert exc.value.status_code == 415
