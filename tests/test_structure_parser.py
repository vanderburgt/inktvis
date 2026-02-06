"""Tests for section numbering detection and heading conversion."""

from inktvis.structure_parser import parse_structure


def test_chapter_heading():
    text = "4 Professioneel gedrag\n\nSome body text here."
    result = parse_structure(text)
    assert result.startswith("## 4 Professioneel gedrag")


def test_section_heading():
    text = "4.1 Gedrag in de school\n\nBody text follows."
    result = parse_structure(text)
    assert "### 4.1 Gedrag in de school" in result


def test_subsection_heading():
    text = "4.1.1 Specifiek gedrag\n\nMore text."
    result = parse_structure(text)
    assert "#### 4.1.1 Specifiek gedrag" in result


def test_multiple_levels():
    text = (
        "4 Professioneel gedrag\n\n"
        "Some intro text.\n\n"
        "4.1 Gedrag in de school\n\n"
        "Body of section.\n\n"
        "4.1.1 Specifiek gedrag\n\n"
        "More detail."
    )
    result = parse_structure(text)
    assert "## 4 Professioneel gedrag" in result
    assert "### 4.1 Gedrag in de school" in result
    assert "#### 4.1.1 Specifiek gedrag" in result


def test_no_false_positive_mid_paragraph():
    text = "We reference section 4.1 in the middle of a sentence."
    result = parse_structure(text)
    # Should NOT create a heading from mid-paragraph reference
    assert "###" not in result


def test_bold_stripped_from_headings():
    text = "4.1 **Gedrag in de school**\n\nBody."
    result = parse_structure(text)
    assert "### 4.1 Gedrag in de school" in result
    assert "**" not in result.split("\n")[0]


def test_preserves_body_text():
    text = "Some normal paragraph text.\n\nAnother paragraph."
    result = parse_structure(text)
    assert result == text


def test_number_only_line_not_heading():
    # A bare number like a page number should not become a heading
    # (only matches if followed by capitalized title of 3+ chars)
    text = "42\n\nSome text."
    result = parse_structure(text)
    assert "##" not in result
