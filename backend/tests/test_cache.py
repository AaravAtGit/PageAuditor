from app.cache import normalize_url


def test_normalize_url():
    assert normalize_url("HTTPS://Example.COM:443/Page?q=1#frag") == "https://example.com/Page?q=1"
    assert normalize_url("http://example.com") == "http://example.com/"
    assert normalize_url("http://example.com:8080/x") == "http://example.com:8080/x"
