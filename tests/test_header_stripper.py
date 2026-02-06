"""Tests for running header/footer detection and removal."""

from inktvis.header_stripper import strip_headers


def test_strips_repeating_header():
    pages = [
        "Chapter Title\nBody text page 1.",
        "Chapter Title\nBody text page 2.",
        "Chapter Title\nBody text page 3.",
        "Chapter Title\nBody text page 4.",
    ]
    result = strip_headers(pages, min_consecutive=3)
    for page in result:
        assert "Chapter Title" not in page
        assert "Body text" in page


def test_strips_repeating_footer():
    pages = [
        "Body text page 1.\nHandboek professionele schoolcultuur",
        "Body text page 2.\nHandboek professionele schoolcultuur",
        "Body text page 3.\nHandboek professionele schoolcultuur",
    ]
    result = strip_headers(pages, min_consecutive=3)
    for page in result:
        assert "Handboek" not in page
        assert "Body text" in page


def test_preserves_non_repeating_lines():
    pages = [
        "Unique header 1\nBody 1.\nFooter 1",
        "Unique header 2\nBody 2.\nFooter 2",
        "Unique header 3\nBody 3.\nFooter 3",
    ]
    result = strip_headers(pages, min_consecutive=3)
    assert "Unique header 1" in result[0]
    assert "Body 1." in result[0]


def test_fewer_than_min_consecutive():
    pages = [
        "Header\nBody 1.",
        "Header\nBody 2.",
    ]
    # With min_consecutive=3, two pages isn't enough to detect
    result = strip_headers(pages, min_consecutive=3)
    assert "Header" in result[0]
    assert "Header" in result[1]


def test_empty_pages():
    pages = ["", "", ""]
    result = strip_headers(pages)
    assert result == ["", "", ""]
