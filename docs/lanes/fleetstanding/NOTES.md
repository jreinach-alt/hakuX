# lane.fleetstanding

## Defect

`fleet.py` `fold_watch()` asked every ready, green lane PR whose lane had no
running unit to release its row's files. A standing row (`standing = true`,
e.g. `[lane.xbox]`) is driven by an interactive session and never has a unit,
so it always read "unit gone". On 2026-09-28 lane.xbox's #561 (touching only
`docs/testing/titles/targets.toml`, outside its row) produced a FAIL asking
the board to release all 16 files the lane was still working in.

## Change

- `docs/testing/fleet.py`, the release loop in `fold_watch()`: a row with
  `standing = true` is never a release candidate. Its session outlives each
  PR, and it releases files by its own board request. The fold-stuck half of
  the loop is unchanged: a standing lane's `fold-ready` PR is still watched.
- `docs/testing/jobs/selftest.d/99-fleet-standing-release.sh`: drives
  `fold_watch()` with `pr_state` stubbed green, over a normal row and a
  standing row, each with a ready PR, unreleased files, and no unit
  (`units = set()`, not `None`, so the FLEET-BLIND branch does not hide it).
  Asserts on printed lines: the normal row's exact RELEASE line is present,
  no line names lane.xbox, and the count is exactly 1.

## Proof (local, no CI spent)

With the fix:

```
== fleet.py: a standing row is never asked to release at ready
  ok   the normal row, ready green PR and no unit, is asked to release its files
  ok   the standing row, ready green PR and no unit, is NOT asked to release
  ok   exactly one release, and fold_watch ran to its end
selftest: 3 passed, 0 failed, PARTIAL: 1 of 99 fragments
```

With `and not meta.get("standing")` removed:

```
== fleet.py: a standing row is never asked to release at ready
  ok   the normal row, ready green PR and no unit, is asked to release its files
  FAIL the standing row, ready green PR and no unit, is NOT asked to release
  FAIL exactly one release, and fold_watch ran to its end
selftest: 1 passed, 2 failed, PARTIAL: 1 of 99 fragments
```

## For the next lane

- The host-side interim (`host-tools/harness_health.py` skipping the forwarded
  FAIL for a standing row) can go once this lands; it is not in this repo.
- The fragment stubs `fleet.pr_state` in-process instead of shimming gh; a
  change to `pr_state`'s return shape would need the stub updated.
