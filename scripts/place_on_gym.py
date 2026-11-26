"""Put a character picture made on a plain teal backdrop (Magnific) onto our procedural gym background.

    python scripts/place_on_gym.py SRC OUT [--width 0.9] [--floor 1.0]

The cut-out is looser than compose_scenes.cutout (Magnific backdrops are lighter teal); background pixels are
removed only where connected to the border, so the figure stays whole.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from compose_scenes import background, place  # noqa: E402


def cut(path: Path, bright: float = 160) -> Image.Image:
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    teal = (np.minimum(g, b) - r > 8) & ((r + g + b) / 3 < bright) & (g >= b - 14)
    lab, _ = ndimage.label(teal)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bg = np.isin(lab, border[border > 0])
    fg = ndimage.binary_opening(ndimage.binary_fill_holes(~bg), iterations=1)
    lab, n = ndimage.label(fg)
    if n > 1:
        sizes = ndimage.sum(fg, lab, range(1, n + 1))
        fg = lab == (1 + int(np.argmax(sizes)))
    alpha = Image.fromarray(fg.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(0.8))
    im = Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")
    im.putalpha(alpha)
    return im.crop(Image.fromarray(fg.astype(np.uint8) * 255).getbbox())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--width", type=float, default=0.9, help="figure width as a fraction of the frame")
    ap.add_argument("--floor", type=float, default=1.0)
    a = ap.parse_args()
    fig = cut(ROOT / a.src)
    canvas = background(1080, 1920)
    place(canvas, fig, 0.5, 1080 * a.width / fig.width, floor=a.floor, shadow=False)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=93)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
