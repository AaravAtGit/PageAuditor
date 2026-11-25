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
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",  # IPv4 loopback disguised as IPv6
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
    """Skip real DNS in these tests: pretend everything is public except 127.0.0.1."""

    async def fake_check(url):
        if "127.0.0.1" in url:
            raise FetchError("private")

    monkeypatch.setattr(fetcher, "check_host_is_public", fake_check)


@respx.mock
async def test_follows_redirects(only_localhost_blocked):
    respx.get("https://example.com/old").respond(301, headers={"location": "/new"})
    respx.get("https://example.com/new").respond(200, headers={"content-type": "text/html"}, text="<h1>hi</h1>")
    assert await fetch_html("https://example.com/old") == ("https://example.com/new", "<h1>hi</h1>")


@respx.mock
async def test_blocks_redirect_to_private_ip(only_localhost_blocked):
    respx.get("https://example.com/").respond(302, headers={"location": "http://127.0.0.1/admin"})
    with pytest.raises(FetchError):
        await fetch_html("https://example.com/")


@respx.mock
async def test_rejects_non_html(only_localhost_blocked):
    respx.get("https://example.com/a.pdf").respond(200, headers={"content-type": "application/pdf"})
    with pytest.raises(FetchError) as exc:
        await fetch_html("https://example.com/a.pdf")
    assert exc.value.status_code == 415
