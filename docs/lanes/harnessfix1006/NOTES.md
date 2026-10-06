# lane.harnessfix1006 -- the Nova's runs are on a known build; a test build never stays on it (#433, 0.5)

Brief: `/home/justin/hakux-work/briefs/harnessfix1006.md`. Attempt 1 of this lane.

## Why the previous attempt did not finish

The branch `lane/harnessfix1006` had no commits beyond master, no pushed ref,
no PR, no `docs/lanes/harnessfix1006/`, and no NOTES when this session began
(the worktree was clean at `bf85412b88`, master). Nothing on disk records what
it did or why it stopped, so the cause is unknown. The likeliest reading is
that it ended before its first commit. This attempt starts from the brief,
not from a previous attempt's work.

## What the brief's premises turned out to be (claims checked, not taken on trust)

- **(e) "every Nova run writes ref, apk_sha and env into result.json".** Already
  true for the dispatcher's two result writers. The soak writer
  (`docs/testing/dispatcher.sh`, the `kind="soak"` dump) writes `apk_sha`,
  `ref`, `env` (from `req_env`) and `device_label`. The disc writer (the
  `meta` dict, `meta["env"]` from `REQ_ENV_JSON`, `meta["device_label"]`)
  writes the same. What the dispatcher does not write is anything for
  `titles/pathfind.py`: that tool's `result.json` (`pathfind.py:848`,
  `:1689`) has `device`, `title_id`, `iso` and no ref, apk_sha or env, and
  pathfind.py never calls `request.sh`. The OUTBOX line "device record not
  readable" comes from lane.pathfind's own tooling, which is not in this
  repo's `docs/testing` tree and was not found in this worktree. **Not fixed
  here:** `pathfind.py` is lane.pathfind's file. See OUTBOX.md.
- **(e) "pathfind.py passes no ref".** Confirmed: no `--ref` anywhere in
  `docs/testing/titles/pathfind.py`.
- **(f) "lanewaker already patched in host-tools/lanewaker.py".** Not checkable
  from this worktree. The sandbox refuses paths outside
  `/home/justin/hakux-work/wt/harnessfix1006`, and `host-tools/` is not in the
  repo (`git ls-files` finds no `lanewaker`). **Not verified; lane.local must
  check it.** See OUTBOX.md.
- **(f) "lane.sh escalates to Opus on attempt 4".** Wrong model name in the
  brief. `docs/testing/jobs/models.env` sets `MODEL_LANE=claude-opus-5-5`,
  `MODEL_LANE_ESCALATED=claude-fable-5-1`, `LANE_ESCALATE_AFTER=3`,
  `LANE_MAX_ATTEMPTS=4`. The attempt after three goes to Fable, and the
  fourth start is refused. `lane.sh` line 205-221 (`next_attempt`) does this,
  and it ignores the per-lane `briefs/<lane>.model` once `n > LANE_ESCALATE_AFTER`.
- **"gameplay" mislabel.** Named below (section "The gameplay label").

## What changed (this lane's branch)

1. **`docs/testing/jobs/device_build.py` (new).** Reads the device's newest
   `results/*/result.json` (by mtime, `device_label == label`) and says whether
   that build is master: `ref` in `master`/`origin/master` (or `MASTER_SHA`),
   and `env == []`. A result with no `env` key is not master, because the
   build it ran is then unknown. `check` exits 0 on master or no run, 4 on a
   non-release build with a line naming the build. `restore` writes one
   60 s `dispatch.restore` request (ref `master`, env `[]`, device label) into
   `queue/` when the run is off master, and writes nothing for a run on master
   or for a restore run (no loop).
2. **`docs/testing/jobs/hold.sh`.** `build_gate` runs before `take` and before
   `wait`'s loop, for the labels in `HOLD_RELEASE_LABELS` (default `nova`; empty
   turns it off). On a non-release build the take is refused, exit 4, and
   nothing is written under `hold/`. The refusal names the build on stderr.
   The Thor is not gated: its screening runs vary env on purpose.
3. **`docs/testing/dispatcher.sh`.** `queue_master_restore <id>` (after the
   `lane_file` helper) calls `device_build.py restore` and logs the result; it
   never fails the run. It is called before `touch "$rdir/DONE"` in both the
   soak branch and the disc branch.
