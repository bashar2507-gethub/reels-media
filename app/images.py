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
_FRAME = ("deep teal background, soft warm amber rim light, cinematic, high detail, vertical composition "
          "with calm empty space in the upper third and the lower third")
STYLES = {
    # objects and food; the default
    "still_life": (f"Minimal editorial still life photograph, {_FRAME}, shallow depth of field. Plain unmarked "
                   "objects only: no packaging, no labels, no engraving. No text, no letters, no numbers, no logos, "
                   "no people, no hands, no faces."),
    # a person training, for sentences about muscles and exercise
    "athlete": (f"Cinematic fitness photograph of an athletic adult in a plain dark fitted tank top, {_FRAME}. "
                "The face is out of frame or in deep shadow, natural realistic anatomy and hands, defined muscles. "
                "Plain unmarked equipment. No text, no letters, no numbers, no logos, no tattoos."),
    # how muscles work inside the body
    "anatomy": (f"Clean educational 3D anatomical illustration of human muscle, realistic muscle fibres, {_FRAME}. "
                "No skin details, no face. No text, no labels, no arrows, no numbers."),
}
STYLE = STYLES["still_life"]
TITLE_Y, CAPTION_Y = 1200, 1667  # title and caption centres at the 1440x2560 working size


class ImageError(RuntimeError):
    """An image could not be generated (message never contains the token)."""


def full_prompt(subject: str, style: str = "still_life") -> str:
    return f"{subject.strip().rstrip('.')}. {STYLES.get(style, STYLE)}"


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


def clean_token(raw: str | None) -> str | None:
    """Tolerate a secret pasted with spaces, a newline or quotes around it."""
    if not raw:
        return None
    return raw.strip().strip("\"'").strip() or None


def token_shape(raw: str | None) -> dict:
    """Safe facts about the secret for the build report (never the value itself).
    Hugging Face access tokens start with "hf_"; anything else is sent to the image
    provider as its own key and is rejected."""
    token = clean_token(raw)
    return {"set": bool(token), "hf_prefix": bool(token and token.startswith("hf_")),
            "length": len(token or ""), "trimmed": bool(raw) and token != raw}


def generate(prompt: str, token: str, attempts: int = 3, sleep: Callable[[float], None] = time.sleep,
             client=None, width: int = GEN_W, height: int = GEN_H) -> Image.Image:
    """One FLUX.1-schnell image for a complete prompt; retries transient failures with backoff."""
    if client is None:
        from huggingface_hub import InferenceClient  # imported lazily: tests and offline builds don't need it
        client = InferenceClient(provider="auto", api_key=token, timeout=120)
    last = "no attempt made"
    for k in range(attempts):
        try:
            return client.text_to_image(prompt, model=MODEL, width=width, height=height, num_inference_steps=4)
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
    report: dict = {"ai": [], "fallback": [], "errors": {}, "token": token_shape(token)}
    raw_token, token = token, clean_token(token)
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
                    full = full_prompt(prompt, scene.get("image_style", "still_life"))
                    grade(fit((generate_fn or generate)(full, token))).save(path)
                    visuals[key] = path
                    report["ai"].append(key)
                    continue
                except Exception as err:
                    report["errors"][key] = _scrub(_scrub(str(err), token), raw_token)[:300]
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
