# Instagram skills (third-party)

The `ig-*` skills come from https://github.com/Jakeschincariol/instagram-agent-skill
at commit `d03c56b` (MIT, see `LICENSE-instagram-agent-skill`). They were copied unchanged.

They are writing aids only. Where they disagree with this repository, `CLAUDE.md`,
`docs/RUNBOOK.md` and `docs/APPROVED_STEPS.md` win, in particular:

- Publishing follows the approved Metricool pipeline, whatever the skills say about posting.
- Every health claim still needs a verified source in `content/evidence/<id>.json`; the hook
  formulas' "numbers over adjectives" never justifies an unsourced or exaggerated figure.
- `ig-viral`'s `yt_dlp` research is not part of the approved pipeline.
- The text heuristics (`ig-human`, `hookscore.py`, `caption.py`) are English-only and do not
  judge Arabic text reliably.
