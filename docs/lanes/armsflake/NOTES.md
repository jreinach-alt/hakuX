# lane.armsflake: the 92-arms-skip-told flake

## The cause

`92-arms-skip-told.sh` had three legs that asserted a whole `arms.sh` tick
posted no comment at all (`! grep -qE "^(pr|issue) comment" gh.log`). But
every tick in the selftest fetches the REAL `origin/lane/*` into the real
repository and collects every prediction on it. The fixture's watermark
(`$WORK/arms/since`) is `date -1 minute` at the start of the run, and a host
run takes about 30 minutes. So a lane that registers a prediction while the
selftest runs makes it live in the fake tick. Its keys name none of the two
fixture goldens and its title is a soak, so arms.sh skips it and, correctly,
tells issue #N once. The comment lands in whichever tick first sees the
pushed file. If that is one of 92's "silent" ticks, the leg fails.

Both host failures match a registration inside their run window:

| master tip | run (UTC) | failing leg | registration in the window |
|---|---|---|---|
| 0e0ba23fb9 | 20:57:45 - 21:25:47 | a second tick does not tell it again | forza414-snap-{mnm,soak}.json, registered 21:14:49/21:15:27, committed 21:15:27 (lane.forza414, issue 414) |
| 8a54dcf1b2 | 23:24:35 - 23:54:35 | and nothing is posted for it | forza414-predl-{auf,doa,mnm}.json, registered 23:43:12 on lane/forza414b (issue 474) |

Several passing runs also had a registration in their window (flip474-ts,
flip474-sysmem, drain474). Inferred, not captured: their comment landed in a
tick outside 92's three silent ones (an earlier fragment's tick, or 92's first
tick, whose leg asserts a comment exists). The host logs carry no per-tick
timestamps to confirm it. Failing takes a push between two particular ticks, which
fits 2 of 15.

**Not an arms.sh bug.** Each captured comment is the first and only
`SKIPPED` notice for its own prediction, which is the behaviour 92 exists to
protect. No grant is needed.

## Reproduction, and the captured comments

The race can be forced without touching any shared ref. A variant of 92
moves the fixture watermark back to 2026-09-27T23:40:00Z just before the
tick under test, so the forza414b registrations (23:43:12) go live
mid-fragment, exactly as a push would. The harness is selftest.sh with only
fragments 10 20 30 40 50 92 sourced. Its `bad()` copies gh.log, the arms tree
and the dispatch dir on every FAIL.

| run (unfixed 92) | result |
|---|---|
| unmodified, no injection | 33 passed, 0 failed |
| watermark moved before the second tick | FAIL a second tick does not tell it again (32/1) |
| watermark moved before the sha5 tick | FAIL and nothing is posted for it (32/1) |

Those are the two host failures, by name. The comments captured in both runs:

```
issue comment 474 --repo example/hakux --body-file .../arms/log/22477788fdee...skipped.md
  [job.arms] SKIPPED: ... forza414-predl-auf.json (sha256 22477788fdee)
  marker: soak predictions (title=4541000D-007_Agent_Under_Fire.xiso.iso) are hand-read
issue comment 474 --repo example/hakux --body-file .../arms/log/08ad772963b1...skipped.md
  [job.arms] SKIPPED: ... forza414-predl-doa.json (sha256 08ad772963b1)
  marker: soak predictions (title=54430006-Dead_or_Alive_1_Ultimate.xiso.iso) are hand-read
issue comment 474 --repo example/hakux --body-file .../arms/log/370071272aa5...skipped.md
  [job.arms] SKIPPED: ... forza414-predl-mnm.json (sha256 370071272aa5)
  marker: no suite with goldens in its keys or disc
```

All three predictions were registered at 23:43:12Z by lane.forza414b. None is
$sha4 or $sha5.

## The fix (test only)

Each leg names the prediction it is about. `posted_for <sha>` is true when a
comment in gh.log has a `--body-file` named `<sha>.*`, or one whose body
carries the sha's first 12 characters. Every body arms.sh writes for a
prediction (`log/<sha>.skipped.md`, `log/<sha>.refused.md`,
`pairs/<sha>.comment.md`) satisfies both.

- "posted as a comment" and "announced": `posted_for $sha4`. They used to
  accept any comment, so another lane's skip could have turned them falsely
  green.
- "a second tick does not tell it again": `nothing_posted_for $sha4`.
- "and nothing is posted for it": `nothing_posted_for $sha5`, plus a new leg,
  "nor for any other prediction behind the watermark". It fails if any comment
  in that tick belongs to a prediction whose exported `$A/expect/<sha>.json`
  is registered before `since`. That keeps what the old blanket leg guarded
  (the committed history stays silent), keyed on the fence itself, so a fresh
  lane registration cannot trip it.

## Proof

All runs are local, on f68fbf1018 (the fix), using the reduced harness unless
the row says "full". A mutant edited arms.sh in the worktree for one run and
was restored with `git checkout` after it. It was never committed.

| run | result |
|---|---|
| fixed 92, watermark moved before the second tick | 34 passed, 0 failed (unfixed: FAIL) |
| fixed 92, watermark moved before the sha5 tick | 34 passed, 0 failed (unfixed: FAIL) |
| mutant: tell_skip's `grep -q '^told='` line deleted (sha4 re-posted every tick) | FAIL a second tick does not tell it again (33/1) |
| mutant: that, plus the `registered_utc < SINCE` fence removed (history re-posted every tick) | FAIL a second tick ..., FAIL ... counted as history, FAIL and nothing is posted for it, FAIL nor for any other prediction behind the watermark (30/4) |
| 20 consecutive loop runs of the fixed fragment | 20 of 20: 34 passed, 0 failed |
| full `bash docs/testing/jobs/selftest.sh` | 2217 passed, 0 failed |

The 20-run loop did not reproduce the natural flake either before or after
the fix: it needs a real lane push between two particular ticks, and none
happened. The injected runs are the reproduction.

## For the next lane

- A fixture that reads the real `origin/lane/*` is not a closed world. Any
  "nothing happened" assertion over a whole tick is exposed to whatever lanes
  push during the run. Assert about the fixture's own objects.
- The reduced harness (fragments 10-50 plus 92) takes about 10 minutes
  locally, and most of that is each tick walking every real lane ref. Two
  runs in parallel take about 20.
- Do not reproduce by creating a local `refs/remotes/origin/lane/*` ref. The
  refs are shared with every worktree on the host, and the real arms job would
  see the fake prediction and comment on a real issue. Moving the fixture's
  `since` does the same thing inside `$T`.
