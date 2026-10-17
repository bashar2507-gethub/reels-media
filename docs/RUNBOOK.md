# Runbook: produce and publish one Reel, unattended

Each scheduled run follows these steps exactly. The owner (Bashar) approved this process on
2026-10-17: 10 Reels a month, each on Instagram and YouTube Shorts, published directly at
8 PM Asia/Riyadh, with no per-clip review. Read `CLAUDE.md` first; its rules always win.

Talk to the owner in Arabic. Report only what tools confirmed.

## 0. Setup

1. Attach and clone: `add_repo(owner="bashar2507-gethub", repo="reels-media", access="push")`, then
   `git clone --depth 1 https://github.com/bashar2507-gethub/reels-media /home/claude/reels-media`.
2. `cd /home/claude/reels-media && pip install -q --break-system-packages -r requirements.txt`.
3. Git identity for commits: `-c user.name="Claude" -c user.email="noreply@anthropic.com"`.

## 1. Guards (stop and report if any fails)

- Earlier runs: any plan item still `scheduled` was published by Metricool after its run ended.
  Read it with `getScheduledPosts` (its publish day) and record `published` with both public links,
  or `failed` with the provider status, before anything else.
- Quota: Metricool Free publishes 20 posts a month and a Reel on two networks counts as 2.
  Count this month's Reels in `content/plan.json` with status `published` (published_at in the
  current month, Asia/Riyadh). If 10 or more, stop: nothing to do this month.
- Duplicates: `getScheduledPosts(brandId="7461887", timezone="Asia/Riyadh")` for today and
  tomorrow. If a post for the chosen Reel already exists, do not create another.

## 2. Pick the Reel

In `content/plan.json` take the first item whose status is `rendered` (already built: go to
step 7). Otherwise take the first `planned` item. A `queued` item older than 2 hours whose
`reels/<id>/status.json` is missing has a stalled render: report it and take the next item.

A `rendered` item whose `reels/<id>/status.json` lists no AI images (`visuals.ai` is empty) gets
one re-render first, in case `HF_TOKEN` has been added since (step 6, "Re-render"). It costs no
credits because the narration is already in `content/audio/`. Publish whichever result passes.

## 3. Evidence

For each claim of the item, search PubMed or PubMed Central (WebSearch, then WebFetch the article
or a trusted record of it) and confirm title, authors, journal, year, DOI or PMID, design, size
and the finding itself. Seed sources in the plan are hints, not facts. Prefer systematic reviews,
meta-analyses, RCTs and guidelines. Drop or soften anything you cannot verify; if the topic
cannot be supported, set the item to `skipped` with a reason and take the next one.
Write `content/evidence/<id>.json` in the same shape as `content/evidence/r002.json`.

## 4. Script

Write `content/<id>.json` in the same shape as `content/r002.json`:
- 55 to 75 spoken Arabic words, 4 to 6 scenes: hook question (scene 1, style "title"),
  explanation, practical example or myth correction, takeaway, save or share call to action.
  Vary the call to action between Reels.
- Hedge where the evidence is limited («قد»، «في دراسة»). No guarantees, no medical advice.
- Spell numbers as words in `say`; put the numeric form as an unspoken annotation in `show`,
  for example `واحد فاصلة ستة غرام (1.6 g/kg)`. `show` must contain exactly the spoken words plus
  annotations in parentheses and `|` caption breaks of at most 4 words.
- Figures: when a sentence gives a number or a calculation, add `overlay` to that sentence:
  `{"big": "70 × 1.6 = 112", "small": "غرام بروتين يوميًا لوزن 70 كغ", "from": "سبعون"}`.
  `big` holds only digits and symbols (shown left to right, large, in amber), `small` is one short
  Arabic line, and `from` is the spoken word at which it appears. Don't repeat the number as a
  bracketed annotation in `show`.
- `image_style` per scene: `still_life` (objects and food, the default), `athlete` (a person
  training, face out of frame; for sentences about muscles or exercise) or `anatomy` (a 3D muscle
  illustration; for how muscles work). At most two scenes with a person per Reel.
- Each scene: `visual` = `<id>-s<n>`, `image_prompt` (English, one concrete object or still life,
  no people, no hands, no text, no screens with numbers; FLUX invents fake writing on labels, so
  avoid packaged products, jars with labels, books, signs and branded or engraved equipment), `fallback` (one of scale, flow, orbs,
  dumbbell, bookmark), `zoom` and `pan` like the existing scripts.
- `post`: caption (hook, short summary, takeaway bullets, call to action, short sources,
  «🎙️ التعليق الصوتي مولّد بالذكاء الاصطناعي.», «معلومات عامة للتثقيف، ولا تغني عن استشارة مختص.»,
  5 to 8 hashtags), `youtube_title` (under 90 characters), `youtube_tags`.
- Check it: `python3 -c` with `app.timeline.narration_text` and `build_timeline(script, EspeakTTS("ar", 210), tmp)`
  must run without errors and give 55 to 75 words.

## 5. Narration (ElevenLabs connector, about 1 credit per character)

