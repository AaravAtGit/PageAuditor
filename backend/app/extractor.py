import json
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from app.schemas import Signals


def _jsonld_types(data, found: list[str]) -> None:
    if isinstance(data, list):
        for item in data:
            _jsonld_types(item, found)
    elif isinstance(data, dict):
        types = data.get("@type", [])
        for t in types if isinstance(types, list) else [types]:
            if t not in found:
                found.append(t)
        for value in data.values():
            _jsonld_types(value, found)


def extract_signals(html: str, url: str) -> Signals:
    soup = BeautifulSoup(html, "lxml")

    schema_types: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            _jsonld_types(json.loads(script.string or ""), schema_types)
        except json.JSONDecodeError:
            pass

    meta = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", rel="canonical")

    site = urlsplit(url).netloc.removeprefix("www.")
    internal = external = 0
    for a in soup.find_all("a", href=True):
        link = urlsplit(urljoin(url, a["href"]))
        if link.scheme in ("http", "https"):
            if link.netloc.removeprefix("www.") == site:
                internal += 1
            else:
                external += 1

    images = soup.find_all("img")
    images_with_alt = sum(1 for img in images if img.get("alt", "").strip())

    # count images before this, some of them live inside <noscript>
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    headings = [f"{h.name.upper()}: {h.get_text(' ', strip=True)}" for h in soup.find_all(["h1", "h2", "h3"])]
    faq = [
        el.get_text(" ", strip=True)
        for el in soup.find_all(["h2", "h3", "h4", "summary", "dt"])
        if el.get_text(strip=True).endswith("?")
    ]
    text = " ".join(soup.get_text(" ").split())

    return Signals(
        title=soup.title.get_text(strip=True) if soup.title else None,
        meta_description=meta.get("content") if meta else None,
        canonical=urljoin(url, canonical["href"]) if canonical else None,
        headings=headings[:50],
        word_count=len(text.split()),
        schema_types=schema_types,
        faq=faq[:20],
        internal_links=internal,
        external_links=external,
        images=len(images),
        images_with_alt=images_with_alt,
        intro_text=text[:1000],
    )
