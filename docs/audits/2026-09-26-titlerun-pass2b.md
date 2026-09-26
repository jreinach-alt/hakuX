# Audit pass 2b: PR #307, lane/titlerun

Head verified: 18e7b430a5 (it remediates pass 2, `2026-09-26-titlerun-pass2.md`).
Pass 1: `2026-09-26-titlerun-pass1.md`.

**Verdict: clean -> fold-ready.**  Neither MEDIUM from pass 1 can occur on
this head.  Both M1 mechanisms that pass 2 found still firing are closed: the
quoted `-T` stamp, and a break that never resumes being reported as nothing
lost.  The four LOWs are unchanged and none of them blocks.

## M1: no longer occurs

### The restart stamp reaches logcat unquoted

`soak_title.sh:145` now passes `-T "$last"`.  The host's adb
(`/usr/local/bin/adb` -> `/mnt/c/platform-tools/adb.exe`) carries the
`export ANDROID_LOG_TAGS=` / `; exec logcat` template.  That template is the
`logcat()` client path, which applies `escape_arg` to each argument, so the
device's logcat gets exactly `09-25 HH:MM:SS.mmm` as one argv entry.  This
matches logcat's `-T` time format.  `$last` comes from
`grep -oE '^[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}'` over
the capture, which produces that shape and nothing else.

The selftest no longer pins the bug.  The fake adb now runs logcat's `-T`
parse and exits "not in time format" on anything else.  The restart check
asserts the unquoted form.  A new mutant puts the pass-2 quoting back, and
the fragment must catch it because the capture then stops at the drop.

### A capture that never resumes is named, not scored as a short run

`parse_logcat` now returns the open break (`pending`).
`truncated = open_break is not None and not soak_end`, and the verdict puts
`capture: truncated` first among the failure reasons.  Fixtures were rebuilt
from selftest.d/89's own generator and run against this head's
`title_verdict.py`:

| fixture | verdict |
|---|---|
| pass-1 M1 `capgap` (12 s + 8x5 s lost, steady 30 fps) | `PASS Playable gameplay=660.0s fps_ok=1.0 hang=False capture_lost=73.5s` |
| pass-2 falsifier (cut at 300 s, 31 break lines), as `truncated` with `held ... for 758s` | `FAIL(capture: truncated -- ... broke 199 s after the mark and never resumed, about 462 s unseen ...)` `capture_lost=461.5s` |
| the same, with no `held` line in run.log | `FAIL(capture: truncated -- ... broke 199 s after the mark and never resumed ...)` `capture_truncated` |
| cut at 50 s, before the mark | `FAIL(capture: truncated -- ... broke before any mark gameplay was captured ...)` `about 714 s unseen` |
| one overlapping replay at 299 s, then the stream down for good | `FAIL(capture: truncated ...)` `capture_lost=461.5s` |

Pass 2's scenario was "fails on duration and gives no sign that the
instrument lost data", and it no longer occurs.  Every truncated variant
names the capture first.  The overlap-then-die case is the path where
`pending` survives a duplicate line, and it is caught too.

## M2: still closed

`lostmark` (`mark booted` in logcat, `mark gameplay` only in run.log with
FAILED) still gives
`FAIL(reached_gameplay: ... its logcat write FAILED after its retries ...)`.
The pass-2 remediation did not touch `route.sh`.

## LOWs, unchanged, for the owner or a later lane

- L1 single-shot key-up and recentre, L3 `table.py` "latest" by
  `judged_utc`, L4 probe lease time: not touched.
- L2 `fps_tolerance = 0.95`: still a policy value for the owner.
- New, LOW: if run.log has neither `held ... for` nor `guest exited after`
  (the guest never appeared), a truncated capture reports
  `capture_lost_s = 0` and `capture_truncated_s = null`.  The
  `capture_truncated` flag and the reason still say the capture was lost,
  so no reader is misled.
- New, LOW: truncation always fails the run, even when the stream dies in the
  last seconds before `soak end` after a full screening window was captured.
  This needs the stream to stay down through `soak end` and the whole pull
  that follows it (`release` kills the capture last), and the reason names
  the cause.  It costs a re-run, not a wrong verdict.

## State

- CI at 18e7b430a5: build x2 and selftest SUCCESS.  GitHub reports the PR
  MERGEABLE.
- The full jobs selftest was not rerun locally here.  CI is the gate of
  record, and it is green at this head.
