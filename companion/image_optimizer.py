"""
Image Optimizer: Resize and convert images for device button icons.

Uses Pillow to resize images to fit within widget bounds and convert to PNG
format for LVGL's lodepng decoder on the device. Handles SVG via cairosvg.
"""

from io import BytesIO
from PIL import Image


def _open_image(input_path: str) -> Image.Image:
    """Open an image file, handling SVG conversion if needed."""
    if input_path.lower().endswith(".svg"):
        try:
            import cairosvg
            png_data = cairosvg.svg2png(url=input_path, output_width=256, output_height=256)
            return Image.open(BytesIO(png_data))
        except ImportError:
            raise ValueError("SVG support requires cairosvg (pip install cairosvg)")
    return Image.open(input_path)


def optimize_icon(input_path: str, max_width: int, max_height: int) -> bytes:
    """
    Open an image file, resize to fit within max dimensions, and return as PNG bytes.

    Args:
        input_path: Path to source image (PNG, JPG, BMP, GIF, SVG, etc.)
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels

    Returns:
        PNG-encoded bytes ready for upload to device SD card
    """
    img = _open_image(input_path)

    # Convert to RGBA for alpha support
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Resize preserving aspect ratio
    img.thumbnail((max_width, max_height), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def optimize_for_widget(input_path: str, widget_width: int, widget_height: int) -> bytes:
    """
    Optimize an image for use as a button icon within a widget.

    Icon area is roughly 60% of widget width and 40% of widget height
    to leave room for label and description text.

    Args:
        input_path: Path to source image
        widget_width: Widget width in pixels
        widget_height: Widget height in pixels

    Returns:
        PNG-encoded bytes
    """
    icon_w = max(16, widget_width * 6 // 10)
    icon_h = max(16, widget_height * 4 // 10)
    return optimize_icon(input_path, icon_w, icon_h)
