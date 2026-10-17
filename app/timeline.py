"""Turn a Reel script into a timed plan: voice track, scenes, and caption words."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from .tts import TTSProvider, read_wav, write_wav

_PUNCT = "؟?!.,،:؛;()[]\"'«»…-–—"
_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")


def normalize(word: str) -> str:
    """Comparable form of a word: no diacritics, tatweel or punctuation."""
    word = _TASHKEEL.sub("", unicodedata.normalize("NFC", word)).replace("ـ", "")
    return word.strip(_PUNCT).lower()


def letter_weight(word: str) -> int:
    return max(1, sum(ch.isalnum() for ch in word))


@dataclass
class Word:
    text: str
    start: float
    end: float
    spoken: bool = True  # False = on-screen annotation the voice does not say


@dataclass
class Caption:
    words: list[Word]

    @property
    def start(self) -> float:
        return min(w.start for w in self.words if w.spoken)

    @property
    def end(self) -> float:
        return max(w.end for w in self.words if w.spoken)


@dataclass
class Sentence:
    say: str
    show: str
    style: str
    start: float
    end: float
    captions: list[Caption] = field(default_factory=list)
    overlay: dict | None = None  # {"big": "70 × 1.6 = 112", "small": "...", "from": "<spoken word>"}


@dataclass
class Scene:
    id: str
    visual: str
    zoom: tuple[float, float]
    pan: tuple[float, float]
    sentences: list[Sentence]
    start: float = 0.0
    end: float = 0.0


@dataclass
class Timeline:
    scenes: list[Scene]
    duration: float
    voice_path: Path
    timing: str

    @property
    def sentences(self) -> list[Sentence]:
        return [s for scene in self.scenes for s in scene.sentences]


# Words a caption line should not end on (particles, conjunctions, demonstratives).
NO_BREAK_AFTER = {
    "في", "من", "على", "إلى", "عن", "مع", "أن", "إن", "قد", "لا", "لم", "لن", "ما", "و", "أو", "ثم",
    "كل", "هذا", "هذه", "ذلك", "الذي", "التي", "عند", "عندما", "كلما", "لكن", "بل", "حتى", "إذا", "لو", "أي",
}
CLAUSE_END = "،,:؛;.؟?!"


def _chunk_cost(words: list[str], total_words: int) -> float:
    chars = len(" ".join(words))
    cost = 100.0 + 0.5 * (chars - 16) ** 2
    last = words[-1]
    if len(words) == 1 and total_words > 1:
        cost += 300
    if normalize(last) in NO_BREAK_AFTER:
        cost += 250
    if last[-1] in CLAUSE_END:
        cost -= 80
    cost += 120 * sum(1 for w in words[:-1] if w[-1] in CLAUSE_END)
    return cost


def split_chunks(show: str, max_words: int = 4, max_chars: int = 24) -> list[list[str]]:
    """Caption chunks: explicit '|' breaks win; otherwise the cheapest split that keeps
    chunks balanced, breaks at clause punctuation and avoids orphans and dangling particles."""
    if "|" in show:
        return [part.split() for part in show.split("|") if part.strip()]
    words = show.split()
    n = len(words)
    if n == 0:
        return []
    best: list[float] = [0.0] + [float("inf")] * n
    back = [0] * (n + 1)
    for end in range(1, n + 1):
        for start in range(max(0, end - max_words), end):
            piece = words[start:end]
            if len(piece) > 1 and len(" ".join(piece)) > max_chars:
                continue
            cost = best[start] + _chunk_cost(piece, n)
            if cost < best[end]:
                best[end], back[end] = cost, start
    chunks, end = [], n
    while end > 0:
        chunks.append(words[back[end]:end])
        end = back[end]
    return chunks[::-1]


def time_words(say: str, show: str, start: float, end: float) -> list[list[Word]]:
    """Spread the sentence time over spoken words by letter count; annotations get no time."""
    spoken_forms = {normalize(w) for w in say.split()}
    chunks = split_chunks(show)
    flat = [w for chunk in chunks for w in chunk]
    spoken_flags = [normalize(w) in spoken_forms and normalize(w) != "" for w in flat]
    total = sum(letter_weight(w) for w, s in zip(flat, spoken_flags) if s) or 1
    cursor, index, timed = start, 0, []
    for chunk in chunks:
        row = []
        for text in chunk:
            spoken = spoken_flags[index]
            index += 1
            if spoken:
                span = (end - start) * letter_weight(text) / total
                row.append(Word(text, cursor, cursor + span, True))
                cursor += span
            else:
                row.append(Word(text, cursor, cursor, False))
        timed.append(row)
    return timed


def build_timeline(
    script: dict,
    tts: TTSProvider,
    workdir: Path,
    sentence_gap: float = 0.18,
    scene_gap: float = 0.32,
    lead_in: float = 0.15,
    tail: float = 0.6,
) -> Timeline:
    workdir.mkdir(parents=True, exist_ok=True)
    cursor, rate, timing = lead_in, None, "exact"
    clips: list[tuple[float, np.ndarray]] = []
    scenes: list[Scene] = []
    for scene_data in script["scenes"]:
        sentences = []
        for index, item in enumerate(scene_data["sentences"]):
            speech = tts.synthesize(item["say"], workdir / f"{scene_data['id']}_{index}.wav")
            samples, sample_rate = read_wav(speech.path)
            rate = rate or sample_rate
            if sample_rate != rate:
                raise ValueError("TTS returned mixed sample rates")
            if speech.timing != "exact":
                timing = "estimated"
            start, end = cursor, cursor + speech.duration
            sentence = Sentence(item["say"], item.get("show", item["say"]), item.get("style", "caption"), start, end)
            sentence.captions = [Caption(row) for row in time_words(sentence.say, sentence.show, start, end)]
            sentence.overlay = item.get("overlay")
            sentences.append(sentence)
            clips.append((start, samples))
            cursor = end + sentence_gap
        cursor += scene_gap - sentence_gap
        scenes.append(Scene(
            id=scene_data["id"], visual=scene_data["visual"],
            zoom=tuple(scene_data.get("zoom", (1.0, 1.08))), pan=tuple(scene_data.get("pan", (0.0, 0.0))),
            sentences=sentences,
        ))
    duration = round(scenes[-1].sentences[-1].end + tail, 3)
    for i, scene in enumerate(scenes):
        scene.start = 0.0 if i == 0 else round(scene.sentences[0].start - scene_gap / 2, 3)
    for i, scene in enumerate(scenes):
        scene.end = scenes[i + 1].start if i + 1 < len(scenes) else duration

    track = np.zeros(int(round(duration * rate)), dtype=np.int16)
    for start, samples in clips:
        at = int(round(start * rate))
        piece = samples[: max(0, track.size - at)]
        track[at: at + piece.size] = piece
    voice_path = workdir / "voice.wav"
    write_wav(voice_path, track, rate)
    return Timeline(scenes, duration, voice_path, timing)


def narration_text(script: dict) -> str:
    """The whole voice-over as one text: sentences joined by spaces, scenes by a paragraph break."""
    return "\n\n".join(" ".join(s["say"] for s in scene["sentences"]) for scene in script["scenes"])


def exact_words(say: str, show: str, spoken: list[tuple[str, float, float]],
                start: float, end: float) -> list[list[Word]]:
    """Caption words timed from the provider's word timings; estimates if they cannot be matched."""
    said = {normalize(w) for w in say.split()} - {""}
    queue = [(normalize(w), s, e) for w, s, e in spoken]
    rows, cursor, at = [], 0, start
    for chunk in split_chunks(show):
        row = []
        for text in chunk:
            key = normalize(text)
            if key not in said:
                row.append(Word(text, at, at, False))
                continue
            hit = next((k for k in range(cursor, len(queue)) if queue[k][0] == key), None)
            if hit is None:
                return time_words(say, show, start, end)
            row.append(Word(text, queue[hit][1], queue[hit][2], True))
            cursor, at = hit + 1, queue[hit][2]
        rows.append(row)
    return rows


