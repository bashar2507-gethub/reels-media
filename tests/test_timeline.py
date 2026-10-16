from app.timeline import build_timeline, normalize, split_chunks, time_words
from app.tts import read_wav


def test_chunks_break_at_clauses_and_avoid_orphans():
    chunks = split_chunks("أحد الأسباب أن هذا الحساب يتغير: كلما نقص وزنك، قل ما يحرقه جسمك كل يوم.")
    assert all(len(c) >= 2 for c in chunks)
    assert all(len(c) <= 4 for c in chunks)
    assert ["كلما", "نقص", "وزنك،"] in chunks
    assert not any(c[-1] in ("ما", "كل", "هذا", "قد") for c in chunks)


def test_explicit_breaks_win():
    assert split_chunks("وهذا ما يسمى | العجز الحراري (Calorie Deficit)") == [
        ["وهذا", "ما", "يسمى"], ["العجز", "الحراري", "(Calorie", "Deficit)"]]


def test_annotation_words_get_no_time():
    rows = time_words("وهذا ما يسمى العجز الحراري.", "وهذا ما يسمى | العجز الحراري (Calorie Deficit)", 1.0, 3.0)
    words = [w for row in rows for w in row]
    spoken = [w for w in words if w.spoken]
    assert [w.text for w in words if not w.spoken] == ["(Calorie", "Deficit)"]
    assert spoken[0].start == 1.0 and abs(spoken[-1].end - 3.0) < 1e-9
    assert all(a.end <= b.start + 1e-9 for a, b in zip(spoken, spoken[1:]))


def test_normalize_strips_diacritics_and_punctuation():
    assert normalize("بروتينًا،") == "بروتينا"


def test_timeline_covers_whole_duration(tmp_path, fake_tts, small_script):
    tl = build_timeline(small_script, fake_tts, tmp_path)
    assert tl.scenes[0].start == 0.0 and tl.scenes[-1].end == tl.duration
    assert all(a.end == b.start for a, b in zip(tl.scenes, tl.scenes[1:]))
    starts = [s.start for s in tl.sentences]
    assert starts == sorted(starts)
    samples, rate = read_wav(tl.voice_path)
    assert abs(samples.size / rate - tl.duration) < 0.01
