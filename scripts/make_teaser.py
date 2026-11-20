"""r030 teaser story: the Gemini bench image with a slow push-in, two lines of text and Marah's whisper.

    python scripts/make_teaser.py
Writes reels/r030/r030-teaser.mp4 (1080x1920, 30 fps, about 7 s). No characters are shown.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS, DUR = 1080, 1920, 30, 7.0
IMG = ROOT / "reels/r030/teaser/bench.jpg"
VOICE = ROOT / "content/audio/r030/teaser_whisper.mp3"
OUT = ROOT / "reels/r030/r030-teaser.mp4"
FONT = ROOT / "assets/fonts/Cairo-Black.ttf"
LINES = [  # (text, start, end, y, size, colour)
    ("بلانكت مو لحاله بعد اليوم...", 0.7, 3.5, 340, 70, (255, 255, 255)),
    ("الساعة 6 المساء", 4.3, DUR, 300, 104, (255, 193, 77)),
    ("تعرفون مين", 4.6, DUR, 430, 92, (255, 255, 255)),
]
WHISPER_AT = 3.6


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def text_layer(text: str, size: int, colour) -> Image.Image:
    font = ImageFont.truetype(str(FONT), size, layout_engine=ImageFont.Layout.RAQM)
    box = font.getbbox(text, direction="rtl", language="ar")
    w, h = box[2] - box[0] + 60, box[3] - box[1] + 60
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((30 - box[0], 30 - box[1]), text, font=font, fill=colour + (255,), direction="rtl", language="ar",
           stroke_width=max(3, size // 18), stroke_fill=(0, 0, 0, 200))
    return layer


def main() -> int:
    src = Image.open(IMG).convert("RGB")
    scale = max(W / src.width, H / src.height)
    base = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    layers = [(text_layer(t, s, c), a, b, y) for t, a, b, y, s, c in LINES]
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(VOICE), "-filter_complex",
         f"[1:a]adelay={int(WHISPER_AT * 1000)}|{int(WHISPER_AT * 1000)},volume=2.2,apad,atrim=0:{DUR},"
         f"aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-16:TP=-1.5[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-t", str(DUR), str(OUT)], stdin=subprocess.PIPE)
    frames = int(DUR * FPS)
    for k in range(frames):
        t = k / FPS
        z = 1.0 + 0.10 * ease(t / DUR)
        cw, ch = W / z, H / z
        cx, cy = base.width / 2, base.height * 0.56
        left = min(max(cx - cw / 2, 0), base.width - cw)
        top = min(max(cy - ch / 2, 0), base.height - ch)
        frame = base.crop((round(left), round(top), round(left + cw), round(top + ch))).resize((W, H), Image.BILINEAR)
        frame = frame.convert("RGBA")
        for layer, a, b, y in layers:
            alpha = min(ease((t - a) / 0.35), 1 - ease((t - (b - 0.3)) / 0.3)) if b < DUR else ease((t - a) / 0.35)
            if alpha <= 0:
                continue
            lift = int(18 * (1 - ease((t - a) / 0.35)))
            l2 = layer.copy()
            l2.putalpha(l2.getchannel("A").point(lambda v: int(v * alpha)))
            frame.alpha_composite(l2, ((W - layer.width) // 2, y + lift))
        fade = min(ease(t / 0.5), 1.0)
        arr = np.asarray(frame.convert("RGB"), dtype=np.float32) * fade
        proc.stdin.write(arr.astype(np.uint8).tobytes())
    proc.stdin.close()
    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
