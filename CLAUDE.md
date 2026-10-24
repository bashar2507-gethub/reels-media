# reels-media: notes for Claude

This repository holds the whole Reels pipeline (code, scripts, evidence, plan) and the published
media under `reels/`. To produce and publish a Reel, follow `docs/RUNBOOK.md` step by step.
`docs/APPROVED_STEPS.md` (Arabic) records what the owner approved; changing any of it needs his approval.

## Owner's rules

- Never ask for API keys or passwords in chat. Secrets live only in GitHub Secrets
  (`HF_TOKEN`, optionally `ELEVENLABS_API_KEY`) and never appear in code, logs, commits or reports.
- Publishing: the owner approved unattended publishing of 10 Reels a month on Instagram and
  YouTube Shorts at 8 PM Asia/Riyadh (2026-10-17). Never create duplicate posts, and report a post
  as published only after Metricool shows it `PUBLISHED` with a public link.
- Every health claim needs a verified source in `content/evidence/<id>.json`. No exaggerated
  claims or guaranteed results; hedge limited evidence.
- Only media we have rights to: Cairo fonts (OFL), FLUX.1-schnell images (Apache-2.0), procedural
  backgrounds, the licensed ElevenLabs voice on the paid plan. No music.
- Never substitute the voice or model, never speed up or time-stretch narration.
- One narration take per Reel (about 400 credits). Never re-run a paid generation to retry.

## Facts

- Voice (owner's choice from 2026-10-24): ElevenLabs «Jeddawi Echo», voice_id `yXEnnEln9armDCyhkXcA`, model `eleven_v4`,
  Arabic. Do not use «عبدالله سعدون» (`t9akNmCDhz230CEXOYmn`) any more. Its natural pace is about 105-110 wpm
  and it has its own pauses, so no pauses are added between sentences.
- Metricool brand `7461887`, timezone Asia/Riyadh. Instagram @uuxuuoouuxuu, YouTube channel
  "The equalizer" (@bashar2507). Free plan: 20 published posts a month, one per network.
- Media links: `https://cdn.jsdelivr.net/gh/bashar2507-gethub/reels-media@<commit>/reels/<id>/<file>`.
- Rendering runs in GitHub Actions ("Render Reel", on pushes to `queue/*.json`); the workspace
  cannot download ElevenLabs files, so the job downloads the narration from its signed link.
- Library page: https://claude.ai/artifact/3xktcPAsz3jeNUW2fuudKo (database collection `reels`).
- Local build: `python scripts/run_poc1.py --script content/<id>.json --narration content/audio/<id>_narration_words.json --out output/<id>_release --release --visuals auto`
- Tests: `python -m pytest`
