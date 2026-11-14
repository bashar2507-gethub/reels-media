import subprocess
from types import SimpleNamespace as NS

import pytest

from app import intro


def _word(start, end):
    return NS(text="x", start=start, end=end)


def test_hook_end_falls_between_the_hook_and_the_next_sentence():
    first = NS(captions=[NS(words=[_word(0.15, 0.5), _word(0.6, 3.27)])], end=3.27)
    second = NS(captions=[NS(words=[_word(3.35, 3.5)])], start=3.35)
    assert intro.hook_end(NS(sentences=[first, second])) == pytest.approx(3.31)


@pytest.mark.skipif(not intro.INTRO.exists(), reason="intro asset missing")
def test_hook_first_keeps_the_same_length_as_the_intro_at_the_start(tmp_path):
    main = tmp_path / "main.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=c=teal:s=1080x1920:r=30:d=6",
                    "-f", "lavfi", "-i", "sine=f=220:d=6:sample_rate=48000",
                    "-ac", "2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(main)],
                   check=True)
    out = tmp_path / "out.mp4"
    intro.insert_after(main, out, 2.0, "flash")
    assert intro.duration(out) == pytest.approx(intro.duration(main) + intro.offset(), abs=0.1)
