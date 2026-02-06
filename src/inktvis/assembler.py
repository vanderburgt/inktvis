"""Page concatenation and final Markdown output assembly."""

from pathlib import Path


def assemble(
    pages: list[str],
    output_path: Path,
    scan_numbers: list[int] | None = None,
    page_numbers: list[int | None] | None = None,
) -> None:
    """Join processed pages into a single Markdown file with page markers.

    Args:
        pages: List of processed Markdown page texts.
        output_path: Path for the output .md file.
        scan_numbers: Original scan numbers from filenames (1-indexed).
        page_numbers: Printed page numbers from OCR (None if not detected).
    """
    parts = []
    for i, page in enumerate(pages):
        scan_num = scan_numbers[i] if scan_numbers else i + 1
        page_num = page_numbers[i] if page_numbers else None
        page_label = f"#{page_num}" if page_num is not None else "none"
        parts.append(f"<!-- page {page_label} / scan #{scan_num} -->")
        parts.append(page.strip())
        parts.append("")  # blank line after each page

    content = "\n".join(parts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
