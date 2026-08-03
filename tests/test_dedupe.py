"""
test_dedupe.py

Tests for src/utils/dedupe.py - the URL-to-article_id hashing logic.
"""

from src.utils.dedupe import make_article_id


def test_same_url_produces_same_id():
    url = "https://example.com/article/1"
    assert make_article_id(url) == make_article_id(url)


def test_different_urls_produce_different_ids():
    id_a = make_article_id("https://example.com/article/1")
    id_b = make_article_id("https://example.com/article/2")
    assert id_a != id_b


def test_case_and_whitespace_are_normalized():
    """
    Same article, differently-formatted URL (uppercase host, trailing
    whitespace) should still hash to the same ID - this is what makes
    dedup robust to minor formatting differences from the source API.
    """
    id_lower = make_article_id("https://example.com/article/1")
    id_upper_with_space = make_article_id("HTTPS://EXAMPLE.COM/article/1  ")
    assert id_lower == id_upper_with_space


def test_id_is_a_hex_string():
    article_id = make_article_id("https://example.com/article/1")
    assert isinstance(article_id, str)
    assert len(article_id) == 64  # SHA-256 hex digest length
    int(article_id, 16)  # raises ValueError if not valid hex