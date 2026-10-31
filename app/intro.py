"""THE BLANKET EFFECT: the signature intro prepended to every Reel (built by scripts/build_intro.py)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import SPEC, VideoSpec
from .video_assembler import aac_args, mp4_args, x264_args

ROOT = Path(__file__).resolve().parents[1]
INTRO = ROOT / "assets" / "intro" / "blanket_effect.mp4"
TRANSITION = 0.2  # seconds of the intro's flash that overlap the Reel's first scene
TRANSITIONS = {"flash": "fadewhite", "zoom": "zoomin", "circle": "circleopen", "slide": "slideup", "fade": "fade"}


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def offset() -> float:
    """Seconds by which the Reel's own content starts later once the intro is prepended."""
    return round(duration(INTRO) - TRANSITION, 3)


def prepend(main: Path, out: Path, transition: str = "flash", spec: VideoSpec = SPEC) -> Path:
    """Intro + Reel, joined by a short transition chosen per Reel (`intro_transition` in the script)."""
    off = offset()
    ms = int(round(off * 1000))
    kind = TRANSITIONS.get(transition, "fadewhite")
    graph = (f"[0:v]fps={spec.fps},format=yuv420p,setsar=1[i];[1:v]fps={spec.fps},format=yuv420p,setsar=1[m];"
             f"[i][m]xfade=transition={kind}:duration={TRANSITION}:offset={off:.3f},"
             f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v];"
             f"[1:a]adelay={ms}|{ms}[ma];[0:a][ma]amix=inputs=2:duration=longest:normalize=0[a]")
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(INTRO), "-i", str(main),
                    "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    *x264_args(spec), *aac_args(spec), *mp4_args(), str(tmp)], check=True)
    tmp.replace(out)
    return out
