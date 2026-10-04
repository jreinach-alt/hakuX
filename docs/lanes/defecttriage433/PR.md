# defecttriage433: classify and rank the defects blocking otherwise-good titles

State: ready

Lane: defecttriage433           Issue: #433 (0.5: 50 Playable)
Base: origin/master @ 2c59b7bbba
Files: docs/lanes/defecttriage433/**
Prediction: none: analysis-only, no arm
Needs device: no

## Summary

Read every title near the Playable bar with a full-window verdict (mostly
from `lane.verdict433`'s existing measurement pass, not yet folded, plus my
own read of "25 to Life" which that pass never covered), classified each
failure from the evidence on disk, ruled out two hypotheses that don't hold
up (the UBO-ring growth log lines in Blood Wake/Battlefield 2: MC are
already-fixed, bounded growth, not a new bug; none of the six titles show a
pipeline-create stall), and ranked the unowned causes.

Two titles (Blood Wake, Battlefield 2: Modern Combat) share an unexplained,
unowned defect: a sustained collapse to ~2-6 fps for minutes at a stretch,
40-90 s into the scored window, on the Thor. That is the top-ranked unowned
cause (2 titles, no prior investigation). Second is D&D Heroes' flat ~14-15
fps ceiling (1 title, cleanly characterized, no hang/stall to isolate).
Third is Bruce Lee's single 21.2 s hang, which per the flake-rerun rule
needs a second run before it is treated as a real defect rather than noise.
Crimson Skies and DOA Ultimate already have an owner or a clear procedural
next step; Kabuki Warriors, 007: Agent Under Fire and Forza are already
owned (uberspike569/shaderprebuild569/lane.kabukistall, done via #530,
forzadecay414 respectively) and needed no new work here. "25 to Life" has
two disagreeing generic-route samples (53.9% vs 83.0%, different builds) and
needs a dedicated route before it can be classified at all.

Full table, ruled-out hypotheses, ranking and three dispatch-ready brief
sketches (Blood Wake/Battlefield 2: MC, D&D Heroes, Bruce Lee) are in
`docs/lanes/defecttriage433/NOTES.md`.

## Local checks run (no CI available, per the offline protocol)

- `python3 -m py_compile docs/lanes/defecttriage433/judge_copy.py` -- the
  only script this lane adds; it is a straight adaptation of
  `lane.verdict433`'s tool of the same name (same shape: copy a result
  dir's inputs from `$DISPATCH_DIR/results`, run `title_verdict.py` over
  the copy, never touch the live dir).
- No harness files changed, so `docs/testing/jobs/selftest.sh` does not
  apply.
- No emulator code changed, so no dispatch run is needed to fold this PR
  (offline_fold.py's fourth check is N/A for a docs-only change).
- Confirmed territory: only `docs/lanes/defecttriage433/**` touched; no
  edits to `territory.toml` or `nv2a_issues.toml`.

Release note (none): analysis and planning docs only, no emulator code
changed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
