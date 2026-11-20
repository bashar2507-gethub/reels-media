import numpy as np

from app import dialogue


def test_spoken_text_drops_tags_and_ellipses():
    assert dialogue.spoken_text("[flatly] [quickly] هذا مقطع... كامل.") == "هذا مقطع كامل."


def test_spread_words_is_proportional_and_ordered():
    words = dialogue.spread_words("abcd abcdefgh", 1.0, 2.2)
    assert [w["text"] for w in words] == ["abcd", "abcdefgh"]
    assert words[0]["start"] == 1.0
    assert abs(words[1]["start"] - 1.4) < 1e-6  # 4 of 12 letters
    assert words[0]["end"] < words[1]["start"] and words[1]["end"] <= 2.2


def test_voiced_span_trims_silence():
    rate = dialogue.RATE
    clip = np.zeros(rate * 2, dtype=np.float32)
    clip[rate // 2: rate] = 0.3
    a, b = dialogue.voiced_span(clip, pad=0.0)
    assert abs(a / rate - 0.5) < 0.03 and abs(b / rate - 1.0) < 0.03


def test_short_words_get_a_minimum_share():
    words = dialogue.spread_words("في abcdef", 0.0, 1.0)
    assert words[0]["end"] - words[0]["start"] >= 0.3
