"""Token estimation and budget tracking for cloud OCR mode."""

from pathlib import Path


# Average image token count for a 300 DPI JPEG page with vision models
AVG_IMAGE_TOKENS = 1200
# Average output tokens per page
AVG_OUTPUT_TOKENS = 800

# Pricing per 1M tokens (USD) - defaults for Gemini 2.5 Flash
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "google/gemini-2.5-flash": (0.10, 0.40),
    "google/gemini-2.0-flash": (0.10, 0.40),
}
DEFAULT_PRICING = (1.0, 2.0)  # conservative fallback


def estimate_cost(input_dir: Path, model: str) -> tuple[float, int]:
    """Estimate total API cost for processing all pages in a directory.

    Args:
        input_dir: Directory containing scan JPEGs.
        model: OpenRouter model ID.

    Returns:
        Tuple of (estimated cost in USD, page count).
    """
    pages = _count_pages(input_dir)
    input_price, output_price = MODEL_PRICING.get(model, DEFAULT_PRICING)

    total_input_tokens = pages * AVG_IMAGE_TOKENS
    total_output_tokens = pages * AVG_OUTPUT_TOKENS

    cost = (
        total_input_tokens * input_price / 1_000_000
        + total_output_tokens * output_price / 1_000_000
    )

    return cost, pages


def _count_pages(input_dir: Path) -> int:
    """Count JPEG files in the input directory."""
    extensions = {".jpg", ".jpeg", ".png"}
    return sum(1 for f in input_dir.iterdir() if f.suffix.lower() in extensions)


class BudgetTracker:
    """Track spending during cloud processing."""

    def __init__(self, budget: float):
        self.budget = budget
        self.spent = 0.0
        self.page_costs: list[tuple[int, float]] = []

    def record(self, page_num: int, cost: float) -> None:
        """Record cost for a processed page."""
        self.spent += cost
        self.page_costs.append((page_num, cost))

    @property
    def remaining(self) -> float:
        return self.budget - self.spent

    @property
    def exceeded(self) -> bool:
        return self.spent > self.budget
