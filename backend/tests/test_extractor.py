from app.extractor import extract_signals

HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>  Acme Widgets | Best Widgets </title>
  <meta name="description" content="Acme makes durable widgets.">
  <link rel="canonical" href="/widgets">
  <script type="application/ld+json">
  {"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "name": "Acme"},
    {"@type": "FAQPage", "mainEntity": [
      {"@type": "Question", "name": "What is a widget?",
       "acceptedAnswer": {"@type": "Answer", "text": "<p>A small <b>gadget</b>.</p>"}}
    ]}
  ]}
  </script>
  <script type="application/ld+json">{ not valid json </script>
  <style>.x { color: red }</style>
</head>
<body>
  <h1>Widgets</h1>
  <p>Acme widgets are built to last for decades and come with a lifetime warranty.</p>
  <h2>How long do widgets last?</h2>
  <p>Most widgets last 20 years.</p>
  <h3>Materials</h3>
  <details><summary>Are they recyclable?</summary>Yes, fully.</details>
  <a href="/about">About</a>
  <a href="https://www.example.com/contact">Contact</a>
  <a href="https://other.org/">Other</a>
  <a href="mailto:hi@example.com">Mail</a>
  <a href="#top">Top</a>
  <img src="a.png" alt="A widget">
  <img src="b.png" alt="">
  <img src="c.png">
  <script>var ignored = "these words should not count";</script>
</body>
</html>
"""


def test_extracts_core_signals():
    s = extract_signals(HTML, "https://example.com/widgets")

    assert s.title == "Acme Widgets | Best Widgets"
    assert s.meta_description == "Acme makes durable widgets."
    assert s.canonical == "https://example.com/widgets"
    assert s.lang == "en"
    assert [(h.level, h.text) for h in s.headings] == [
        (1, "Widgets"),
        (2, "How long do widgets last?"),
        (3, "Materials"),
    ]


def test_jsonld_types_and_invalid_blocks():
    s = extract_signals(HTML, "https://example.com/widgets")
    assert {"Organization", "FAQPage", "Question", "Answer"} <= set(s.jsonld_types)
    assert s.jsonld_invalid_blocks == 1


def test_faq_from_all_sources():
    s = extract_signals(HTML, "https://example.com/widgets")
    by_source = {f.source: f for f in s.faq}
    assert by_source["jsonld"].answer == "A small gadget ."
    assert by_source["heading"].question == "How long do widgets last?"
    assert by_source["details"].answer == "Yes, fully."


def test_links_treat_www_as_internal_and_skip_non_http():
    s = extract_signals(HTML, "https://example.com/widgets")
    assert s.links.internal == 2
    assert s.links.external == 1


def test_image_alt_coverage():
    s = extract_signals(HTML, "https://example.com/widgets")
    assert (s.images.total, s.images.with_alt, s.images.empty_alt, s.images.missing_alt) == (3, 1, 1, 1)
    assert s.images.coverage == 0.333


def test_word_count_ignores_scripts_and_styles():
    s = extract_signals(HTML, "https://example.com/widgets")
    assert s.word_count > 0
    assert "ignored" not in s.lead_excerpt
    assert s.lead_excerpt.startswith("Acme widgets are built")


def test_empty_page_does_not_crash():
    s = extract_signals("<html></html>", "https://example.com/")
    assert s.title is None and s.word_count == 0 and s.images.coverage == 1.0
