# dashretro: the 0.5 panel counts the Playable ledger and pathfind's held runs (#433)

State: ready

Lane: dashretro          Issue: #433
Base: master @ d354705c69
Files: docs/testing/jobs/status_html.py, docs/lanes/dashretro/PR.md
Prediction: none: renderer change, checked by rendering the live host and the status selftest fragments
Needs device: no    Needs NDK: no
Release note (none): status page only; no emulator code.

**What was wrong.** "1. How close is 0.5?" read Measured 83 / 145, Benchmarked 16 / 145, Playable 0 / 50 with 25
titles on the Playable ledger. Since 09-29 titles have been measured and confirmed by pathfind's 600 s held runs, not
queued soaks, and the owner's count is `pm/playable-accepted.tsv`; titles05() read neither.

**The change** (titles05, after the dispatch-verdict loop):
- pathfind held runs (`$WORK/wt/pathfind/docs/lanes/pathfind/runs/*/verdict.json` and `*/*/verdict.json`,
  `STATUS_PATHFIND_RUNS` overrides): each fps reading makes its title Measured at the verdict's time and is a
  measurement row (device defaults to nova). A held run is not a MAX run, so it never makes a title Benchmarked by
  itself, and it never replaces a MAX measurement.
- the Playable ledger (`$WORK/pm/playable-accepted.tsv`, `STATUS_PLAYABLE_LEDGER` overrides): each row makes its
  title Playable (and so Benchmarked, as the stage order defines) and Measured, at its acceptance time; the chart's
  Benchmarked and Playable lines and the 48 h forecast use that time.
- names join existing rows by title id, else a normalised name (case, punctuation, a leading "the", parenthesised
  regions), else a unique suffix match ("JSRF - Jet Set Radio Future" -> "Jet Set Radio Future").

**Result on this host** (status.sh --print, STATUS_OUT_DIR scratch): Measured 98, Benchmarked 41, Playable 25 / 50,
the Playable line stepping on the ledger dates (10-03 to 10-05). Selftest fragments 64-67 and 99-status-*: 121 passed,
0 failed (their fixtures have no ledger and no pathfind runs, so nothing they assert moves).
