# lane.handbackpark: handback must not resume a draft parked with `blocked:*`

## Defect

`jobs/handback.sh`'s strand cause skipped a draft only for the labels in
`STRAND_STALE`, and the only `blocked:` label there was `blocked:needs-owner`.
Under #433's 0.5 policy the host parked #436 (lane.visual404) and #439
(lane.fmv303c) with `blocked:after-0.5`. Both read as unowned drafts and were
strand-resumed twice each on 2026-09-26. Each of those sessions only re-posted
that the lane was parked, and each one used up part of DRAFT_STRAND_MAX.

## Change (handback.sh only)

- `parked_label`: a prefix test (`blocked:*`) on the PR's labels, applied in
  the shared per-row body. It therefore covers **every** cause: needs-rebase,
  draft-strand-arm/-runs/-idle/-quiet and idle-no-pr (which has PR `none` and no
  labels, so for that cause only the issue half below can apply).
  `STRAND_STALE` keeps its explicit list unchanged. `blocked:needs-owner` still
  matches there first and still prints "already moved on".
- `parked_lanes`: this runs one `gh issue list` per tick for open issues with a
  `blocked:*` label and maps them to lanes through territory `issues`, with the
  same loader as `idle_lanes`. A row whose lane has a parked issue is skipped.
  This covers the issue half of the brief for every cause, including the no-PR
  idle lane. The rule is ANY parked issue, which matches how `idle_lanes`
  already treats `decision-needed`.
- A skip writes no marker and no tick-log line. It is a standing state, so
  lifting the label makes the next tick act at the same head. `list` prints
  `#<pr> <branch>: <cause>, skipped: parked by <label | issue #N label>`.

The audit and remediation causes are not in handback.sh. It has only the
needs-rebase label row. Those causes live in cloud.sh, see below.

## Proof

`handback.sh list` on this host, run from this worktree (2026-09-26 17:15 PDT):

```
#436 lane/visual404: draft-strand-quiet, skipped: parked by blocked:after-0.5 (a blocked:* label has its own actor)
#439 lane/fmv303c: draft-strand-quiet, skipped: parked by blocked:after-0.5 (a blocked:* label has its own actor)
```

`selftest.d/99-handback-parked.sh` has 17 checks and 2 mutants. It passes on
this branch, and so do all seven handback fragments together (256 passed, 0
failed). With the prefix test reverted to the literal
(`blocked:needs-owner) printf`) in the real file:

```
  FAIL (a) a draft labelled blocked:after-0.5, quiet past the clock, is not resumed
  FAIL (a)   list says it was skipped for that label
  FAIL (a)   nothing is said on the PR
  FAIL (a)   and DRAFT_STRAND_MAX is not spent
  FAIL (b) the same draft without the label is resumed
  FAIL (f) a judged arm on a parked draft does not resume it
  FAIL (f)   list says so
  FAIL (g) needs-rebase on a parked PR is skipped
  FAIL mutant anchor 'noprefix' no longer matches handback.sh
selftest: 10 passed, 9 failed
```

(b) fails too because (a) left a resume marker at that head. That is the
marker the defect would leave on the host.

The full `selftest.sh` does not finish within one 10-minute tool call from a
lane session, and a lane cannot detach it (`systemd-run` needs approval). I ran
it as the runner with its fragment list narrowed to the handback fragments,
through an untracked copy. CI runs the whole thing.

## The same hole outside this file (not fixed here)

- `jobs/cloud.sh` `pr_by_label` (~l.388) skips only `claimed:cloud` and
  `blocked:needs-owner`. A PR carrying `needs-audit-*` or `needs-remediation`
  plus `blocked:after-0.5` would still be claimed by the audit outlet.
- `jobs/cloud.sh` `issue_cloud` (~l.392) has the same literal. An issue
  labelled `cloud` and `blocked:after-0.5` would still be claimed for a cloud
  session.
  The fix is the same prefix, `startswith("blocked:")`, in both jq filters.
  That needs a lane that owns cloud.sh.

## Do not repeat

- Adding `blocked:after-0.5` to `STRAND_STALE` would fix today's case and
  reopen with the next `blocked:<x>`.
- A selftest `gh` shim ignores `--jq`. The idle fragment's shim answers every
  `issue list` with bare issue numbers, so `parked_lanes` ignores any line that
  has no `blocked:` label after a tab instead of treating it as parked.
