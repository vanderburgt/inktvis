"""Cloud OCR using vision LLM via OpenRouter API."""

import asyncio
import base64
import re
from pathlib import Path

import httpx

SYSTEM_PROMPT = """\
You are an OCR and formatting assistant. You will receive a scanned page from a Dutch
non-fiction textbook. Your task:

1. Extract ALL text from the image accurately. This is Dutch text — pay attention to
   Dutch-specific characters and diacritics.

2. Format the extracted text as Markdown:
   - Chapter titles → ## (H2)
   - Section numbers like "4.1 Title" → ### (H3)
   - Sub-sections like "4.1.1 Title" → #### (H4)
   - Bold text → **bold**
   - Preserve paragraph breaks
   - Footnote markers → [^N] inline
   - Footnote text (usually at page bottom) → [^N]: text
   - Tables → Markdown tables using | col | col | syntax with a header separator row.
     IMPORTANT: Keep separator rows short, e.g. | --- | --- |. Never repeat dashes excessively.
   - Diagrams, flowcharts, or architectural figures → reproduce as compact ASCII art
     inside a fenced code block. Use boxes (+--+), arrows (-->, <--), labels, and spatial
     layout. Use plain ASCII characters: +, -, |, >, <, v, ^.
     Keep diagrams concise — max 30 lines, max 80 characters wide. Simplify complex visuals
     rather than generating excessive vertical/horizontal spacing.
   - Photos or other non-diagrammatic images → describe as a blockquote:
     > [Image]: Description of the visual content

3. EXCLUDE:
   - Running headers (chapter title repeated at top of page)
   - Running footers (page numbers at bottom)

4. On the very first line, report the printed page number visible on the scan as
   [page:N] where N is the number, or [page:none] if no page number is visible
   (e.g. cover pages, title pages, blank pages). Then continue with the Markdown content.

5. Return ONLY the page marker and Markdown content. No commentary, no explanations, no code fences.\
"""

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RETRIES = 3
BASE_DELAY = 2.0


async def ocr_page(
    image_path: Path,
    api_key: str,
    model: str = "google/gemini-2.5-flash",
) -> tuple[str, float, int | None]:
    """OCR a single page using a vision LLM via OpenRouter.

    Args:
        image_path: Path to the scan JPEG.
        api_key: OpenRouter API key.
        model: Model identifier.

    Returns:
        Tuple of (markdown text, cost in USD, page number or None).

    Raises:
        httpx.HTTPStatusError: After MAX_RETRIES failed attempts.
    """
    image_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}",
                        },
                    },
                    {
                        "type": "text",
                        "text": "Please extract and format all text from this scanned page.",
                    },
                ],
            },
        ],
        "max_tokens": 8192,
        "temperature": 0.0,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    OPENROUTER_URL, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"]
                # Strip code fences if the model wraps output
                text = _strip_code_fences(text)
                # Fix runaway repeated characters (model hallucination)
                text = _collapse_runaway_lines(text)
                # Extract page number marker from first line
                text, page_number = _extract_page_number(text)

                # Extract cost from usage if available
                usage = data.get("usage", {})
                cost = _estimate_cost_from_usage(usage, model)

                return text, cost, page_number

        except (httpx.HTTPStatusError, httpx.ReadTimeout, KeyError) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = BASE_DELAY * (2**attempt)
            await asyncio.sleep(delay)

    # Should not reach here, but satisfy type checker
    raise RuntimeError("Max retries exceeded")


def _collapse_runaway_lines(text: str) -> str:
    """Collapse runaway repeated characters on excessively long lines.

    Vision models sometimes hallucinate endless dashes in table separators
    and ASCII art borders, producing lines of 100K+ characters.
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        if len(line) > 500:
            line = re.sub(r"-{4,}", "---", line)
            line = re.sub(r"={4,}", "===", line)
            line = re.sub(r"_{4,}", "___", line)
        result.append(line)
    return "\n".join(result)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences if the model wraps its output."""
    text = text.strip()
    if text.startswith("```markdown"):
        text = text[len("```markdown") :]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _extract_page_number(text: str) -> tuple[str, int | None]:
    """Extract [page:N] marker from the first line and return cleaned text + page number."""
    lines = text.split("\n", 1)
    first_line = lines[0].strip()
    match = re.match(r"^\[page:(\d+|none)\]$", first_line, re.IGNORECASE)
    if match:
        remainder = lines[1].strip() if len(lines) > 1 else ""
        value = match.group(1)
        page_num = int(value) if value.lower() != "none" else None
        return remainder, page_num
    return text, None


def _estimate_cost_from_usage(usage: dict, model: str) -> float:
    """Estimate cost in USD from API usage data."""
    # OpenRouter sometimes includes cost directly
    if "total_cost" in usage:
        return float(usage["total_cost"])

    # Rough estimates for common models
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    # Gemini 2.5 Flash pricing (approximate)
    if "gemini" in model.lower() and "flash" in model.lower():
        input_cost = prompt_tokens * 0.10 / 1_000_000
        output_cost = completion_tokens * 0.40 / 1_000_000
    else:
        # Conservative fallback
        input_cost = prompt_tokens * 1.0 / 1_000_000
        output_cost = completion_tokens * 2.0 / 1_000_000

    return input_cost + output_cost
