# crashattr: a title verdict counts only hakuX's own crashes, not the device's

State: draft

```
Lane: crashattr            Issue: none (harness defect, dispatched directly)
Base: master @ 2790e4b700
Files: docs/testing/title_verdict.py, docs/testing/jobs/selftest.d/89-title-verdict.sh, docs/lanes/crashattr/NOTES.md, docs/lanes/crashattr/PR.md, docs/lanes/crashattr/falsify.py, docs/lanes/crashattr/crashattr.diff
Prediction: none: harness log parsing, no arm (verified by replaying 965 dispatch result logcats)
Needs device: no    Needs NDK: no
```

Release note (none): harness verdict only; no emulator code changes.

`title_verdict.py` scored any `F/libc` or `F/DEBUG` line as a hakuX crash. Those
tags belong to the whole device, so three 10-02 Nova runs (ToeJam & Earl III,
Tron 2.0 x2) failed on Android's `media.extractor` aborting, and one 09-26 run
on `surfaceflinger`.

The fix judges a tombstone by its `Cmdline:` (falling back to `>>> name <<<`)
and a libc line by its pid. A libc `Fatal signal ... pid N (name)` line also
counts by its 15-character comm. A tombstone that names no process does not
count.

The pid check is needed, not optional. hakuX's handler re-raises under
`SIG_DFL`, so none of the 9 real hakuX crashes in results/ left a tombstone or a
named line. Each left only a nameless `FORTIFY:` or `exiting due to SIG_DFL`
line from hakuX's pid, which a name-only check would have dropped.

| set | runs | old crash | new hakuX crash lines |
|---|---|---|---|
| media.extractor bystanders | 3 | true | 0 -> crash false |
| surfaceflinger bystander | 1 | true | 0 (crash stays true from run.log `guest exited`) |
| real hakuX libc crashes (09-29) | 9 | true | 1-2 -> true |
| hakuX-crash BugCheck | 2 | true | 10 -> true |
| bystanders renamed to a hakuX process | 4 | true | 1-188 -> true |

Old and new differ in exactly the 4 bystander runs out of 965. The three 10-02
runs still fail on duration or an unconfirmed generic route, so none of them
becomes Playable from this change.

Local checks: `falsify.py` 0 of 19 rows wrong. With the patch,
`SELFTEST_ONLY=89-title-verdict` gave 114 passed, 0 failed, with 5 new mutants
each caught. `99-hitch-report` and `66-status-titles` gave 30 passed, 0 failed.
Full `jobs/selftest.sh` on a scratch tree with the diff applied: all 120
fragments, 0 failed (97 in one run before its 50-minute cap, 2582 ok; the
other 23 in a second run, 361 passed). `preflight.sh`: pending, run once the
diff is applied on the branch.

Waiting: the territory grant for `title_verdict.py` (lane.routedriver2) and
`89-title-verdict.sh` ([free]). See NOTES.md, "Territory".

🤖 Generated with [Claude Code](https://claude.com/claude-code)
