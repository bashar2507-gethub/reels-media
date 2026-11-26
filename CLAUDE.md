# reels-media: notes for Claude

This repository holds the whole Reels pipeline (code, scripts, evidence, plan) and the published
media under `reels/`. To produce and publish a Reel, follow `docs/RUNBOOK.md` step by step.
`docs/APPROVED_STEPS.md` (Arabic) records what the owner approved; changing any of it needs his approval.

## Owner's rules

- Never ask for API keys or passwords in chat. Secrets live only in GitHub Secrets
  (`HF_TOKEN`, optionally `ELEVENLABS_API_KEY`) and never appear in code, logs, commits or reports.
- Publishing: the owner approved unattended publishing of 10 Reels a month on Instagram and
  YouTube Shorts (2026-10-17), at 6 PM Asia/Riyadh from 2026-11-17 (8 PM before; he moved it on 2026-11-15).
  Never create duplicate posts, and report a post as published only after Metricool shows it `PUBLISHED`
  with a public link. Never delete or archive a published post; the owner does that himself.
- Every health claim needs a verified source in `content/evidence/<id>.json`. No exaggerated
  claims or guaranteed results; hedge limited evidence.
- Only media we have rights to: Cairo fonts (OFL), FLUX.1-schnell images (Apache-2.0), procedural
  backgrounds, the licensed ElevenLabs voice on the paid plan, and a few light ElevenLabs sound effects under dialogue
  Reels (owner, 2026-11-20; first in r030). No laughs, laugh bed or crickets: the owner found them cheap. No music.
- Never substitute the voice or model, never speed up or time-stretch narration.
- One narration take per Reel (about 400 credits). Never re-run a paid generation to retry.

## Facts

- Voice (owner's choice from 2026-10-24): ElevenLabs «Jeddawi Echo», voice_id `yXEnnEln9armDCyhkXcA`, model `eleven_v4`,
  Arabic. Do not use «عبدالله سعدون» (`t9akNmCDhz230CEXOYmn`) any more. Its natural pace is about 105-110 wpm
  and it has its own pauses, so no pauses are added between sentences.
- Marah's voice (owner's choice, 2026-11-20): ElevenLabs «Nora S - Saudi Natural & Calm», voice_id
  `FZeLZd39ejvLgzR2gY0t`, model `eleven_v4`, Arabic, only for Marah's own lines and for the Reels she narrates (plan items with `"narrator": "marah"`,
  owner 2026-11-22). Every other narration and Blanket stay Jeddawi Echo.
- Marah's signature opener «MARAH MOMENT» (owner, 2026-11-26): `assets/intro/marah_moment.mp4`, her catchphrase
  «لحظة لحظة!»; it opens the Reels she presents (`"intro": "marah"`) instead of THE BLANKET EFFECT. No name tag on it.
  From 2026-11-26 it shows the V-sign selfie `images/magnific/marah_vsign_1hand_a.jpg` (owner's choice).
- Magnific images (owner's decision, 2026-11-26): Magnific's terms limit free-plan images to personal use with
  attribution; the owner was told and chose to use them anyway (`images/magnific/`). Their generation is free up to
  20 images a day. Hugging Face image credits ran out on 2026-11-26 (402 Payment Required).
- Metricool brand `7461887`, timezone Asia/Riyadh. Instagram @blanket_fitness, YouTube channel
  "Blanket_Fitness" (@Blanket_Fitness); renamed by the owner on 2026-11-21 (before: @uuxuuoouuxuu, "The equalizer"
  @bashar2507). TikTok is posted by the owner in the app, not through Metricool. Free plan: 20 published posts a month, one per network.
- Media links: `https://cdn.jsdelivr.net/gh/bashar2507-gethub/reels-media@<commit>/reels/<id>/<file>`.
- Rendering runs in GitHub Actions ("Render Reel", on pushes to `queue/*.json`); the workspace
  cannot download ElevenLabs files, so the job downloads the narration from its signed link.
- Library page: https://claude.ai/artifact/3xktcPAsz3jeNUW2fuudKo (database collection `reels`).
- Weekly trend research (owner, 2026-11-15): every Sunday morning a scheduled run follows `docs/TRENDS.md` and sends
  the owner ideas to approve; nothing enters `content/plan.json` without his yes.
- Amazon.sa Associates (owner, 2026-11-20): tracking ID `uxoxufit-21`; Instagram is the only registered site, so no
  affiliate links or product lines anywhere else. Rules: `docs/RUNBOOK.md` step 4b and `affiliate` in `content/plan.json`.
- Characters (owner's brief, 2026-11-20): `docs/CHARACTERS.md`. Blanket is calm, serious and analytical, with minimal,
  deliberate movements; Marah, the female character from the owner's own images (blonde ponytail, navy cap, purple top
  and shorts, pink headphones and watch; sheets and pose references in `assets/characters/marah/`), is cheerful, curious
  and expressive. Keep both consistent in every video. Use Marah when he asks or a study is on women; first used in r029 s2b.
- Dialogue Reels (owner, 2026-11-20; first r030): one take per line in each character's voice, mixed by
  `scripts/mix_dialogue.py --spec content/<id>_dialogue.json` (no speed change); takes are kept in the repo through the
  "Fetch Audio" workflow (`audio_queue/<id>.json`) before their signed links expire. Two-character scenes are composed
  from solo cut-outs by `scripts/compose_scenes.py` (duo edits drew mouths). Future format: Marah brings the common
  question or myth, Blanket corrects it with the studies. The owner hears every take before it is mixed; words the
  voice gets wrong he records himself, and the recording is converted to the character's voice with ElevenLabs
  speech-to-speech (`eleven_multilingual_sts_v2`) (owner, 2026-11-21).
- Local build: `python scripts/run_poc1.py --script content/<id>.json --narration content/audio/<id>_narration_words.json --out output/<id>_release --release --visuals auto`
- Tests: `python -m pytest`
