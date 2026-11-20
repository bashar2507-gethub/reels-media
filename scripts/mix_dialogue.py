"""Mix a dialogue Reel's takes into content/audio/<id>_narration.mp3 and _narration_words.json.

    python scripts/mix_dialogue.py --spec content/<id>_dialogue.json

The spec lists the lines in order (speaker, take file, text as generated), the gaps, and the
sound effects; see app/dialogue.py. The takes are used as generated: no speed change.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import dialogue  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    spec = json.loads((ROOT / parser.parse_args().spec).read_text(encoding="utf-8"))
    rid = spec["reel_id"]
    folder = ROOT / spec["folder"]
    lines = []
    for line in spec["lines"]:
        lines.append({**line, "audio": folder / line["file"]})
    sfx = {name: folder / f for name, f in spec["sfx"].items()}
    bed = folder / spec["bed"]["file"] if spec.get("bed") else None
    out = ROOT / "content" / "audio" / f"{rid}_narration.mp3"
    words, total = dialogue.mix(lines, sfx, bed, out, bed_gain_db=spec.get("bed", {}).get("gain_db", 0.0))
    meta = {k: spec[k] for k in ("voices", "model_id", "language_code", "generated_on", "credits", "note") if k in spec}
    meta.update({"timing_source": "letter-count spread over each take's voiced span (app/dialogue.py)",
                 "duration_s": total, "words": words, "audio": out.name})
    (ROOT / "content" / "audio" / f"{rid}_narration_words.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {total:.2f} s, {len(words)} words, {60 * len(words) / total:.0f} wpm overall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
