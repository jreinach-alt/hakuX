# Audit pass 1 — PR #206, `claude/dispatch-script-deps`

*dispatcher: hash every file the snapshot ships, or an edit never reaches a
worker*

- **Auditor:** `job.cloud`, 2026-09-24, pass 1 (diff read)
- **Diff read:** `gh pr diff 206`, 4 files, +284/−2
- **Head at audit:** `4229a1216d`, CI `build`/`build`/`selftest` all SUCCESS,
  `MERGEABLE`/`CLEAN`
- **Verdict:** 1 HIGH, 2 MEDIUM, 5 LOW → `needs-remediation`

---

## What the diff is

Two changes and two guards:

1. `dispatcher.sh` — `SCRIPT_DEPS` widened from 4 files to the 9 that
   `snapshot_scripts` copies, so `src_hash` moves when any of them changes and
   a worker re-execs onto the new snapshot.
2. `fleet.py` — a new `queue_stall()` and a new `FAIL` path, so a dispatch
   request nobody claims wakes the board instead of rendering as a busy fleet.
3. `selftest.d/97-dispatch-deploy.sh` — asserts set(`SCRIPT_DEPS`) ==
   set(`snapshot_scripts`).
4. `selftest.d/98-fleet-queue-stall.sh` — five fixtures over `queue_stall()`.

**Change 1 is correct and I could not break it.** Checked against the tree
rather than against the comment:

