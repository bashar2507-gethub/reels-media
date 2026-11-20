"""Mix a two-character dialogue Reel into one narration track (first used for r030).

Each line is its own paid take (Blanket = Jeddawi Echo, Marah = Nora S), kept in
content/audio/<id>/. The takes are never sped up or stretched: only the silence the voice
model leaves before and after a line is trimmed, and the lines are laid out one after the
other with short gaps. Light sound effects and a low, steady audience bed sit underneath.

The output is the usual <id>_narration.mp3 plus <id>_narration_words.json, so the normal
renderer builds the scenes and captions from it. Word times are spread over each line's
voiced span by letter count (the same rule timeline.time_words uses for estimates).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np

RATE = 44100
TAG = re.compile(r"\[[^\]]*\]")


def spoken_text(text: str) -> str:
    """The words of a take without its delivery tags or ellipses."""
    text = TAG.sub(" ", text).replace("...", " ").replace("…", " ")
    return " ".join(text.split())


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def voiced_span(samples: np.ndarray, threshold_db: float = -42.0, pad: float = 0.04) -> tuple[int, int]:
    """First and last sample above the threshold (20 ms windows), with a little padding."""
    win = int(0.02 * RATE)
    n = len(samples) // win
    if n == 0:
        return 0, len(samples)
    rms = np.sqrt(np.mean(samples[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    loud = np.nonzero(20 * np.log10(rms) > threshold_db)[0]
    if len(loud) == 0:
        return 0, len(samples)
    start = max(0, loud[0] * win - int(pad * RATE))
    end = min(len(samples), (loud[-1] + 1) * win + int(pad * RATE))
    return start, end


def letter_weight(word: str) -> int:
    return max(1, len(re.sub(r"[^\w]", "", word)))


def spread_words(text: str, start: float, end: float) -> list[dict]:
    """Word timings across [start, end] in proportion to letters, with a small gap between words."""
    words = text.split()
    if not words:
        return []
    weights = [letter_weight(w) for w in words]
    total = sum(weights)
    out, t = [], start
    for word, weight in zip(words, weights):
        length = (end - start) * weight / total
        out.append({"text": word, "type": "word", "start": round(t, 3), "end": round(t + length * 0.92, 3)})
        t += length
    return out


def fade(samples: np.ndarray, seconds: float = 0.012) -> np.ndarray:
    n = min(int(seconds * RATE), len(samples) // 2)
    if n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        samples[:n] *= ramp
        samples[-n:] *= ramp[::-1]
    return samples


def mix(lines: list[dict], sfx: dict[str, Path], bed: Path | None, out_mp3: Path,
        lead_in: float = 0.15, tail: float = 0.6, bed_gain_db: float = -24.0) -> tuple[list[dict], float]:
    """Lay out the lines and effects; returns the word timings and the total length in seconds.

    Each line: {"audio": Path, "text": str, "gap_before": s, "sfx_before": [{"name", "gain_db", "advance"}],
    "sfx_after": [{"name", "gain_db", "delay"}], "voice_gain_db": 0}. Overlapping effects are mixed,
    never inserted, so they add no time except where gap_before makes room for them.
    """
    voice_parts, events, words = [], [], []
    t = lead_in
    for line in lines:
        t += line.get("gap_before", 0.25)
        clip = decode(line["audio"])
        a, b = voiced_span(clip)
        clip = fade(clip[a:b] * 10 ** (line.get("voice_gain_db", 0.0) / 20))
        for fx in line.get("sfx_before", []):
            events.append((max(0.0, t - fx.get("advance", 0.5)), fx))
        voice_parts.append((t, clip))
        length = len(clip) / RATE
        words += spread_words(spoken_text(line["text"]), t + 0.03, t + length - 0.03)
        for fx in line.get("sfx_after", []):
            events.append((t + length + fx.get("delay", 0.05), fx))
        t += length
    total = t + tail
    for at, fx in events:
        total = max(total, at + len(decode(sfx[fx["name"]])) / RATE + 0.1)

    track = np.zeros(int(total * RATE) + RATE, dtype=np.float32)
    for at, clip in voice_parts:
        i = int(at * RATE)
        track[i:i + len(clip)] += clip
    for at, fx in events:
        clip = fade(decode(sfx[fx["name"]]) * 10 ** (fx.get("gain_db", -12.0) / 20), 0.02)
        i = int(at * RATE)
        track[i:i + len(clip)] += clip[: len(track) - i]
    track = track[: int(total * RATE)]
    if bed is not None:
        loop = decode(bed)
        reps = int(np.ceil(len(track) / len(loop)))
        under = np.tile(loop, reps)[: len(track)] * 10 ** (bed_gain_db / 20)
        under = fade(under, 0.8)
        track += under
    peak = float(np.max(np.abs(track))) or 1.0
    track *= 0.89 / peak  # about -1 dBFS; the assembler applies loudnorm afterwards
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "-",
                    "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)], input=track.tobytes(), check=True)
    return words, round(total, 3)
