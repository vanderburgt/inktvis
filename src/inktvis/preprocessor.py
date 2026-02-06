"""Image preprocessing for local OCR mode."""

from pathlib import Path
import tempfile

from PIL import Image, ImageFilter


def preprocess(image_path: Path) -> Path:
    """Convert image to grayscale and apply Otsu thresholding.

    Args:
        image_path: Path to the input JPEG scan.

    Returns:
        Path to the preprocessed temporary image file.
    """
    img = Image.open(image_path)
    gray = img.convert("L")
    # Apply adaptive thresholding via Pillow's point method (Otsu-like)
    # Calculate threshold using histogram
    histogram = gray.histogram()
    total_pixels = gray.size[0] * gray.size[1]
    threshold = _otsu_threshold(histogram, total_pixels)
    binary = gray.point(lambda p: 255 if p > threshold else 0)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    binary.save(tmp.name)
    return Path(tmp.name)


def _otsu_threshold(histogram: list[int], total: int) -> int:
    """Compute Otsu's threshold from a grayscale histogram."""
    sum_total = sum(i * histogram[i] for i in range(256))
    sum_bg = 0.0
    weight_bg = 0
    max_variance = 0.0
    best_threshold = 0

    for t in range(256):
        weight_bg += histogram[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        sum_bg += t * histogram[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg

        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if variance > max_variance:
            max_variance = variance
            best_threshold = t

    return best_threshold
