"""Section numbering detection and Markdown heading conversion for local OCR mode."""

import re


# Patterns for numbered sections at the start of a line
# X.Y.Z Title -> #### (H4)
# X.Y Title -> ### (H3)
# X Title -> ## (H2)
SECTION_PATTERNS = [
    # X.Y.Z - subsection (H4)
    (re.compile(r"^(\d+\.\d+\.\d+)[ \t]+(.+)$", re.MULTILINE), 4),
    # X.Y - section (H3)
    (re.compile(r"^(\d+\.\d+)[ \t]+(.+)$", re.MULTILINE), 3),
    # X - chapter (H2), but only when it looks like a heading
    # (single number followed by a capitalized title, not a list item)
    (re.compile(r"^(\d+)[ \t]+([A-Z\u00C0-\u024F].{2,})$", re.MULTILINE), 2),
]


def parse_structure(text: str) -> str:
    """Detect numbered section patterns and convert to Markdown headings.

    Args:
        text: Raw OCR text (possibly with **bold** markers).

    Returns:
        Text with section numbers converted to Markdown heading syntax.
    """
    # Process subsections first (most specific), then sections, then chapters
    for pattern, level in SECTION_PATTERNS:
        text = pattern.sub(lambda m: _make_heading(m, level), text)

    # Collapse excessive blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text


def _make_heading(match: re.Match, level: int) -> str:
    """Convert a regex match to a Markdown heading."""
    number = match.group(1)
    title = match.group(2).strip()
    # Remove bold markers from headings (they're already emphasized by heading level)
    title = title.replace("**", "")
    prefix = "#" * level
    return f"{prefix} {number} {title}"
