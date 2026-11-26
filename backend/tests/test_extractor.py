from app.extractor import extract_signals

HTML = """
<html><head>
  <title>Acme Widgets</title>
  <meta name="description" content="Acme makes durable widgets.">
  <link rel="canonical" href="/widgets">
  <script type="application/ld+json">
    {"@graph": [{"@type": "Organization"}, {"@type": "FAQPage", "mainEntity": [{"@type": "Question"}]}]}
  </script>
</head><body>
  <h1>Widgets</h1>
  <p>Acme widgets last for decades.</p>
  <h2>How long do widgets last?</h2>
  <h3>Materials</h3>
  <a href="/about">About</a> <a href="https://www.example.com/x">X</a> <a href="https://other.org">O</a>
  <a href="mailto:hi@example.com">Mail</a>
  <img src="a.png" alt="A widget"> <img src="b.png" alt=""> <img src="c.png">
  <script>var notCounted = 1;</script>
</body></html>
"""


def test_extract_signals():
    s = extract_signals(HTML, "https://example.com/widgets")
    assert s.title == "Acme Widgets"
    assert s.meta_description == "Acme makes durable widgets."
    assert s.canonical == "https://example.com/widgets"
    assert s.headings == ["H1: Widgets", "H2: How long do widgets last?", "H3: Materials"]
    assert s.schema_types == ["Organization", "FAQPage", "Question"]
    assert s.faq == ["How long do widgets last?"]
    assert (s.internal_links, s.external_links) == (2, 1)
    assert (s.images, s.images_with_alt) == (3, 1)
    assert "notCounted" not in s.intro_text
    assert s.word_count > 0


def test_empty_page():
    s = extract_signals("<html></html>", "https://example.com/")
    assert s.title is None and s.word_count == 0


def test_images_inside_noscript():
    s = extract_signals('<noscript><img src="a.png" alt="A"></noscript>', "https://example.com/")
    assert (s.images, s.images_with_alt) == (1, 1)
