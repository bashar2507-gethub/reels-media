"""PoC-1: build one test Reel and run the Media Gate. Nothing is uploaded, scheduled or published.

    python scripts/run_poc1.py                          # offline: espeak-ng placeholder voice
    python scripts/run_poc1.py --tts elevenlabs --estimate-only   # characters and credits, no API call
    python scripts/run_poc1.py --tts elevenlabs         # needs ELEVENLABS_API_KEY (paid plan)

The voice is never sped up to hit a target length: the length follows natural narration,
and a Reel outside 25-30 s is reported as a warning.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audio_metrics import ARABIC_RATE_WPM, analyse  # noqa: E402
from app.caption_qa import check_caption_order  # noqa: E402
from app.config import CONTENT_DIR, ELEVENLABS_VOICE_ID, OUTPUT_DIR, SPEC  # noqa: E402
from app.images import scene_images  # noqa: E402
from app.subtitles import write_ass  # noqa: E402
from app.timeline import (build_timeline, build_timeline_from_narration, narration_text,  # noqa: E402
                          timeline_from_speech)
from app.tts import ElevenLabsTTS, EspeakTTS, TTSError, estimated_credits, speech_from_recording  # noqa: E402
from app.validation import validate_reel  # noqa: E402
from app.video_assembler import assemble, extract_cover  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, default=CONTENT_DIR / "poc1.json")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR / "poc1")
    parser.add_argument("--tts", choices=["espeak", "elevenlabs"], default="espeak")
    # espeak-ng's -s value does not map to Arabic words: -s 150 measured 99 wpm and -s 236 measured 147 wpm
    # (narration pace), so 210 is interpolated to land near 135. Placeholder only.
    parser.add_argument("--wpm", type=int, default=210, help="espeak-ng -s value (placeholder voice only)")
    parser.add_argument("--voice-id", default=os.environ.get("ELEVENLABS_VOICE_ID", ELEVENLABS_VOICE_ID))
    parser.add_argument("--model", default=os.environ.get("ELEVENLABS_MODEL_ID", "eleven_v4"))
    parser.add_argument("--speed", type=float, default=0.95)
    parser.add_argument("--stability", type=float, default=0.45)
    parser.add_argument("--similarity", type=float, default=0.75)
    parser.add_argument("--style", type=float, default=0.0)
    parser.add_argument("--estimate-only", action="store_true", help="print characters and credits, call nothing")
    parser.add_argument("--narration", type=Path,
                        help="words JSON of a narration already generated (its 'audio' file sits next to it)")
    parser.add_argument("--sentence-gap", type=float, default=0.40, help="extra pause between sentences (s)")
    parser.add_argument("--scene-gap", type=float, default=0.70, help="extra pause between scenes (s)")
    parser.add_argument("--release", action="store_true",
                        help="publishing build: no on-screen test label (everything else identical)")
    parser.add_argument("--visuals", choices=["procedural", "auto", "ai"], default="procedural",
                        help="scene images: procedural only, AI with procedural fallback (auto), or AI only")
    args = parser.parse_args()

    script = json.loads(args.script.read_text(encoding="utf-8"))
    text = narration_text(script)
    if args.tts == "elevenlabs" and args.estimate_only:
        print(f"narration: {len(text)} characters, about {estimated_credits(text)} credits per take "
              f"({args.model}, voice {args.voice_id})")
        return 0

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    visuals, image_report = scene_images(script["scenes"], out / "visuals",
                                         token=os.environ.get("HF_TOKEN"), mode=args.visuals)
    gaps = {"sentence_gap": args.sentence_gap, "scene_gap": args.scene_gap}
    if args.narration:
        meta = json.loads(args.narration.read_text(encoding="utf-8"))
        (out / "audio").mkdir(parents=True, exist_ok=True)
        speech = speech_from_recording(args.narration.parent / meta["audio"], meta["words"], out / "audio" / "narration.wav")
        timeline = timeline_from_speech(script, speech, out / "audio", **gaps)
        voice_label = f"ElevenLabs {meta.get('model_id')} · {meta.get('voice')} ({meta.get('voice_id')})"
        tag = "PoC-1 · خلفيات مؤقتة للاختبار"
    elif args.tts == "elevenlabs":
        try:
            tts = ElevenLabsTTS(args.voice_id, args.model, stability=args.stability, similarity_boost=args.similarity,
                                style=args.style, speed=args.speed)
            timeline = build_timeline_from_narration(script, tts, out / "audio", **gaps)
        except TTSError as err:
            print(f"STOPPED at text-to-speech: {err}")
            return 2
        voice_label, tag = f"ElevenLabs {args.model} · voice {args.voice_id}", "PoC-1 · خلفيات مؤقتة للاختبار"
    else:
        timeline = build_timeline(script, EspeakTTS("ar", args.wpm), out / "audio")
        voice_label, tag = "espeak-ng placeholder", "PoC-1 · خلفيات وصوت مؤقتان للاختبار"

    if args.release:
        tag = None
    voice = analyse(timeline.voice_path, " ".join(s.say for s in timeline.sentences))
    ass_path = write_ass(timeline, out / "captions.ass", tag=tag)
    (out / "timeline.json").write_text(json.dumps(
        {"duration": timeline.duration, "timing": timeline.timing, "voice": voice_label, "voice_metrics": voice.as_dict(),
         "scenes": [asdict(s) for s in timeline.scenes]}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    started = time.time()
    video = assemble(timeline, visuals, ass_path, out / f"{script['reel_id']}.mp4")
    render_seconds = time.time() - started
    cover = extract_cover(video, script.get("cover_at_seconds", 1.0), out / f"{script['reel_id']}_cover.jpg")

    report = validate_reel(video, SPEC)
    qa = check_caption_order(ass_path, timeline)
    low, high = ARABIC_RATE_WPM
    report["checks"] += [
        {"name": "captions_rtl_order", "passed": qa["passed"],
         "value": f"{qa['checked']} positions checked" + (f", {len(qa['failures'])} wrong" if qa["failures"] else ""),
         "limit": "highlight follows right-to-left reading", "source": "internal", "severity": "hard"},
        {"name": "speaking_rate", "passed": low <= voice.wpm_span <= high, "value": f"{voice.wpm_span:.0f} wpm",
         "limit": f"{low}-{high} Arabic words per minute", "source": "internal", "severity": "soft"},
    ]
    report["passed"] = report["passed"] and qa["passed"]
    report["warnings"] = [c["name"] for c in report["checks"] if c["severity"] == "soft" and not c["passed"]]
    report.update({"render_seconds": round(render_seconds, 1), "cover": str(cover), "voice": voice_label,
                   "voice_metrics": voice.as_dict(), "caption_failures": qa["failures"], "visuals": image_report})
    (out / "media_gate.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"video: {video}  ({timeline.duration:.2f} s, rendered in {render_seconds:.0f} s) | voice: {voice_label}")
    for c in report["checks"]:
        mark = "PASS" if c["passed"] else ("WARN" if c["severity"] == "soft" else "FAIL")
        print(f"  {mark:4} {c['name']:<22} {c['value']:<34} limit: {c['limit']} [{c['source']}]")
    print(f"visuals: {len(image_report['ai'])} AI, {len(image_report['fallback'])} procedural"
          + (f" (errors: {image_report['errors']})" if image_report["errors"] else ""))
    print("MEDIA GATE:", "PASSED" if report["passed"] else "FAILED", "| warnings:", report["warnings"] or "none")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
