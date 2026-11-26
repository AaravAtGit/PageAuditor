import json
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from app.schemas import Signals


def extract_signals(html: str, url: str) -> Signals:
    soup = BeautifulSoup(html, "lxml")

    meta = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", rel="canonical")
    images = soup.find_all("img")
    images_with_alt = sum(1 for img in images if img.get("alt", "").strip())
    schema_types = find_schema_types(soup)
    internal, external = count_links(soup, url)

    # drop non-visible content before reading the text
    # (images and JSON-LD are read above because they can live inside these tags)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())

    headings = [f"{h.name.upper()}: {h.get_text(' ', strip=True)}" for h in soup.find_all(["h1", "h2", "h3"])]
    questions = [q.get_text(" ", strip=True) for q in soup.find_all(["h2", "h3", "h4", "summary", "dt"])]

    return Signals(
        title=soup.title.get_text(strip=True) if soup.title else None,
        meta_description=meta.get("content") if meta else None,
        canonical=urljoin(url, canonical["href"]) if canonical else None,
        headings=headings,
        word_count=len(text.split()),
        schema_types=schema_types,
        faq=[q for q in questions if q.endswith("?")],
        internal_links=internal,
        external_links=external,
        images=len(images),
        images_with_alt=images_with_alt,
        intro_text=text[:1000],
    )


def find_schema_types(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            collect_types(json.loads(script.string or ""), found)
        except json.JSONDecodeError:
            pass
    return found


def collect_types(data, found: list[str]) -> None:
    # JSON-LD nests objects anywhere (@graph, mainEntity...), so walk the whole tree
    if isinstance(data, list):
        for item in data:
            collect_types(item, found)
    elif isinstance(data, dict):
        types = data.get("@type", [])
        for t in types if isinstance(types, list) else [types]:
            if t not in found:
                found.append(t)
        for value in data.values():
            collect_types(value, found)


def count_links(soup: BeautifulSoup, url: str) -> tuple[int, int]:
    site = urlsplit(url).netloc.removeprefix("www.")
    internal = external = 0
    for a in soup.find_all("a", href=True):
        link = urlsplit(urljoin(url, a["href"]))
        if link.scheme not in ("http", "https"):
            continue  # mailto:, tel:, javascript:
        if link.netloc.removeprefix("www.") == site:
            internal += 1
        else:
            external += 1
    return internal, external
