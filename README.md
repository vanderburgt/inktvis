# Inktvis

Convert scanned book pages (JPEG/PNG) into a single, well-structured Markdown file — optimized for use as LLM context.

For projects that require ingestion of information that is only available in hard copy.

Inktvis extracts text from 300 DPI color scans of books, applies heading hierarchy based on section numbering, strips running headers/footers, preserves bold formatting and footnotes, and assembles everything into one clean `.md` file.

## Features

- **Two processing modes**: cloud (vision LLM via OpenRouter) or local (Tesseract OCR)
- **Heading hierarchy**: `4` → H2, `4.1` → H3, `4.1.1` → H4
- **Running header/footer removal**: statistical detection (local) or prompt-based (cloud)
- **Bold text** preserved as `**bold**`
- **Footnotes** converted to Markdown syntax (`[^1]` inline, `[^1]: text` at end)
- **Table extraction** as proper Markdown tables (cloud mode)
- **Diagram reproduction** as ASCII art in code blocks (cloud mode)
- **Image descriptions** as blockquote text (cloud mode)
- **Page traceability** via `<!-- page #N / scan #M -->` comments
- **Cost control**: budget ceiling, dry-run estimates, per-page cost logging
- **Dutch language** optimized (works with other languages by changing model/Tesseract lang)

## Installation

Inktvis requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) (a fast Python package manager).

### Linux

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone <repo-url> && cd inktvis
uv sync
```

### macOS

```bash
# Install uv if you don't have it
brew install uv

# Clone and install
git clone <repo-url> && cd inktvis
uv sync
```

### Windows

```powershell
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone and install
git clone <repo-url>
cd inktvis
uv sync
```

For local mode, also install Tesseract with Dutch language support:

```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-nld

# Windows — download installer from https://github.com/UB-Mannheim/tesseract/wiki
# and add to PATH

# Verify
tesseract --list-langs | grep nld
```

## Usage

After installation, run `inktvis` via `uv run` from the project directory:

```bash
uv run inktvis ./scans output.md
```

### Cloud mode (recommended)

Requires an [OpenRouter](https://openrouter.ai/) API key.

```bash
# Set API key (add to .env or export)
export OPENROUTER_API_KEY=sk-or-...

# Process all scans
uv run inktvis ./scans output.md

# Estimate cost without processing
uv run inktvis ./scans output.md --dry-run

# Process a subset for testing
uv run inktvis ./scans output.md --page-range 1-5 --verbose

# Speed up with concurrent requests
uv run inktvis ./scans output.md --workers 5

# Pass API key directly
uv run inktvis ./scans output.md --api-key sk-or-...
```

### Local mode

```bash
uv run inktvis ./scans output.md --mode local --verbose
```

### All options

```
inktvis <input_dir> <output_file> [options]

Arguments:
  input_dir              Directory containing scan images (JPEG/PNG)
  output_file            Path for the output Markdown file

Options:
  --mode [local|cloud]   Processing mode (default: cloud)
  --api-key TEXT         OpenRouter API key (or OPENROUTER_API_KEY env var)
  --budget FLOAT         Maximum spend in USD (default: 12.0)
  --model TEXT           OpenRouter model ID
  --workers INT          Concurrent API requests, cloud mode only (default: 1)
  --page-range TEXT      Process subset, e.g. "1-10" for testing
  --verbose              Show per-page processing details
  --dry-run              Estimate cost without processing (cloud mode)
```

## How it works

### Cloud pipeline

Each page image is sent to a vision LLM with a structured prompt that instructs the model to OCR the text, apply Markdown formatting, and strip headers/footers — all in one pass. Pages are processed sequentially with retry logic and budget tracking.

### Local pipeline

1. **Preprocessing** — convert to grayscale, apply Otsu thresholding
2. **Tesseract OCR** — extract text via hOCR with bold detection from font attributes
3. **Header stripping** — detect lines repeating across 3+ consecutive pages in the same position
4. **Structure parsing** — regex-based conversion of numbered sections to Markdown headings
5. **Assembly** — concatenate into a single `.md` file with page markers

## Input requirements

- JPEG or PNG files in a single directory (can be mixed)
- Filenames with numeric ordering (e.g., `Scan 1.jpeg`, `Scan 2.jpeg`, `0001.png`, ...)
- 300 DPI recommended (works at other resolutions but accuracy may vary)

### Page ordering and gaps in numbering

Inktvis sorts files by the number extracted from each filename and processes them in that order. Gaps in numbering are allowed — `Scan 1.jpeg`, `Scan 3.jpeg`, `Scan 7.jpeg` will be processed in that order. The output markers use the format `<!-- page #N / scan #M -->` where the page number is the printed page number detected by OCR (or `none` for unnumbered pages like covers), and the scan number is from the original filename.

This is intentional. It means you can:

- **Rescan a page** by replacing the file (e.g., drop in a better `Scan 5.jpeg` and rerun).
- **Remove pages** by deleting files from the directory before processing.
- **Reorder pages** by renumbering files to control the sequence.
- **Insert pages** by using intermediate numbers (e.g., add `Scan 4.jpeg` between `Scan 3.jpeg` and `Scan 5.jpeg`).

The `--page-range` option also works on processing order, not scan numbers. `--page-range 1-3` processes the first three files in sorted order regardless of their filenames.

## Cost

Cloud mode roughly costs $0.001 per page (as per 6 Feb 2026)

## Known limitations

- Footnotes spanning multiple pages may be truncated
- Local mode bold detection is approximate (~80% accuracy)
- Table extraction, diagram reproduction, and image descriptions are cloud-mode only
- ASCII diagram fidelity depends on diagram complexity — simple box-and-arrow diagrams work best

## Roadmap

- Optimizations for local processing on lower end machines
- Switch language
- More router integrations (EdenAI, etc.)