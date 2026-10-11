# stuckdetect1007: a stuck/menu detector for pathfind's 600-s hold, validated offline on stored frames (#433)
State: ready

Lane: stuckdetect1007            Issue: none (harness defect, dispatched directly; #433, 0.5)
Base: master @ cd20abf797
Files: docs/lanes/stuckdetect1007/stuckdetect.py, docs/lanes/stuckdetect1007/95-stuckdetect.sh, docs/lanes/stuckdetect1007/NOTES.md, docs/lanes/stuckdetect1007/OUTBOX.md, docs/lanes/stuckdetect1007/PR.md
Prediction: none: analysis-only (a standalone detector module validated by offline frame replay; no device run, no pixels claimed by this PR)
Needs device: no    Needs NDK: no
Release note (none): an offline detector module and a staged selftest leg under docs/lanes/; no edits to pathfind.py/drive.py in this PR, no player-visible effect.

Three Nova runs on 2026-10-07 each burned 30-40 min stuck where the existing 600 s hold
(`docs/testing/titles/pathfind.py`, `hold_play`) did not catch it: Arx Fatalis (view pressed to a
wall, "gameplay" on all 12 look-checks), Cel Damage (car against a canyon wall), Gui Yi (the
genre loop walked back into a merchant NPC and reopened its shop for ~1700 s, `HOLD_SHED`'s one
shed only firing once). Owner order 10-07 14:10 PDT: catch this without burning more runs.

`docs/lanes/stuckdetect1007/stuckdetect.py` is a standalone, dependency-free module (no
`pathfind.py`/`classify.py` import -- a territory boundary) that:

- builds a coarse per-frame signature (16x12 grey grid, FPS-corner masked, + an 8-bucket
  histogram) needing PIL/numpy,
- but keeps every decision (`is_stuck`, `menu_stuck`, `distinct_views`, the `stuck_step` hook) as
  a pure function over plain Signature tuples, so the CI selftest runner (no PIL/numpy) drives
  the whole decision logic with synthetic signatures and never touches an image,
- flags "stuck" when **every consecutive pair** in a trailing 4-sample window is near-identical
  -- not first-vs-last, which is what let Arx Fatalis's jittering wall view through the existing
  offline position check,
- adds a menu-stuck variant gated on `hold_look`'s own state answers, and an unstick-ladder hook
  (`stuck_step`) that takes the genre's `HOLD_UNSTICK` ladder as a parameter rather than
  duplicating it, so pathfind's and this module's ladders cannot drift apart.

**Validated against 14 stored hold runs already on disk** (lane.pathfind's `runs/`, read-only):
the 3 must-flag runs the brief named, plus all 3 explicitly-named must-not-flag banked Playables
(Indigo Prophecy, Blade II, Capcom vs SNK 2) and 8 more banked Playables found from
`pm/playable-accepted.tsv`. Every must-flag run flags (4-16 samples in); every must-not-flag run
stays clear, including Blowout, a dark-hangar patrol that false-triggered at pathfind's own
`SIG_MATCH=9.0` bar and is why the shipped `GRID_BAR` is 7.0 instead (full threshold sweep and
margin in NOTES.md). `distinct_views` is implemented and reported but **not** used as a gate:
measured over the whole hold it does not separate must-flag from must-not-flag on this data
(Cel Damage, a must-flag run, measured higher than three must-not-flag runs) -- reported
honestly in NOTES.md rather than fitted.

Each fix has a selftest leg that can fail: `stuckdetect.py selftest` (20 synthetic checks,
stdlib-only) plus two source mutants in `95-stuckdetect.sh` (the fix removed outright; the
weaker first-vs-last rule reinstated -- `hitch_report.position_fail`'s own shape) that each turn
`selftest` red. Verified locally against a harness shim reproducing `selftest.sh`'s
`ok`/`bad`/`check` contract (the real `docs/testing/jobs/selftest.sh` needed an approval this
session could not grant itself; see NOTES.md).

No `pathfind.py`/`drive.py` edits in this PR (territory: `docs/lanes/stuckdetect1007/**` only).
`OUTBOX.md` names the exact integration points (line numbers against this branch's base, flagged
as a shape not a diff since lane.pathfind's `hold.jsonl` output already shows fields -- `ladder`,
`ladder_round` -- this base's `pathfind.py` doesn't have, i.e. that file has moved under active
work) for lane.local to grant: moving the selftest leg into `selftest.d/95-stuckdetect.sh`
(the number is free), and wiring `stuck_step` into `hold_play`'s kept-frame loop.

No device time used or requested: the whole validation is offline replay of frames already on
disk. The Puyo Pop case (lost a match, then story dialogue) is explicitly named in NOTES.md as
out of this module's reach (each dialogue line changes the frame, so a scene-not-changing check
cannot catch it) -- not claimed as fixed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
