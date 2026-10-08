# savestate433: a settings-only refusal names its fix (`# state: any`); the save store finds saves under an alias TitleID

State: ready

Lane: savestate433            Issue: #433 (#397 profile-save stage)
Base: master @ 6c828f9860 (merged)
Files: docs/lanes/savestate433/NOTES.md, docs/lanes/savestate433/PR.md, docs/lanes/savestate433/OUTBOX.md, docs/lanes/savestate433/scratch/needsave.py, docs/lanes/savestate433/scratch/needsave.out, docs/lanes/savestate433/scratch/hddstate.py, docs/lanes/savestate433/scratch/queuecheck.py, docs/lanes/savestate433/scratch/selftest-alias.out, docs/lanes/savestate433/scratch/status-alias.out, docs/lanes/savestate433/scratch/selftest-only.out, docs/lanes/savestate433/scratch/legs.sh, docs/testing/titles/titlestate.py, docs/testing/titles/titlestate_selftest.py
Prediction: none: harness only, no emulator code
Needs device: no    Needs NDK: no

## Summary

The first PR (golden profiles, route state, refusal) folded at 07:57. At
08:12 lane.local's queue runner dropped Star Wars Ep. III, its top-P title
today, on that PR's guard. The reason named no fix.

- **SW3's route is headed `returning`, and its golden `cb663b62ffcf` holds
  title data only**, so `returning` (which needs a save directory) is refused.
- **Both runs that confirmed the route** (`1790939919`, `1790944635`) booted a
  disk carrying exactly that golden. The survey with no save took the same
  path to play. The honest header is `any`, which loads the golden unchanged.
- **The refusal now says so:** both settings-only refusals (`resolve_route`,
  `compose`) end with "head it `# state: any` if the route was confirmed on
  this golden as it is; else `promote` a save with a save directory".
- **No guard is loosened:** `returning` on a settings-only golden is still
  refused. Castlevania's 10-01 void stays caught.

**The profile-save stage:** by the status page's own logic
(`status_html._registry`), every title on master with a route already has a
stored save. The 30 titles without a route get theirs with their route,
through the dispatcher's harvest and first-run golden. No title is waiting on
this stage.

**Also found** (lane.local's, in OUTBOX): ToeJam's queue lines will be
refused. Its route is not in the worktree the runner uses, and it needs
`# state: any` too.

**The save store now finds saves under an alias TitleID** (the 08:56 NEW
ISSUE).
- The status page listed Gunvalkyrie as "no save" while the store held one.
  It looked up targets.toml's id (`49470017`), and the save is filed under
  the disk's id (`5345000B`).
- `titlestate.store_saves` and `store_dir` now resolve the alias (`disk_tid`)
  themselves. That fixes the status page and `choose()`, which had the same
  miss, without touching `status_html.py`, which is in no lane's row.
- Live: Gunvalkyrie, JSRF and DOA3 read `save= True` with their stored save
  ids (`scratch/status-alias.out`).

Release note (none): harness message only.

## Local checks (no CI while offline)

- `python3 docs/testing/titles/titlestate_selftest.py`: 96 ok, 0 failed
  (`scratch/selftest-alias.out`).
  - The new SW3 leg and the amended Castlevania leg were red before the change.
  - The two alias legs ("listed under the targets id", "directory is found
    under it") were red before the store change (`[]`).
- `scratch/legs.sh` after merging master 6c828f9860: `SELFTEST_ONLY` with
  all 10 fragments that load titlestate.py or status_html.py (64-67 status,
  85-savestate, 99-hdd-split, 99-status-*). 218 passed, 0 failed
  (`scratch/selftest-only.out`).
- **The full `selftest.sh` was not run to the end here.** On this host, under
  load, 5 fragments took 19 min (40-arms-refusal 554 s against its measured
  333 s), so a serial run would take hours. Those 5 passed. The fold runs the
  full suite.
- `SELFTEST_ONLY=<fragment> docs/testing/jobs/selftest.sh`, run for every
  fragment that loads titlestate:
  - 85-savestate.sh: 27 passed;
  - 99-hdd-split.sh: 63 passed;
  - 65-status-objective.sh: 18 passed;
  - 66-status-titles.sh: 18 passed;
  - 99-status-fullwindow.sh: 1 passed;
  - 0 failed in all of them.

## Next

NOTES.md "Next": P x win for each candidate. First is lane.local's two
header lines: P 0.95, and 2 of today's titles stop being refused.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
