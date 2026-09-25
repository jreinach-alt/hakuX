# Audit pass 1: PR #249 (lane/toolsmith), dispatcher hardening, defects 0-10

Auditor: job.cloud, 2026-09-25. Head audited: `709b99dd7b`. The diff was read
against `origin/master`, 15 files. CI on this head: build ×2 and selftest are
green.

The file is named `-249-` because `2026-09-25-toolsmith-pass1.md` already
holds PR #229's pass 1 for the same lane on the same date.

**Result: 1 MEDIUM, 5 LOW, 0 HIGH. Next state: `needs-remediation`.**

The core of defect 0 is correct. `void_reason`/`compare`/`judge`/`report` keep
void rows out of every class and total. `judge` alone sees them, the INCOMPLETE
and UNJUDGED lines carry neither PASS nor FAIL, and `--probe` refuses. A real
FAIL still wins over void legs. `adb_call`'s control flow is right: `a || b && c`
breaks on success or on retries exhausted, and 124 and 137 are both a hang and
are never retried. run_disc.sh sources devices.sh, and its long-lived logcat
reader stays unwrapped. The half-run rule in arms.sh (two distinct refs) does
what the ARM ERROR recipe needs.

## MEDIUM

### M1. INCOMPLETE says "Re-run the arm", and nothing can re-run it

`ab_compare.py` (INCOMPLETE branch of `report`) and `jobs/arms.sh` (judge loop,
`already_ran`, `RAN`).

The INCOMPLETE verdict ends with "Re-run the arm; this is not a verdict". But
arms.sh treats it like any other verdict line:

1. The judge loop writes `echo "$verdict" > "$A/judged/$sha"`, so
   `already_ran` is true from then on.
2. Both halves carry a clean `request.json` with no ERROR. So under this PR's
   own two-ref rule the sha is in `RAN` as well. Deleting `judged/<sha>` and
   `pairs/<sha>.json` (the only re-queue recipe arms.sh publishes) still
   leaves the sha counted as run.
3. `label_decide` skips it (`cls is None`), so the PR gets no label either.

**Failure scenario.** This is the PR's motivating case. A pull truncates part of
one arm, as #224's `42c014b32fab` did with 56 W_param PNGs. That arm still has
captures, so defect 3's 0-capture interop requeue does not fire. ab_compare
correctly prints INCOMPLETE. arms.sh then marks the prediction judged, posts
"Re-run the arm", and never queues it again. The lane follows the ARM ERROR
recipe and deletes the markers, and still nothing is queued. The only path
that works is registering a changed prediction file (a new sha), and no
comment says so. The PR sits unlabelled, and the one verdict it was built to
produce is a dead end.

**Remedy (either).**
- (a) In arms.sh, handle an INCOMPLETE verdict like a half-run pair: do not
  write `judged/<sha>`, or write it and requeue once. Leave the voided results
  out of `RAN`, for example by dropping a marker the RAN walk skips as it skips
  ERROR.
- (b) At minimum, make the verdict text and the arms comment name the action
  that works: "register the prediction again (any edit changes its sha)".

Add a selftest leg that feeds an INCOMPLETE verdict through arms.sh and
asserts the stated recovery actually queues.

## LOW

### L1. Three comments name a selftest fragment that does not exist

`ab_compare.py`, `score_sweep.py` and `dispatcher.sh` all say the
SCORED_STATUSES copies are checked by `selftest.d/35-dispatch-hardening.sh`.
The fragment is `51-dispatch-hardening.sh`. Someone editing one copy will look
for the guard under the wrong name. Fix the three pointers.

### L2. A run whose captures are all unscored now ERRORs as "0 captures"

`dispatcher.sh` result writer: `captures=len(rows)` now counts SCORED rows only.
Suppose a disc's captures all come back `no-golden`, as with a suite that has
no goldens yet or a newly built test. Or suppose they all come back `size`. The
run then gets no DONE and an ERROR saying "ran but produced 0 captures", even
though every capture exists. If the log also has a UtilAcceptVsock line, the
run is requeued as an interop loss. The blast radius is bounded, because arms.sh
refuses suites with no goldens. But the message is false for a direct
request.sh run. Suggest gating the ERROR on `len(every) == 0`, and reporting
"N captures, none scorable (no-golden …)" when `every` is non-empty and `rows`
is empty.

### L3. `adb_call` retries calls its comment does not list as safe

devices.sh says every routed call is safe to repeat. But run_disc.sh's `a` now
routes `am start -a VIEW … rom_path` and `input keyevent` through it as well.
LauncherActivity has the default launchMode. So after an interop drop that
returned non-zero AFTER the intent was delivered, a retried `am start` sends a
second launch intent. That most likely surfaces as a crash or a 0-capture
ERROR, not a silent wrong result, hence LOW. Pass `ADB_RETRIES=0` for
`am start`, or correct the comment.

### L4. Arms that share no capture no longer die

`compare()` now walks `a.captures() | b.captures()`, so `if not rows: die("the
arms share no capture…")` in `main` is unreachable while either arm has a
capture. Comparing two unrelated results, for example discs with disjoint
suites, now prints every capture as VOID. With no prediction the verdict is
"UNJUDGED … VOID" and the exit status is 0, where before it was a refusal.
Restore the check on the intersection (`a.captures() & b.captures()`).

### L5. The interop requeue writes straight into `queue/`

The one-time requeue does `json.dump(r, open("$D/queue/$id.req", "w"))`. That
file is a visible `*.req` before it is complete, and another device's worker
can claim it mid-write. The window is microseconds, but the claim loop's other
writers already use `mv`. Write to a temp name and rename.

## Not findings (checked)

- The shader-cache clear is keyed per device on the apk's sha256. On an env A/B,
  where both arms have the same apk, the first arm after an apk change runs
  cold and the second runs warm. That asymmetry existed before this PR, in
  smaller form, and `result.json` now records `shader_cache`, so it is visible.
  Soak readers should check the field.
- `sweep_queue.sh`: `collect`, `status` and `resume` need none of the four
  build inputs, and `pause` reads the recorded serial. Correct.
- check_coverage's sweep stamp takes `min(lane, sweep)`, a failed scan does not
  stamp, and the selftest covers both.
