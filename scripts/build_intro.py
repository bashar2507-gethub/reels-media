"""Build "THE BLANKET EFFECT": the 1.8 s signature intro used at the start of every Reel.

    python scripts/build_intro.py

Frames come from images/intro-frames/ (The Blanket, generated from the owner's character sheet):
a_dormant (still, eyes dark), b_ignite (same pose, eyes lit), c_lunge (closer, leaning in).
The motion, eye glow, flash and sound are made here, so the result is the same every time.
Sound is synthesised (sub-bass impact + noise whoosh): no music, nothing licensed.
Writes assets/intro/blanket_effect.mp4 (1080x1920, 30 fps, H.264 + AAC 48 kHz stereo).
"""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import SPEC  # noqa: E402
from app.video_assembler import aac_args, mp4_args, x264_args  # noqa: E402

W, H, FPS, DUR = SPEC.width, SPEC.height, SPEC.fps, 1.8
SR = SPEC.audio_rate
FRAMES = ROOT / "images" / "intro-frames"
OUT = ROOT / "assets" / "intro" / "blanket_effect.mp4"
GOLD_CORE = np.array([255, 248, 228], np.float32)
GOLD_HALO = np.array([255, 178, 70], np.float32)


def cover(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.Resampling.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    return np.asarray(im.crop((l, t, l + W, t + H)), np.float32)


def find_eyes(img: np.ndarray, top: float = 0.45) -> list[tuple[float, float, float]]:
    """The two brightest small blobs in the upper part of the frame: (x, y, radius)."""
    lum = img[: int(H * top)].mean(axis=2)
    thr = np.percentile(lum, 99.6)
    mask = (lum >= thr).astype(np.uint8)
    n, _, stats, cents = cv2.connectedComponentsWithStats(mask)
    blobs = sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA])[:2]
    eyes = [(float(cents[i][0]), float(cents[i][1]), max(10.0, (stats[i, cv2.CC_STAT_AREA] / np.pi) ** 0.5)) for i in blobs]
    if len(eyes) < 2:
        raise SystemExit(f"could not find two eyes in frame (found {len(eyes)})")
    return sorted(eyes)


def glow_layer(eyes, k: float) -> np.ndarray:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    layer = np.zeros((H, W, 3), np.float32)
    for x, y, r in eyes:
        d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
        core = np.exp(-(d / (r * 1.1)) ** 2)
        halo = np.exp(-(d / (r * 5.0)) ** 2) * 0.55
        streak = np.exp(-((yy - y) / (r * 0.35)) ** 2) * np.exp(-np.abs(xx - x) / (r * 9)) * 0.35
        layer += core[..., None] * GOLD_CORE + (halo + streak)[..., None] * GOLD_HALO
    return layer * k


def screen(base: np.ndarray, layer: np.ndarray) -> np.ndarray:
    return 255 - (255 - base) * (255 - np.clip(layer, 0, 255)) / 255


def zoom(img: np.ndarray, s: float, cx: float, cy: float, dx: float = 0, dy: float = 0) -> np.ndarray:
    m = np.float32([[s, 0, (1 - s) * cx + dx], [0, s, (1 - s) * cy + dy]])
    return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def scale_eyes(eyes, s, cx, cy, dx=0, dy=0):
    return [((x - cx) * s + cx + dx, (y - cy) * s + cy + dy, r * s) for x, y, r in eyes]


def vignette() -> np.ndarray:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.42) / (H / 2)) ** 2)
    return (1 - 0.55 * np.clip(r - 0.35, 0, 1))[..., None]


