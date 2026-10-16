"""Text-to-speech layer.

Every provider returns a trimmed mono WAV plus how its timing was obtained, so the
rest of the pipeline never depends on one vendor.
  - ElevenLabsTTS: production voice over the official REST API, with exact word timings.
  - EspeakTTS: offline robotic placeholder for pipeline tests only; never publish it.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np


class TTSError(RuntimeError):
    """Raised when a provider cannot produce usable speech."""


@dataclass
class Speech:
    path: Path
    sample_rate: int
    duration: float
    timing: str  # "exact" (provider word boundaries) or "estimated"
    words: list[tuple[str, float, float]] | None = None  # (word, start, end) seconds from clip start


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, out_path: Path) -> Speech: ...


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise TTSError(f"{path}: expected 16-bit PCM")
        rate, channels = w.getframerate(), w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return data, rate


def write_wav(path: Path, samples: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.astype(np.int16).tobytes())


def trim_bounds(samples: np.ndarray, rate: int, threshold: float = 0.02, pad: float = 0.03) -> tuple[int, int]:
    """Sample range that keeps the speech plus a short pad, without leading or trailing silence."""
    if samples.size == 0:
        return 0, 0
    level = np.abs(samples.astype(np.float32)) / 32768.0
    loud = np.flatnonzero(level > threshold)
    if loud.size == 0:
        return 0, 0
    keep = int(pad * rate)
    return max(int(loud[0]) - keep, 0), min(int(loud[-1]) + keep + 1, samples.size)


def trim_silence(samples: np.ndarray, rate: int, threshold: float = 0.02, pad: float = 0.03) -> np.ndarray:
    """Cut leading and trailing silence, keeping a short pad around the speech."""
    start, end = trim_bounds(samples, rate, threshold, pad)
    return samples[start:end]


def decode_to_wav(source: Path, target: Path, rate: int = 44100) -> None:
    """Any audio file to mono 16-bit WAV, the format the timeline works with."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-ac", "1", "-ar", str(rate),
                           "-c:a", "pcm_s16le", str(target)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise TTSError(f"could not decode {source.name}: {proc.stderr.strip()[:200]}")


def words_from_alignment(alignment: dict) -> list[tuple[str, float, float]]:
    """Group ElevenLabs character timestamps into whitespace-separated words."""
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not (len(chars) == len(starts) == len(ends)):
        raise TTSError("alignment arrays have different lengths")
    words, current, first, last = [], [], 0.0, 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if current:
                words.append(("".join(current), first, last))
                current = []
            continue
        if not current:
            first = float(s)
        current.append(ch)
        last = float(e)
    if current:
        words.append(("".join(current), first, last))
    return words


def speech_from_recording(audio: Path, words: list[dict], out_wav: Path) -> Speech:
    """A narration made elsewhere (for example in ElevenLabs via the Claude connector) plus its
    word timings, ready for the timeline. Non-word entries such as audio events are skipped."""
    decode_to_wav(Path(audio), Path(out_wav))
    samples, rate = read_wav(Path(out_wav))
    timed = [(str(w["text"]), float(w["start"]), float(w["end"]))
             for w in words if w.get("type", "word") == "word"]
    if not timed:
        raise TTSError("the recording has no word timings")
    return Speech(Path(out_wav), rate, samples.size / rate, "exact", timed)


def estimated_credits(text: str) -> int:
    """ElevenLabs bills text-to-speech by characters; 1 credit per character was observed
    for eleven_v4 (294 characters = 294 credits). Other models may bill differently."""
    return len(text)


class ElevenLabsError(TTSError):
    def __init__(self, message: str, status: int | None, transient: bool) -> None:
        super().__init__(message)
        self.status = status
        self.transient = transient


Transport = Callable[[str, dict, bytes, float], tuple[int, bytes]]


