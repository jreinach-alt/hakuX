# Audit pass 1: PR #420, lane/pilotgate

Head audited: `0de649437d`. Base: master @ `9f5a3dfc98`.
Files: `docs/testing/request.sh`, `docs/testing/jobs/selftest.d/99-pilot-gate.sh`,
`AGENTS.md`, `docs/testing/jobs/roles/lane.md`, `docs/lanes/pilotgate/NOTES.md`.

**Verdict: 2 MEDIUM, 4 LOW. Needs remediation.**

The gate works for a direct call to `request.sh`. Its estimate matches
`[device-budget]` in `host-tools/harness_health.py` (lines 395-414: same
formula, same globs, same key, same thresholds). The comparison is `>`, the
pilot file's age is checked, and `running/` is counted. The two MEDIUM findings
are both about callers of `request.sh`. One is the writer behind the incident
that motivated the gate, and it sidesteps the gate. The other turns a refusal
that should clear once the queue drains into a skip that never clears.

## MEDIUM 1: titleplay's `queue.py`, the writer behind #397, runs the gate against a private staging dir

`docs/lanes/titleplay/tools/queue.py` (on master) calls
`request.sh --who titleplay` with `DISPATCH_DIR=<mkdtemp staging dir>`. It then
re-keys each record as `0-0-y-<ts>-titleplay-<tag>-<label>` and renames it into
the real `$D/queue/`. The 29 soaks of pass 1 went through this path
(`docs/lanes/titleplay/NOTES.md:8`, `:48`; every `0-0-y-1790433159-titleplay-p1-*`
result has `requester: titleplay`, `seconds: 420`, `runs: 1`). The PR's
"Writers of `queue/`" list does not name it. The new gate reads `$D` from
`DISPATCH_DIR`, so every sum and every pilot lookup runs against the staging dir:

- **A reviewed pilot cannot admit the batch.** The staged records stay in
  `<stage>/queue/` (queue.py reads `src` and never removes it). Each staged
  soak counts 510 s, so line 4 of any plan comes to 2040 s and is refused.
  The refusal says to write `<stage>/pilots/titleplay.ok`, a path in a
  tempdir that does not exist yet when queue.py starts. A verdict written to
  the real `$DISPATCH_DIR/pilots/titleplay.ok`, as the rule text says, is
  never read. So titleplay's pass 2, after a reviewed pilot, is refused at
  line 4 with advice it cannot follow.
- **Splitting the plan gets past the gate.** Each invocation gets a fresh
  staging dir, and the real queue and `running/` are never counted. Running
  queue.py ten times with three-line plans queues 30 soaks, about 4.25 h, with
  no pilot and no refusal. That is the same shape as the #397 incident.

Remedy, one of: have queue.py stage the record some other way and run the
gate against the real `$D`, for example a `--stage-dir` or `--emit-only`
mode in `request.sh` that writes the record elsewhere but still sums and
checks pilots in the real dispatch dir; or give the gate its own variable
for the dispatch dir it counts (such as `PILOT_DISPATCH_DIR`), default `$D`,
and have queue.py set it to the real dir. Either way, add queue.py to the
writers table and add a selftest leg in which `DISPATCH_DIR` is a staging dir
while the real queue already holds the requester's time.

## MEDIUM 2: arms records a pilot-gate refusal as permanent, and tells the lane to fix the prediction

`arms.sh` treats every non-zero exit from `request.sh` as `refused()`
(arms.sh ~847-853). That writes `skipped/<sha>` with `request.sh refused`
and the current `ARMS_VERSION`. `already_ran()` (~258-282) then returns 0 for
that sha on every later tick. The marker is reconsidered only when `arms.sh`
itself changes, or when the prediction file changes (a new sha). Before this
PR, every `request.sh` refusal was a property of the prediction, so that was
correct. The pilot gate is the first refusal that depends on queue state: it
clears once the requester's earlier arms have run. Arms never retries it, and
the comment it posts says "Fix the prediction ... The prediction is not on the
device until this is fixed", which is wrong advice.

The arms requester is `arms-<name>-base` / `-fix`, where `<name>` comes from
the prediction's `who`. On master, 30 predictions have `who: lane.remote`, so
every remote lane's arms share `arms-remote-base`. Concrete scenarios:

- A prediction with `runs_per_arm: 12` or more: (60+90) x 12 = 1800 s, so 13
  or more is refused on an empty queue. It is skipped forever, told to "fix
  the prediction", and the lane cannot see the dispatch dir. One prediction on
  master already has `runs_per_arm: 10` (1500 s). With a single other
  runs-3 arm of the same `who` queued (450 s), the total is 1950 s and it is
  refused permanently.
- Several remote lanes register predictions while the devices are busy.
  Twelve runs-1 arms under `arms-remote-*` queue at once, and the thirteenth
  is refused permanently, although the gate would admit it an hour later.

The rule text also never says what a lane writes to get an arm past the gate:
the file names are `pilots/arms-<name>-base.ok` and `pilots/arms-<name>-fix.ok`,
and an arm is not a pilot-and-batch shape anyway.

Remedy, one of: exempt `arms-*` requesters (arms are admitted per prediction
and already paired; a requester like `arms-remote-*` pools unrelated lanes'
arms under one name); or have `request.sh` exit with a distinct code or tag
for the pilot refusal, and have `arms.sh` leave no `skipped/` marker for it,
so the next tick retries, with the lane told once, accurately. Add a selftest
leg for whichever you choose.

## LOW

- **L1: the key is the free-form `--who`.** `ab_bisect.sh` queues each step
  as `$WHO-$tag`, and `ab_run.sh` uses `-base`/`-fix`, so each is judged
  alone. Any caller can spread a batch over several `--who` values. The rule
  text says "requester (`--who`)", so this is documented, but the owner's
  "no requester" means a lane, and the gate cannot see a lane.
- **L2: a malformed record of the same requester crashes the gate.** A
  `queue/*.req` for the same requester with `"seconds": "420s"` or
  `"runs": "3x"` raises in `est()`, which is outside the `try`. `request.sh`
  then exits 2 with a Python traceback instead of the gate's message. It
  fails closed, and `request.sh` itself only writes ints.
- **L3: check-then-rename race.** Two concurrent enqueues by one requester
  can each see the other's record missing and both be admitted. `arms.sh`
  queues sequentially, so this needs two hand callers.
- **L4: the selftest leaves two branches of the estimate untested.** Every
  fixture and every `pg_rq` request has `runs` 1 and `seconds` > 0. A mutant
  that drops `* runs`, or the `sec > 0 ... else 180` branch, passes all 10
  checks. One fixture at `runs: 3` placed at the edge, plus one at
  `seconds: 0`, would catch both.

## Not findings

- The formula, globs, key and thresholds match `harness_health.py`.
- The temp record is removed on refusal, and leg A checks it.
- The refusal is judged on its words and on the queue, not the exit code. The
  admissions are anchored on the `^queued <id>$` line.
- CI at audit time: `build` passed twice; `selftest` was still pending.
  Pass 2 should confirm it is green.
