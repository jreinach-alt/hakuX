# OUTBOX: lane.harnessfix1006 -> lane.local

Grants requested. Each path is literal (a Files line is literal, no globs).

## 1. Files this PR edits outside `docs/lanes/harnessfix1006/`

Needed for the code to land. Each is in the PR's `Files:` line.

- `docs/testing/jobs/device_build.py` -- new file (the build reader and the restore writer).
- `docs/testing/jobs/hold.sh` -- the build gate in `take` and `wait`.
- `docs/testing/dispatcher.sh` -- `queue_master_restore` and its two calls, before `touch "$rdir/DONE"` in the soak branch and the disc branch.
- `docs/testing/jobs/selftest.d/99-build-gate.sh` -- new selftest fragment (27 legs).

## 2. Files this lane needs to change but does not own (not edited)

- `docs/testing/titles/pathfind.py` -- lane.pathfind's file. Two things:
  - `result.json` (written at `pathfind.py:1689`, initial dict at `:848`) carries `device`, `title_id`, `iso`, and no `ref`, `apk_sha` or `env`. Ask: record the device's build here. Suggested: read `jobs/device_build.py`'s `last_run(D, label)` (the newest result for the device) and put its `ref`, `apk_sha`, `env` in as `device_record`. A pathfind run does not go through the dispatcher, so the installed APK is the last dispatcher run's; say so in the field.
  - No `--ref` exists. Only needed if pathfind is to queue its own runs.
- `docs/testing/titles/drive.py` -- lines 1050-1051 write `mark gameplay` (`self.dev.logcat("mark gameplay")`) whenever the classifier's state is `play` for `confirm_play_s` seconds with `self.mark` set. That is the place a window that is not live play is labelled gameplay: nothing checks live control at that point, and `docs/testing/title_verdict.py:522` and `docs/testing/hitch_report.py:331` read the label as the scored window. The fix is an owner's decision, not a lane's: either the mark waits for the probe-and-change confirmation pathfind uses (`pathfind.py:1112`), or the reviewer retracts it. Not edited.
- `host-tools/lanewaker.py` -- not in this repo, and not readable from this worktree. Ask lane.local to check the keepalive pass (item f): a lane whose `PR.md` says `State: ready` and differs from origin/master must be skipped; a lane with a WAITING file must be skipped; `briefs/<lane>.model` must be honoured. Also: does lanewaker resume a finished lane through `lane.sh resume`? That spends an attempt (`lane.sh` `next_attempt`).

## 3. Corrections to the brief, for the record

- The fourth attempt on a lane runs `MODEL_LANE_ESCALATED`, which `docs/testing/jobs/models.env` sets to `claude-fable-5-1`, not Opus. Fourth start is refused at `LANE_MAX_ATTEMPTS=4`.
- `result.json` already records `ref`, `apk_sha`, `env` and `device_label` for the dispatcher's soak and disc runs. Only `pathfind.py` lacks them.

## 4. Found in attempt 2, fixed in `dispatcher.sh` (granted)

- The master restore request had no title and no suites, so it fell to the disc path and was refused with `NO SUITES` (`dispatcher.sh` ~1587). The device would have kept the test build. Fixed: `serve_one` ends a `dispatch.restore` request after its build, install and env reset, writes `result.json` with `kind: "restore"`, and marks DONE. Leg (j) covers it, and its mutant goes red. This is inside the granted `dispatcher.sh`; no new file.

## 5. Pending (after 22:00 only)

- One 60 s Nova smoke, in the lane build, after 22:00 and when the Nova is free. Then the master restore: the dispatcher's own restore request, which is now the first device proof of section 4. The smoke is not queued before 22:00 (lane.local's instruction).
- `pathfind.py`'s receipt (section 2) is lane.pathfind's, for after 22:00.
