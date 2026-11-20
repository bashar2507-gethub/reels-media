"""Compose character scenes from solo cut-outs on one procedural gym background (first used for r030).

    python scripts/compose_scenes.py --spec images/r030-scenes.json

The solo images are generated on a flat green key (images/queue/<job>.json); here the green
is keyed out and each character is placed on the same background with a soft floor shadow,
so faces, sizes and lighting stay identical from scene to scene.
Spec: {"out_dir", "size": [w, h], "scenes": {"s01": [{"src", "x", "scale", "floor"?, "lift"?, "flip"?}, ...]}}
x is the figure's centre as a fraction of the width; scale is output pixels per source pixel; floor
is where the feet stand (a fraction of the height; above 1 crops the legs for a close shot).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
FLOOR = 0.955  # feet line, as a fraction of the frame height


def background(w: int, h: int) -> Image.Image:
    """Dark petrol-teal gym: vignette, warm amber rim light, soft out-of-focus racks and plates."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.array([14, 44, 46], np.float32)
    dist = np.sqrt(((x - w * 0.5) / w) ** 2 + ((y - h * 0.62) / h) ** 2)
    light = np.clip(1.25 - 1.5 * dist, 0.35, 1.2)[..., None]
    img = base * light
    floor = y > h * 0.74
    img[floor] *= 0.78
    amber = np.array([255, 170, 80], np.float32)
    for cx in (0.0, 1.0):
        d = np.sqrt(((x - w * cx) / w) ** 2 + ((y - h * 0.2) / h) ** 2)
        img += amber * (np.clip(0.42 - d, 0, None) ** 2)[..., None] * 0.9
    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    props = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(props)
    shade = (6, 22, 24, 200)
    for fx in (0.06, 0.94):  # two racks at the sides
        cx = int(w * fx)
        d.rectangle([cx - w * 0.012, h * 0.38, cx + w * 0.012, h * 0.75], fill=shade)
        d.rectangle([cx - w * 0.09, h * 0.47, cx + w * 0.09, h * 0.475], fill=shade)
        for py in (0.5, 0.6):
            r = w * 0.05
            d.ellipse([cx - r, h * py - r, cx + r, h * py + r], fill=shade)
    props = props.filter(ImageFilter.GaussianBlur(w * 0.012))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), props)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line([(0, h * 0.74), (w, h * 0.74)], fill=(255, 190, 110, 40), width=max(2, w // 300))
    return Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(3)))


def cutout(path: Path) -> Image.Image:
    """Cut the character out of its dark petrol-teal background.

    Background pixels are teal (green and blue well above red) and dark; only those connected to
    the image border are removed, so dark parts inside the figure (outlines, shorts) stay.
    """
    from scipy import ndimage
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    teal = (np.minimum(g, b) - r > 9) & (r < 0.6 * np.minimum(g, b) + 4) & ((r + g + b) / 3 < 120) & (g >= b - 4)  # navy cap: b > g
    labels, _ = ndimage.label(teal)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    bg = np.isin(labels, border[border > 0])
    fg = ndimage.binary_fill_holes(~bg)
    fg = ndimage.binary_opening(fg, iterations=1)
    lab, n = ndimage.label(fg)
    if n > 1:  # keep the figure, drop specks
        sizes = ndimage.sum(fg, lab, range(1, n + 1))
        fg = lab == (1 + int(np.argmax(sizes)))
    a = Image.fromarray(fg.astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(0.8))
    im = Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")
    im.putalpha(a)
    box = Image.fromarray(fg.astype(np.uint8) * 255).getbbox()
    return im.crop(box) if box else im


def place(canvas: Image.Image, figure: Image.Image, x: float, scale: float, floor: float = FLOOR,
          lift: float = 0.0, flip: bool = False, shadow: bool = True) -> None:
    """Draw a figure with its bottom at `floor` (minus `lift` for a jump) and its centre at x.

    scale is output pixels per source pixel, so a jumping pose keeps the size of a standing one.
    """
    w, h = canvas.size
    if flip:
        figure = figure.transpose(Image.FLIP_LEFT_RIGHT)
    tw, th = int(figure.width * scale), int(figure.height * scale)
    fig = figure.resize((tw, th), Image.LANCZOS)
    bottom = h * (floor - lift)
    left, top = int(w * x - tw / 2), int(bottom - th)
    if shadow and floor <= 1.0:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sw = min(tw, 520 * scale) * (0.9 - 1.2 * lift)
        sh = 22 * scale
        ImageDraw.Draw(layer).ellipse([w * x - sw / 2, h * floor - sh, w * x + sw / 2, h * floor + sh],
                                      fill=(0, 0, 0, int(150 * (1 - 2 * lift))))
        canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(14 * scale)))
    _paste_clipped(canvas, fig, left, top)


def _paste_clipped(canvas: Image.Image, fig: Image.Image, left: int, top: int) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(fig, (left, top), fig)
    canvas.alpha_composite(layer)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    spec = json.loads((ROOT / parser.parse_args().spec).read_text(encoding="utf-8"))
    w, h = spec.get("size", [1080, 1920])
    bg = background(w, h)
    out = ROOT / spec["out_dir"]
    out.mkdir(parents=True, exist_ok=True)
    cache: dict[str, Image.Image] = {}
    for name, layers in spec["scenes"].items():
        canvas = bg.copy()
        for layer in layers:
            src = layer["src"]
            if src not in cache:
                cache[src] = cutout(ROOT / src)
            place(canvas, cache[src], layer["x"], layer["scale"], layer.get("floor", FLOOR), layer.get("lift", 0.0),
                  layer.get("flip", False), layer.get("shadow", True))
        canvas.convert("RGB").save(out / f"{name}.jpg", quality=93)
        print(out / f"{name}.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
