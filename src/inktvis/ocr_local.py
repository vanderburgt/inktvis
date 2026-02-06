"""Local OCR using Tesseract with hOCR output for bold detection."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytesseract
from PIL import Image

from .preprocessor import preprocess


def ocr_page(image_path: Path) -> str:
    """OCR a single page using Tesseract with bold detection via hOCR.

    Args:
        image_path: Path to the scan JPEG.

    Returns:
        Extracted text with **bold** markers applied.
    """
    preprocessed = preprocess(image_path)
    try:
        hocr = pytesseract.image_to_pdf_or_hocr(
            str(preprocessed),
            lang="nld",
            extension="hocr",
            config="--oem 1",
        )
        text = _parse_hocr(hocr)
    finally:
        preprocessed.unlink(missing_ok=True)

    return text


def _parse_hocr(hocr_bytes: bytes) -> str:
    """Parse hOCR XML to extract text with bold markers.

    Bold detection uses font size/weight attributes from Tesseract's hOCR output.
    """
    hocr_str = hocr_bytes.decode("utf-8", errors="replace")
    # Fix common hOCR issues for XML parsing
    hocr_str = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", hocr_str)

    try:
        root = ET.fromstring(hocr_str)
    except ET.ParseError:
        # Fallback: strip HTML tags and return plain text
        return _fallback_extract(hocr_str)

    ns = {"html": "http://www.w3.org/1999/xhtml"}
    lines = []
    current_line: list[str] = []

    for elem in root.iter():
        tag = elem.tag.replace(f"{{{ns['html']}}}", "")
        classes = elem.get("class", "")

        if "ocr_line" in classes:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []

        if "ocrx_word" in classes:
            word = (elem.text or "").strip()
            if not word:
                continue

            title = elem.get("title", "")
            is_bold = _is_bold(title, elem)

            if is_bold:
                current_line.append(f"**{word}**")
            else:
                current_line.append(word)

    if current_line:
        lines.append(" ".join(current_line))

    # Merge consecutive bold words
    text = "\n".join(lines)
    text = re.sub(r"\*\*\s+\*\*", " ", text)  # merge adjacent bold markers
    # Clean up **word** **word** -> **word word**
    text = re.sub(r"\*\*([^*]+)\*\*(\s+)\*\*([^*]+)\*\*", r"**\1\2\3**", text)
    # Repeat to catch chains
    text = re.sub(r"\*\*([^*]+)\*\*(\s+)\*\*([^*]+)\*\*", r"**\1\2\3**", text)

    return text


def _is_bold(title: str, elem: ET.Element) -> bool:
    """Detect if a word is bold based on hOCR attributes."""
    # Check for x_font attributes indicating bold
    if "Bold" in title or "bold" in title:
        return True
    # Check font weight in style
    style = elem.get("style", "")
    if "font-weight" in style and "bold" in style:
        return True
    return False


def _fallback_extract(hocr_str: str) -> str:
    """Extract plain text from hOCR when XML parsing fails."""
    text = re.sub(r"<[^>]+>", " ", hocr_str)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
