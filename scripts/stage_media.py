"""Put a finished Reel's video and cover into the public media repository and print their URLs.

Metricool only accepts media by public URL, so each approved Reel is committed to the
`reels-media` GitHub repository and served through jsDelivr, pinned to the commit, so a
URL never changes once given to Metricool.

    python scripts/stage_media.py --repo /home/claude/reels-media --owner bashar2507-gethub \
        --reel-id poc1 --video output/poc1_release/poc1.mp4 --cover output/poc1_release/poc1_cover.jpg

Nothing is published here: this only makes the files reachable. Posting stays a separate,
approved step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True, help="local clone of the media repository")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--name", default="reels-media")
    parser.add_argument("--reel-id", required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--cover", type=Path)
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()

    files = [("video", args.video)] + ([("cover", args.cover)] if args.cover else [])
    folder = args.repo / "reels" / args.reel_id
    folder.mkdir(parents=True, exist_ok=True)
    placed = {}
    for kind, source in files:
        digest = sha256(source)
        target = folder / f"{args.reel_id}-{kind}-{digest[:10]}{source.suffix.lower()}"
        if not target.exists():
            shutil.copy2(source, target)
        placed[kind] = (target, digest)

    git(args.repo, "add", "reels")
    if git(args.repo, "status", "--porcelain"):
        git(args.repo, "commit", "-m", f"Add media for {args.reel_id}")
        git(args.repo, "push", "origin", args.branch)
    commit = git(args.repo, "rev-parse", "HEAD")

    out = {}
    for kind, (target, digest) in placed.items():
        rel = target.relative_to(args.repo).as_posix()
        out[kind] = {
            "url": f"https://cdn.jsdelivr.net/gh/{args.owner}/{args.name}@{commit}/{rel}",
            "raw": f"https://raw.githubusercontent.com/{args.owner}/{args.name}/{commit}/{rel}",
            "sha256": digest,
            "bytes": target.stat().st_size,
        }
    out["commit"] = commit
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
