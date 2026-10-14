# savestateconv1014: R3 admits --from-state; Part B names two blockers, with evidence (#433)

State: ready

Lane: savestateconv1014    Issue: #433
Base: master @ a45f88b319
Files: docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py, docs/lanes/savestateconv1014/NOTES.md, docs/lanes/savestateconv1014/PR.md
Prediction: none: analysis-only + read-only/lifecycle device probes, no device-timed arm to register
Needs device: no (device work for this PR is done; the two Nova holds already ran)    Needs NDK: no

Part A (merge lane/holdfollow1013 + finish its R3 gate): **done.** Merged
`lane/holdfollow1013` (R3 admits a `--no-record` re-hold of a known path) and added the
`--from-state` case to `r3_refusal()`: a hold started from a captured save state does no
navigation at all, so R3 admits it unconditionally on a known-path title, stronger than
`--no-record` (no replay either). A title with no known path is untouched by this branch --
that case belongs to the state-load check itself (Part D), not R3.
`python3 docs/testing/titles/pathfind_selftest.py` passes: `pathfind_selftest: all ok`.

Four mutants run against `r3_refusal()` (drop the final refusal; drop the
`--no-replay`/`--no-guide` narrowing under `--no-record`; drop the `--no-record` admission
entirely; drop the `--from-state` admission entirely) -- all four caught (`FAIL r3`), clean
tree passes. Full table in NOTES.md.

Part B (device measurement, 5 questions): **done, names two blockers with evidence**,
per the brief's readiness allowance ("A-D done, or B names a blocker with its evidence").

- **B1 (disk binding)**: re-confirmed live, 2026-10-14, that `titlestate.py`'s dispatcher
  rebuilds the shared titles disk from the composed goldens on every ordinary run (the
  `plan()` "build" action), discarding any save state's qcow2-internal snapshot -- this
  already-documented `disk-snapshot-missing` defect (`docs/lanes/savestate1011/NOTES.md`)
  blocks Part C/D's actual promise (a soak restarting from a state tomorrow) until a title's
  golden record can carry "load this state" or the pipeline bypasses goldens for
  state-bearing runs. Host-sha and two `plan()` dry-runs (harvest vs. build) in NOTES.md.
- **B2 (prefs routing)**: confirmed by code reading -- a harness launch (`LauncherActivity`)
  never applies per-game runtime overrides, so only the global `savestate_auto_save`/
  `savestate_auto_load` prefs reach it. This is the brief's own pre-approved fallback and was
  exercised live (write, verify by read-back, restore, verify again).
- **B3 (trigger behavior) -- new finding**: the already-shipped auto-save-on-quit thread
  (`onStop()` -> `autoSaveOnQuit("stop")`) appears to **stall indefinitely** (0.0% CPU, no
  completion/error log, no state file produced, for 90+ s) when triggered by a clean "go
  home" backgrounding, rather than completing or cleanly timing out within its documented
  10 s join window. This lifecycle path isn't covered by the existing pause-menu/swipe-away
  UX checklist. Logged as `WAITING:` -- it's Kotlin/native territory
  (`MainActivity.kt`/`hxs.c`), not this lane's to fix.
- **B4 (load/timing)**: blocked on B3 -- no save ever completed to load back.
- **B5 (snapshot cap)**: confirmed by code reading -- per-title (title ID is embedded in the
  qcow2 snapshot name), not per-image.

Parts C/D/E: **deferred**, citing B1 and B3 above (full reasoning in NOTES.md's "Why C/D/E
stop here"). Implementing `--save-state`/`--from-state`/`convert.tsv` now would either ship a
state-taking path whose state the very next dispatcher run throws away (B1), or depend on a
capture trigger that stalls under exactly the lifecycle path an unattended pipeline would use
(B3). This matches the brief's stated priority: "deliver A and B finished rather than C-E
half done."

`python3 docs/testing/titles/titlestate_selftest.py`: one pre-existing failure
(`a .first-run/.returning file declares its own variant`, on `doa3.returning.route` /
`ninja-gaiden-black.returning.route`) -- confirmed via `git diff origin/master` that neither
file nor `titlestate.py`/`titlestate_selftest.py` differs from `origin/master` on this branch;
the failure traces to `zetaroutes1012` (unrelated lane, route-file content, not code), not to
anything touched here.

Device time: two short Nova holds (read-only states-listing/sha probe, then the
prefs-mutation + Tork round-trip + restore), both released promptly, well under the 75-minute
budget.

Release note (none): harness/profile-gate work and read-only device measurement only;
nothing device-facing shipped this round.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
