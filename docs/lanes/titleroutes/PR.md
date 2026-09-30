# titleroutes: sessions 39-40, both handhelds restricted today; three "lost" benchmarks found

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 2ba1a6e9a2
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/PR.md, docs/lanes/titleroutes/OUTBOX.md
Prediction: none: no arm (bookkeeping only; no code or golden changed)
Needs device: no (both handhelds are restricted today; see below)

## What this session found

Session 38's own work had already folded cleanly into `origin/master` as
`2c59b7bbba` before this session started -- not a failure recovery, a
routine continuation. Merged `origin/master` (fast-forward,
`39d518f9b6..2ba1a6e9a2`, no conflicts): brings in `lane.defecttriage433`'s
classification of the six titles blocking 0.5 Playable (analysis only, no
files of mine).

Neither handheld has device work available this session:

- **Nova**: session 38's three re-queued benchmarks (Midnight Club 3, 187:
  Ride or Die, Crash: Wrath of Cortex) never ran. They're parked at
  `dispatch/parked/titleroutes-daypark-0930/`: owner plan (lane.local
  10:05 PDT) sends the Nova's battery to Playable confirmations first
  today; my three return to queue tonight after the evening dock.
- **Thor**: `dispatch/hold/thor.why` was rewritten at 17:48 PDT today to
  "no queued runs" (fan still dead, light work only) -- this supersedes
  the 12:40 PDT "Thor screening program" addendum's allowance for queued
  `--hard-pin` soaks. No interactive hold, no queued soak.

`titlestate_selftest.py` passes; `targets.toml` parses with `tomllib`
(unchanged). See NOTES.md session 39 for detail.

Checked whether offline route-authoring (the Thor-screening addendum's own
suggestion) could fill the gap: of 4 candidate Thor titles with pass-1
survey frames reaching gameplay, 3 (Blinx, Blinx 2, Forza) belong to
lane.slowdown462 and the 4th (25 to Life) has too little evidence to draft
confidently. More useful: cross-referenced `lane.routeprep`'s 24 offline
route drafts against my adopted routes and found 9 still pending device
validation (8 others were already superseded by my own routes under
different filenames). Ranked them by evidence quality for the next device
session: Burnout Revenge and Galleon (Nova, strong pass-1 evidence) first,
then DOA3 (Thor, strong evidence), then 5 guess-only drafts that need a nav
session before a validation replay is worth it. Detail in NOTES.md.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks pass.
- `targets.toml`: parses with `tomllib`, unchanged this session.

## Device proof

None this session -- see "What this session found" above for why.

## Session 40 update (resumed 12:45 PDT)

Not a rescue: session 39 ended correctly on a `waiting:`. This session
resolved session 38's "lost benchmarks" report: the three original
session-37 requests (not session 38's re-queued duplicates) are `DONE` in
`dispatch/results/` with real, non-void fps readings (Midnight Club 3 29.67
median/87.5% >= 30; 187: Ride or Die 59.94 median/100% >= 30; Crash: Wrath of
Cortex 56.18 median/100% >= 60 as an upper bound). They were never lost --
session 38's re-queued duplicates are now flagged as redundant (parked,
not touched). Device state re-checked fresh: Nova has no hold but is
actively running `lane.verdict433`'s confirmation soak (`.owner` = nova) and
is earmarked for Playable confirmations today regardless; Thor's
`lanelocal-fanwait` still reads "no queued runs". No device work available.
Full detail in NOTES.md session 40 and OUTBOX.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
