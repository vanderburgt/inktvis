"""CLI entry point for Inktvis."""

import asyncio
import re
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .assembler import assemble
from .cost_estimator import BudgetTracker, estimate_cost
from .header_stripper import strip_headers
from .ocr_cloud import ocr_page as ocr_page_cloud
from .structure_parser import parse_structure

console = Console()


def _sort_scans(input_dir: Path) -> list[Path]:
    """Sort scan files by numeric suffix extracted from filenames."""
    extensions = {".jpg", ".jpeg", ".png"}
    files = [f for f in input_dir.iterdir() if f.suffix.lower() in extensions]

    def extract_number(path: Path) -> int:
        match = re.search(r"(\d+)", path.stem)
        if match:
            return int(match.group(1))
        return 0

    files.sort(key=extract_number)
    return files


def _extract_scan_number(path: Path) -> int:
    """Extract the numeric scan number from a filename."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def _filter_page_range(files: list[Path], page_range: str | None) -> list[Path]:
    """Filter files to the specified page range (1-indexed)."""
    if not page_range:
        return files

    match = re.match(r"^(\d+)-(\d+)$", page_range)
    if not match:
        console.print(f"[red]Invalid page range: {page_range}. Use format '1-10'.[/red]")
        sys.exit(1)

    start = int(match.group(1)) - 1  # Convert to 0-indexed
    end = int(match.group(2))
    return files[start:end]


@click.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option("--mode", type=click.Choice(["local", "cloud"]), default="cloud", help="Processing mode.")
@click.option("--api-key", envvar="OPENROUTER_API_KEY", help="OpenRouter API key.")
@click.option("--budget", type=float, default=12.0, help="Maximum spend in USD.")
@click.option("--model", default="google/gemini-2.5-flash", help="OpenRouter model ID.")
@click.option("--workers", type=int, default=1, help="Concurrent API requests (cloud mode).")
@click.option("--page-range", default=None, help="Process subset, e.g. '1-10'.")
@click.option("--verbose", is_flag=True, help="Show per-page details.")
@click.option("--dry-run", is_flag=True, help="Estimate cost without processing (cloud mode).")
def main(
    input_dir: Path,
    output_file: Path,
    mode: str,
    api_key: str | None,
    budget: float,
    model: str,
    workers: int,
    page_range: str | None,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Convert scanned book pages to structured Markdown.

    INPUT_DIR: Directory containing scan JPEGs.
    OUTPUT_FILE: Path for the output Markdown file.
    """
    files = _sort_scans(input_dir)
    if not files:
        console.print("[red]No JPEG files found in input directory.[/red]")
        sys.exit(1)

    files = _filter_page_range(files, page_range)
    console.print(f"Found [bold]{len(files)}[/bold] pages to process.")

    if mode == "cloud":
        est_cost, page_count = estimate_cost(input_dir, model)
        console.print(f"Estimated cost: [bold]${est_cost:.2f}[/bold] for {page_count} pages (budget: ${budget:.2f})")

        if dry_run:
            return

        if not api_key:
            console.print("[red]API key required for cloud mode. Set --api-key or OPENROUTER_API_KEY.[/red]")
            sys.exit(1)

        if est_cost > budget:
            console.print("[red]Estimated cost exceeds budget. Aborting.[/red]")
            sys.exit(1)

        if not click.confirm("Proceed with cloud processing?"):
            return

        asyncio.run(_process_cloud(files, output_file, api_key, model, budget, workers, verbose))

    elif mode == "local":
        _process_local(files, output_file, verbose)


async def _process_cloud(
    files: list[Path],
    output_file: Path,
    api_key: str,
    model: str,
    budget: float,
    workers: int,
    verbose: bool,
) -> None:
    """Process pages using cloud vision LLM."""
    tracker = BudgetTracker(budget)
    pages: list[str] = []
    page_numbers: list[int | None] = []
    failed: list[tuple[int, str]] = []

    semaphore = asyncio.Semaphore(workers)

    async def process_one(idx: int, file: Path) -> tuple[int, str | None, int | None]:
        async with semaphore:
            if tracker.exceeded:
                return idx, None, None
            try:
                text, cost, page_num = await ocr_page_cloud(file, api_key, model)
                tracker.record(idx + 1, cost)
                if verbose:
                    console.print(f"  Page {idx + 1}: ${cost:.4f}")
                return idx, text, page_num
            except Exception as e:
                return idx, None, None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing pages...", total=len(files))

        if workers == 1:
            # Sequential processing
            for idx, file in enumerate(files):
                if tracker.exceeded:
                    console.print(f"[red]Budget exceeded at page {idx + 1}. Stopping.[/red]")
                    break
                _, text, page_num = await process_one(idx, file)
                if text is not None:
                    pages.append(text)
                    page_numbers.append(page_num)
                else:
                    failed.append((idx + 1, str(files[idx])))
                    pages.append("")  # placeholder
                    page_numbers.append(None)
                progress.advance(task)
        else:
            # Concurrent processing
            tasks = [process_one(idx, f) for idx, f in enumerate(files)]
            results: list[tuple[str | None, int | None]] = [(None, None)] * len(files)
            for coro in asyncio.as_completed(tasks):
                idx, text, page_num = await coro
                if text is not None:
                    results[idx] = (text, page_num)
                else:
                    failed.append((idx + 1, str(files[idx])))
                progress.advance(task)
            pages = [r[0] if r[0] is not None else "" for r in results]
            page_numbers = [r[1] for r in results]

    if failed:
        console.print(f"\n[yellow]Failed pages: {', '.join(str(f[0]) for f in failed)}[/yellow]")

    console.print(f"\nTotal cost: [bold]${tracker.spent:.4f}[/bold]")
    scan_numbers = [_extract_scan_number(f) for f in files]
    assemble(pages, output_file, scan_numbers=scan_numbers, page_numbers=page_numbers)
    console.print(f"Output written to [bold]{output_file}[/bold]")


def _process_local(files: list[Path], output_file: Path, verbose: bool) -> None:
    """Process pages using local Tesseract OCR."""
    from .ocr_local import ocr_page as ocr_page_local

    raw_pages: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("OCR processing...", total=len(files))
        for idx, file in enumerate(files):
            try:
                text = ocr_page_local(file)
                raw_pages.append(text)
                if verbose:
                    console.print(f"  Page {idx + 1}: {len(text)} chars")
            except Exception as e:
                console.print(f"[red]Page {idx + 1} failed: {e}[/red]")
                raw_pages.append("")
            progress.advance(task)

    # Strip running headers/footers
    console.print("Stripping running headers/footers...")
    cleaned = strip_headers(raw_pages)

    # Apply structure parsing
    console.print("Parsing document structure...")
    structured = [parse_structure(page) for page in cleaned]

    scan_numbers = [_extract_scan_number(f) for f in files]
    assemble(structured, output_file, scan_numbers=scan_numbers)
    console.print(f"Output written to [bold]{output_file}[/bold]")


if __name__ == "__main__":
    main()
