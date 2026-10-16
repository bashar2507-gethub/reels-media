"""Arabic captions as ASS, rendered by libass (HarfBuzz shaping + FriBidi ordering).

Text is kept in logical order; libass handles right-to-left layout, letter joining
and mixed English terms. Positions keep text clear of Instagram's top and bottom UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import SPEC, VideoSpec
from .timeline import Caption, Timeline

WHITE = "&H00FFFFFF&"
ACCENT = "&H004DC1FF&"      # amber  #FFC14D (ASS colours are BGR)
ANNOTATION = "&H00F2D27A&"  # cyan   #7AD2F2, on-screen terms the voice does not say
KEEP_PUNCT = "؟?!"
DROP_PUNCT = ".،,:؛;"


@dataclass(frozen=True)
class Layout:
    caption_font: str = "Cairo ExtraBold"
    caption_size: int = 112
    caption_y: int = 1250
    title_font: str = "Cairo Black"
    title_size: int = 150
    title_y: int = 900
    tag_font: str = "Cairo SemiBold"
    tag_size: int = 50
    side_margin: int = 110
    hold: float = 0.35  # keep a caption up this long if the next one is not there yet
    # libass only auto-detects right-to-left base direction when a style's Encoding is -1.
    # With the VSFilter default (1), colour-tagged word runs are laid out left to right and
    # Arabic captions come out in the wrong order. caption_qa checks this on every render.
    encoding: int = -1


def ass_time(seconds: float) -> str:
    cs = int(round(max(seconds, 0.0) * 100))
    h, rest = divmod(cs, 360000)
    m, rest = divmod(rest, 6000)
    s, cs = divmod(rest, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def clean(text: str) -> str:
    """Strip characters that ASS would read as override blocks or escapes."""
    return text.replace("{", "").replace("}", "").replace("\\", "").replace("\n", " ").strip()


MIN_HIGHLIGHT = 0.15  # seconds; shorter highlights flash by unread


def highlight_groups(caption: Caption, min_seconds: float = MIN_HIGHLIGHT) -> list[list[int]]:
    """Spoken words grouped so no highlight is shorter than min_seconds: a very short word
    (في، مع، قد) lights up together with the word after it."""
    spoken = [i for i, w in enumerate(caption.words) if w.spoken]
    groups, current = [], []
    for k, i in enumerate(spoken):
        current.append(i)
        if caption.words[i].end - caption.words[current[0]].start >= min_seconds or k == len(spoken) - 1:
            groups.append(current)
            current = []
    return groups


def caption_text(words: list[str], active: int | set[int] | None, spoken: list[bool]) -> str:
    lit = active if isinstance(active, set) else ({active} if active is not None else set())
    parts = []
    last = len(words) - 1
    for i, word in enumerate(words):
        word = clean(word)
        if i == last and word and word[-1] in DROP_PUNCT and word[-1] not in KEEP_PUNCT:
            word = word.rstrip(DROP_PUNCT)
        if not spoken[i]:
            parts.append("{\\c" + ANNOTATION + "}" + word + "{\\c" + WHITE + "}")
        elif i in lit:
            parts.append("{\\c" + ACCENT + "}" + word + "{\\c" + WHITE + "}")
        else:
            parts.append(word)
    return " ".join(parts)


def caption_events(caption: Caption, until: float, layout: Layout) -> list[str]:
    """One event per highlight group, so the words being said are lit as they are spoken."""
    texts = [w.text for w in caption.words]
    spoken = [w.spoken for w in caption.words]
    groups = highlight_groups(caption)
    events = []
    pos = f"\\an5\\pos({SPEC.width // 2},{layout.caption_y})"
    for n, group in enumerate(groups):
        start = caption.words[group[0]].start
        end = caption.words[groups[n + 1][0]].start if n + 1 < len(groups) else until
        fade = "\\fad(90,0)" if n == 0 else ""
        text = "{" + pos + fade + "}" + caption_text(texts, set(group), spoken)
        events.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{text}")
    return events


def build_ass(timeline: Timeline, layout: Layout = Layout(), spec: VideoSpec = SPEC, tag: str | None = None) -> str:
    m, enc = layout.side_margin, layout.encoding
    styles = "\n".join([
        f"Style: Caption,{layout.caption_font},{layout.caption_size},{WHITE},{WHITE},&H00101010&,&H96000000&,"
        f"0,0,0,0,100,100,0,0,1,7,2,5,{m},{m},0,{enc}",
        f"Style: Title,{layout.title_font},{layout.title_size},{WHITE},{WHITE},&H00101010&,&H96000000&,"
        f"0,0,0,0,100,100,0,0,1,9,3,5,{m - 20},{m - 20},0,{enc}",
        f"Style: Tag,{layout.tag_font},{layout.tag_size},&H40FFFFFF&,&H40FFFFFF&,&H80000000&,&HA0000000&,"
        f"0,0,0,0,100,100,0,0,1,2,0,9,60,60,0,{enc}",
    ])
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {spec.width}", f"PlayResY: {spec.height}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "YCbCr Matrix: None", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        styles, "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if tag:
        lines.append(f"Dialogue: 2,{ass_time(0)},{ass_time(timeline.duration)},Tag,,0,0,0,,"
                     f"{{\\an9\\pos({spec.width - 60},250)}}{clean(tag)}")
    sentences = timeline.sentences
    captions = [(s, c) for s in sentences if s.style != "title" for c in s.captions]
    for s in sentences:
        if s.style == "title":
            nxt = [x.start for x in sentences if x.start > s.start]
            end = min(nxt) if nxt else timeline.duration
            lines.append(f"Dialogue: 1,{ass_time(s.start)},{ass_time(end)},Title,,0,0,0,,"
                         f"{{\\an5\\pos({spec.width // 2},{layout.title_y})\\fad(150,120)}}{clean(s.show)}")
    for k, (_, caption) in enumerate(captions):
        next_start = captions[k + 1][1].start if k + 1 < len(captions) else timeline.duration
        until = min(next_start, caption.end + layout.hold) if next_start - caption.end > layout.hold else next_start
        lines.extend(caption_events(caption, until, layout))
    return "\n".join(lines) + "\n"


def write_ass(timeline: Timeline, path: Path, **kwargs) -> Path:
    path.write_text(build_ass(timeline, **kwargs), encoding="utf-8")
    return path
