# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                              # Install dependencies
uv run pytest                                        # Run all tests
uv run pytest tests/test_structure_parser.py -v      # Run single test file
uv run pytest -k "test_chapter"                      # Run tests matching pattern
uv run inktvis ./scans output.md --verbose           # Cloud mode (default)
uv run inktvis ./scans output.md --mode local        # Local mode (Tesseract)
uv run inktvis ./scans output.md --dry-run           # Cost estimate only
uv run inktvis ./scans output.md --workers 5         # Concurrent cloud requests
```

## Architecture

Two independent pipelines that both produce a single Markdown file with `<!-- page #N / scan #M -->` markers. Accepts JPEG and PNG input (can be mixed in one directory).

### Cloud pipeline (`--mode cloud`)

`cli.py:_process_cloud()` → `ocr_cloud.py:ocr_page()` → `assembler.py:assemble()`

The vision LLM (via OpenRouter API) handles everything in one pass: OCR, heading hierarchy, table extraction, ASCII diagram reproduction, footnotes, and header/footer exclusion. The system prompt in `ocr_cloud.py:SYSTEM_PROMPT` controls all extraction behavior. The LLM also reports the printed page number as `[page:N]` on the first line, which is parsed and stripped by `_extract_page_number()`.

Post-processing in `_collapse_runaway_lines()` fixes a known model hallucination where vision LLMs generate 100K+ character lines of repeated dashes in table separators and ASCII art. This collapses runs of 4+ dashes/equals/underscores on any line exceeding 500 characters.

Concurrency is controlled by `--workers` (asyncio semaphore). Budget tracking via `cost_estimator.py:BudgetTracker` can halt mid-run.

### Local pipeline (`--mode local`)

`cli.py:_process_local()` → `preprocessor.py` → `ocr_local.py` → `header_stripper.py` → `structure_parser.py` → `assembler.py`

Each stage is separate: image preprocessing (Otsu thresholding), Tesseract OCR with hOCR bold detection, statistical header/footer removal (lines repeating across 3+ consecutive pages), regex-based heading conversion from numbered sections, then assembly. No table/diagram/image support in local mode.

### Key design decisions

- Scan numbers come from filenames (e.g., "Scan 14.jpeg" → 14, "0015.png" → 15); page numbers come from OCR detection of printed page numbers. These are independent.
- Cloud mode prompt changes affect all extraction behavior — there's no post-processing of cloud output (except runaway line collapse).
- `--page-range` operates on sorted file order, not scan numbers.
- Dutch language is hardcoded in both the cloud system prompt and local Tesseract config (`lang="nld"`).
- File discovery in `_sort_scans()` supports `.jpg`, `.jpeg`, and `.png`. MIME type is detected from extension for the API call.
- Cloud retry logic: 3 attempts with exponential backoff (2s base delay). Failed pages get empty placeholders; processing continues.
