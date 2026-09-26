# Audit pass 2: PR #307, lane/titlerun

Head verified: 503a2dcfa8 (remediation of pass 1, commit 503a2dcfa8 on top
of 30962fb809).  Pass 1: `docs/audits/2026-09-26-titlerun-pass1.md`.

**Verdict: not clean -> needs-remediation.**  M2 no longer occurs.  M1's
verdict half is fixed, but the new restart in `soak_title.sh` passes the
stamp to logcat inside literal quotes.  On a real device every restart then
fails, the capture stops at the first drop, and the verdict fails a title
that plays correctly with a wrong reason and `capture_lost_s = 0`.

## M1: still fires, through the new restart

### What is fixed

The pass-1 fixture now gets the right answer: `capgap` (12 s lost once and
5 s lost eight times, guest at a steady 30 fps).  Run against this head:

    PASS Playable gameplay=660.0s fps_ok=1.0 hang=False capture_lost=73.5s

Windows that span a gap are not scored.  Hang gaps have the capture gap
subtracted.  A replayed duplicate is read once.  The gaps are reported.
If the ring replay works, this half of the fix is correct.

### What still fires: `-T "'$last'"` (soak_title.sh:139)

The comment says "adb joins its arguments into one device shell command, so
the stamp's space needs the inner quotes."  That is true for `adb shell`,
which is why route.sh's `"'mark $1'"` works.  It is not true for
`adb logcat`.  AOSP `adb/client/commandline.cpp` `logcat()` builds
`export ANDROID_LOG_TAGS=...; exec logcat` and then appends
`escape_arg(arg)` for each argument.  The host's `/usr/local/bin/adb`
carries exactly those template strings (`export ANDROID_LOG_TAGS=`,
`; exec logcat`, ` -v long`).  With the per-argument escape reproduced and a
stub `logcat` that prints its argv, the device receives:

    exec logcat '-v' 'time' '-T' ''\''09-25 13:04:59.500'\'''
    argv[-T]
    argv['09-25 13:04:59.500']

The quote characters reach logcat.  logcat's `-T` parser
(`strptime "%m-%d %H:%M:%S.%q"`) rejects a leading `'`, prints
"not in time format" to stderr (which the soak sends to /dev/null), and
exits.  The loop counts that as another drop.  All `LOGCAT_RESTARTS` (30)
tries are used up in about 60 s, and nothing is captured after the first
drop.  The `soak end` line is lost too.

Falsifier, run against this head.  The fixture is the selftest's `pass`
run, but the capture ends at 300 s, followed by 31 break lines and nothing
else, as the loop above would write it.  The verdict is:

    FAIL(duration: 199 s of gameplay < 600 s screening)  capture_gaps_s=[] capture_lost_s=0

The guest plays for 660 s.  The verdict fails it on duration and gives no
sign that the instrument lost data.  This is the pass-1 M1 failure class,
and a first drop is now enough to trigger it, where pass 1 needed a long
gap.

The selftest pins the bug instead of catching it.  selftest.d/89 l.304
asserts that the fake adb was called with `-T '09-25 13:00:01.000'` (quotes
included).  The fake adb does not escape the way real adb does, so the check
is green on exactly the argument that real logcat rejects.

### A second, independent gap: a break that never closes is not reported

parse_logcat (title_verdict.py l.118-140) records a gap only when a line
arrives after the break.  If the capture never resumes (restarts exhausted,
or the device stays away until the hold ends), `pending` is dropped.
`end_t` then falls back to the last captured line, and the run reports
`capture_lost_s = 0`.  The falsifier above shows this even without the
quoting bug.  It needs no quoting error, only a stream that stays down for
the last 31 restarts.

### Remedy

- Pass the stamp as a plain argument, `-T "$last"`, because `adb logcat`
  escapes each argument itself.  Make the selftest's fake adb reproduce
  `escape_arg` and a `-T` parse, or assert on the unquoted form, so that the
  quoted form fails the check.
- In the verdict, treat a break with no line after it (or a run with no
  `soak end` line in logcat while run.log shows the soak ran to its end) as
  lost capture up to the soak's end.  Report it (e.g. `capture_truncated`),
  and name it in the reason when duration or reached_gameplay fails.  Add
  the fixture above and assert that the reason names the capture, not the
  duration.

## M2: no longer occurs

`route.sh` `mark_logcat` makes three tries 2 s apart, and non-empty output
on exit 0 counts as a failure.  The verdict reads
`mark <x>: logcat write FAILED` from run.log and names it even when other
marks reached logcat.  The pass-1 scenario (`mark booted` present,
`mark gameplay` only in run.log with FAILED) gives, against this head:

    FAIL(reached_gameplay: no `mark gameplay` in logcat (the route played
    `mark gameplay`, but its logcat write FAILED after its retries: see run.log))

That reason is correct.  `adb shell log ... "'mark $1'"` uses `adb shell`,
which joins its arguments without escaping, so the inner quotes are right
here.

## LOWs

The remediation did not touch L1 (single-shot release), L3 (`table.py`
ordering) or L4 (probe lease time).  L2 (`fps_tolerance`) is still for the
owner to decide.  None of them blocks.
