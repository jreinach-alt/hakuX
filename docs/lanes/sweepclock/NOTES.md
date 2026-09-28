# lane.sweepclock

## Cause

`selftest.d/76-pr-sweep.sh` read `TRUNK_CT` once, at source time, from
`$REPO`'s `refs/remotes/origin/master`, and built every fixture check time as
an offset from it (`-600` stale, `+600` live). Each `ps` run executes the real
`jobs/pr-sweep.sh`, which does `git -C "$REPO" fetch -q origin master` against
`$REPO`'s real origin and re-reads the trunk time. A fold landing on master
during the ~23-minute selftest moves that head; once it moves more than 600 s,
the `live:FAILURE:+600` check predates it, is called stale, and
`a stale failure ALONGSIDE a live one is a live red` fails. PR #523's run
36364245109 failed that way: #503 folded 894 s after the head the fixture
had read.

A worktree's refs are shared with the host checkout too, so on the host a
fetch by any other job moves the same ref. A git shim that no-ops `fetch`
would not have protected against that, which is why I went with the
fixture-owned origin.

## Fix (fixture only)

The fragment now builds `$PS/origin.git` (bare) and `$PS/repo`, with a single
empty commit dated 2026-09-19T12:00:00Z, and `ps()` runs pr-sweep with
`HAKUX_REPO_DIR=$PS/repo`. `TRUNK_CT` is read from that repo. pr-sweep's own
fetch still runs and still reads the ref by name, but from an origin only the
fragment writes. New check: `the sweep's trunk is the fixture's own, at its
fixed date`. pr-sweep.sh is unchanged. It uses `$REPO` only for the trunk
and board fetches, and the board is `HAKUX_BOARD_REF=` (the in-tree file)
here anyway.

## Mutant (`.scratch/run76.sh`, not committed)

The driver runs one fragment behind selftest.sh's own preamble. In `mutant`
mode, `$REPO`/`HAKUX_REPO_DIR` is a scratch repo whose origin gets a commit
900 s past the head immediately before the stale-alongside-live block, and
only the origin moves (the local tracking ref is reset back), the same way a
fold lands.

| fragment | plain | mutant (fold +900 s mid-run) |
|---|---|---|
| master's 76 | 57 passed, 0 failed | 56 passed, **1 failed**: `a stale failure ALONGSIDE a live one is a live red` |
| this branch | 58 passed, 0 failed | 58 passed, 0 failed |

The master+mutant result is #523's failure: the same single check.

## Siblings checked

- `78-sweep-remote.sh`: has its own bare origin. Fine.
- `87-fold-stale-ci.sh`: runs the real fold.sh against the real `$REPO`, but
  pins the tip with `FOLD_TIP_SHA`/`FOLD_TIP_EPOCH`, so `tip_state` never
  fetches. Fine.
- `73-cloud-claim.sh`, `74-fold-multi.sh`, `87-nightly-trunk.sh`,
  `94-arms-verdict-scope.sh`, `94-arms-withdrawn.sh`, `98-lane-shape.sh`:
  each builds its own repo or origin. None of them keys a timestamp to the
  real trunk.
- Among jobs that read a commit time (fold.sh `tip_state`, issue-sweep.sh remote
  branch tips, status.sh last fold), no other fragment builds check times
  from the real master head. No sibling needed the fix.

## Do not repeat

- Do not fix this with a `fetch` no-op shim alone: the shared worktree refs
  can still move under it on the host.
