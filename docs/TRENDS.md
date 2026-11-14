# Weekly trend research (owner, 2026-11-15)

The owner asked for this on 2026-11-15: at the start of every week (Sunday, Asia/Riyadh), find which fitness and
muscle-building ideas are getting the most views right now and give him what was found, so he can decide which to
add. A scheduled task runs it every Sunday morning; he can also ask for it in chat. This step only proposes: nothing
enters `content/plan.json` without his yes. Talk to him in Arabic.

## 1. Read first

`CLAUDE.md`, `content/plan.json` (every item, any status), `content/analytics/summary.json` (what holds our viewers)
and the last four files in `content/ideas/`, so nothing is proposed twice without new evidence.

## 2. Collect this week's signals

WebSearch ("standard" first, "extended" for the last 7-14 days) and WebFetch, in English and in Arabic. Look for:
- View and search numbers: articles that give views or video counts for a TikTok, Instagram or YouTube trend;
  search-growth pages (Exploding Topics fitness topics, Glimpse, Treendly); sales figures (Amazon) when reported.
- Trend lists from the field: ACSM's yearly survey, Strava and Hyrox figures, gym-chain reports for the Gulf
  (GymNation's UAE and KSA report).
- New studies with wide coverage: journal pages, university news, monthly research round-ups such as The Elite
  Trainer's "Keeping up with current research".
- Our audience's calendar: Saudi and Gulf events (Hyrox, fitness expos in Riyadh and Jeddah, Riyadh Season), the
  weather, Ramadan (start proposing about six weeks before), Eid, school holidays, New Year.

For every signal keep what it is, the number, the date and the link. A trend without a source link is not reported,
and a number that is not on the page is not quoted. No paid tools or credits for this (TinyFish, Higgsfield's
virality tool and the like). YouTube, Instagram, TikTok, PubMed and PMC pages often cannot be fetched from here; use a
journal or publisher page, a university news page or another trusted record instead.

## 3. Filter

Keep an idea only if:
- it fits gym-goers: muscle, strength, training, recovery, nutrition for training; fat loss through a training angle;
- peer-reviewed evidence answers it (a meta-analysis, an RCT, a position stand, or a large cohort stated as an
  association), and a record of it can be opened now;
- it is not already in `content/plan.json` in any status (a trend that fits a planned item becomes a proposal to
  re-hook or move that item);
- it is safe: no extreme diets, no drugs, SARMs or steroids, no medicine doses, no treatment advice. A false or risky
  trend can still be a «خرافة أم حقيقة؟» Reel when the evidence answers it clearly.
Poses, dances and memes with no question to answer get one line at most under "not for us".

## 4. Write the report (5 to 8 ideas)

Write `content/ideas/<YYYY-MM-DD>.md` in Arabic, numbered, most promising first. For each idea:
- the question as a hook (at most 8 words, concrete, no "why" opener) with `hook_type`, `series` and `category`;
- why now: the signal with its number, date and source, marked as data or as an estimate;
- the evidence: one or two sources (journal, year, DOI or PMID) and how strong it is (strong, moderate, limited);
- the fit with our numbers in `content/analytics/summary.json`;
- the recommendation: add now, add later (say when), or re-hook a planned item, with one line why.
End with the sources as links. Commit and push (`git pull -q --rebase origin main` first); if the push fails, still
send the report.

## 5. Send it

Send the owner the report with `SendUserMessage`, in Arabic: the numbered ideas in two or three lines each, where each
would go in the order, and one question: which numbers to add. Change nothing else in this step: not the plan, the
schedule or the approved steps.

## 6. When the owner answers

In the same session or a later chat, add only the numbers he approves to `content/plan.json` as `planned` items with
the next free `rNNN` id, `subject`, `hook_idea`, hedged `claims`, `seed_sources` (hints the Reel run verifies),
`category`, `hook_type`, `series` and `idea_from` ("weekly trends <date>: <signal>"). Place them where he says;
otherwise follow `order_note` (training topics first, fat-loss topics in between, at least three Reels between two
items on the same subject, seasonal items before their season ends, remakes kept one a week). Adding items never
changes the 10 Reels a month. Record his answer at the end of that week's file in `content/ideas/`, commit and push,
and tell him where each idea landed.
