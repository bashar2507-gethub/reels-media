"""Build one queued Reel and record the outcome (runs in GitHub Actions).

Input `queue/<id>.json`:
    {"reel_id": "...", "script": {...content JSON...},
     "narration": {"url": "https://...", "words": [...], "voice": ..., "voice_id": ..., ...}}
When `narration.url` is absent and ELEVENLABS_API_KEY is set, the narration is generated
here through the ElevenLabs API instead.

Output in `reels/<id>/`: the video and cover (file names carry the start of their SHA-256)
and `status.json`. A Reel that fails the Media Gate gets a status.json with the reasons and
no video, so nothing unchecked can ever be posted. Nothing is published here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REEL_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
MAX_AUDIO_BYTES = 50_000_000


def download(url: str, target: Path) -> None:
    if not url.startswith("https://"):
        raise ValueError("narration url must use https")
    request = urllib.request.Request(url, headers={"User-Agent": "reels-render/1.0"})
    size = 0
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as handle:
        while chunk := response.read(1 << 16):
            size += len(chunk)
            if size > MAX_AUDIO_BYTES:
                raise ValueError("narration file is larger than expected")
            handle.write(chunk)
    if size == 0:
        raise ValueError("narration download was empty")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(reel_id: str, job: dict) -> dict:
    script = job["script"]
    if script.get("reel_id") != reel_id:
        raise ValueError("script.reel_id does not match the queue file name")
    write_json(ROOT / "content" / f"{reel_id}.json", script)
    out = ROOT / "output" / f"{reel_id}_release"
    cmd = [sys.executable, "scripts/run_poc1.py", "--script", f"content/{reel_id}.json",
           "--out", str(out.relative_to(ROOT)), "--release", "--visuals", "auto"]

    narration = job.get("narration") or {}
    if narration.get("url"):
        audio_dir = ROOT / "content" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        mp3 = audio_dir / f"{reel_id}_narration.mp3"
        download(narration["url"], mp3)
        meta = {k: v for k, v in narration.items() if k != "url"}
        meta["audio"] = mp3.name
        words = audio_dir / f"{reel_id}_narration_words.json"
        write_json(words, meta)
        cmd += ["--narration", str(words.relative_to(ROOT))]
    elif os.environ.get("ELEVENLABS_API_KEY"):
        cmd += ["--tts", "elevenlabs", "--speed", "1.0", "--stability", "0.5"]
    else:
        raise ValueError("no narration url and no ELEVENLABS_API_KEY")

    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    gate_path = out / "media_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else None
    status: dict = {
        "build_seconds": round(time.time() - started),
        "log_tail": (proc.stdout + proc.stderr)[-1500:],
    }
    if gate:
        checks = gate.get("checks", [])
        status.update({
            "checks": f"{sum(c['passed'] for c in checks)}/{len(checks)}",
            "failed_checks": [c["name"] for c in checks if not c["passed"] and c.get("severity") != "soft"],
            "warnings": gate.get("warnings", []),
            "visuals": gate.get("visuals"),
            "duration_s": gate.get("voice_metrics", {}).get("seconds"),
            "wpm": round(gate.get("voice_metrics", {}).get("wpm_span", 0)),
        })
    if proc.returncode != 0 or not gate or not gate.get("passed"):
        status["passed"] = False
        return status

    target = ROOT / "reels" / reel_id
    target.mkdir(parents=True, exist_ok=True)
    for kind, source in (("video", out / f"{reel_id}.mp4"), ("cover", out / f"{reel_id}_cover.jpg")):
        digest = sha256(source)
        dest = target / f"{reel_id}-{kind}-{digest[:10]}{source.suffix}"
        shutil.copy2(source, dest)
        status[kind] = dest.relative_to(ROOT).as_posix()
        status[f"{kind}_sha256"] = digest
        status[f"{kind}_bytes"] = dest.stat().st_size
    status["cover_at_seconds"] = script.get("cover_at_seconds", 1.0)
    status["passed"] = True
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reel-id", required=True)
    reel_id = parser.parse_args().reel_id
    if not REEL_ID.match(reel_id):
        print("invalid reel id")
        return 2
    target = ROOT / "reels" / reel_id
    target.mkdir(parents=True, exist_ok=True)
    status = {"reel_id": reel_id, "passed": False, "run_id": os.environ.get("GITHUB_RUN_ID"),
              "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        job = json.loads((ROOT / "queue" / f"{reel_id}.json").read_text(encoding="utf-8"))
        status.update(build(reel_id, job))
    except Exception as err:  # recorded for the publishing run; never published
        status["error"] = f"{type(err).__name__}: {err}"[:500]
    for secret in ("HF_TOKEN", "ELEVENLABS_API_KEY"):
        value = os.environ.get(secret)
        if value:
            status = json.loads(json.dumps(status, ensure_ascii=False).replace(value, "[secret]"))
    write_json(target / "status.json", status)
    print(json.dumps({k: v for k, v in status.items() if k != "log_tail"}, ensure_ascii=False, indent=2))
    return 0 if status["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
