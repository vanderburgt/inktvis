"""Running header/footer detection and removal for local OCR mode."""


def strip_headers(pages: list[str], min_consecutive: int = 3) -> list[str]:
    """Remove running headers and footers from page texts.

    Detects lines appearing in the same position (first 2 or last 2 lines)
    across min_consecutive or more consecutive pages.

    Args:
        pages: List of raw OCR page texts.
        min_consecutive: Minimum consecutive pages for a line to be classified
            as a running header/footer.

    Returns:
        List of page texts with headers/footers removed.
    """
    if len(pages) < min_consecutive:
        return pages

    header_lines = _find_repeating_lines(pages, position="top", min_consecutive=min_consecutive)
    footer_lines = _find_repeating_lines(pages, position="bottom", min_consecutive=min_consecutive)

    result = []
    for i, page in enumerate(pages):
        lines = page.split("\n")
        cleaned = _remove_lines(lines, header_lines.get(i, set()), footer_lines.get(i, set()))
        result.append("\n".join(cleaned).strip())

    return result


def _find_repeating_lines(
    pages: list[str], position: str, min_consecutive: int, check_lines: int = 2
) -> dict[int, set[int]]:
    """Find line indices that are repeating headers/footers.

    Returns:
        Dict mapping page index to set of line indices to remove.
    """
    removals: dict[int, set[int]] = {}

    for line_offset in range(check_lines):
        # Track consecutive runs
        run_start = 0
        run_text = None

        for i in range(len(pages)):
            lines = pages[i].split("\n")

            if position == "top":
                idx = line_offset
            else:  # bottom
                idx = len(lines) - 1 - line_offset

            if idx < 0 or idx >= len(lines):
                # End current run
                if run_text is not None and (i - run_start) >= min_consecutive:
                    for j in range(run_start, i):
                        page_lines = pages[j].split("\n")
                        target_idx = line_offset if position == "top" else len(page_lines) - 1 - line_offset
                        if target_idx >= 0 and target_idx < len(page_lines):
                            removals.setdefault(j, set()).add(target_idx)
                run_text = None
                continue

            current = lines[idx].strip()
            if not current:
                # Skip blank lines, end run
                if run_text is not None and (i - run_start) >= min_consecutive:
                    for j in range(run_start, i):
                        page_lines = pages[j].split("\n")
                        target_idx = line_offset if position == "top" else len(page_lines) - 1 - line_offset
                        if target_idx >= 0 and target_idx < len(page_lines):
                            removals.setdefault(j, set()).add(target_idx)
                run_text = None
                continue

            # Normalize for comparison (ignore case, extra spaces)
            normalized = " ".join(current.lower().split())

            if run_text is not None and normalized == run_text:
                # Continue run
                pass
            elif run_text is not None and normalized != run_text:
                # End run, check if long enough
                if (i - run_start) >= min_consecutive:
                    for j in range(run_start, i):
                        page_lines = pages[j].split("\n")
                        target_idx = line_offset if position == "top" else len(page_lines) - 1 - line_offset
                        if target_idx >= 0 and target_idx < len(page_lines):
                            removals.setdefault(j, set()).add(target_idx)
                run_start = i
                run_text = normalized
            else:
                # Start new run
                run_start = i
                run_text = normalized

        # Handle final run
        if run_text is not None and (len(pages) - run_start) >= min_consecutive:
            for j in range(run_start, len(pages)):
                page_lines = pages[j].split("\n")
                target_idx = line_offset if position == "top" else len(page_lines) - 1 - line_offset
                if target_idx >= 0 and target_idx < len(page_lines):
                    removals.setdefault(j, set()).add(target_idx)

    return removals


def _remove_lines(lines: list[str], header_indices: set[int], footer_indices: set[int]) -> list[str]:
    """Remove lines at specified indices."""
    to_remove = header_indices | footer_indices
    return [line for i, line in enumerate(lines) if i not in to_remove]