| claim | checked |
|---|---|
| `snapshot_scripts` ships exactly those 9 | `dispatcher.sh:108-109` — same 9, same names ✔ |
| the widened list parses as 9 words | the `\`-newline inside the double-quoted assignment is a line continuation and is removed; `src_hash`'s unquoted `cat $SCRIPT_DEPS` therefore sees 9 operands, none of them glob characters ✔ |
| the live snapshot holds those 9 | `dispatch/bin/` = exactly those 9 files ✔ |
| a wider hash cannot re-exec mid-run | the hash check is at the top of the worker tick loop, before `reqs=(...)`; `serve_one` is synchronous, so a re-exec can only land between requests ✔ |
| it deploys itself | `dispatcher.log` shows the re-exec at 09-20 21:53:10 and again 09-21 08:58 ✔ |

**Change 2 is where the findings are**, and one of them is in the guard for
change 1. The two selftest fragments are well built — both refuse to be
vacuously green, `97`'s non-empty + anchor-member checks are exactly the right
shape, `98`'s three quiet cases are as load-bearing as the loud one and the PR
body is right to say so. What neither fragment can see is what the check means
on a fleet with more than one request in it.

---

## HIGH

### H1 — `queue_stall` cannot tell "passed over" from "waiting its turn", which is the whole distinction it claims to draw

`docs/testing/fleet.py:275`

```python
stalled = [(i, now - t) for i, t in pending if newest_result > t]
```

`newest_result` is the newest mtime of **any** directory under `results/`. The
docstring says the discriminator is "did a result land after this was queued",
offered as a proxy for "the fleet FINISHED OTHER WORK, so I am being skipped".
Under this queue's own service discipline that inference does not hold:
requests are served in ASCII order, i.e. in arrival order, so **every request
that is not at the head of the queue** has results landing after its
`queued_utc` as a matter of course — those are the requests ahead of it being
served, in order, exactly as designed. `results/<id>` is also `mkdir`ed at
**claim** time (`dispatcher.sh:587`), so a run still in progress bumps
`newest_result` too: the very run this request is queued behind is counted as
evidence that the fleet skipped it.

**Failure scenario.** `arms.sh:74` queues up to `ARMS_QUEUE_MAX=4` requests in
one burst; `affinity.py` rule 2 pins an A/B pair to a single device, so a burst
of two pairs can land two pairs on one handheld while the other serves a soak
or is held. Arm service times on this fleet are 6–93 min
(`1789963700-blendarm50-1474765` was 93.4 min queue→done). The 3rd and 4th arms
in that burst cross 120 min while being served strictly in order; `queue_stall`
returns them, `fleet.py` prints `FAIL: 2 dispatch request(s) have waited over
2h with devices serving`, and `board.sh:279` starts a model session on that
`FAIL` **every tick until the queue drains** — for a fleet that is doing
nothing wrong. The PR body sets this standard itself: "a FAIL that fires on a
healthy fleet spends a window every twenty minutes for nothing."

**Why the fixtures cannot see it.** `98`'s "backlog → quiet" case
(`qs 300 400 0`) has exactly one request and one result, and stays quiet only
because *nothing at all* completed after the request was queued. That is not
what a backlog looks like; a real backlog is other requests completing while
you wait, which is the flagging case. Every fixture in `98` has a queue depth
of one, so the whole FIFO population is outside them.

**The correct signal is already on disk.** `request.sh:684` builds the id as
`$(date +%s)-$WHO-$$`, so a result directory's name carries the **queue**
epoch of the request it served. "A request queued after me was completed while
I waited" — which really is being skipped, and really is what happened in the
incident this PR fixes — is `max(queue-epoch of completed results) > my
queue-epoch`, parsed from the directory name. That also removes the
in-progress-run problem, since it does not use mtime at all. (See L1: the
comment at `fleet.py:264` asserts the opposite about those names, which is
presumably why mtime was reached for.)

---

## MEDIUM

### M1 — `all_held` counts every file in `lanes/` as a serving lane, with no liveness test and no regard for which lanes can claim the request

`docs/testing/fleet.py:281-287`

```python
lanes = {l for l in os.listdir(os.path.join(D, "lanes")) if not l.endswith(".lastbrief")}
held  = {h for h in os.listdir(os.path.join(D, "hold")) if not h.endswith(".why") and h != "lifted"}
all_held = bool(lanes) and lanes.issubset(held)
```

Two problems, one exclusion:

- **No `kill -0`.** `affinity.py:90` `serving()` is explicit that a lane file
  is a *pid* and that liveness is the only test that survives — "a list written
  by the supervisor outlives the worker it describes, and the worker is the
  thing that dies (one lane was silently down for 25 minutes on 2026-09-12)".
  This re-implements lane enumeration without that test, so a lane file left by
  a SIGKILLed worker — the exact leak `lane_release` exists to bound — is
  counted forever.
- **The wrong denominator.** The live `lanes/` is
  `{desktop, nova, thor}`. `desktop` is `desktop_channel.sh serve`, which
  claims *only an explicit `--device desktop` pin* (`desktop_channel.sh:556`)
  and can never claim a handheld request. For a queue of handheld requests the
  serving set is `{nova, thor}`.

**Failure scenario.** The documented out-of-service gesture is
`touch $D/hold/<label>` on the handhelds (`dispatcher.sh:1235`). An operator
holds `nova` and `thor` with four arms already queued and results already on
disk from before the hold: `pending` is non-empty, `newest_result > t` holds
(those earlier results), so `stalled` is non-empty; `lanes = {desktop, nova,
thor}` is not a subset of `held = {nova, thor}`, so `all_held` is False and the
loud branch runs. The board is woken every tick for the whole duration of a
deliberate hold — which is precisely the noise the PR body names the exclusion
as existing to prevent. As written the quiet branch is unreachable on this
dispatch dir unless somebody also holds `desktop`, and nothing tells them to.

### M2 — the invariant the guard asserts is not the invariant the deploy needs: `sweep_queue.sh` is executed from `$SNAP` and is in neither list

`docs/testing/jobs/selftest.d/97-dispatch-deploy.sh:59` (the `$DEPS = $SNAPPED`
check)

The set that decides whether an edit reaches a worker is **the files a worker
executes out of `$SNAP`**, and `SCRIPT_DEPS`/`snapshot_scripts` is only a
subset of it. A worker is `exec bash "$SNAP/dispatcher.sh" worker "$SERIAL"`
(`dispatcher.sh:1315`), so `HERE` is `$SNAP` for everything it invokes. Of the
sibling scripts `dispatcher.sh` calls through `$HERE/`, eight are shipped —
and `sweep_queue.sh` (`dispatcher.sh:347`, `:353`) is not. Confirmed on the
live host: `dispatch/bin/` holds exactly nine files and `sweep_queue.sh` is not
among them, while `docs/testing/sweep_queue.sh` exists and was touched today.

**Failure scenario.** The corpus sweep is running; an agent request arrives;
`serve_one` calls `preempt_sweep`, which logs "preempting the sweep" and then
runs `bash $SNAP/sweep_queue.sh pause` → exit 127, no such file, appended to
`dispatcher.log`. Nothing checks that status. The sweep runner is **not**
parked, `$SWEEP_STATE/PAUSE` is never created, the dispatcher installs the
experimental APK on the same device, and the sweep's following rows come from
the wrong binary — the failure `sweep_queue.sh:11-19` says the pause/resume
protocol exists to prevent. `resume_sweep` then never fires, because it gates
on the `PAUSE` file that was never written.

This is a pre-existing hole, not one this diff opens — but this diff is the
one that writes the deploy invariant down and installs a green check over it,
and a passing `97` is now the evidence anyone will cite for "the deploy set is
correct". Either ship `sweep_queue.sh` (one word in two lists, and `97` then
covers it), or have `97` assert the third set directly: every `$HERE/<file>`
invoked by a shipped script is itself shipped.

---

## LOW

- **L1 — `fleet.py:264-266`** asserts "A result directory is named with the
  epoch of the CLAIM, not of the queueing". It is named with the epoch of the
  **queueing**: `request.sh:684`, `ID="$(date +%s)-$WHO-$$"`, built when the
  request is written. Two live pairs confirm it —
  `1789968297-arms-primpv13-base` and `…-fix` share one epoch and were served
  10 min apart. The comment is the stated justification for reaching for mtime
  instead of the name, so correcting it is part of H1's remedy.
- **L2 — `fleet.py:854`** inserts the new block between the
  "NON-ZERO, LIKE THE OTHERS" comment and the `if unclaimed:` block that
  comment documents ("the lane is editing files nothing knows it holds"). A
  reader now attributes it to `queue_stall`.
- **L3 — `fleet.py:863`, and `fleet.py:195`** the operator-facing FAIL text cites
  `dispatcher.sh:508` for "a pin to a lane that is registered but served by no
  worker is claimed by nobody". Line 508 is `lane_claim() {`; the skip it means
  is `serve_one` at `:556-559`. Prefer naming the function
  (`serve_one`'s affinity check) — a line number in a message drifts on the
  next edit to that file.
- **L4 — `98`** exercises `queue_stall()` and never the emission: nothing
  asserts that a stall prints `^FAIL` on **stderr** (which is what
  `board.sh:279` greps, via `2>&1 >/dev/null`) and sets `rc`. Delete the call
  at `fleet.py:854` and the suite stays green. One check that runs `fleet.py`
  against a stalled `$DISPATCH_DIR` and greps its stderr would close it.
- **L5 — process.** The PR body has no `roles/lane.md` header block — no
  `Lane:`, `Base:`, `Files:`, `Prediction:`, `Needs device:` — and there is no
  `docs/lanes/<lane>/NOTES.md` in the diff. Nothing machine-reads `Files:`, but
  the board does, to keep two lanes off one file; with `dispatcher.sh` and
  `fleet.py` undeclared, a second lane can be handed either of them and both
  preflights will pass. Add the block (`Files: docs/testing/dispatcher.sh,
  docs/testing/fleet.py, docs/testing/jobs/selftest.d/97-dispatch-deploy.sh,
  docs/testing/jobs/selftest.d/98-fleet-queue-stall.sh`,
  `Prediction: none: harness-only`).

---

## What pass 2 must verify

Not that a commit exists — that each scenario above can no longer occur:

1. **H1** — a request that is merely waiting behind other work is not
   reported. Needs a fixture with queue depth > 1: two requests queued in one
   burst, the earlier one completing after both were queued, the later one past
   the threshold → quiet. And a request skipped by a **later-queued** request
   that completed → FAIL.
2. **M1** — with `lanes = {desktop, nova, thor}` and `hold = {nova, thor}`,
   the quiet branch is taken; and a lane file holding a dead pid does not keep
   the quiet branch from being taken.
3. **M2** — either `sweep_queue.sh` is in both lists and `97` covers it, or
   `97` fails against a mutant that adds a `$HERE/<unshipped>.sh` call to a
   shipped script.
4. **L4** — a mutant that deletes the `queue_stall()` call in `main` turns the
   suite red.

Every fix above is in `fleet.py`/`dispatcher.sh`/`selftest.d` only; no device
run is needed to verify any of them.