class ElevenLabsTTS:
    """ElevenLabs text-to-speech with character timestamps (POST /v1/text-to-speech/{voice_id}/with-timestamps).

    The API key comes only from ELEVENLABS_API_KEY (or an explicit argument) and is never logged,
    written to disk or included in error messages. Only rate limits (429), server errors (5xx) and
    network failures are retried, with exponential backoff; authentication, plan and validation
    errors stop immediately.
    """

    name = "elevenlabs"
    ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"

    def __init__(self, voice_id: str, model_id: str = "eleven_v4", language_code: str | None = "ar",
                 stability: float = 0.45, similarity_boost: float = 0.75, style: float = 0.0,
                 speed: float = 0.95, use_speaker_boost: bool = True, output_format: str = "mp3_44100_128",
                 api_key: str | None = None, max_retries: int = 4, timeout: float = 120.0,
                 transport: Transport | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        key = api_key if api_key is not None else os.environ.get("ELEVENLABS_API_KEY", "")
        if not key:
            raise TTSError("ELEVENLABS_API_KEY is not set")
        if not voice_id:
            raise TTSError("an ElevenLabs voice_id is required")
        self._key = key
        self.voice_id, self.model_id, self.language_code = voice_id, model_id, language_code
        self.voice_settings = {"stability": stability, "similarity_boost": similarity_boost, "style": style,
                               "use_speaker_boost": use_speaker_boost, "speed": speed}
        self.output_format, self.max_retries, self.timeout = output_format, max_retries, timeout
        self._transport = transport or self._urllib_post
        self._sleep = sleep

    def request_body(self, text: str) -> dict:
        body = {"text": text, "model_id": self.model_id, "voice_settings": dict(self.voice_settings)}
        if self.language_code:
            body["language_code"] = self.language_code
        return body

    @staticmethod
    def _urllib_post(url: str, headers: dict, data: bytes, timeout: float) -> tuple[int, bytes]:
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()

    def _describe(self, status: int | None, body: bytes) -> str:
        message = body.decode("utf-8", errors="replace")[:300]
        try:
            detail = json.loads(body).get("detail")
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("status") or message
            elif detail:
                message = str(detail)[:300]
        except (ValueError, AttributeError):
            pass
        return f"ElevenLabs HTTP {status}: {message}".replace(self._key, "***")

    def _post(self, text: str) -> dict:
        url = (self.ENDPOINT.format(voice_id=urllib.parse.quote(self.voice_id, safe=""))
               + "?" + urllib.parse.urlencode({"output_format": self.output_format}))
        headers = {"xi-api-key": self._key, "Content-Type": "application/json", "Accept": "application/json"}
        data = json.dumps(self.request_body(text), ensure_ascii=False).encode("utf-8")
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                status, body = self._transport(url, headers, data, self.timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                status, body = None, str(err).encode()
            if status == 200:
                return json.loads(body)
            transient = status is None or status == 429 or status >= 500
            if not transient or attempt == self.max_retries:
                raise ElevenLabsError(self._describe(status, body), status, transient)
            self._sleep(delay)
            delay *= 2
        raise ElevenLabsError("unreachable", None, True)

    def synthesize(self, text: str, out_path: Path) -> Speech:
        out_path = Path(out_path)
        payload = self._post(text)
        if not payload.get("audio_base64") or not payload.get("alignment"):
            raise TTSError("ElevenLabs response is missing audio or alignment")
        encoded = out_path.with_suffix(".mp3")
        encoded.write_bytes(base64.b64decode(payload["audio_base64"]))
        decode_to_wav(encoded, out_path)
        samples, rate = read_wav(out_path)
        start, end = trim_bounds(samples, rate)
        if end <= start:
            raise TTSError("ElevenLabs returned silent audio")
        write_wav(out_path, samples[start:end], rate)
        offset, duration = start / rate, (end - start) / rate
        words = [(w, min(max(s - offset, 0.0), duration), min(max(e - offset, 0.0), duration))
                 for w, s, e in words_from_alignment(payload["alignment"])]
        return Speech(out_path, rate, duration, "exact", words)


class EspeakTTS:
    """Offline robotic voice from espeak-ng. Placeholder for tests; never publish it."""

    name = "espeak-ng"

    def __init__(self, voice: str = "ar", words_per_minute: int = 170) -> None:
        if shutil.which("espeak-ng") is None:
            raise TTSError("espeak-ng is not installed")
        self.voice = voice
        self.words_per_minute = words_per_minute

    def synthesize(self, text: str, out_path: Path) -> Speech:
        out_path = Path(out_path)
        raw = out_path.with_name(out_path.stem + ".raw.wav")
        proc = subprocess.run(
            ["espeak-ng", "-v", self.voice, "-s", str(self.words_per_minute), "-w", str(raw), text],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0 or not raw.exists():
            raise TTSError(f"espeak-ng failed: {proc.stderr.strip()}")
        samples, rate = read_wav(raw)
        raw.unlink()
        samples = trim_silence(samples, rate)
        if samples.size == 0:
            raise TTSError(f"espeak-ng produced silence for {text!r}")
        write_wav(out_path, samples, rate)
        return Speech(out_path, rate, samples.size / rate, timing="estimated")
