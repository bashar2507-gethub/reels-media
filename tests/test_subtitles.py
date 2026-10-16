from app.caption_qa import check_caption_order
from app.subtitles import ACCENT, ANNOTATION, Layout, ass_time, build_ass, caption_text, clean, write_ass
from app.timeline import build_timeline


def test_ass_time_rounding():
    assert ass_time(0) == "0:00:00.00"
    assert ass_time(61.237) == "0:01:01.24"
    assert ass_time(3599.999) == "1:00:00.00"


def test_clean_removes_override_characters():
    assert clean("نص {خطير} \\N") == "نص خطير N"


def test_highlight_marks_only_the_active_word():
    text = caption_text(["أن", "هذا", "الحساب"], 1, [True, True, True])
    assert text.count(ACCENT) == 1 and text.index(ACCENT) < text.index("هذا")


def test_very_short_words_light_up_with_the_next_word():
    from app.timeline import Caption, Word
    from app.subtitles import highlight_groups
    caption = Caption([Word("في", 1.00, 1.03), Word("البداية", 1.03, 1.46), Word("قد", 1.50, 1.58),
                       Word("يصغر", 1.58, 1.82)])
    assert highlight_groups(caption) == [[0, 1], [2, 3]]


def test_annotations_use_their_own_colour():
    text = caption_text(["العجز", "(Calorie", "Deficit)"], 0, [True, False, False])
    assert text.count(ANNOTATION) == 2


def test_styles_request_automatic_base_direction(tmp_path, fake_tts, small_script):
    ass = build_ass(build_timeline(small_script, fake_tts, tmp_path))
    styles = [line for line in ass.splitlines() if line.startswith("Style:")]
    assert styles and all(line.endswith(",-1") for line in styles)


def test_rendered_captions_read_right_to_left(tmp_path, fake_tts, small_script):
    tl = build_timeline(small_script, fake_tts, tmp_path)
    result = check_caption_order(write_ass(tl, tmp_path / "ok.ass"), tl)
    assert result["checked"] >= 4 and result["passed"], result["failures"]


def test_caption_qa_catches_left_to_right_layout(tmp_path, fake_tts, small_script):
    tl = build_timeline(small_script, fake_tts, tmp_path)
    broken = write_ass(tl, tmp_path / "broken.ass", layout=Layout(encoding=1))
    assert not check_caption_order(broken, tl)["passed"]
