"""
Image Optimizer: Resize and convert images for device button icons.

Uses Pillow to resize images to fit within widget bounds and convert to PNG
format for LVGL's lodepng decoder on the device. Handles SVG via cairosvg.
"""

from io import BytesIO
from PIL import Image


def _open_image(input_path: str, target_width: int = 256, target_height: int = 256) -> Image.Image:
    """Open an image file, handling SVG conversion if needed."""
    if input_path.lower().endswith(".svg"):
        try:
            import cairosvg
            png_data = cairosvg.svg2png(url=input_path, output_width=target_width, output_height=target_height)
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
    img = _open_image(input_path, max_width, max_height)

    # Convert to RGBA for alpha support
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Resize preserving aspect ratio
    img.thumbnail((max_width, max_height), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def optimize_for_slideshow(input_path: str) -> bytes:
    """
    Optimize an image for the device slideshow (800x480 screen).

    Resizes to fit within 800x480 preserving aspect ratio, converts to JPEG.

    Args:
        input_path: Path to source image (PNG, JPG, BMP, GIF, SVG, etc.)

    Returns:
        JPEG-encoded bytes ready for upload to device /pictures/ folder

    Raises:
        ValueError: If the file is not a valid image
    """
    try:
        img = _open_image(input_path)
    except Exception as e:
        raise ValueError(f"Cannot open image: {e}")

    # Convert to RGB for JPEG (no alpha channel)
    if img.mode in ("RGBA", "P", "LA", "PA"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize preserving aspect ratio to fit 800x480
    img.thumbnail((800, 480), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def optimize_for_widget(input_path: str, widget_width: int, widget_height: int) -> bytes:
    """
    Optimize an image for use as a button icon within a widget.

    Renders at full widget size so the device firmware can display it
    at any zoom level without pixelation. The firmware handles layout
    (icon-only vs icon+label sizing) via lv_img_set_zoom.

    Args:
        input_path: Path to source image
        widget_width: Widget width in pixels
        widget_height: Widget height in pixels

    Returns:
        PNG-encoded bytes
    """
    icon_w = max(16, widget_width)
    icon_h = max(16, widget_height)
    return optimize_icon(input_path, icon_w, icon_h)
