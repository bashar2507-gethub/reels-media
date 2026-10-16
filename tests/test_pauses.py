import numpy as np

from app.timeline import align_to_script, insert_pauses, timeline_from_speech
from app.tts import Speech, write_wav

RATE = 16000


def _bursts(spans, total):
    """Tone where words are spoken, true silence elsewhere."""
    x = np.zeros(int(total * RATE))
    for s, e in spans:
        t = np.arange(int(s * RATE), int(e * RATE))
        x[t] = 0.4 * 32767 * np.sin(2 * np.pi * 200 * t / RATE)
    return x.astype(np.int16)


def test_alignment_survives_a_missing_and_an_extra_word():
    heard = [("جسمك", 0.0, 0.3), ("يخسر", 0.35, 0.6), ("[pause]", 0.6, 0.7), ("طاقة", 1.0, 1.3)]
    out = align_to_script(["جسمك", "يخسر", "الدهون", "طاقة"], heard, min_match=0.7)
    assert [w for w, _, _ in out] == ["جسمك", "يخسر", "الدهون", "طاقة"]
    assert out[1][2] <= out[2][1] < out[2][2] <= out[3][1]


def test_pauses_land_in_silence_and_shift_later_words():
    words = [("a", 0.10, 0.40), ("b", 0.45, 0.80), ("c", 0.85, 1.20)]
    audio = _bursts([(s, e) for _, s, e in words], 1.4)
    out, moved = insert_pauses(audio, RATE, words, {0: 0.5, 1: 0.25})
    assert abs(out.size / RATE - (audio.size / RATE + 0.75)) < 0.002
    assert moved[0][1] == 0.10 and abs(moved[1][1] - 0.95) < 1e-9 and abs(moved[2][1] - 1.60) < 1e-9
    gap = out[int(0.42 * RATE): int(0.42 * RATE) + int(0.45 * RATE)]
    assert np.abs(gap).max() < 200  # the inserted pause is silent


def test_timeline_from_recorded_narration_adds_scene_and_sentence_pauses(tmp_path, small_script):
    say = [w for sc in small_script["scenes"] for s in sc["sentences"] for w in s["say"].split()]
    spans, t = [], 0.1
    for w in say:
        spans.append((w, t, t + 0.3))
        t += 0.32
    path = tmp_path / "narr.wav"
    write_wav(path, _bursts([(s, e) for _, s, e in spans], t + 0.2), RATE)
    speech = Speech(path, RATE, t + 0.2, "exact", spans)
    tl = timeline_from_speech(small_script, speech, tmp_path / "w", sentence_gap=0.4, scene_gap=0.7)
    first, second, third = tl.sentences
    assert second.start - first.end > 0.7 and third.start - second.end > 0.4
    assert tl.scenes[1].start > first.end and tl.timing == "exact"