def frames():
    a, b, c = (cover(FRAMES / f) for f in ("a_dormant.jpg", "b_ignite.jpg", "c_lunge.jpg"))
    eyes_b, eyes_c = find_eyes(b), find_eyes(c, top=0.5)
    print("eyes b:", [(round(x), round(y), round(r)) for x, y, r in eyes_b], "eyes c:", [(round(x), round(y), round(r)) for x, y, r in eyes_c])
    vig = vignette()
    bcx, bcy = np.mean([e[0] for e in eyes_b]), np.mean([e[1] for e in eyes_b])
    ccx, ccy = np.mean([e[0] for e in eyes_c]), np.mean([e[1] for e in eyes_c])
    rng = np.random.default_rng(7)
    n = round(DUR * FPS)
    for f in range(n):
        t = f / FPS
        if t < 0.70:                                   # 1. dark, still, almost asleep
            s = 1.0 + 0.035 * t / 0.70
            img = zoom(a, s, bcx, bcy) * 0.72
            g = np.zeros_like(img)
        elif t < 1.05:                                 # 2. eyes ignite
            u = min(1.0, (t - 0.70) / 0.12)
            s = 1.035 + 0.03 * (t - 0.70) / 0.35
            base = zoom(a, s, bcx, bcy) * (1 - u) * 0.72 + zoom(b, s, bcx, bcy) * u * 0.85
            k = (0 if t < 0.70 else 1.5 * u) if t < 0.82 else 1.05 + 0.12 * np.sin((t - 0.82) * 40)
            img, g = base, glow_layer(scale_eyes(eyes_b, s, bcx, bcy), k)
        elif t < 1.45:                                 # 3. sudden lunge toward the camera
            u = (t - 1.05) / 0.40
            e = 1 - (1 - u) ** 3                       # fast start, settles
            s = 1.0 + 0.55 * e
            amp = 22 * (1 - u)
            dx, dy = rng.uniform(-amp, amp), rng.uniform(-amp, amp)
            subs = [zoom(c, s - 0.04 * j * (1 - u), ccx, ccy, dx, dy) for j in range(3)]  # motion blur
            img = np.mean(subs, axis=0) * 0.95
            g = glow_layer(scale_eyes(eyes_c, s, ccx, ccy, dx, dy), 1.6)
        else:                                          # 4. golden-white flash into the Reel
            s = 1.55 + 0.1 * (t - 1.45) / 0.35
            img = zoom(c, s, ccx, ccy) * 0.95
            g = glow_layer(scale_eyes(eyes_c, s, ccx, ccy), 1.6 + 2.5 * (t - 1.45) / 0.35)
        out = screen(img * vig, g)
        if t >= 1.40:                                  # flash builds to near white at the end
            a_f = min(1.0, (t - 1.40) / 0.36) ** 1.6
            out = out * (1 - a_f) + np.array([255, 238, 205], np.float32) * a_f
        out += rng.normal(0, 3.0, out.shape).astype(np.float32)   # light film grain
        yield np.clip(out, 0, 255).astype(np.uint8)


def sound() -> np.ndarray:
    n = int(DUR * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(3)
    audio = np.zeros(n, np.float32)
    # low room tone while dark
    audio += 0.03 * np.sin(2 * np.pi * 42 * t) * np.clip(1 - t / 1.0, 0, 1)
    # whoosh: noise swelling into the lunge, brightening as it rises
    w0, w1 = 0.72, 1.08
    m = (t >= w0) & (t < w1 + 0.15)
    noise = rng.normal(0, 1, n).astype(np.float32)
    env = np.zeros(n, np.float32)
    env[m] = np.where(t[m] < w1, ((t[m] - w0) / (w1 - w0)) ** 2, np.exp(-(t[m] - w1) / 0.05))
    lo = cv2.GaussianBlur(noise.reshape(1, -1), (0, 0), sigmaX=6).ravel()      # darker band
    hi = noise - cv2.GaussianBlur(noise.reshape(1, -1), (0, 0), sigmaX=2).ravel()  # airy band
    mix = np.clip((t - w0) / (w1 - w0), 0, 1)
    audio += 0.35 * env * (lo * (1 - mix) * 2.2 + hi * mix * 0.9)
    # cinematic bass impact at the lunge: falling sub sine + click, saturated
    i0 = 1.05
    ti = np.clip(t - i0, 0, None)
    on = t >= i0
    freq = 38 + 80 * np.exp(-ti / 0.06)
    phase = 2 * np.pi * np.cumsum(np.where(on, freq, 0)) / SR
    boom = np.sin(phase) * np.exp(-ti / 0.35) * on
    click = rng.normal(0, 1, n) * np.exp(-ti / 0.008) * on
    audio += 0.9 * np.tanh(1.6 * boom) + 0.25 * click
    # fade the tail so the narration starts clean
    audio *= np.clip((DUR - t) / 0.12, 0, 1)
    audio = audio / max(1e-6, np.abs(audio).max()) * 10 ** (-3 / 20)   # peak -3 dBFS
    return audio.astype(np.float32)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wav = OUT.with_suffix(".wav")
    pcm = (sound() * 32767).astype(np.int16)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())
    tmp = OUT.with_name("blanket_effect.part.mp4")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
           "-map", "0:v", "-map", "1:a", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           *x264_args(SPEC), *aac_args(SPEC), *mp4_args(), "-t", f"{DUR}", str(tmp)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in frames():
        proc.stdin.write(fr.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        return 1
    tmp.replace(OUT)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
