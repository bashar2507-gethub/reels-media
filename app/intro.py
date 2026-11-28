"""Signature intros: THE BLANKET EFFECT (scripts/build_intro.py) on every Reel, and MARAH MOMENT
(scripts/build_marah_intro.py, owner 2026-11-26) in its place on the Reels Marah presents (`"intro": "marah"`)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import SPEC, VideoSpec
from .video_assembler import aac_args, mp4_args, x264_args

ROOT = Path(__file__).resolve().parents[1]
INTRO = ROOT / "assets" / "intro" / "blanket_effect.mp4"
MARAH = ROOT / "assets" / "intro" / "marah_moment.mp4"
OUTRO = ROOT / "assets" / "outro" / "marah_outro.mp4"  # owner, 2026-11-28: Marah's call to action ends every Reel
TRANSITION = 0.2  # seconds of the intro's flash that overlap the Reel's first scene
TRANSITIONS = {"flash": "fadewhite", "zoom": "zoomin", "circle": "circleopen", "slide": "slideup", "fade": "fade"}


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def pick(script: dict) -> Path:
    """The intro a script asks for: Marah's moment for `"intro": "marah"`, otherwise THE BLANKET EFFECT."""
    return MARAH if script.get("intro") == "marah" else INTRO


def offset(path: Path = INTRO) -> float:
    """Seconds by which the Reel's own content starts later once the intro is prepended."""
    return round(duration(path) - TRANSITION, 3)


def prepend(main: Path, out: Path, transition: str = "flash", spec: VideoSpec = SPEC, path: Path = INTRO) -> Path:
    """Intro + Reel, joined by a short transition chosen per Reel (`intro_transition` in the script)."""
    off = offset(path)
    ms = int(round(off * 1000))
    kind = TRANSITIONS.get(transition, "fadewhite")
    graph = (f"[0:v]fps={spec.fps},format=yuv420p,setsar=1[i];[1:v]fps={spec.fps},format=yuv420p,setsar=1[m];"
             f"[i][m]xfade=transition={kind}:duration={TRANSITION}:offset={off:.3f},"
             f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v];"
             f"[1:a]adelay={ms}|{ms}[ma];[0:a][ma]amix=inputs=2:duration=longest:normalize=0[a]")
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-i", str(main),
                    "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    *x264_args(spec), *aac_args(spec), *mp4_args(), "-shortest", str(tmp)], check=True)  # sound never outlasts the picture
    tmp.replace(out)
    return out


def append(main: Path, out: Path, path: Path = OUTRO, transition: str = "fade", spec: VideoSpec = SPEC) -> Path:
    """Reel + outro (Marah's call to action), joined by a short crossfade of picture and sound."""
    off = round(duration(main) - TRANSITION, 3)
    kind = TRANSITIONS.get(transition, "fade")
    pcm = f"aformat=sample_rates={spec.audio_rate}:channel_layouts=stereo"
    graph = (f"[0:v]fps={spec.fps},format=yuv420p,setsar=1[m];[1:v]fps={spec.fps},format=yuv420p,setsar=1[o];"
             f"[m][o]xfade=transition={kind}:duration={TRANSITION}:offset={off:.3f},"
             f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v];"
             f"[0:a]{pcm}[ma];[1:a]{pcm}[oa];[ma][oa]acrossfade=d={TRANSITION}[a]")
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(main), "-i", str(path),
                    "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    *x264_args(spec), *aac_args(spec), *mp4_args(), str(tmp)], check=True)
    tmp.replace(out)
    return out


def hook_end(timeline) -> float:
    """Where the hook question ends: halfway between its last spoken word and the next sentence's first word."""
    first, second = timeline.sentences[0], timeline.sentences[1]
    last = first.captions[-1].words[-1].end if first.captions else first.end
    nxt = second.captions[0].words[0].start if second.captions else second.start
    return (last + max(nxt, last)) / 2


def insert_after(main: Path, out: Path, at: float, transition: str = "flash", spec: VideoSpec = SPEC,
                 blend: float = 0.3) -> Path:
    """Hook first: the Reel's opening (0..`at`, the hook question) plays, then the intro, then the rest.

    The cut into the intro is hard (the intro opens on black); the intro flashes into the rest with the
    per-Reel transition, as when it is prepended. The total length is the same as with `prepend`.
    `blend` is half the crossfade between scenes 1 and 2 in the assembled Reel: those frames are replaced by
    a still of the clean scene on each side, so no half-faded image shows around the intro.
    """
    at = round(at * spec.fps) / spec.fps  # cut on a frame boundary so picture and sound stay in step
    if not 0.5 <= at <= duration(main) - 1.0:
        raise ValueError(f"hook split at {at:.2f} s is outside the Reel")
    blend = max(0.0, min(blend, at - 0.2))
    off = offset()
    ms = int(round(off * 1000))
    kind = TRANSITIONS.get(transition, "fadewhite")
    norm = f"fps={spec.fps},format=yuv420p,setsar=1"
    pcm = f"aformat=sample_rates={spec.audio_rate}:channel_layouts=stereo"
    graph = (f"[0:v]{norm},split=2[m1][m2];[1:v]{norm}[i];"
             f"[m1]trim=end={at - blend:.3f},setpts=PTS-STARTPTS,"
             f"tpad=stop_mode=clone:stop_duration={blend:.3f}[hook];"
             f"[m2]trim=start={at + blend:.3f},setpts=PTS-STARTPTS,"
             f"tpad=start_mode=clone:start_duration={blend:.3f}[rest];"
             f"[i][rest]xfade=transition={kind}:duration={TRANSITION}:offset={off:.3f}[ir];"
             f"[hook][ir]concat=n=2:v=1:a=0,scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v];"
             f"[0:a]asplit=2[a1][a2];"
             f"[a1]atrim=end={at:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={max(0.0, at - 0.03):.3f}:d=0.03,{pcm}[ha];"
             f"[a2]atrim=start={at:.3f},asetpts=PTS-STARTPTS,adelay={ms}|{ms}[ra];"
             f"[1:a][ra]amix=inputs=2:duration=longest:normalize=0,{pcm}[ira];"
             f"[ha][ira]concat=n=2:v=0:a=1[a]")
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(main), "-i", str(INTRO),
                    "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    *x264_args(spec), *aac_args(spec), *mp4_args(), "-shortest", str(tmp)], check=True)  # sound never outlasts the picture
    tmp.replace(out)
    return out
