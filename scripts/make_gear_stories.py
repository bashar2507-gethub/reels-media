"""Instagram stories for the affiliate tools highlight (owner, 2026-11-21).

    python scripts/make_gear_stories.py --out reels/gear-stories

One 1080x1920 story per tool plus an opening story and a highlight cover. No product photos
(Amazon images are not ours to reuse) and no prices; the owner adds the link sticker in the
Instagram app on the empty space marked by the arrow.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from compose_scenes import background, cutout, place  # noqa: E402

FONTS = ROOT / "assets" / "fonts"
W, H = 1080, 1920
AMBER, FG, MUTED = (242, 169, 59), (234, 242, 241), (160, 186, 189)

TOOLS = [
    ("01", "أحزمة سحب نيوبرين", ["قبضة أثبت في السحب الثقيل", "مثل الديدلفت والرو"]),
    ("02", "أحزمة سحب Hard Pull", ["أمتن للأوزان الثقيلة", "والمجموعات الطويلة"]),
    ("03", "شيكر EYSOO", ["يخلط البروتين بسرعة", "ويقفل بإحكام في الشنطة"]),
    ("04", "أشرطة مقاومة PROIRON", ["14 قطعة لتمرين كامل", "في البيت أو السفر"]),
]


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Cairo-{weight}.ttf"), size, layout_engine=ImageFont.Layout.RAQM)


def centred(d: ImageDraw.ImageDraw, y: int, text: str, f, fill, max_w: int = 960) -> int:
    while f.getlength(text, direction="rtl", language="ar") > max_w and f.size > 30:
        f = font_like(f, f.size - 4)
    box = d.textbbox((0, 0), text, font=f, direction="rtl", language="ar")
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((W - w) / 2 - box[0], y - box[1]), text, font=f, fill=fill, direction="rtl", language="ar")
    return y + h


def font_like(f, size):
    return ImageFont.truetype(f.path, size, layout_engine=ImageFont.Layout.RAQM)


def pill(d, y: int, text: str, f, fg, bg) -> None:
    box = d.textbbox((0, 0), text, font=f, direction="rtl", language="ar")
    w, h = box[2] - box[0], box[3] - box[1]
    x0 = (W - w) / 2 - 36
    d.rounded_rectangle([x0, y, x0 + w + 72, y + h + 36], radius=(h + 36) // 2, fill=bg)
    d.text((x0 + 36 - box[0], y + 18 - box[1]), text, font=f, fill=fg, direction="rtl", language="ar")


def sticker_hint(d, y: int) -> None:
    """An arrow and a dashed frame where the link sticker goes."""
    centred(d, y, "اضغط على الرابط", font("ExtraBold", 50), AMBER)
    ax = W // 2
    d.polygon([(ax - 28, y + 95), (ax + 28, y + 95), (ax, y + 135)], fill=AMBER)
    top, bottom, left, right = y + 160, y + 330, 200, W - 200
    for x in range(left, right, 36):
        d.line([(x, top), (min(x + 18, right), top)], fill=(255, 255, 255, 110), width=4)
        d.line([(x, bottom), (min(x + 18, right), bottom)], fill=(255, 255, 255, 110), width=4)
    for yy in range(top, bottom, 36):
        d.line([(left, yy), (left, min(yy + 18, bottom))], fill=(255, 255, 255, 110), width=4)
        d.line([(right, yy), (right, min(yy + 18, bottom))], fill=(255, 255, 255, 110), width=4)


def footer(d, y: int = 1060) -> None:
    return  # owner, 2026-11-21: no disclosure line on the stories


MARAH_SKIN = (161.0, 164.0, 165.0)  # median skin of assets/characters/marah/reference_front.png


def match_skin(src: Path, dst: Path, target=MARAH_SKIN) -> Path:
    """Pull the grey skin of a generated Marah image to her reference tone.

    Skin is the low-saturation mid-grey; white socks, shoes and the eyes (brighter) and the dark
    outfit are left alone. The gain is faded in with a soft mask so the edges do not band.
    """
    import numpy as np
    a = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    mx, mn = a.max(2), a.min(2)
    hard = (mx - mn < 18) & (mx > 120) & (mx < 215)
    gain = np.array(target, np.float32) / np.median(a[hard], 0)
    soft = np.asarray(Image.fromarray((hard * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)),
                      np.float32)[..., None] / 255
    out = a * (1 - soft) + np.clip(a * gain, 0, 255) * soft
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out.round().astype(np.uint8)).save(dst, quality=95)
    return dst


def base(blanket: Image.Image, x: float, marah: Image.Image | None = None) -> Image.Image:
    canvas = background(W, H)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, 0, W, 1000], fill=(4, 14, 16, 120))
    canvas.alpha_composite(shade.filter(ImageFilter.GaussianBlur(120)))
    place(canvas, blanket, x, 0.62, floor=1.16)
    if marah is not None:  # r030 keeps Marah at 0.9 of Blanket's scale
        place(canvas, marah, 1 - x, 0.56, floor=1.16)
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reels/gear-stories")
    parser.add_argument("--blanket", default="images/r030-solo/b_thumb1.jpg")
    args = parser.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    blanket = cutout(ROOT / args.blanket)
    poses = ["m_welcome2", "m_hips1", "m_cap1", "m_chin1", "m_welcome2"]
    marahs = {p: cutout(match_skin(ROOT / f"images/r030-solo/{p}.jpg", ROOT / f"images/gear-stories/{p}.jpg"))
              for p in set(poses)}

    # opening story
    c = base(blanket, 0.24, marahs[poses[0]])
    d = ImageDraw.Draw(c, "RGBA")
    pill(d, 300, "Blanket Fitness", font("ExtraBold", 40), (29, 18, 6), AMBER)
    centred(d, 430, "أدواتي المفضلة", font("Black", 120), FG)
    centred(d, 640, "للتمرين", font("Black", 120), AMBER)
    centred(d, 860, "4 أدوات أنصح فيها", font("SemiBold", 52), FG)
    centred(d, 950, "كمّل الستوريات وخذ رابط كل وحدة", font("SemiBold", 44), MUTED)
    footer(d)
    c.convert("RGB").save(out / "00-intro.jpg", quality=93)

    for i, (num, name, lines) in enumerate(TOOLS):
        c = base(blanket, 0.78 if i % 2 == 0 else 0.22, marahs[poses[i + 1]])
        d = ImageDraw.Draw(c, "RGBA")
        pill(d, 280, f"أدواتي المفضلة  ·  {num}", font("ExtraBold", 38), (29, 18, 6), AMBER)
        y = centred(d, 420, name, font("Black", 96), FG)
        y += 50
        for line in lines:
            y = centred(d, y, line, font("SemiBold", 54), MUTED) + 22
        footer(d, y + 10)
        sticker_hint(d, y + 110)
        c.convert("RGB").save(out / f"{num}-tool.jpg", quality=93)

    # highlight cover: shown in a circle, so keep it to the centre
    cover = Image.new("RGB", (1080, 1920), (14, 44, 46))
    cd = ImageDraw.Draw(cover)
    cd.ellipse([140, 560, 940, 1360], fill=AMBER)
    cx, cy = 540, 960  # a simple dumbbell
    cd.rounded_rectangle([cx - 210, cy - 22, cx + 210, cy + 22], radius=12, fill=(29, 18, 6))
    for s in (-1, 1):
        cd.rounded_rectangle([cx + s * 150 - 30, cy - 120, cx + s * 150 + 30, cy + 120], radius=18, fill=(29, 18, 6))
        cd.rounded_rectangle([cx + s * 215 - 24, cy - 80, cx + s * 215 + 24, cy + 80], radius=16, fill=(29, 18, 6))
    cover.save(out / "highlight-cover.jpg", quality=93)
    for p in sorted(out.glob("*.jpg")):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