def align_to_script(script_words: list[str], heard: list[tuple[str, float, float]],
                    min_match: float = 0.8) -> list[tuple[str, float, float]]:
    """Give every script word a time from heard words (provider alignment or a transcript).
    Words are matched on their normalised form; unmatched script words share the time between
    their matched neighbours. Fails when too little matches, rather than guessing."""
    a = [normalize(w) for w in script_words]
    b = [normalize(w) for w, _, _ in heard]
    times: list[tuple[float, float] | None] = [None] * len(a)
    for block in SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            times[block.a + k] = (heard[block.b + k][1], heard[block.b + k][2])
    matched = sum(t is not None for t in times)
    if not a or matched < min_match * len(a):
        raise ValueError(f"only {matched} of {len(a)} script words were found in the timing data")
    i = 0
    while i < len(a):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(a) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else (times[j][0] if j < len(a) else 0.0)
        hi = times[j][0] if j < len(a) else lo
        step = (hi - lo) / (j - i)
        for k in range(i, j):
            times[k] = (lo + (k - i) * step, lo + (k - i + 1) * step)
        i = j
    return [(w, s, e) for w, (s, e) in zip(script_words, times)]


def _quietest_point(samples: np.ndarray, rate: int, lo: float, hi: float) -> float:
    """Time of the lowest-energy 10 ms frame in [lo, hi] (where a cut is inaudible)."""
    hop = int(0.01 * rate)
    a, b = max(int(lo * rate), 0), min(int(hi * rate), samples.size)
    if b - a < 2 * hop:
        return (lo + hi) / 2
    frames = samples[a: a + (b - a) // hop * hop].astype(np.float64).reshape(-1, hop)
    best = int(np.argmin((frames ** 2).mean(axis=1)))
    return (a + best * hop + hop / 2) / rate


def insert_pauses(samples: np.ndarray, rate: int, words: list[tuple[str, float, float]],
                  gaps: dict[int, float], fade_out: float = 0.03, fade_in: float = 0.015):
    """Lengthen the silence after word i by gaps[i] seconds, cutting at the quietest point
    between that word and the next. The voice itself is not stretched or re-timed; the last
    word's tail fades into the pause and the next word fades in, so no edit is audible."""
    cuts = []
    for i in sorted(k for k, g in gaps.items() if g > 0 and k + 1 < len(words)):
        lo = max(words[i][2] - 0.2, words[i][1] + 0.05)
        hi = min(words[i + 1][1] + 0.08, words[i + 1][2] - 0.05)
        cuts.append((i, _quietest_point(samples, rate, lo, max(hi, lo)), gaps[i]))
    n_out, n_in = max(1, int(fade_out * rate)), max(1, int(fade_in * rate))
    pieces, shifts, start, added = [], [], 0, 0.0
    for i, t, gap in cuts:
        at = int(round(t * rate))
        piece = samples[start:at].astype(np.float64)
        if piece.size > n_out:
            piece[-n_out:] *= np.linspace(1.0, 0.0, n_out)
        if start and piece.size > n_in:
            piece[:n_in] *= np.linspace(0.0, 1.0, n_in)
        pieces += [piece, np.zeros(int(round(gap * rate)))]
        shifts.append((i, added))
        added += gap
        start = at
    tail = samples[start:].astype(np.float64)
    if cuts and tail.size > n_in:
        tail[:n_in] *= np.linspace(0.0, 1.0, n_in)
    pieces.append(tail)
    out = np.concatenate(pieces).round().astype(np.int16) if pieces else samples

    def shift_for(index: int) -> float:
        total = 0.0
        for last_index, before in shifts:
            if index > last_index:
                total = before + gaps[last_index]
        return total

    moved = [(w, s + shift_for(k), e + shift_for(k)) for k, (w, s, e) in enumerate(words)]
    return out, moved


def build_timeline_from_narration(script: dict, tts: TTSProvider, workdir: Path, lead_in: float = 0.15,
                                  tail: float = 0.6, sentence_gap: float = 0.0, scene_gap: float = 0.0) -> Timeline:
    """One request for the whole voice-over, so intonation flows across sentences;
    sentence, scene and caption timings are cut from the provider's word timings."""
    workdir.mkdir(parents=True, exist_ok=True)
    speech = tts.synthesize(narration_text(script), workdir / "narration.wav")
    return timeline_from_speech(script, speech, workdir, lead_in, tail, sentence_gap, scene_gap)


def timeline_from_speech(script: dict, speech, workdir: Path, lead_in: float = 0.15, tail: float = 0.6,
                         sentence_gap: float = 0.0, scene_gap: float = 0.0) -> Timeline:
    """Timeline from one recorded narration plus its word timings. sentence_gap and scene_gap
    add silence at sentence and scene boundaries for a natural rhythm (seconds, 0 = keep as is)."""
    if not speech.words:
        raise ValueError("the narration has no word timings")
    workdir.mkdir(parents=True, exist_ok=True)
    script_words = [w for scene in script["scenes"] for s in scene["sentences"] for w in s["say"].split()]
    aligned = align_to_script(script_words, speech.words)
    gaps, index = {}, -1
    for n, scene_data in enumerate(script["scenes"]):
        for m, item in enumerate(scene_data["sentences"]):
            index += len(item["say"].split())
            last_in_scene = m == len(scene_data["sentences"]) - 1
            gaps[index] = scene_gap if last_in_scene else sentence_gap
    samples, rate = read_wav(speech.path)
    samples, aligned = insert_pauses(samples, rate, aligned, gaps)
    words = [(w, lead_in + s, lead_in + e) for w, s, e in aligned]
    speech_seconds = samples.size / rate
    pointer, scenes = 0, []
    for scene_data in script["scenes"]:
        sentences = []
        for item in scene_data["sentences"]:
            count = len(item["say"].split())
            span = words[pointer: pointer + count]
            if len(span) < count:
                raise ValueError("the voice-over's word timings do not cover the whole script")
            pointer += count
            sentence = Sentence(item["say"], item.get("show", item["say"]), item.get("style", "caption"),
                                span[0][1], span[-1][2])
            sentence.captions = [Caption(row) for row in exact_words(sentence.say, sentence.show, span,
                                                                    sentence.start, sentence.end)]
            sentence.overlay = item.get("overlay")
            sentences.append(sentence)
        scenes.append(Scene(
            id=scene_data["id"], visual=scene_data["visual"],
            zoom=tuple(scene_data.get("zoom", (1.0, 1.08))), pan=tuple(scene_data.get("pan", (0.0, 0.0))),
            sentences=sentences,
        ))
    duration = round(max(lead_in + speech_seconds, scenes[-1].sentences[-1].end) + tail, 3)
    for i, scene in enumerate(scenes):
        scene.start = 0.0 if i == 0 else round((scenes[i - 1].sentences[-1].end + scene.sentences[0].start) / 2, 3)
    for i, scene in enumerate(scenes):
        scene.end = scenes[i + 1].start if i + 1 < len(scenes) else duration
    track = np.zeros(int(round(duration * rate)), dtype=np.int16)
    at = int(round(lead_in * rate))
    piece = samples[: max(0, track.size - at)]
    track[at: at + piece.size] = piece
    voice_path = workdir / "voice.wav"
    write_wav(voice_path, track, rate)
    return Timeline(scenes, duration, voice_path, speech.timing)
