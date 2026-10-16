"""Scene images for a Reel.

AI images come from FLUX.1-schnell (Apache-2.0) through Hugging Face Inference Providers,
using the HF_TOKEN secret. Every image is cover-cropped to the 9:16 working size and graded
so the Arabic title and captions stay legible. When there is no token, or a request fails,
the scene falls back to one of the procedural backgrounds, so an image API can never block
a Reel; the build report says which scenes used which.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from .placeholders import H, SCENES, W, make_placeholder

MODEL = "black-forest-labs/FLUX.1-schnell"
GEN_W, GEN_H = 1024, 1792  # 9:16 at about 1.8 megapixels, multiples of 64
STYLE = (
    "Minimal editorial still life photograph, deep teal background, soft warm amber rim light, "
    "cinematic, high detail, shallow depth of field, vertical composition with calm empty space "
    "in the lower third. No text, no letters, no numbers, no logos, no people, no hands, no faces."
)
TITLE_Y, CAPTION_Y = 1200, 1667  # title and caption centres at the 1440x2560 working size


class ImageError(RuntimeError):
    """An image could not be generated (message never contains the token)."""


def full_prompt(subject: str) -> str:
    return f"{subject.strip().rstrip('.')}. {STYLE}"


def fit(image: Image.Image) -> Image.Image:
    """Cover-crop any image to the W x H working size."""
    image = image.convert("RGB")
    scale = max(W / image.width, H / image.height)
    size = (max(W, round(image.width * scale)), max(H, round(image.height * scale)))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    left, top = (resized.width - W) // 2, (resized.height - H) // 2
    return resized.crop((left, top, left + W, top + H))


def grade(image: Image.Image) -> Image.Image:
    """Slightly darker overall, darker bands behind the title and captions, soft vignette."""
    a = np.asarray(image, dtype=np.float32)
    y = np.arange(H, dtype=np.float32)
    band = 0.45 * np.exp(-(((y - CAPTION_Y) / 330) ** 2)) + 0.22 * np.exp(-(((y - TITLE_Y) / 260) ** 2))
    a = a * (0.88 * (1 - band))[:, None, None]
    yy, xx = np.ogrid[:H, :W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a = a * (1 - 0.25 * np.clip(r - 0.6, 0, 1))[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def _scrub(text: str, token: str | None) -> str:
    return text.replace(token, "[token]") if token else text


def generate(subject: str, token: str, attempts: int = 3, sleep: Callable[[float], None] = time.sleep,
             client=None) -> Image.Image:
    """One FLUX.1-schnell image for `subject`; retries transient failures with backoff."""
    if client is None:
        from huggingface_hub import InferenceClient  # imported lazily: tests and offline builds don't need it
        client = InferenceClient(provider="auto", api_key=token, timeout=120)
    last = "no attempt made"
    for k in range(attempts):
        try:
            return client.text_to_image(full_prompt(subject), model=MODEL, width=GEN_W, height=GEN_H,
                                        num_inference_steps=4)
        except Exception as err:  # provider, quota or network errors all fall back the same way
            last = _scrub(f"{type(err).__name__}: {err}", token)
            if k + 1 < attempts:
                sleep(2 ** k)
    raise ImageError(last[:300])


def scene_images(scenes: list[dict], out_dir: Path, token: str | None = None, mode: str = "auto",
                 generate_fn: Callable[[str, str], Image.Image] | None = None) -> tuple[dict[str, Path], dict]:
    """Images keyed by each scene's `visual`.

    mode "procedural" never calls the API; "auto" uses AI when a scene has an `image_prompt`
    and a token is set, otherwise the procedural `fallback`; "ai" raises instead of falling back.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    visuals: dict[str, Path] = {}
    report: dict = {"ai": [], "fallback": [], "errors": {}}
    names = list(SCENES)
    for i, scene in enumerate(scenes):
        key = scene["visual"]
        if key in visuals:
            continue
        path = out_dir / f"{key}.png"
        prompt = scene.get("image_prompt")
        if prompt and mode != "procedural":
            if token:
                try:
                    grade(fit((generate_fn or generate)(prompt, token))).save(path)
                    visuals[key] = path
                    report["ai"].append(key)
                    continue
                except Exception as err:
                    report["errors"][key] = _scrub(str(err), token)[:300]
            else:
                report["errors"][key] = "HF_TOKEN is not set"
            if mode == "ai":
                raise ImageError(f"scene {key}: {report['errors'][key]}")
        fallback = scene.get("fallback")
        if fallback not in SCENES:
            fallback = key if key in SCENES else names[i % len(names)]
        visuals[key] = make_placeholder(fallback, path, seed=i + 3)
        report["fallback"].append(key)
    return visuals, report
