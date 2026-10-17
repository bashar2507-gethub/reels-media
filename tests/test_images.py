import pytest
from PIL import Image

from app.images import ImageError, full_prompt, scene_images
from app.placeholders import H, W

SCENES = [
    {"visual": "s1", "image_prompt": "A bathroom scale on a stone floor", "fallback": "scale"},
    {"visual": "s2", "image_prompt": "A glass of water", "fallback": "flow"},
    {"visual": "s3", "fallback": "bookmark"},
]


def fake_image(prompt, token):
    return Image.new("RGB", (1024, 1792), (200, 120, 40))


def test_prompt_keeps_subject_and_forbids_text():
    p = full_prompt("A plate of grilled chicken.")
    assert p.startswith("A plate of grilled chicken. ") and "No text" in p


def test_ai_images_are_cropped_and_graded(tmp_path):
    visuals, report = scene_images(SCENES, tmp_path, token="tok", generate_fn=fake_image)
    assert report["ai"] == ["s1", "s2"] and report["fallback"] == ["s3"]
    img = Image.open(visuals["s1"])
    assert img.size == (W, H)
    # the caption band is darker than the top of the frame
    assert img.getpixel((W // 2, 1667))[0] < img.getpixel((W // 2, 300))[0]


def test_without_token_every_scene_falls_back(tmp_path):
    visuals, report = scene_images(SCENES, tmp_path, token=None)
    assert report["ai"] == [] and set(report["fallback"]) == {"s1", "s2", "s3"}
    assert all(p.exists() for p in visuals.values())


def test_api_errors_fall_back_without_leaking_the_token(tmp_path):
    def broken(prompt, token):
        raise RuntimeError(f"401 for token {token}")
    visuals, report = scene_images(SCENES, tmp_path, token="secret-token", generate_fn=broken)
    assert report["ai"] == [] and "s1" in report["errors"]
    assert "secret-token" not in str(report)


def test_pasted_whitespace_and_quotes_are_tolerated(tmp_path):
    seen = []

    def capture(prompt, token):
        seen.append(token)
        return fake_image(prompt, token)
    visuals, report = scene_images(SCENES[:1], tmp_path, token=' "hf_abc123"\n', generate_fn=capture)
    assert seen == ["hf_abc123"] and report["ai"] == ["s1"]
    assert report["token"] == {"set": True, "hf_prefix": True, "length": 9, "trimmed": True}


def test_ai_mode_refuses_to_fall_back(tmp_path):
    with pytest.raises(ImageError):
        scene_images(SCENES, tmp_path, token=None, mode="ai")
