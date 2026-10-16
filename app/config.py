"""Paths and the video spec shared by the assembler and the Media Gate."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
CONTENT_DIR = ROOT / "content"
OUTPUT_DIR = ROOT / "output"

# "عبدالله سعدون" (Abdullah Saadoun): professional library voice, male, Saudi accent.
# Taken from ElevenLabs' voice search on 2026-10-16, not typed from memory. Not a secret.
ELEVENLABS_VOICE_ID = "t9akNmCDhz230CEXOYmn"


@dataclass(frozen=True)
class VideoSpec:
    """Encoding targets for one Reel: 1080x1920, H.264 + AAC, 30 fps."""

    width: int = 1080
    height: int = 1920
    fps: int = 30
    crf: int = 20
    maxrate: str = "12M"
    bufsize: str = "24M"
    gop: int = 60
    audio_rate: int = 48000
    audio_channels: int = 2
    audio_bitrate: str = "128k"
    target_lufs: float = -16.0
    true_peak_db: float = -1.5
    target_min_s: float = 25.0
    target_max_s: float = 30.0


SPEC = VideoSpec()
