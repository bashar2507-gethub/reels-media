from pathlib import Path

import numpy as np
import pytest

from app.tts import Speech, write_wav


class FakeTTS:
    """Deterministic tone instead of speech: 60 ms per character, exact timing."""

    name = "fake"

    def synthesize(self, text: str, out_path: Path) -> Speech:
        rate = 22050
        t = np.arange(int(0.06 * len(text) * rate)) / rate
        write_wav(out_path, (0.3 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16), rate)
        return Speech(Path(out_path), rate, t.size / rate, "exact")


@pytest.fixture
def fake_tts() -> FakeTTS:
    return FakeTTS()


@pytest.fixture
def small_script() -> dict:
    return {
        "scenes": [
            {"id": "a", "visual": "scale", "sentences": [{"say": "لماذا يتوقف وزنك؟", "style": "title"}]},
            {"id": "b", "visual": "orbs", "sentences": [
                {"say": "جسمك يخسر الدهون عندما يصرف طاقة أكثر مما يأكل."},
                {"say": "وهذا ما يسمى العجز الحراري.", "show": "وهذا ما يسمى | العجز الحراري (Calorie Deficit)"},
            ]},
        ]
    }
