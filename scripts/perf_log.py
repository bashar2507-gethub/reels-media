"""Performance log: the data loop behind every Reel (owner, 2026-11-15).

    python scripts/perf_log.py --rows <rows.json> [--write]

<rows.json> holds the "rows" returned by Metricool's getAnalyticsDataByMetrics for these Instagram Reels
fields, in this order (the run saves the tool result to a file first):

    IGRE02 IGRE06 IGRE23 IGRE11 IGRE10 IGRE07 IGRE21 IGRE12 IGRE24 IGRE28 IGRE30
    published, url, views, reach, likes, comments, shares, saves, average watch time (s), view rate %, skip rate %

Each row is matched to its plan item through the item's Instagram link. With --write the numbers are kept in
content/analytics/instagram_reels.json (one entry per Reel, refreshed every run) and a comparison by topic
category, hook type, series and intro position goes to content/analytics/summary.json. Reels younger than
3 days are logged but left out of the comparison, because their numbers are still moving.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIELDS = ["IGRE02", "IGRE06", "IGRE23", "IGRE11", "IGRE10", "IGRE07", "IGRE21", "IGRE12", "IGRE24", "IGRE28", "IGRE30"]
KEYS = ["published", "url", "views", "reach", "likes", "comments", "shares", "saves",
        "avg_watch_s", "view_rate_pct", "skip_rate_pct"]
GROUPS = ["category", "hook_type", "series", "intro"]
MIN_AGE_DAYS = 3
LOG = ROOT / "content" / "analytics" / "instagram_reels.json"
SUMMARY = ROOT / "content" / "analytics" / "summary.json"


def norm_url(url: str | None) -> str:
    return (url or "").split("?")[0].rstrip("/").lower()


def number(value):
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def plan_items() -> list[dict]:
    plan = json.loads((ROOT / "content" / "plan.json").read_text(encoding="utf-8"))
    return plan["items"] if isinstance(plan, dict) else plan


def video_seconds(reel_id: str) -> float | None:
    status = ROOT / "reels" / reel_id / "status.json"
    try:
        video = ROOT / json.loads(status.read_text(encoding="utf-8"))["video"]
        from app.intro import duration
        return round(duration(video), 2)
    except Exception:  # an older Reel without a stored video, or no ffprobe: watch % is left out
        return None


def intro_position(reel_id: str, published: str) -> str:
    try:
        status = json.loads((ROOT / "reels" / reel_id / "status.json").read_text(encoding="utf-8"))
        if status.get("intro"):
            return status["intro"].get("position", "start")
    except Exception:
        pass
    return "start" if published >= "20261031" else "none"


def build_log(rows: list[list], now: datetime) -> dict:
    by_url = {norm_url((it.get("links") or {}).get("instagram")): it for it in plan_items()
              if (it.get("links") or {}).get("instagram")}
    log = {}
    for row in rows:
        rec = dict(zip(KEYS, row))
        item = by_url.get(norm_url(rec["url"]))
        if not item:
            continue
        for key in KEYS[2:]:
            rec[key] = number(rec[key])
        published = str(rec["published"])[:14]
        age = (now - datetime.strptime(published[:8], "%Y%m%d").replace(tzinfo=timezone.utc)).days
        reach = rec["reach"] or 0
        per_reach = (lambda n: round(100 * n / reach, 2) if reach and n is not None else None)
        seconds = video_seconds(item["id"])
        rec.update({
            "id": item["id"], "subject": item.get("subject"), "category": item.get("category", "unknown"),
            "hook_type": item.get("hook_type", "unknown"), "series": item.get("series", "none"),
            "intro": intro_position(item["id"], published), "age_days": age,
            "video_s": seconds,
            "watch_pct": round(100 * rec["avg_watch_s"] / seconds, 1) if seconds and rec["avg_watch_s"] else None,
            "likes_per_reach_pct": per_reach(rec["likes"]), "shares_per_reach_pct": per_reach(rec["shares"]),
            "saves_per_reach_pct": per_reach(rec["saves"]), "comments_per_reach_pct": per_reach(rec["comments"]),
            "fetched": now.strftime("%Y-%m-%d"),
        })
        log[item["id"]] = rec
    return log


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.fmean(values), 1) if values else None


def summarise(log: dict) -> dict:
    settled = [r for r in log.values() if r["age_days"] >= MIN_AGE_DAYS]
    summary = {"reels": len(settled), "overall": {}, "by": {}}
    metrics = ["skip_rate_pct", "avg_watch_s", "watch_pct", "views", "likes_per_reach_pct",
               "shares_per_reach_pct", "saves_per_reach_pct", "comments_per_reach_pct"]
    summary["overall"] = {m: mean(r[m] for r in settled) for m in metrics}
    for group in GROUPS:
        buckets: dict[str, list] = {}
        for r in settled:
            buckets.setdefault(str(r.get(group)), []).append(r)
        summary["by"][group] = {k: {"n": len(v), **{m: mean(r[m] for r in v) for m in metrics}}
                                for k, v in sorted(buckets.items())}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.rows.read_text(encoding="utf-8"))
    rows = data.get("rows", []) if isinstance(data, dict) else data
    now = datetime.now(timezone.utc)
    log = build_log(rows, now)
    if not log:
        print("no rows matched a published plan item (check the Instagram links in content/plan.json)")
        return 1
    summary = summarise(log)
    summary["generated"] = time.strftime("%Y-%m-%d")
    print(f"{len(log)} Reels logged, {summary['reels']} at least {MIN_AGE_DAYS} days old")
    print("overall:", summary["overall"])
    for group, buckets in summary["by"].items():
        print(f"\nby {group}:")
        for name, s in buckets.items():
            print(f"  {name:<14} n={s['n']:<2} skip={s['skip_rate_pct']}% watch={s['avg_watch_s']}s "
                  f"({s['watch_pct']}%) likes/reach={s['likes_per_reach_pct']}% shares/reach={s['shares_per_reach_pct']}%")
    if args.write:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        merged = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
        merged.update(log)
        LOG.write_text(json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {LOG.relative_to(ROOT)} and {SUMMARY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
