"""Media Gate: check a rendered Reel before it may be scheduled.

Each check names where its limit comes from:
  instagram - Meta "IG User Media" reference, Reels specifications
  metricool - Metricool help: auto-publish only for videos under 1 minute
  internal  - this project's own targets (resolution, loudness, silence, sync)
Hard checks block scheduling. Soft checks are warnings for human review.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import SPEC, VideoSpec

_CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"dinf", b"mvex"}


@dataclass
class Check:
    name: str
    passed: bool | None  # None = could not be determined (treated as not passed)
    value: str
    limit: str
    source: str
    severity: str = "hard"


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(path: Path) -> dict:
    proc = _run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "ffprobe failed")
    return json.loads(proc.stdout)


def mp4_layout(path: Path) -> tuple[list[str], bool]:
    """Top-level box order, and whether any track carries an edit list (edts)."""
    order: list[str] = []
    has_edts = False
    with open(path, "rb") as f:
        def walk(start: int, end: int, depth: int) -> None:
            nonlocal has_edts
            pos = start
            while pos + 8 <= end:
                f.seek(pos)
                header = f.read(8)
                size, kind, head = int.from_bytes(header[:4], "big"), header[4:8], 8
                if size == 1:
                    size, head = int.from_bytes(f.read(8), "big"), 16
                elif size == 0:
                    size = end - pos
                if size < head:
                    return
                if depth == 0:
                    order.append(kind.decode("latin-1"))
                if kind == b"edts":
                    has_edts = True
                elif kind in _CONTAINERS:
                    walk(pos + head, pos + size, depth + 1)
                pos += size
        walk(0, path.stat().st_size, 0)
    return order, has_edts


def x264_open_gop(path: Path) -> bool | None:
    """Read open_gop from the x264 settings string the encoder embeds in the stream."""
    with open(path, "rb") as f:
        blob = f.read(8 * 1024 * 1024)
    match = re.search(rb"open_gop=(\d)", blob)
    return None if match is None else match.group(1) == b"1"


def peak_video_bitrate(path: Path) -> float:
    """Highest bitrate over any 1-second window of video packets, in bits per second."""
    proc = _run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "packet=pts_time,size", "-of", "csv=p=0", str(path)])
    packets = []
    for line in proc.stdout.split():
        fields = line.split(",")
        if len(fields) >= 2 and "N/A" not in fields[:2]:
            packets.append((float(fields[0]), int(fields[1])))
    packets.sort()
    peak, window, lo = 0, 0, 0
    for hi, (t, size) in enumerate(packets):
        window += size
        while packets[lo][0] <= t - 1.0:
            window -= packets[lo][1]
            lo += 1
        peak = max(peak, window)
    return peak * 8.0


def loudness(path: Path) -> tuple[float | None, float | None]:
    """Integrated loudness (LUFS) and true peak (dBTP) via the EBU R128 meter."""
    proc = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                 "-filter_complex", "ebur128=peak=true", "-f", "null", "-"])
    summary = proc.stderr[proc.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+)", summary)
    return (float(i.group(1)) if i else None, float(tp.group(1)) if tp else None)


def long_silences(path: Path, min_seconds: float = 1.5, noise_db: int = -45) -> int:
    proc = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                 "-af", f"silencedetect=noise={noise_db}dB:d={min_seconds}", "-f", "null", "-"])
    return len(re.findall(r"silence_start", proc.stderr))


def decode_errors(path: Path) -> str:
    return _run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"]).stderr.strip()


def validate_reel(path: Path, spec: VideoSpec = SPEC) -> dict:
    checks: list[Check] = []

    def add(name, passed, value, limit, source, severity="hard"):
        checks.append(Check(name, passed, str(value), limit, source, severity))

    if not path.exists():
        add("file_exists", False, "missing", "file present", "internal")
        return {"file": str(path), "passed": False, "checks": [asdict(c) for c in checks], "warnings": []}

    info = probe(path)
    fmt, streams = info["format"], info["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    order, has_edts = mp4_layout(path)
    size_mb = path.stat().st_size / 1e6

    add("file_size", size_mb <= 300, f"{size_mb:.1f} MB", "<= 300 MB", "instagram")
    name = fmt.get("format_name", "")
    add("container", "mp4" in name or "mov" in name, name, "MOV or MP4", "instagram")
    moov_first = "moov" in order and "mdat" in order and order.index("moov") < order.index("mdat")
    add("moov_before_mdat", moov_first, " > ".join(order), "moov atom at the front", "instagram")
    add("no_edit_lists", not has_edts, "edts present" if has_edts else "none", "no edit lists", "instagram")

    if video is None:
        add("video_stream", False, "missing", "one video stream", "instagram")
    else:
        add("video_codec", video["codec_name"] in ("h264", "hevc"), video["codec_name"], "H.264 or HEVC", "instagram")
        add("chroma_420", video.get("pix_fmt") in ("yuv420p", "yuvj420p"), video.get("pix_fmt"), "4:2:0", "instagram")
        field = video.get("field_order", "unknown")
        add("progressive", field == "progressive", field, "progressive scan", "instagram")
        open_gop = x264_open_gop(path)
        add("closed_gop", None if open_gop is None else not open_gop,
            "unknown" if open_gop is None else f"open_gop={int(open_gop)}", "closed GOP", "instagram")
        num, den = (int(x) for x in video["avg_frame_rate"].split("/"))
        fps = num / den if den else 0.0
        add("frame_rate", 23 <= fps <= 60, f"{fps:.2f} fps", "23-60 fps", "instagram")
        w, h = int(video["width"]), int(video["height"])
        add("max_width", w <= 1920, f"{w} px", "<= 1920 px wide", "instagram")
        add("aspect_9_16", abs(w / h - 9 / 16) < 0.01, f"{w}x{h}", "9:16 recommended", "instagram", "soft")
        add("resolution", (w, h) == (spec.width, spec.height), f"{w}x{h}", f"{spec.width}x{spec.height}", "internal")
        peak = peak_video_bitrate(path)
        add("peak_video_bitrate", peak <= 25e6, f"{peak / 1e6:.1f} Mbps", "<= 25 Mbps (1 s window)", "instagram")

    duration = float(fmt.get("duration", 0.0))
    add("duration_instagram", 3 <= duration <= 900, f"{duration:.2f} s", "3 s to 15 min", "instagram")
    add("duration_autopublish", 3 <= duration <= 900, f"{duration:.2f} s", "3 s to 15 min (Metricool help centre)", "metricool")
    add("duration_target", spec.target_min_s <= duration <= spec.target_max_s, f"{duration:.2f} s",
        f"{spec.target_min_s:.0f}-{spec.target_max_s:.0f} s", "internal", "soft")

    if audio is None:
        add("audio_stream", False, "missing", "AAC audio track", "internal")
    else:
        add("audio_codec", audio["codec_name"] == "aac", audio["codec_name"], "AAC", "instagram")
        rate = int(audio.get("sample_rate", 0))
        add("audio_sample_rate", 0 < rate <= 48000, f"{rate} Hz", "<= 48 kHz", "instagram")
        channels = int(audio.get("channels", 0))
        add("audio_channels", channels in (1, 2), channels, "mono or stereo", "instagram")
        bitrate = int(audio.get("bit_rate") or 0)
        add("audio_bitrate", 0 < bitrate <= 128_000 * 1.05, f"{bitrate / 1000:.0f} kbps", "128 kbps", "instagram")
        lufs, peak_db = loudness(path)
        add("loudness", lufs is not None and abs(lufs - spec.target_lufs) <= 2, f"{lufs} LUFS",
            f"{spec.target_lufs:.0f} +/- 2 LUFS", "internal", "soft")
        add("true_peak", peak_db is not None and peak_db <= -1.0, f"{peak_db} dBTP", "<= -1.0 dBTP", "internal", "soft")
        gaps = long_silences(path)
        add("no_long_silence", gaps == 0, f"{gaps} gaps", "no silence >= 1.5 s", "internal", "soft")
        if video is not None:
            vd, ad = float(video.get("duration", 0)), float(audio.get("duration", 0))
            add("av_duration_match", abs(vd - ad) <= 0.1, f"video {vd:.2f} s, audio {ad:.2f} s", "<= 0.1 s apart",
                "internal")

    errors = decode_errors(path)
    add("decodes_cleanly", errors == "", "no errors" if not errors else errors[:200], "full decode", "internal")

    passed = all(c.passed is True for c in checks if c.severity == "hard")
    warnings = [c.name for c in checks if c.severity == "soft" and c.passed is not True]
    return {"file": str(path), "passed": passed, "checks": [asdict(c) for c in checks], "warnings": warnings}
