"""Offline placeholder visuals for dry runs and tests (no paid API calls).

Abstract 9:16 scenes: gradients, soft light and simple line icons. They exist to
exercise motion, crossfades and caption legibility, and are never published.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1440, 2560
AMBER = (255, 172, 64)
BLUE = (70, 165, 255)
GOLD = (236, 206, 150)
STEEL = (170, 190, 205)


def _base(seed: int) -> np.ndarray:
    t = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    top, bottom = np.array([14, 44, 52], np.float32), np.array([5, 9, 13], np.float32)
    img = np.repeat(top * (1 - t) + bottom * t, W, axis=1)
    rng = np.random.default_rng(seed)
    img += rng.normal(0, 2.2, img.shape).astype(np.float32)
    return img


def _glow(img: np.ndarray, cx: float, cy: float, radius: float, color, strength: float) -> None:
    yy, xx = np.ogrid[:H, :W]
    falloff = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (radius ** 2))).astype(np.float32)
    img += falloff[..., None] * np.array(color, np.float32) * strength


def _caption_band(img: np.ndarray) -> None:
    """Darken the caption zone so white text stays legible."""
    y = np.arange(H, dtype=np.float32)
    band = np.exp(-(((y - 1670) / 330) ** 2))
    img *= (1 - 0.45 * band)[:, None, None]


def _compose(img: np.ndarray, layer: Image.Image) -> Image.Image:
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    halo = layer.filter(ImageFilter.GaussianBlur(28))
    base = Image.alpha_composite(base, halo)
    base = Image.alpha_composite(base, layer)
    return base.convert("RGB")


def _scale(draw: ImageDraw.ImageDraw) -> None:
    px, py, half, tilt = 720, 820, 380, math.radians(6)
    dx, dy = half * math.cos(tilt), half * math.sin(tilt)
    left, right = (px - dx, py - dy), (px + dx, py + dy)
    draw.line([(px, py), (px, 1400)], fill=GOLD + (255,), width=16)
    draw.rounded_rectangle([560, 1390, 880, 1430], radius=18, fill=GOLD + (255,))
    draw.line([left, right], fill=GOLD + (255,), width=14)
    draw.ellipse([px - 22, py - 22, px + 22, py + 22], fill=GOLD + (255,))
    for (x, y), color, n in ((left, AMBER, 3), (right, BLUE, 4)):
        pan_y = y + 300
        draw.line([(x, y), (x - 120, pan_y)], fill=GOLD + (200,), width=5)
        draw.line([(x, y), (x + 120, pan_y)], fill=GOLD + (200,), width=5)
        draw.arc([x - 150, pan_y - 60, x + 150, pan_y + 60], 0, 180, fill=GOLD + (255,), width=10)
        for k in range(n):
            cx = x - (n - 1) * 34 + k * 68
            draw.ellipse([cx - 28, pan_y - 52, cx + 28, pan_y + 4], fill=color + (255,))


def _flow(draw: ImageDraw.ImageDraw, rng: np.random.Generator) -> None:
    for _ in range(260):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(240, 640)
        x, y = 720 + dist * math.cos(angle), 900 + dist * math.sin(angle) * 1.15
        r = max(3.0, 16 - dist / 50)
        alpha = int(255 * max(0.25, 1 - dist / 700))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=BLUE + (alpha,))
    draw.ellipse([590, 770, 850, 1030], fill=AMBER + (255,))


def _orbs(draw: ImageDraw.ImageDraw) -> None:
    for x, r in ((1090, 170), (720, 120), (380, 78)):
        draw.ellipse([x - r, 960 - r, x + r, 960 + r], fill=AMBER + (255,))
        draw.ellipse([x - r, 1230 - r * 0.18, x + r, 1230 + r * 0.18], fill=AMBER + (60,))


def _dumbbell(draw: ImageDraw.ImageDraw) -> None:
    cy = 960
    draw.rounded_rectangle([420, cy - 18, 1020, cy + 18], radius=16, fill=STEEL + (255,))
    for side in (-1, 1):
        for k, height in enumerate((330, 270, 210)):
            x = 720 + side * (230 + k * 62)
            draw.rounded_rectangle([x - 26, cy - height / 2, x + 26, cy + height / 2], radius=14,
                                   fill=STEEL + (255,), outline=AMBER + (255,), width=4)


def _bookmark(draw: ImageDraw.ImageDraw) -> None:
    pts = [(540, 660), (900, 660), (900, 1200), (720, 1060), (540, 1200)]
    draw.polygon(pts, outline=AMBER + (255,), width=16)
    draw.polygon([(600, 720), (840, 720), (840, 1080), (720, 980), (600, 1080)], fill=AMBER + (70,))


SCENES = {
    "scale": ((560, 760, 520, BLUE, 0.35), _scale),
    "flow": ((720, 900, 460, AMBER, 0.30), _flow),
    "orbs": ((900, 960, 520, AMBER, 0.28), _orbs),
    "dumbbell": ((720, 960, 520, BLUE, 0.30), _dumbbell),
    "bookmark": ((720, 930, 480, AMBER, 0.32), _bookmark),
}


def make_placeholder(name: str, out_path: Path, seed: int = 7) -> Path:
    (gx, gy, gr, gcolor, gs), painter = SCENES[name]
    img = _base(seed)
    _glow(img, gx, gy, gr, gcolor, gs)
    _caption_band(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if painter is _flow:
        painter(draw, np.random.default_rng(seed))
    else:
        painter(draw)
    _compose(img, layer).save(out_path)
    return out_path


def make_all(names: list[str], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {n: make_placeholder(n, out_dir / f"{n}.png", seed=i + 3) for i, n in enumerate(dict.fromkeys(names))}
