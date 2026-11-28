"""Build Marah's call-to-action outro (owner, 2026-11-28): the closing clip of a Reel.

    python scripts/build_marah_outro.py            # video, needs content/audio/marah/outro_cta.mp3
    python scripts/build_marah_outro.py --still    # only the final frame, for review

Marah's V-sign selfie (images/magnific/marah_vsign_1hand_a.jpg, the owner's pick) with four simple icons drawn
here (follow, like, repost, comment; generic shapes, not the platforms' logos). Each icon pops in when she says its
word in her line «إذا عجبك المقطع، اعمل فولو، ولايك، وريبوست… وبالمرّة، اعطينا رأيك بالتعليقات!» (one ElevenLabs
take, Nora S). No music: a soft synthesised pop under each icon.
Writes assets/outro/marah_outro.mp4 (1080x1920, 30 fps, H.264 + AAC) and assets/outro/marah_outro_still.jpg.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from app.config import SPEC  # noqa: E402
from make_gear_stories import font  # noqa: E402

W, H, FPS = SPEC.width, SPEC.height, SPEC.fps
SR = SPEC.audio_rate
SELFIE = ROOT / "images/magnific/marah_vsign_1hand_a.jpg"
VOICE = ROOT / "content/audio/marah/outro_cta.mp3"
TIMES = ROOT / "content/audio/marah/outro_cta_words.json"   # optional: when each icon word starts
OUT = ROOT / "assets/outro/marah_outro.mp4"
STILL = ROOT / "assets/outro/marah_outro_still.jpg"
PINK = (240, 138, 180)
AMBER = (242, 169, 59)
WHITE = (255, 255, 255)
ICONS = [("follow", "فولو"), ("like", "لايك"), ("repost", "ريبوست"), ("comment", "تعليق")]
KEYWORDS = {"follow": "فولو", "like": "لايك", "repost": "ريبوست", "comment": "بالتعليقات"}
ROW_Y = 1560
SIZE = 190


def base() -> Image.Image:
    src = Image.open(SELFIE).convert("RGB")
    s = max(W / src.width, H / src.height)
    src = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    x0, y0 = (src.width - W) // 2, (src.height - H) // 2
    img = src.crop((x0, y0, x0 + W, y0 + H)).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, ROW_Y - 200, W, H], fill=(6, 16, 20, 150))
    img.alpha_composite(shade.filter(ImageFilter.GaussianBlur(70)))
    return img


def draw_icon(kind: str, size: int) -> Image.Image:
    """One round badge with a simple white glyph, drawn at 4x and scaled down for smooth edges."""
    k = 4
    S = size * k
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = {"follow": AMBER, "like": (235, 64, 96), "repost": (72, 190, 160), "comment": PINK}[kind]
    d.ellipse([0, 0, S - 1, S - 1], fill=fill + (255,))
    d.ellipse([10 * k, 10 * k, S - 10 * k, S - 10 * k], outline=(255, 255, 255, 90), width=3 * k)
    c = S / 2
    w = S * 0.06
    if kind == "follow":                       # person with a plus
        d.ellipse([c - S * .2, S * .2, c + S * .02, S * .42], fill=WHITE)
        d.pieslice([c - S * .31, S * .46, c + S * .13, S * .9], 180, 360, fill=WHITE)
        px, py, r = c + S * .2, S * .36, S * .1
        d.rectangle([px - r, py - w / 2, px + r, py + w / 2], fill=WHITE)
        d.rectangle([px - w / 2, py - r, px + w / 2, py + r], fill=WHITE)
    elif kind == "like":                       # heart
        r = S * .14
        d.ellipse([c - 2 * r, S * .3, c, S * .3 + 2 * r], fill=WHITE)
        d.ellipse([c, S * .3, c + 2 * r, S * .3 + 2 * r], fill=WHITE)
        d.polygon([(c - 2 * r + 2, S * .3 + r * 1.25), (c + 2 * r - 2, S * .3 + r * 1.25), (c, S * .76)], fill=WHITE)
    elif kind == "repost":                     # two arrows in a loop
        box = [S * .25, S * .3, S * .75, S * .7]
        d.arc(box, 200, 340, fill=WHITE, width=int(w))
        d.arc(box, 20, 160, fill=WHITE, width=int(w))
        for ang, sgn in ((340, 1), (160, -1)):
            a = math.radians(ang)
            x, y = c + S * .25 * math.cos(a), S / 2 + S * .2 * math.sin(a)
            t = S * .08
            d.polygon([(x - t, y - sgn * t * .2), (x + t, y - sgn * t * .2), (x, y + sgn * t * 1.1)], fill=WHITE)
    else:                                      # speech bubble with three dots
        d.rounded_rectangle([S * .22, S * .27, S * .78, S * .65], radius=S * .12, fill=WHITE)
        d.polygon([(S * .34, S * .62), (S * .48, S * .62), (S * .3, S * .78)], fill=WHITE)
        for i in range(3):
            x = S * (.37 + .13 * i)
            d.ellipse([x - S * .035, S * .425, x + S * .035, S * .495], fill=fill + (255,))
    return im.resize((size, size), Image.LANCZOS)


def ease_out_back(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def frame(img: Image.Image, shown: dict[str, float]) -> Image.Image:
    """shown: icon -> seconds since it appeared (missing = not yet)."""
    out = img.copy()
    d = ImageDraw.Draw(out)
    gap = (W - 4 * SIZE) / 5
    f = font("ExtraBold", 40)
    for i, (kind, label) in enumerate(reversed(ICONS)):   # right to left: فولو first on the right
        if kind not in shown:
            continue
        p = ease_out_back(shown[kind] / 0.28)
        size = int(SIZE * p)
        if size < 24:
            continue
        cx = gap + SIZE / 2 + i * (SIZE + gap)
        icon = draw_icon(kind, size)
        out.alpha_composite(icon, (int(cx - size / 2), int(ROW_Y - size / 2)))
        if shown[kind] > 0.12:
            box = d.textbbox((0, 0), label, font=f, direction="rtl", language="ar")
            tw = box[2] - box[0]
            d.text((cx - tw / 2 - box[0], ROW_Y + SIZE / 2 + 18 - box[1]), label, font=f, fill=WHITE,
                   direction="rtl", language="ar", stroke_width=3, stroke_fill=(0, 0, 0))
    return out


def word_times(lead: float) -> dict[str, float]:
    if TIMES.exists():
        words = json.loads(TIMES.read_text(encoding="utf-8"))["words"]
        t = {}
        for kind, key in KEYWORDS.items():
            for w in words:
                if key in w["text"]:
                    t[kind] = lead + w["start"]
                    break
        if len(t) == 4:
            return t
    return {"follow": lead + 1.2, "like": lead + 1.8, "repost": lead + 2.4, "comment": lead + 4.0}


def pop(dur=0.09) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    return (np.sin(2 * np.pi * (520 + 900 * t / dur) * t) * np.exp(-t * 40) * 0.25).astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", action="store_true")
    a = ap.parse_args()
    img = base()
    STILL.parent.mkdir(parents=True, exist_ok=True)
    frame(img, {k: 1.0 for k, _ in ICONS}).convert("RGB").save(STILL, quality=92)
    print(STILL)
    if a.still:
        return 0
    lead = 0.15
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VOICE), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    voice = np.frombuffer(raw, np.float32)
    dur = lead + len(voice) / SR + 0.5
    times = word_times(lead)
    track = np.zeros(int(dur * SR) + SR, np.float32)
    i = int(lead * SR)
    track[i:i + len(voice)] += voice
    for t in times.values():
        j = int(t * SR)
        p = pop()
        track[j:j + len(p)] += p
    track = track[: int(dur * SR)]
    track *= 0.89 / (np.abs(track).max() or 1)
    wav = OUT.with_suffix(".wav")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((track * 32767).astype(np.int16).tobytes())
    n = int(round(dur * FPS))
    tmp = OUT.with_name("marah_outro.tmp.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", str(SR),
                             "-ac", "2", "-shortest", "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    for k in range(n):
        t = k / FPS
        shown = {kind: t - at for kind, at in times.items() if t >= at}
        zoom = 1.0 + 0.04 * (t / dur)
        f = frame(img, shown)
        if zoom > 1.0:
            zw, zh = int(W / zoom), int(H / zoom)
            f = f.crop(((W - zw) // 2, (H - zh) // 2, (W - zw) // 2 + zw, (H - zh) // 2 + zh)).resize((W, H))
        proc.stdin.write(f.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        return 1
    tmp.replace(OUT)
    wav.unlink()
    print(OUT, f"{dur:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
