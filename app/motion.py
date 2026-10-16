"""Smooth Ken Burns motion for still images.

Frames are resampled with sub-pixel precision (PIL affine + bicubic), which avoids
the stepping that FFmpeg's zoompan shows on slow zooms.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def smoothstep(p: float) -> float:
    p = min(max(p, 0.0), 1.0)
    return p * p * (3.0 - 2.0 * p)


class StillMotion:
    def __init__(self, image_path: Path, out_w: int, out_h: int,
                 zoom: tuple[float, float] = (1.0, 1.08), pan: tuple[float, float] = (0.0, 0.0)) -> None:
        if min(zoom) < 1.0:
            raise ValueError("zoom must stay >= 1.0 so the frame is always covered")
        self.image = Image.open(image_path).convert("RGB")
        self.out_w, self.out_h = out_w, out_h
        self.zoom, self.pan = zoom, pan
        self.cover = max(out_w / self.image.width, out_h / self.image.height)

    def frame(self, progress: float) -> np.ndarray:
        p = smoothstep(progress)
        scale = self.cover * (self.zoom[0] + (self.zoom[1] - self.zoom[0]) * p)
        vis_w, vis_h = self.out_w / scale, self.out_h / scale
        slack_x = (self.image.width - vis_w) / 2
        slack_y = (self.image.height - vis_h) / 2
        cx = self.image.width / 2 + self.pan[0] * slack_x * (2 * p - 1)
        cy = self.image.height / 2 + self.pan[1] * slack_y * (2 * p - 1)
        x0, y0 = cx - vis_w / 2, cy - vis_h / 2
        data = (1 / scale, 0.0, x0, 0.0, 1 / scale, y0)
        out = self.image.transform((self.out_w, self.out_h), Image.Transform.AFFINE, data,
                                   resample=Image.Resampling.BICUBIC)
        return np.asarray(out, dtype=np.uint8)
