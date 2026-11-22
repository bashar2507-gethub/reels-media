"""Short study stories for the «دراسات» highlight (owner, 2026-11-22; first s001, triceps and diabetes).

    python scripts/make_study_story.py --spec content/studies/s001.json

One narration take, a still frame with the character, the title and the source card, and burnt-in captions
whose words come from the script itself (so they are spelled right) and whose times are spread over each
spoken segment of the take by letter count. No speed change, no music.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from app.dialogue import spread_words  # noqa: E402
from compose_scenes import background, cutout, place  # noqa: E402
from make_gear_stories import AMBER, FG, MUTED, H, W, centred, font, match_skin, pill  # noqa: E402

TEAL = (63, 179, 181)


def frame(spec: dict) -> Image.Image:
    c = background(W, H)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, 0, W, 1000], fill=(4, 14, 16, 130))
    c.alpha_composite(shade.filter(ImageFilter.GaussianBlur(120)))
    ch = spec["character"]
    src = ROOT / ch["src"]
    if ch.get("match_skin"):
        src = match_skin(src, ROOT / "images" / "studies" / src.name)
    place(c, cutout(src), ch.get("x", 0.5), ch.get("scale", 0.8), floor=ch.get("floor", 1.2))
    d = ImageDraw.Draw(c, "RGBA")
    pill(d, 250, spec["label"], font("ExtraBold", 38), (29, 18, 6), AMBER)
    centred(d, 370, spec["title"], font("Black", 104), FG)
    centred(d, 530, spec["subtitle"], font("SemiBold", 44), AMBER)
    d.rounded_rectangle([90, 630, W - 90, 900], radius=26, fill=(10, 30, 33, 220), outline=TEAL + (160,), width=3)
    centred(d, 655, "المصدر", font("ExtraBold", 34), TEAL)
    latin = ImageFont.truetype(str(ROOT / "assets/fonts/Cairo-SemiBold.ttf"), 34)
    for i, line in enumerate(spec["source"]):
        w = d.textlength(line, font=latin)
        d.text(((W - w) / 2, 712 + i * 50), line, font=latin, fill=FG)
    centred(d, 830, spec["institution"], font("SemiBold", 32), MUTED)
    return c


def caption(base: Image.Image, words: list[str]) -> Image.Image:
    im = base.copy()
    d = ImageDraw.Draw(im, "RGBA")
    text = " ".join(words)
    f = font("Black", 64)
    box = d.textbbox((0, 0), text, font=f, direction="rtl", language="ar")
    w, h = box[2] - box[0], box[3] - box[1]
    y = 990
    d.rounded_rectangle([(W - w) / 2 - 34, y - 22, (W + w) / 2 + 34, y + h + 26], radius=22, fill=(4, 14, 16, 200))
    d.text(((W - w) / 2 - box[0], y - box[1]), text, font=f, fill=AMBER, direction="rtl", language="ar")
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    spec = json.loads((ROOT / ap.parse_args().spec).read_text(encoding="utf-8"))
    out = ROOT / spec["out_dir"]
    tmp = out / "frames"
    tmp.mkdir(parents=True, exist_ok=True)
    base = frame(spec).convert("RGB")
    base.save(out / "cover.jpg", quality=93)
    audio = ROOT / spec["audio"]
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(audio)], capture_output=True, text=True, check=True).stdout)
    # caption chunks of at most 4 words, timed inside each spoken segment
    chunks = []
    for seg in spec["segments"]:
        words = spread_words(seg["text"], seg["start"], seg["end"])
        for i in range(0, len(words), 4):
            part = words[i:i + 4]
            chunks.append((part[0]["start"], [w["text"] for w in part]))
    lines, t_prev = [], 0.0
    blank = tmp / "blank.jpg"
    base.save(blank, quality=92)
    timeline = [(0.0, None)] + chunks
    for n, (start, words) in enumerate(timeline):
        end = timeline[n + 1][0] if n + 1 < len(timeline) else total + 0.4
        if end - start <= 0.01:
            continue
        path = blank if words is None else tmp / f"c{n:03d}.jpg"
        if words is not None:
            caption(base, words).save(path, quality=92)
        lines += [f"file '{path.name}'", f"duration {end - start:.3f}"]
    lines.append(f"file '{path.name}'")
    (tmp / "list.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    video = out / f"{spec['id']}-story.mp4"
    part = out / f"{spec['id']}-story.tmp.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
                    "-i", str(audio), "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "19", "-c:a", "aac", "-b:a", "160k", "-af", "apad=pad_dur=0.4", "-shortest",
                    "-movflags", "+faststart", str(part)], check=True)
    part.rename(video)
    print(video)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