1. `creative_create_flow(name="UXOXU Reel <id>")`.
2. `creative_generate_speech(flow_id, model_id="eleven_v4", voice_id="t9akNmCDhz230CEXOYmn",
   generations_count=1, prompt=narration_text(script))`. One take only. Never call it again to
   retry: if it fails, stop and report.
3. Poll `creative_get_flow_run_status` until `all_completed`. Keep `generations[0].id` and
   `media[0].url` (a signed link that expires after 2 hours).
4. `creative_add_flow_asset_node(flow_id, modality="audio", generation_id=...)` returns the node
   to transcribe (it may be the speech node itself).
5. `creative_transcribe_audio(flow_id, model_id="eleven_scribe_v1", connect_from=[node])`, poll
   until done, and keep `transcripts[0].words_download_url` and `word_count`.
   The transcript must match the narration text; if words are missing or changed, stop and report.

## 6. Render (GitHub Actions)

1. Write `queue/<id>.json`: `{"reel_id", "script", "narration": {"url", "words_url", "voice":
   "عبدالله سعدون", "voice_id", "model_id": "eleven_v4", "language_code": "ar", "generation_id",
   "timing_source": "ElevenLabs eleven_scribe_v1 transcription", "generated_on"}}`. Copy the two
   signed links exactly; each signature is 512 hex characters.
2. Set the plan item to `queued`, commit queue, script, evidence and plan, and push to `main`.
   The push starts the "Render Reel" workflow.
3. Poll every 30 s, up to 30 minutes: `git pull -q --rebase origin main`, then look for
   `reels/<id>/status.json`.
4. `passed: false`: set the item to `failed` with the reason from `error` or `failed_checks`,
   commit, update the library page (step 9) and stop. Nothing unchecked is ever posted.
5. `passed: true`: set the item to `rendered`. The commit that added the video is
   `git log -1 --format=%H -- <status.video>`; the media link is
   `https://cdn.jsdelivr.net/gh/bashar2507-gethub/reels-media@<commit>/<status.video>`.

Visual check (after every passing render): pull, then take one frame from the middle of each
scene (`ffmpeg -v error -ss <seconds> -i <status.video> -frames:v 1 -vf scale=360:-1 <png>`) and
look at each with Read. Every frame needs: no invented writing, no visible face, natural hands and
anatomy, legible captions and figures. If a scene fails, rewrite its `image_prompt` (or change its
`image_style`) in `queue/<id>.json` and re-render; this costs images only. After two failed tries,
delete that scene's `image_prompt` so it uses its procedural `fallback`.

Re-render: `git rm -r -q reels/<id>`, set `"rerender_requested": "<UTC time>"` in
`queue/<id>.json`, commit and push, then poll as in 3. The job reuses
`content/audio/<id>_narration.mp3` and its words file, so the expired signed links don't matter.

## 7. Publish (Metricool connector)

Time: 20:00 Asia/Riyadh today, or now + 10 minutes if that has passed. One call:

```
createScheduledPost(blogId="7461887", date="<YYYY-MM-DDTHH:MM:00+03:00>", info={
  "autoPublish": true, "draft": false, "descendants": [], "firstCommentText": "",
  "hasNotReadNotes": false, "media": ["<jsDelivr link>"], "mediaAltText": [],
  "providers": [{"network": "instagram"}, {"network": "youtube"}],
  "publicationDate": {"dateTime": "<YYYY-MM-DDTHH:MM:00>", "timezone": "Asia/Riyadh"},
  "shortener": false, "smartLinkData": {"ids": []}, "text": "<post.caption>",
  "instagramData": {"type": "REEL", "showReelOnFeed": true, "isAiGenerated": true},
  "youtubeData": {"title": "<post.youtube_title>", "type": "short", "privacy": "public",
                  "tags": <post.youtube_tags>, "category": "EDUCATION", "madeForKids": false,
                  "isAiGeneratedContent": true}})
```

Leave out `videoCoverMilliseconds` and `videoThumbnailUrl` when YouTube is a provider: YouTube
rejects a custom cover unless the channel is verified. If the call errors, check
`getScheduledPosts` before trying again, so no duplicate is created.

## 8. Verify

1. `getScheduledPosts` must show the post with both providers `PENDING`. Set the plan item to
   `scheduled` with `metricool_post_id` and the publish time, commit and push.
2. If the publish time is within 60 minutes, wait until 5 minutes after it (an `until` loop on
   the clock), then read it again: each provider must be `PUBLISHED` with a `publicUrl`. Anything
   else is a failure to report, not a success. If it is further away, end the run here; the next
   run records the outcome (step 1).

## 9. Record

1. Plan item: status `published`, `published_at`, `links` {instagram, youtube}, `metricool_post_id`.
   Copy the same into `content/<id>.json` under `post.published`. Commit and push.
2. Library page `https://claude.ai/artifact/3xktcPAsz3jeNUW2fuudKo`: `Artifact` read it once, upload the
   video and cover as assets (`Artifact` publish with `url`, `asset: true`, `file_paths`), then
   `ArtifactData set` collection `reels`, doc `<id>` in the same shape as doc `poc1` (status
   `published`, `links`, `publishedAt`, asset ids, caption, sources, checks, wpm, durationS).
3. Final message (Arabic): the topic, both links, the checks result, and any problem.
