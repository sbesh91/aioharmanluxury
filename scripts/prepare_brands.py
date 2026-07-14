#!/usr/bin/env python3
"""Turn an official brand logo into Home Assistant brands assets.

Feed it a transparent-background PNG of the *official* logo (sourced from the
brand's own brand kit / press assets), and it emits the four spec-compliant
files the home-assistant/brands repo expects:

    icon.png       256x256 square (contain, transparent padding)
    icon@2x.png    512x512 square
    logo.png       landscape, shortest side 256, brand proportions kept
    logo@2x.png    landscape, shortest side 512

Usage:
    python prepare_brands.py <source_logo.png> [out_dir]

Default out_dir: ./core_integrations/harman_luxury
"""

import sys
from pathlib import Path

from PIL import Image

ICON = 256
ICON_2X = 512
LOGO_SHORT = 256
LOGO_SHORT_2X = 512


def _trim(img: Image.Image) -> Image.Image:
    """Trim transparent padding around the subject."""
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def _logo(img: Image.Image, shortest: int) -> Image.Image:
    """Scale keeping aspect so the shortest side equals ``shortest``."""
    w, h = img.size
    scale = shortest / min(w, h)
    return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def _icon(img: Image.Image, size: int) -> Image.Image:
    """Fit the logo into a transparent square canvas, centered."""
    w, h = img.size
    scale = size / max(w, h)
    resized = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    src = Image.open(sys.argv[1]).convert("RGBA")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "core_integrations/harman_luxury")
    out.mkdir(parents=True, exist_ok=True)

    trimmed = _trim(src)

    for name, image in (
        ("logo.png", _logo(trimmed, LOGO_SHORT)),
        ("logo@2x.png", _logo(trimmed, LOGO_SHORT_2X)),
        ("icon.png", _icon(trimmed, ICON)),
        ("icon@2x.png", _icon(trimmed, ICON_2X)),
    ):
        path = out / name
        image.save(path, "PNG", optimize=True)
        print(f"wrote {path}  {image.size}")


if __name__ == "__main__":
    main()
