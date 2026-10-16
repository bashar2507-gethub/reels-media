"""Objective voice checks: speaking rate, pauses, pitch movement, loudness.

They cannot replace listening, but they catch the usual causes of a robotic or rushed
voice: too many words per minute, missing pauses, and flat intonation.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

ARABIC_RATE_WPM = (125, 145)  # target for explanatory Arabic narration


def load_mono(path: Path, rate: int = 16000) -> np.ndarray:
    """Decode any audio file to mono float32 at `rate` via FFmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if any(ch.isalnum() for ch in w)])


def speech_spans(x: np.ndarray, rate: int, threshold_db: float = -40.0, min_pause: float = 0.12):
    """(start, end) seconds of speech, split wherever the level stays below the threshold."""
    hop = int(0.01 * rate)
    frames = x[: len(x) // hop * hop].reshape(-1, hop)
    level = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    loud = level > threshold_db
    spans, start, quiet = [], None, 0
    for i, on in enumerate(loud):
        if on:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * 0.01 >= min_pause:
                spans.append((start * 0.01, (i - quiet + 1) * 0.01))
                start, quiet = None, 0
    if start is not None:
        spans.append((start * 0.01, (len(loud) - quiet) * 0.01))
    return spans


def pitch_track(x: np.ndarray, rate: int, fmin: float = 70.0, fmax: float = 320.0) -> np.ndarray:
    """F0 per 10 ms frame (Hz) on voiced frames, by normalised autocorrelation."""
    n, hop = int(0.04 * rate), int(0.01 * rate)
    lo, hi = int(rate / fmax), int(rate / fmin)
    floor = 10 ** (-35 / 20)
    out = []
    for i in range(0, len(x) - n, hop):
        seg = x[i:i + n] - x[i:i + n].mean()
        if np.sqrt((seg ** 2).mean()) < floor:
            continue
        spec = np.fft.rfft(seg, 2 * n)
        ac = np.fft.irfft(spec * np.conj(spec))[:n]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.5:
            out.append(rate / lag)
    return np.array(out)


@dataclass
class VoiceReport:
    seconds: float
    words: int
    speech_seconds: float
    wpm_speech: float          # words per minute while speaking (pauses excluded)
    wpm_span: float            # narration pace: first word to last word, natural pauses included
    pauses: int
    mean_pause_s: float
    pitch_std_semitones: float  # intonation movement; very low values sound monotone
    pitch_range_semitones: float
    peak_dbfs: float

    def as_dict(self) -> dict:
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in asdict(self).items()}


def analyse(path: Path, text: str, rate: int = 16000) -> VoiceReport:
    x = load_mono(path, rate)
    spans = speech_spans(x, rate)
    speech = sum(b - a for a, b in spans)
    gaps = [b[0] - a[1] for a, b in zip(spans, spans[1:])]
    f0 = pitch_track(x, rate)
    semis = 12 * np.log2(f0 / np.median(f0)) if f0.size else np.array([0.0])
    words = count_words(text)
    seconds = len(x) / rate
    span = spans[-1][1] - spans[0][0] if spans else 0.0
    return VoiceReport(
        seconds=seconds, words=words, speech_seconds=speech,
        wpm_speech=60 * words / speech if speech else 0.0, wpm_span=60 * words / span if span else 0.0,
        pauses=len(gaps), mean_pause_s=float(np.mean(gaps)) if gaps else 0.0,
        pitch_std_semitones=float(np.std(semis)),
        pitch_range_semitones=float(np.percentile(semis, 95) - np.percentile(semis, 5)),
        peak_dbfs=float(20 * np.log10(np.abs(x).max() + 1e-9)),
    )
