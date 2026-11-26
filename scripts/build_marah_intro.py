"""Build "MARAH MOMENT": Marah's signature opener (owner, 2026-11-26), the counterpart of THE BLANKET EFFECT.

    python scripts/build_marah_intro.py

Unlike Blanket's intro it is not a separate slate: it is the first 1.4 s of the hook itself. Marah pops in with
her raised finger and says her catchphrase «لحظة لحظة!» (one ElevenLabs take, content/audio/marah/lahza_lahza.mp3),
a pink ring bursts behind her and her eyes and fingertip twinkle (no name tag: owner, 2026-11-26). The hook question
follows straight after. Research behind it: brand cues work in the first two seconds when a character is active in
the scene and there is a sound signature (System1 x TikTok); a separate branded slate costs views (Billion Dollar
Boy), which matches our own data on the Blanket intro.
Sound is synthesised (soft pop + sparkle chime) under her voice: no music, nothing licensed.
Writes assets/intro/marah_moment.mp4 (1080x1920, 30 fps, H.264 + AAC) and a preview frame.
"""
from __future__ import annotations

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
from app.dialogue import decode, voiced_span  # noqa: E402
from app.video_assembler import aac_args, mp4_args, x264_args  # noqa: E402
from compose_scenes import background, cutout  # noqa: E402
from make_gear_stories import font, match_skin  # noqa: E402

W, H, FPS = SPEC.width, SPEC.height, SPEC.fps
SR = SPEC.audio_rate
DUR = 1.4
POSE = ROOT / "images/r030-solo/m_poke1.jpg"
# owner, 2026-11-26: the cute move is the V-sign selfie (Magnific, owner's choice of 1hand a); full-frame picture
SELFIE = ROOT / "images/magnific/marah_vsign_1hand_a.jpg"
SELFIE_EYE = (440, 448)       # the glowing eye inside the V, in source pixels (768x1344)
SELFIE_FINGERS = (555, 378)   # tips of the V fingers
VOICE = ROOT / "content/audio/marah/lahza_lahza.mp3"
OUT = ROOT / "assets/intro/marah_moment.mp4"
PINK = (240, 138, 180)
VOICE_AT = 0.12


