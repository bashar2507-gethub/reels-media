"""Caption QA: prove that rendered Arabic captions read right to left.

The captions are rendered alone on a black canvas with the same libass, ASS file and
fonts as the final video, so background colours cannot confuse the detector. For every
caption with two or more spoken words we locate the highlighted word when the first
word is spoken and when the last word is spoken. Reading right to left, the first word
must sit to the right of the last one, or on a higher line if the caption wraps.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .config import FONTS_DIR, SPEC, VideoSpec
from .subtitles import highlight_groups
from .timeline import Timeline
from .video_assembler import filter_path

ACCENT_RGB = (255, 193, 77)
QA_SCALE = 2      # half-size render: enough for positions, four times less data
SETTLE = 0.12     # sample after the caption's 90 ms fade-in has finished


def _pairs(timeline: Timeline) -> list[tuple[float, float, str]]:
    """For each caption with two or more highlight groups: a moment inside the first group's
    highlight and one inside the last group's, both after the caption's fade-in."""
    out = []
    for sentence in timeline.sentences:
        if sentence.style == "title":
            continue
        for caption in sentence.captions:
            groups = highlight_groups(caption)
            if len(groups) < 2:
                continue
            first_start = caption.words[groups[0][0]].start
            first_end = caption.words[groups[1][0]].start
            last_start = caption.words[groups[-1][0]].start
            last_end = max(caption.words[groups[-1][-1]].end, last_start + 2 * SETTLE)
            out.append((min(first_start + SETTLE, (first_start + first_end) / 2),
                        min(last_start + SETTLE, (last_start + last_end) / 2),
                        " ".join(w.text for w in caption.words)))
    return out


def _accent_centre(frame: np.ndarray) -> tuple[float, float] | None:
    mask = np.abs(frame.astype(np.int16) - np.array(ACCENT_RGB)).sum(axis=2) < 90
    mask[: int(mask.shape[0] * 0.18)] = False  # ignore the corner tag area
    ys, xs = np.nonzero(mask)
    return None if xs.size == 0 else (float(xs.mean()), float(ys.mean()))


def check_caption_order(ass_path: Path, timeline: Timeline, spec: VideoSpec = SPEC,
                        fonts_dir: Path = FONTS_DIR) -> dict:
    pairs = _pairs(timeline)
    if not pairs:
        return {"passed": True, "checked": 0, "failures": []}
    w, h, fps = spec.width // QA_SCALE, spec.height // QA_SCALE, spec.fps
    # Overlay figures share the accent colour; check the captions on their own.
    text = Path(ass_path).read_text(encoding="utf-8")
    kept = [ln for ln in text.splitlines()
            if not (ln.startswith("Dialogue:") and ln.split(",")[3] in ("Overlay", "OverlaySub"))]
    ass_path = Path(ass_path).with_name(Path(ass_path).stem + "_qa.ass")
    ass_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    wanted = sorted({int(t * fps) for a, b, _ in pairs for t in (a, b)})
    select = "+".join(f"eq(n\\,{n})" for n in wanted)
    cmd = ["ffmpeg", "-v", "error", "-f", "lavfi",
           "-i", f"color=c=black:s={w}x{h}:r={fps}:d={timeline.duration:.3f}",
           "-vf", f"ass=filename={filter_path(ass_path)}:fontsdir={filter_path(fonts_dir)}:shaping=complex,"
                  f"select='{select}'",
           "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, timeout=600)
    if raw.returncode != 0:
        return {"passed": False, "checked": 0, "failures": [raw.stderr.decode(errors="replace")[:300]]}
    frames = dict(zip(wanted, np.frombuffer(raw.stdout, dtype=np.uint8).reshape(-1, h, w, 3)))
    line_gap = spec.height / QA_SCALE * 0.02
    failures = []
    for t_first, t_last, label in pairs:
        first = _accent_centre(frames[int(t_first * fps)])
        last = _accent_centre(frames[int(t_last * fps)])
        if first is None or last is None:
            failures.append(f"no highlighted word visible in '{label}'")
            continue
        same_line = abs(first[1] - last[1]) <= line_gap
        ok = first[0] > last[0] if same_line else first[1] < last[1]
        if not ok:
            failures.append(f"{t_first:.2f}s '{label}' reads left to right")
    return {"passed": not failures, "checked": len(pairs), "failures": failures}
