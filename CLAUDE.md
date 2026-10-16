# fitness-reels: notes for Claude

Read `docs/APPROVED_STEPS.md` (Arabic) before producing or publishing a Reel. It holds the steps and settings the account owner approved on 2026-10-16. Changing any of them needs his approval.

## Owner's rules

- Never ask for API keys or passwords in chat. Secrets live only in environment variables or GitHub Secrets and never appear in code, logs or reports.
- Publishing is off by default. Publish only with the owner's explicit approval, never create duplicate posts, and report success only after Metricool confirms it and the status is checked.
- Every health claim needs a verified source in `content/evidence/<reel_id>.json`. No exaggerated claims or guaranteed results.
- Use only media we have rights to (Cairo fonts under OFL, procedural visuals, licensed ElevenLabs voice on the paid plan).
- Never substitute the voice or model silently, never speed up or time-stretch narration, and keep originals for rollback.
- Don't spend credits beyond what is approved or change any plan.

## Facts

- Voice: ElevenLabs «عبدالله سعدون», voice_id `t9akNmCDhz230CEXOYmn`, model `eleven_v4`, language `ar`.
- Metricool brand id `7461887`, timezone Asia/Riyadh, Instagram @uuxuuoouuxuu. The Metricool connector only accepts media by public URL.
- Media hosting: public repo `bashar2507-gethub/reels-media` (Claude GitHub app installed on it only). Attach it with add_repo (push), clone it, then `python scripts/stage_media.py --repo <clone> --owner bashar2507-gethub --reel-id <id> --video ... --cover ...` commits, pushes and prints jsDelivr URLs pinned to the commit. Pass the video URL as `media` in createScheduledPost.
- Build a publishing version: `python scripts/run_poc1.py --narration content/audio/<id>_narration_words.json --out output/<id>_release --release`
- Tests: `python -m pytest`
