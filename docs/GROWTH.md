# Growth plan: why the Reels are built the way they are (2026-11-15)

The owner asked (2026-11-15) for research-based improvements to views, likes, followers, retention, shares,
comments and reach, applied automatically to every new Reel. This file is the reasoning; `docs/RUNBOOK.md` holds
the steps and `docs/APPROVED_STEPS.md` (Arabic) what the owner approved. The owner's report (Arabic) is the doc
"خطة نمو UXOXU Reels" (https://claude.ai/artifact/9THfEXDFUNyzn2jfPnw8Cp).

## Baseline (Metricool, Instagram, 12 Reels, 16 Oct to 11 Nov 2026)

- 1,490 views, about 124 per Reel; 32 likes, 0 comments, 5 shares, 4 saves.
- About 66% of viewers skip in the first 3 seconds; average watch time 6.8 s of about 40 s.
- Muscle/training topics: 8.6 s average watch, 60% skip. Fat-loss topics: 5.0 s, 71% (6 Reels each).
- "How many" hooks held best (9.7 s, n=2); "why" hooks worst (4.1 s, n=2).
- The four Reels with the 1.8 s intro at the start: 5.5 s average watch, against 7.5 s for the eight before it
  (small sample, and all four are fat-loss topics, so the cause is not settled).
- Instagram followers: 5, flat since 20 Oct. YouTube subscribers: 147 to 168 (16 Oct to 14 Nov).
- Metricool returns no per-Short YouTube numbers for this channel.

## What the platforms say (official statements, not independent tests)

- Instagram: watch time, likes per reach and sends per reach are the main signals; sends matter most for reaching
  non-followers ([Mosseri, Jan 2025](https://www.socialmediatoday.com/news/instagram-shares-algorithm-insights-2025/738034/)).
  Skip rate = share of views skipped in the first 3 s, with a retention chart per Reel
  ([Aug 2025](https://www.socialmediatoday.com/news/instagram-adds-retention-insights-reels/758464/)). At most 5
  hashtags per post ([Dec 2025](https://www.socialmediatoday.com/news/instagrams-implementing-new-limits-on-hashtag-use/808309/)).
  Original content is favoured; clickbait, engagement bait and exaggerated health claims can be excluded from
  recommendations ([Instagram Creators](https://creators.instagram.com/recommendations-and-originality)).
  Trial Reels need 1,000+ followers.
- YouTube: Shorts views count every start or replay since 31 Mar 2025
  ([TechCrunch](https://techcrunch.com/2025/03/26/youtube-is-changing-how-youtube-shorts-views-are-counted));
  engaged views count viewers who stay past the opening seconds ([Help](https://support.google.com/youtube/answer/12220281));
  up to three hashtags show above the title, more than 60 are all ignored, unrelated ones break policy
  ([Help](https://support.google.com/youtube/answer/6390658)); the audience drives recommendations and storytelling
  matters more than length ([Todd Sherman, 2023](https://www.searchenginejournal.com/youtube-explains-how-shorts-algorithm-works/494953/)).

## What research says

- Practical value, surprise, interest and high-arousal emotions predict sharing; sadness reduces it
  (Berger & Milkman, Journal of Marketing Research, peer-reviewed; news articles, not short video).
- Curiosity comes from a noticed information gap (Loewenstein 1994, Psychological Bulletin, peer-reviewed review).
- Captions improve comprehension and memory for hearing viewers too (Gernsbacher 2015, peer-reviewed review).
- Posting 3-5 times a week goes with about 12% more reach per post than 1-2 (Buffer, 2.1M posts, association only).
- Hooks in the first 1-3 s, mid-video re-hooks, series and specific calls to action are practitioner advice without
  published controlled tests; we apply them and measure them with our own numbers.

## The ten improvements and where they live

1. Hook heard in the first second, concrete, at most 8 words, typed (`hook_type`): RUNBOOK step 4.
2. Hook-first option (hook, then the intro): built in `app/intro.py`, waits for the owner's approval (step 5a).
3. Open-loop structure with one mid-video turn and the answer in the second half: step 4.
4. 6-8 scenes (a new picture every 4-6 s), scene 1 shows the question, character placed below the figures: steps 4, 5b.
5. Worth sending: a takeaway usable today and "send it to …" in the call to action: step 4.
6. Call to action with a reason to follow, plus at most two of like, comment, send, rotated; the full set in the
   caption; the comment question as Instagram's first comment: steps 4 and 7.
7. One text per network: Instagram keyword-first caption with 3-5 hashtags; YouTube keyword-first title under
   60 characters, its own description and 3 hashtags: steps 4 and 7.
8. Topic mix from data (gym-goer angle, training topics first): `content/plan.json` order and step 4.
9. Recurring series with a small on-screen label: `series` in the plan, `series_label` in the script.
10. Performance log every run and lessons every 5 Reels: step 1b, `scripts/perf_log.py`, `docs/LEARNINGS.md`.

## Open decisions for the owner

- Turn on hook-first (sample sent 2026-11-15).
- Test 18:00 against 20:00 (Metricool's best-time data peaks around 18:00 for Instagram and 15:00-17:00 for YouTube).
- More than 10 Reels a month needs a paid Metricool plan (Free = 20 posts a month).
- Instagram profile: a readable name and a bio that promises what the account gives; only the owner can change it.
