"""Assemble a Reel: still scenes with motion and crossfades, burned-in Arabic captions,
loudness-normalised voice, encoded to the Instagram Reels spec.
"""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Iterator

import numpy as np

from .config import FONTS_DIR, SPEC, VideoSpec
from .motion import StillMotion, smoothstep
from .timeline import Timeline


class AssemblyError(RuntimeError):
    """FFmpeg failed or produced no file."""


def filter_path(path: Path) -> str:
    """Escape a path for use inside an FFmpeg filtergraph option."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def x264_args(spec: VideoSpec = SPEC) -> list[str]:
    return [
        "-c:v", "libx264", "-preset", "medium", "-crf", str(spec.crf),
        "-maxrate", spec.maxrate, "-bufsize", spec.bufsize,
        "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p",
        "-g", str(spec.gop), "-flags", "+cgop",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
    ]


def aac_args(spec: VideoSpec = SPEC) -> list[str]:
    return ["-c:a", "aac", "-b:a", spec.audio_bitrate, "-ar", str(spec.audio_rate), "-ac", str(spec.audio_channels)]


def mp4_args() -> list[str]:
    # Instagram wants the moov atom first and no edit lists.
    return ["-movflags", "+faststart", "-use_editlist", "0"]


def render_frames(timeline: Timeline, visuals: dict[str, Path], spec: VideoSpec = SPEC,
                  crossfade: float = 0.6) -> Iterator[np.ndarray]:
    scenes = timeline.scenes
    motions = [StillMotion(visuals[s.visual], spec.width, spec.height, s.zoom, s.pan) for s in scenes]
    half = crossfade / 2

    def progress(j: int, t: float) -> float:
        a, b = scenes[j].start - half, scenes[j].end + half
        return (t - a) / (b - a)

    for k in range(int(round(timeline.duration * spec.fps))):
        t = k / spec.fps
        i = next((j for j, s in enumerate(scenes) if s.start <= t < s.end), len(scenes) - 1)
        frame = motions[i].frame(progress(i, t))
        if i + 1 < len(scenes) and t > scenes[i].end - half:
            alpha = smoothstep((t - (scenes[i].end - half)) / crossfade)
            other = motions[i + 1].frame(progress(i + 1, t))
            frame = (frame * (1 - alpha) + other * alpha).astype(np.uint8)
        elif i > 0 and t < scenes[i].start + half:
            alpha = smoothstep((t - (scenes[i].start - half)) / crossfade)
            other = motions[i - 1].frame(progress(i - 1, t))
            frame = (other * (1 - alpha) + frame * alpha).astype(np.uint8)
        yield frame


def assemble(timeline: Timeline, visuals: dict[str, Path], ass_path: Path, out_path: Path,
             spec: VideoSpec = SPEC, fonts_dir: Path = FONTS_DIR) -> Path:
    duration = f"{timeline.duration:.3f}"
    graph = (
        f"[0:v]ass=filename={filter_path(ass_path)}:fontsdir={filter_path(fonts_dir)}:shaping=complex,"
        f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v];"
        f"[1:a]loudnorm=I={spec.target_lufs}:TP={spec.true_peak_db}:LRA=11,"
        f"aresample={spec.audio_rate},apad,atrim=0:{duration}[a]"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{spec.width}x{spec.height}", "-r", str(spec.fps), "-i", "-",
        "-i", str(timeline.voice_path),
        "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
        *x264_args(spec), *aac_args(spec), *mp4_args(), "-t", duration, str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    errors: list[bytes] = []
    reader = threading.Thread(target=lambda: errors.append(proc.stderr.read()), daemon=True)
    reader.start()
    try:
        for frame in render_frames(timeline, visuals, spec):
            proc.stdin.write(frame.tobytes())
    except BrokenPipeError:
        pass
    finally:
        proc.stdin.close()
    code = proc.wait()
    reader.join()
    if code != 0 or not out_path.exists():
        raise AssemblyError(b"".join(errors).decode(errors="replace") or f"ffmpeg exited {code}")
    return out_path


def extract_cover(video: Path, at_seconds: float, out_jpg: Path) -> Path:
    """A 9:16 JPEG cover taken from the video (Instagram: JPEG, sRGB, up to 8 MB)."""
    proc = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{at_seconds:.2f}", "-i", str(video),
         "-frames:v", "1", "-q:v", "3", str(out_jpg)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not out_jpg.exists():
        raise AssemblyError(proc.stderr or "cover extraction failed")
    return out_jpg
