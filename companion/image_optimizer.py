"""
Image Optimizer: Resize and convert images for device button icons.

Uses Pillow to resize images to fit within widget bounds and convert to PNG
format for LVGL's lodepng decoder on the device. Handles SVG via cairosvg.
"""

import struct
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


def _fit_with_matte(img: Image.Image, width: int, height: int) -> Image.Image:
    """Fit image to canvas with edge-sampled color matte background.

    If the image already fills the canvas exactly, returns it as-is.
    Otherwise, samples the dominant color from the image edges and
    fills the letterbox/pillarbox bars with that color, then composites
    the contain-fitted image centered on top.
    """
    # Check if image already fills canvas
    img_ratio = img.width / img.height
    canvas_ratio = width / height
    if abs(img_ratio - canvas_ratio) < 0.01:
        return img.resize((width, height), Image.LANCZOS)

    # Sample edge pixels to find a representative background color.
    # Shrink the image to speed up pixel sampling, then grab border pixels.
    thumb = img.copy()
    thumb.thumbnail((64, 64), Image.LANCZOS)
    if thumb.mode != "RGB":
        thumb = thumb.convert("RGB")
    tw, th = thumb.size
    edge_pixels = []
    for x in range(tw):
        edge_pixels.append(thumb.getpixel((x, 0)))
        edge_pixels.append(thumb.getpixel((x, th - 1)))
    for y in range(th):
        edge_pixels.append(thumb.getpixel((0, y)))
        edge_pixels.append(thumb.getpixel((tw - 1, y)))
    # Average edge color
    r = sum(p[0] for p in edge_pixels) // len(edge_pixels)
    g = sum(p[1] for p in edge_pixels) // len(edge_pixels)
    b = sum(p[2] for p in edge_pixels) // len(edge_pixels)

    # Create solid color background
    matte = Image.new("RGB", (width, height), (r, g, b))

    # Fit foreground: contain (fit within canvas, preserve aspect ratio, no cropping)
    fg = img.copy()
    if fg.mode != "RGB":
        fg = fg.convert("RGB")
    fg.thumbnail((width, height), Image.LANCZOS)
    fg_x = (width - fg.width) // 2
    fg_y = (height - fg.height) // 2
    matte.paste(fg, (fg_x, fg_y))

    return matte


def optimize_for_sjpg(input_path: str, width: int = 800, height: int = 480) -> bytes:
    """
    Convert an image to SJPG (LVGL split-JPEG) format.

    SJPG decodes in 16-pixel-tall strips without loading the full image
    into RAM, which is ideal for ESP32 devices.

    Images that don't match the canvas aspect ratio get a blurred
    zoom-to-fill matte behind the centered image (no black bars).

    Args:
        input_path: Path to source image
        width: Target width in pixels
        height: Target height in pixels

    Returns:
        SJPG-encoded bytes

    Raises:
        ValueError: If the file is not a valid image
    """
    SPLIT_HEIGHT = 16
    JPEG_QUALITY = 90

    try:
        img = _open_image(input_path, width, height)
    except Exception as e:
        raise ValueError(f"Cannot open image: {e}")

    if img.mode != "RGB":
        img = img.convert("RGB")

    img = _fit_with_matte(img, width, height)
    w, h = img.size

    # Slice into 16px-tall horizontal strips
    strips = []
    for y in range(0, h, SPLIT_HEIGHT):
        strip_h = min(SPLIT_HEIGHT, h - y)
        strip = img.crop((0, y, w, y + strip_h))
        buf = BytesIO()
        strip.save(buf, format="JPEG", quality=JPEG_QUALITY)
        strips.append(buf.getvalue())

    total_frames = len(strips)

    # Build SJPG binary
    out = BytesIO()
    out.write(b"_SJPG__\x00")                           # magic
    out.write(b"V1.00\x00")                              # version
    out.write(struct.pack("<H", w))                       # width
    out.write(struct.pack("<H", h))                       # height
    out.write(struct.pack("<H", total_frames))            # total_frames
    out.write(struct.pack("<H", SPLIT_HEIGHT))            # split_height
    for s in strips:
        out.write(struct.pack("<H", len(s)))              # frame sizes
    for s in strips:
        out.write(s)                                      # JPEG data
    return out.getvalue()


def optimize_for_slideshow(input_path: str) -> bytes:
    """
    Optimize an image for the device slideshow (800x480 screen).

    Converts to SJPG format for efficient ESP32 rendering.

    Args:
        input_path: Path to source image

    Returns:
        SJPG-encoded bytes ready for upload to device /pictures/ folder

    Raises:
        ValueError: If the file is not a valid image
    """
    return optimize_for_sjpg(input_path)


def optimize_for_widget(input_path: str, widget_width: int, widget_height: int,
                        has_label: bool = False) -> bytes:
    """
    Optimize an image for use as a button icon within a widget.

    Resizes to the exact pixel area the icon will occupy on the display
    so the firmware renders at 1:1 with no zoom scaling. Accounts for
    label space when a text label is shown below the icon.

    Args:
        input_path: Path to source image
        widget_width: Widget width in pixels
        widget_height: Widget height in pixels
        has_label: Whether the widget shows a text label (reserves bottom space)

    Returns:
        PNG-encoded bytes
    """
    # Match firmware layout: padding + label space
    PAD = 4  # LVGL flex container padding
    LABEL_H = 20  # ~montserrat_16 line height
    if has_label:
        icon_w = max(16, widget_width - PAD * 2)
        icon_h = max(16, widget_height - PAD * 2 - LABEL_H)
    else:
        icon_w = max(16, widget_width - PAD * 2)
        icon_h = max(16, widget_height - PAD * 2)
    return optimize_icon(input_path, icon_w, icon_h)
