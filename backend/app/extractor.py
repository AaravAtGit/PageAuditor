"""Deterministic on-page signal extraction. No LLM involved here."""

import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from app.schemas import FAQItem, Heading, ImageAltCoverage, LinkCounts, Signals

MAX_HEADINGS = 60
MAX_FAQ = 20
MAX_TEXT = 300  # chars kept per heading / FAQ field
LEAD_EXCERPT_CHARS = 1500
NON_CONTENT_TAGS = ["script", "style", "noscript", "template", "svg", "iframe"]
SKIP_LINK_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:")


def _clean(text: str | None, limit: int = MAX_TEXT) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": re.compile(f"^{name}$", re.I)})
    content = tag.get("content") if tag else None
    return _clean(content) or None


def _canonical(soup: BeautifulSoup, base_url: str) -> str | None:
    for link in soup.find_all("link", href=True):
        rel = link.get("rel") or []
        if any(r.lower() == "canonical" for r in rel):
            return urljoin(base_url, link["href"].strip())
    return None


def _headings(soup: BeautifulSoup) -> list[Heading]:
    out = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = _clean(tag.get_text(" "))
        if text:
            out.append(Heading(level=int(tag.name[1]), text=text))
        if len(out) >= MAX_HEADINGS:
            break
    return out


def _walk_jsonld(node, types: list[str], faq: list[FAQItem]) -> None:
    """Collect every @type (including nested ones) and FAQPage Q&A pairs."""
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, types, faq)
        return
    if not isinstance(node, dict):
        return

    node_type = node.get("@type")
    for t in node_type if isinstance(node_type, list) else [node_type]:
        if isinstance(t, str) and t not in types:
            types.append(t)

    if node_type == "Question" or (isinstance(node_type, list) and "Question" in node_type):
        answer = node.get("acceptedAnswer") or node.get("suggestedAnswer") or {}
        if isinstance(answer, list):
            answer = answer[0] if answer else {}
        answer_html = str(answer.get("text", "")) if isinstance(answer, dict) else ""
        # Answer text in FAQPage schema often contains HTML; strip it to plain text.
        q = _clean(str(node.get("name", "")))
        a = _clean(BeautifulSoup(answer_html, "lxml").get_text(" ")) if answer_html else ""
        if q and a:
            faq.append(FAQItem(question=q, answer=a, source="jsonld"))

    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_jsonld(value, types, faq)


def _jsonld(soup: BeautifulSoup) -> tuple[list[str], int, list[FAQItem]]:
    types: list[str] = []
    faq: list[FAQItem] = []
    invalid = 0
    for script in soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            invalid += 1
            continue
        _walk_jsonld(data, types, faq)
    return types, invalid, faq


def _next_content_text(heading: Tag) -> str:
    """Text of the elements after a heading, up to the next heading."""
    parts = []
    for sib in heading.find_next_siblings():
        if sib.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            break
        parts.append(sib.get_text(" "))
        if sum(len(p) for p in parts) > MAX_TEXT:
            break
    return _clean(" ".join(parts))


def _html_faq(soup: BeautifulSoup) -> list[FAQItem]:
    items: list[FAQItem] = []

    # <details><summary>Question?</summary>Answer</details>
    for details in soup.find_all("details"):
        summary = details.find("summary")
        if not summary:
            continue
        q = _clean(summary.get_text(" "))
        summary_text = summary.get_text(" ")
        a = _clean(details.get_text(" ").replace(summary_text, "", 1))
        if q and a:
            items.append(FAQItem(question=q, answer=a, source="details"))

    # Headings phrased as questions, answered by the following content
    for heading in soup.find_all(["h2", "h3", "h4"]):
        q = _clean(heading.get_text(" "))
        if q.endswith("?"):
            a = _next_content_text(heading)
            if a:
                items.append(FAQItem(question=q, answer=a, source="heading"))

    # <dl><dt>Question?</dt><dd>Answer</dd></dl>
    for dt in soup.find_all("dt"):
        q = _clean(dt.get_text(" "))
        dd = dt.find_next_sibling("dd")
        if q.endswith("?") and dd:
            items.append(FAQItem(question=q, answer=_clean(dd.get_text(" ")), source="definition_list"))

    return items


def _host_key(host: str | None) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def _links(soup: BeautifulSoup, base_url: str) -> LinkCounts:
    base_host = _host_key(urlsplit(base_url).hostname)
    internal = external = 0
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.lower().startswith(SKIP_LINK_SCHEMES):
            continue
        absolute = urlsplit(urljoin(base_url, href))
        if absolute.scheme not in ("http", "https"):
            continue
        if _host_key(absolute.hostname) == base_host:
            internal += 1
        else:
            external += 1
    return LinkCounts(internal=internal, external=external)


def _images(soup: BeautifulSoup) -> ImageAltCoverage:
    total = with_alt = empty_alt = missing_alt = 0
    for img in soup.find_all("img"):
        total += 1
        alt = img.get("alt")
        if alt is None:
            missing_alt += 1
        elif alt.strip():
            with_alt += 1
        else:
            empty_alt += 1
    return ImageAltCoverage(
        total=total,
        with_alt=with_alt,
        empty_alt=empty_alt,
        missing_alt=missing_alt,
        coverage=round(with_alt / total, 3) if total else 1.0,
    )


def _lead_excerpt(body: Tag) -> str:
    main = body.find("main") or body.find("article") or body
    paragraphs = [_clean(p.get_text(" "), 10_000) for p in main.find_all("p")]
    text = " ".join(p for p in paragraphs if len(p) > 40)
    return _clean(text or main.get_text(" "), LEAD_EXCERPT_CHARS)


def extract_signals(html: bytes | str, base_url: str, encoding: str | None = None) -> Signals:
    soup = BeautifulSoup(html, "lxml", from_encoding=encoding if isinstance(html, bytes) else None)

    # JSON-LD must be read before we strip <script> tags for the text pass.
    jsonld_types, jsonld_invalid, jsonld_faq = _jsonld(soup)

    title_tag = soup.find("title")
    html_tag = soup.find("html")
    signals = dict(
        title=_clean(title_tag.get_text()) if title_tag else None,
        meta_description=_meta(soup, "description"),
        canonical=_canonical(soup, base_url),
        lang=(html_tag.get("lang") or None) if html_tag else None,
        links=_links(soup, base_url),
        images=_images(soup),
    )

    for tag in soup(NON_CONTENT_TAGS):
        tag.decompose()

    body = soup.body or soup
    faq = (jsonld_faq + _html_faq(soup))[:MAX_FAQ]

    return Signals(
        **signals,
        headings=_headings(soup),
        word_count=len(body.get_text(" ").split()),
        jsonld_types=jsonld_types,
        jsonld_invalid_blocks=jsonld_invalid,
        faq=faq,
        lead_excerpt=_lead_excerpt(body),
    )