4. **`docs/testing/jobs/selftest.d/99-build-gate.sh` (new).** 27 legs, of which
   the mutant-sanity legs prove the two mutants (gate removed, restore never
   asked) actually do what their real legs refuse. Run with
   `SELFTEST_ONLY=99-build-gate.sh`: 27 passed, 0 failed (`selftest-pass.txt`).
   Run against a `hold.sh` with the gate line replaced by `:`
   (`SELFTEST_HOLD_SH`): (b), (c), (d) and the gate-presence leg go red
   (`selftest-mutant-nogate.txt`). The mutant is what the owner's incident
   looks like: the take succeeds on a test build.

## The gameplay label

`docs/testing/titles/drive.py:1050-1051`. The driver writes `mark gameplay`
into logcat when its classifier state is `play` for `confirm_play_s` seconds
with `self.mark` set. Nothing checks that the window is live player control
at that point: the state is the classifier's own call, and the frames are
reviewed only later. That is how a window that is not live play gets the
label that `title_verdict.py` (`:522`, `gp = [... lab == "gameplay"]`) and
`hitch_report.py:331` then score as the gameplay window. The dispatcher
comment at `docs/testing/dispatcher.sh` ("a Crimson Skies soak's 'gameplay'
frames were ... a dialog", #474) is the documented case. **Not fixed:**
`drive.py` is not in this lane's grant. The fix needs a decision: either
`mark gameplay` waits for the probe-and-change check that `pathfind.py`
uses (`pathfind.py:1112`), or the route's mark is retracted by the reviewer.
Named in OUTBOX.md for lane.local.

## Lanewaker and attempts (item f, the question the brief asks)

Not verified from this worktree (see above). What the repo shows:

- Every `lane.sh start` and `lane.sh resume` is one attempt
  (`next_attempt`, `lane.sh` line 205). `handback.sh` resumes a parked or
  stranded lane through `lane.sh resume` and says in its own comments
  (`handback.sh` ~1529-1545) that each resume counts, and rolls the count back
  on a failed resume. A `waiting:` lane is not stranded (`handback.sh`
  ~1454-1474), so it is not resumed on that path.
- Whether lanewaker's keepalive pass resumes a `State: ready` lane through
  `lane.sh` is the open question for lane.local. If it does, that spends an
  attempt on a finished lane, and that is the thing to fix there.

## Preflight

`docs/testing/preflight.sh` on the branch: every gate ok except `coverage`,
which fails on #859 ("NHL Hitz Pro hangs on the loading screen"): an open
issue with no lane and no `blocked_on`. That row is the board's, not this
lane's, and this lane's diff does not touch territory or nv2a files.
Run with `--allow-tracker` too, the same gate still failed (exit 1), so the
escape did not cover it; the failure is reported, not hidden. The run's output is
`preflight-run.txt`.

## Not done, and why

- The 60 s Nova smoke. It runs after the fix lands in the lane build and the
  grants are in, and the Nova is held by lane.pathfind (`nova.why`: NBA 2K3
  held run). Not queued this session: a queued request would wait behind that
  hold, and the brief says a smoke goes in a gap, which this session cannot
  see.
- `pathfind.py` result fields (ref, apk_sha, env) and the OUTBOX reader. Not
  this lane's file.
- The `drive.py` gameplay fix (decision above).
- The lanewaker verification (sandbox).
- The restore's real dispatch: `queue_master_restore` writes a `.req` file
  named `<epoch>-dispatch.restore-<tail>.req`, and the dispatcher's queue
  reader is not confirmed to accept a `dispatch.restore` requester or a
  request with `title: ""` and no `program`. Must be read by lane.local against
  `dispatcher.sh`'s queue walk before the smoke.

## What the next lane should not repeat

- Do not gate on "the Nova's build" from `hold/` or `running/` alone: a
  running request owns the device without writing a result yet. The gate
  reads results, which is the only record of what ran.
- Do not add an override to skip the gate for a lane. A lane that needs a test
  build gets it through a request, and the restore follows.
