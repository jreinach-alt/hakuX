# lane.suffixpr

## The defect

`fleet.py`'s `lane_prs()` (the brief calls it `open_lane_prs`; that name does
not exist) filed a `lane/<rest>` PR under the lane `<rest>`. A lane's second PR
is on `lane/<name>-<suffix>`, so it was filed under a lane with no row and no
unit, and `<name>` read as having no open PR. On 2026-09-28 job.board retired
`[lane.sustain507]` while #547 (`lane/sustain507-levers`) was open.

## The change

`branch_lane(ref, rows, units, work)` resolves `lane/<rest>` in this order:

1. `<rest>` when it is a territory row or a live `hakux-lane-*` unit
   (a running lane with no row yet keeps its own PR, not its prefix's);
2. the LONGEST row `x` with `<rest>` starting `x-`;
3. the one `$WORK/wt/<x>` worktree with the head checked out (handback.sh
   `lane_name()`'s resolver); two such worktrees is not guessed at;
4. `<rest>`, as before.

`remote` rows are still matched first. `lane/cloud-*` returns `<rest>` at once.

`pr_of` (first PR per lane, `setdefault`) became `prs_of` (every PR per lane),
printed by one helper.

## Each section, for a lane with one merged and one open suffixed PR

sustain507: #537 on `lane/sustain507` merged, #547 on `lane/sustain507-levers`
open as a draft, row present, unit gone.

| section | before | after |
|---|---|---|
| RUNNING | not listed (no unit); a running lane showed `no PR yet` | not listed; a running lane shows every open PR, `PR #a draft, PR #b READY` |
| REMOTE LANES | first PR only | every PR (not applicable to sustain507) |
| READY, NOT FOLDED | #547 listed under lane `sustain507-levers`, `finished` | listed under `sustain507` once ready; `unit up`/`finished` now asks about the real lane's unit |
| fold_watch / RELEASED AT READY | looked up row `sustain507-levers`: none, so no files, never a release candidate | reads row `sustain507`'s files, so a ready green #547 releases them |
| FOLD-READY, NOT FOLDING / BLOCKED | lane column said `sustain507-levers` | says `sustain507` |
| LANE CLAIMED WITH NO RUNNING AGENT | `sustain507 holds 2 file(s), issues 507,424,525` (nothing about PRs; this section never read `pr_of`) | same line plus `, PR #547 draft`, or `, no open PR` |

The last row is the one job.board retired from. It did not read `pr_of`
before, so the mapping alone would not have changed that section; the PR
list is now printed on it so a reader retiring rows sees the open PR.

Two open PRs for one lane: both are kept (`prs_of` is a list); READY, BLOCKED
and fold_watch iterate `prs` and never used `pr_of`, so they already kept both.

## Proof

Fragment `selftest.d/99-fleet-suffixed-pr.sh` stubs `gh` /pulls as 96 does,
calls `fleet.lane_prs({}, rows, {})` and asserts on `MAP <ref> -> <lane>`
lines. With the fix: 9 passed (and 96-fleet-registry still 28 passed).

With the old one-line mapping restored:

```
== fleet.py: a lane's suffixed PR is filed under the lane
  FAIL lane/sustain507-levers is filed under sustain507, its row
  FAIL lane/flip474-ts is filed under flip474
  ok   lane/foo-bar with rows foo and foo-bar is foo-bar: exact wins
  FAIL lane/foo-bar-2 goes to the LONGEST prefix row, foo-bar
  ok   lane/zzz-1 with no matching row keeps zzz-1
  FAIL lane/qux-x, no row, goes to the worktree that has it checked out
  ok   lane/cloud-abc is left as is, even with a row called cloud
  ok   the lane's own-name PR is still its own
  ok   every PR in the fixture was mapped, none dropped
selftest: 5 passed, 4 failed, PARTIAL: 1 of 97 fragments
```

The five that pass there are the ones the old mapping already got right; they
guard against the fix breaking them.

Live, `python3 docs/testing/fleet.py` on the host, 2026-09-28 05:53 PDT, #547
open:

```
=== LANE CLAIMED WITH NO RUNNING AGENT (14)
  ...
  sustain507   holds 2 file(s), issues 507,424,525, PR #547 draft
```

## Limits, for the next lane

- The prefix rule wins over the worktree rule, so a NEW lane `foo-x` that has
  no row yet and no running unit, while a row `foo` exists, gets its PR filed
  under `foo`. A running `foo-x` is caught by the units check. A lane without
  a row is already a FAIL (RUNNING WITH NO TERRITORY ROW).
- handback.sh has a third resolver (the PR body's `Lane:` line) that this does
  not copy. Neither incident needed it; add it if a lane is found that moved
  its worktree off the suffixed branch AND has no row.