def ease_out_back(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def eyes_and_tip(fig: Image.Image) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    """Centres of the two glowing eyes (bright white in the head) and the raised fingertip (topmost opaque pixel)."""
    from scipy import ndimage
    a = np.asarray(fig).astype(np.float32)
    h = a.shape[0]
    head = a[: int(h * 0.2)]
    white = (head[..., :3].min(axis=2) > 235) & (head[..., 3] > 200)
    lab, n = ndimage.label(white)
    blobs = sorted(((ndimage.sum(white, lab, i), ndimage.center_of_mass(white, lab, i)) for i in range(1, n + 1)),
                   reverse=True)[:2]
    eyes = [(c[1], c[0]) for _, c in blobs]
    alpha = a[..., 3] > 200
    left_part = alpha[: int(h * 0.3), : int(a.shape[1] * 0.2)]  # the raised hand is on the left of the figure
    ys, xs = np.nonzero(left_part)
    i = int(np.argmin(ys))
    return eyes, (float(xs[i]), float(ys[i]))


def clear_enclosed_background(fig: Image.Image) -> Image.Image:
    """cutout() keeps background enclosed by the figure (between a hand on the hip and the waist); clear it."""
    from scipy import ndimage
    a = np.asarray(fig).copy()
    rgb = a[..., :3].astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    teal = (np.minimum(g, b) - r > 9) & (r < 0.6 * np.minimum(g, b) + 4) & ((r + g + b) / 3 < 120) & (g >= b - 4)
    teal &= a[..., 3] > 0
    lab, n = ndimage.label(teal)
    if n:
        sizes = ndimage.sum(teal, lab, range(1, n + 1))
        big = np.isin(lab, 1 + np.nonzero(sizes > 1500)[0])
        big = ndimage.binary_dilation(big, iterations=2)
        a[..., 3] = np.where(big, 0, a[..., 3])
    return Image.fromarray(a)


def star(d: ImageDraw.ImageDraw, x: float, y: float, r: float, alpha: int) -> None:
    """A four-point twinkle."""
    if r <= 1 or alpha <= 0:
        return
    w = r * 0.18
    d.polygon([(x, y - r), (x + w, y - w), (x + r, y), (x + w, y + w), (x, y + r), (x - w, y + w), (x - r, y),
               (x - w, y - w)], fill=(255, 245, 250, alpha))


def frames():
    base = background(W, H)
    tint = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(tint).ellipse([-200, 300, W + 200, 1700], fill=PINK + (40,))
    base.alpha_composite(tint.filter(ImageFilter.GaussianBlur(160)))
    fig = clear_enclosed_background(cutout(match_skin(POSE, ROOT / "images/intro-frames/marah_poke_skin.jpg")))
    eyes, tip = eyes_and_tip(fig)
    scale = 1.45  # output px per source px at rest
    floor = H * 1.18
    cx = W * 0.52
    tag_font = font("Black", 64)
    n = round(DUR * FPS)
    for k in range(n):
        t = k / FPS
        im = base.copy()
        # pink ring burst behind her, 0.08-0.55 s
        rt = (t - 0.08) / 0.47
        if 0 <= rt <= 1:
            ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            r = 120 + 900 * (1 - (1 - rt) ** 3)
            ImageDraw.Draw(ring).ellipse([cx - r, H * 0.42 - r, cx + r, H * 0.42 + r], outline=PINK + (int(220 * (1 - rt)),),
                                         width=int(28 * (1 - rt)) + 4)
            im.alpha_composite(ring.filter(ImageFilter.GaussianBlur(3)))
        # pop-in with overshoot, 0-0.32 s, rising from slightly below
        p = ease_out_back(t / 0.32)
        s = scale * (0.55 + 0.45 * p)
        rise = (1 - min(t / 0.32, 1)) * 160
        fw, fh = int(fig.width * s), int(fig.height * s)
        f = fig.resize((fw, fh), Image.LANCZOS)
        left, top = int(cx - fw / 2), int(floor - fh + rise)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(f, (left, top), f)
        im.alpha_composite(layer)
        # twinkles: eyes at 0.30-0.70 s, fingertip at 0.45-0.95 s
        tw = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(tw)
        for (ex, ey) in eyes:
            q = (t - 0.30) / 0.40
            if 0 <= q <= 1:
                env = np.sin(np.pi * q)
                star(d, left + ex * s, top + ey * s, 70 * env, int(255 * env))
        q = (t - 0.45) / 0.50
        if 0 <= q <= 1:
            env = np.sin(np.pi * q)
            star(d, left + tip[0] * s, top + tip[1] * s - 10, 110 * env, int(255 * env))
        im.alpha_composite(tw.filter(ImageFilter.GaussianBlur(1.2)))
        # «مرح» tag slides in from the right, 0.35-0.6 s, stays
        q = 0  # name tag removed at the owner's request (2026-11-26)
        if q > 0:
            tag = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            td = ImageDraw.Draw(tag)
            box = td.textbbox((0, 0), "مرح", font=tag_font, direction="rtl", language="ar")
            tw_, th = box[2] - box[0], box[3] - box[1]
            x1 = W - 70 + (1 - ease_out_back(q)) * 500
            y0 = 300
            td.rounded_rectangle([x1 - tw_ - 70, y0, x1, y0 + th + 44], radius=(th + 44) // 2, fill=PINK + (235,))
            td.text((x1 - 35 - tw_ - box[0], y0 + 22 - box[1]), "مرح", font=tag_font, fill=(40, 10, 40, 255),
                    direction="rtl", language="ar")
            im.alpha_composite(tag)
        yield np.asarray(im.convert("RGB"))


def frames_selfie():
    """Full-frame V-sign selfie: pops in with a pink flash, the eye in the V twinkles, then the fingertips."""
    src = Image.open(SELFIE).convert("RGB")
    k = max(W / src.width, H / src.height)
    base = src.resize((round(src.width * k), round(src.height * k)), Image.LANCZOS)
    ox, oy = (base.width - W) / 2, (base.height - H) / 2
    eye = (SELFIE_EYE[0] * k - ox, SELFIE_EYE[1] * k - oy)
    tips = (SELFIE_FINGERS[0] * k - ox, SELFIE_FINGERS[1] * k - oy)
    n = round(DUR * FPS)
    for i in range(n):
        t = i / FPS
        z = max(1.0, 1.05 + 0.22 * (1 - ease_out_back(t / 0.32)))  # zooms in from 1.27 with a small overshoot, rests at 1.05
        cw, ch = W / z, H / z
        cx = eye[0] + (W / 2 - eye[0]) * min(t / 0.32, 1)  # starts centred on the V eye, settles on the frame
        cy = eye[1] + (H / 2 - eye[1]) * min(t / 0.32, 1)
        l = min(max(cx - cw / 2, 0), W - cw); u = min(max(cy - ch / 2, 0), H - ch)
        frame = base.crop((round(l + ox), round(u + oy), round(l + ox + cw), round(u + oy + ch))).resize((W, H), Image.LANCZOS)
        im = frame.convert("RGBA")
        sx = lambda p: ((p[0] - l) * z, (p[1] - u) * z)
        if t < 0.18:  # pink flash
            fl = Image.new("RGBA", (W, H), PINK + (int(170 * (1 - t / 0.18)),))
            im.alpha_composite(fl)
        rt = (t - 0.08) / 0.47
        if 0 <= rt <= 1:
            ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ex, ey = sx(eye)
            r = 60 + 700 * (1 - (1 - rt) ** 3)
            ImageDraw.Draw(ring).ellipse([ex - r, ey - r, ex + r, ey + r], outline=PINK + (int(220 * (1 - rt)),),
                                         width=int(24 * (1 - rt)) + 4)
            im.alpha_composite(ring.filter(ImageFilter.GaussianBlur(3)))
        tw = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(tw)
        q = (t - 0.30) / 0.40
        if 0 <= q <= 1:
            e = np.sin(np.pi * q); ex, ey = sx(eye)
            star(d, ex, ey, 95 * e, int(255 * e))
        q = (t - 0.45) / 0.50
        if 0 <= q <= 1:
            e = np.sin(np.pi * q); fx, fy = sx(tips)
            star(d, fx, fy - 10, 120 * e, int(255 * e))
        im.alpha_composite(tw.filter(ImageFilter.GaussianBlur(1.2)))
        yield np.asarray(im.convert("RGB"))


def sound() -> np.ndarray:
    n = int(DUR * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    # soft pop at 0.02 s: short falling sine with a fast decay
    a = t - 0.02
    m = a >= 0
    out[m] += 0.5 * np.sin(2 * np.pi * (520 - 260 * np.clip(a[m] / 0.08, 0, 1)) * a[m]) * np.exp(-a[m] * 38)
    # sparkle chime at 0.42 s (fingertip twinkle): bright partials, gentle decay
    a = t - 0.42
    m = a >= 0
    for f, g in ((2093, 0.16), (3136, 0.10), (4186, 0.06)):
        out[m] += g * np.sin(2 * np.pi * f * a[m]) * np.exp(-a[m] * 7)
    # her voice
    v = decode(VOICE)
    i0, i1 = voiced_span(v, pad=0.02)
    v = v[i0:i1]
    v = np.interp(np.arange(0, len(v), 44100 / SR), np.arange(len(v)), v).astype(np.float32) if SR != 44100 else v
    j = int(VOICE_AT * SR)
    out[j:j + len(v)] += v[: n - j] * 1.0
    peak = float(np.max(np.abs(out))) or 1.0
    out *= 0.89 / peak
    fade = int(0.03 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wav = OUT.with_suffix(".wav")
    pcm = (sound() * 32767).astype(np.int16)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())
    tmp = OUT.with_name("marah_moment.part.mp4")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
           "-map", "0:v", "-map", "1:a", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           *x264_args(SPEC), *aac_args(SPEC), *mp4_args(), "-t", f"{DUR}", str(tmp)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    last = None
    for fr in (frames_selfie() if SELFIE.exists() else frames()):
        proc.stdin.write(fr.tobytes())
        last = fr
    proc.stdin.close()
    if proc.wait() != 0:
        return 1
    tmp.replace(OUT)
    Image.fromarray(last).save(OUT.with_name("marah_moment_last.jpg"), quality=90)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
