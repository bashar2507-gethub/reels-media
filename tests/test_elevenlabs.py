"""ElevenLabs provider against the documented API shape, with the network replaced by a fake."""
import base64
import json
import subprocess

import pytest

from app.timeline import build_timeline_from_narration, narration_text
from app.tts import ElevenLabsError, ElevenLabsTTS, TTSError, words_from_alignment

KEY = "test-key-not-real"


def _mp3(tmp_path, seconds=1.2):
    path = tmp_path / "tone.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=220:sample_rate=44100:duration={seconds}", str(path)], check=True)
    return base64.b64encode(path.read_bytes()).decode()


def _alignment(text, start=0.1, end=1.1):
    step = (end - start) / len(text)
    return {"characters": list(text),
            "character_start_times_seconds": [start + i * step for i in range(len(text))],
            "character_end_times_seconds": [start + (i + 1) * step for i in range(len(text))]}


class FakeApi:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, url, headers, data, timeout):
        self.calls.append({"url": url, "headers": headers, "body": json.loads(data)})
        return self.replies.pop(0)


def _ok(tmp_path, text):
    return 200, json.dumps({"audio_base64": _mp3(tmp_path), "alignment": _alignment(text)}).encode()


def test_request_follows_the_documented_endpoint(tmp_path):
    api = FakeApi([_ok(tmp_path, "مرحبا بك")])
    tts = ElevenLabsTTS("voice123", api_key=KEY, transport=api)
    speech = tts.synthesize("مرحبا بك", tmp_path / "out.wav")
    call = api.calls[0]
    assert call["url"] == ("https://api.elevenlabs.io/v1/text-to-speech/voice123/with-timestamps"
                           "?output_format=mp3_44100_128")
    assert call["headers"]["xi-api-key"] == KEY
    assert call["body"]["model_id"] == "eleven_v4" and call["body"]["language_code"] == "ar"
    assert call["body"]["voice_settings"] == {"stability": 0.45, "similarity_boost": 0.75, "style": 0.0,
                                              "use_speaker_boost": True, "speed": 0.95}
    assert speech.timing == "exact" and [w for w, _, _ in speech.words] == ["مرحبا", "بك"]
    assert all(0 <= s <= e <= speech.duration for _, s, e in speech.words)


def test_rate_limit_is_retried_with_backoff(tmp_path):
    waits = []
    api = FakeApi([(429, b'{"detail": {"status": "too_many_concurrent_requests"}}'), _ok(tmp_path, "نص")])
    ElevenLabsTTS("v", api_key=KEY, transport=api, sleep=waits.append).synthesize("نص", tmp_path / "o.wav")
    assert len(api.calls) == 2 and waits == [1.0]


def test_plan_and_auth_errors_stop_without_retry_or_leaking_the_key(tmp_path):
    body = json.dumps({"detail": {"status": "detected_unusual_activity",
                                  "message": f"Free Tier access has been disabled {KEY}"}}).encode()
    api = FakeApi([(401, body)])
    with pytest.raises(ElevenLabsError) as err:
        ElevenLabsTTS("v", api_key=KEY, transport=api, sleep=lambda s: None).synthesize("نص", tmp_path / "o.wav")
    assert len(api.calls) == 1 and not err.value.transient
    assert KEY not in str(err.value) and "Free Tier" in str(err.value)


def test_missing_key_is_refused(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(TTSError):
        ElevenLabsTTS("v")


def test_alignment_groups_characters_into_words():
    words = words_from_alignment(_alignment("أ ب\n\nج"))
    assert [w for w, _, _ in words] == ["أ", "ب", "ج"]


def test_timeline_cuts_sentences_from_one_narration(tmp_path, small_script):
    text = narration_text(small_script)
    api = FakeApi([(200, json.dumps({"audio_base64": _mp3(tmp_path, 6.0),
                                     "alignment": _alignment(text, 0.2, 5.8)}).encode())])
    tl = build_timeline_from_narration(small_script, ElevenLabsTTS("v", api_key=KEY, transport=api), tmp_path)
    assert len(api.calls) == 1 and tl.timing == "exact"
    sentences = tl.sentences
    assert all(a.end <= b.start for a, b in zip(sentences, sentences[1:]))
    assert tl.scenes[0].start == 0.0 and tl.scenes[-1].end == tl.duration
    term = sentences[-1].captions[-1].words
    assert [w.spoken for w in term] == [True, True, False, False]  # "(Calorie Deficit)" is shown, not said
