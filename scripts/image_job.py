"""Generate the AI images listed in images/queue/<id>.json (used for carousel posts).

Each entry: {"key", "prompt", "style"}; optional top-level "width"/"height" (multiples of 64).
Writes images/<id>/<key>.jpg and images/<id>/status.json. Runs in GitHub Actions with HF_TOKEN.
The status never contains the token.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.images import _scrub, clean_token, full_prompt, generate, token_shape  # noqa: E402


EDIT_MODEL = "Qwen/Qwen-Image-Edit-2509"  # Apache-2.0; keeps a character from a reference image


def character_prompt(scene: str, character: str) -> str:
    return (f"Keep exactly the same character as in the image: {character}. Same flat cartoon illustration style with "
            f"clean black outlines and soft cel shading. New scene: {scene.strip().rstrip('.')}. Background: dark "
            "petrol-teal gym with warm amber rim light. Vertical 9:16 composition with calm empty space in the upper "
            "third and the lower third. No text, no captions, no extra letters or numbers anywhere.")


def edit_from_reference(reference: Path, prompt: str, token: str, model: str, attempts: int = 3):
    import time
    from huggingface_hub import InferenceClient
    client = InferenceClient(provider="auto", api_key=token, timeout=180)
    last = "no attempt"
    for k in range(attempts):
        try:
            return client.image_to_image(reference.read_bytes(), prompt=prompt, model=model)
        except Exception as err:
            last = _scrub(f"{type(err).__name__}: {err}", token)
            time.sleep(2 ** k)
    raise RuntimeError(last[:300])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    args = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", args.job_id):
        raise SystemExit("bad job id")
    job = json.loads(Path(f"images/queue/{args.job_id}.json").read_text(encoding="utf-8"))
    out = Path("images") / args.job_id
    out.mkdir(parents=True, exist_ok=True)
    raw = os.environ.get("HF_TOKEN")
    token = clean_token(raw)
    w, h = int(job.get("width", 1024)), int(job.get("height", 1280))
    status = {"job": args.job_id, "ok": [], "errors": {}, "token": token_shape(raw), "width": w, "height": h}
    for item in job["images"]:
        key = item["key"]
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", key):
            status["errors"][key] = "bad key"
            continue
        if not token:
            status["errors"][key] = "HF_TOKEN is not set"
            continue
        try:
            if item.get("reference"):
                img = edit_from_reference(Path(item["reference"]), character_prompt(item["prompt"], job.get("character", "")),
                                          token, job.get("edit_model", EDIT_MODEL))
            else:
                img = generate(full_prompt(item["prompt"], item.get("style", "still_life")), token, width=w, height=h)
            img.convert("RGB").save(out / f"{key}.jpg", quality=92)
            status["ok"].append(key)
        except Exception as err:
            status["errors"][key] = _scrub(_scrub(str(err), token), raw)[:300]
    status["passed"] = not status["errors"]
    (out / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in status.items() if k != "token"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
