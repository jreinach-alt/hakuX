# lane.inflightpark: `blocked:in-flight` on an issue does not park its lanes

## Defect

`handback.sh` parked every lane whose territory issue carried any `blocked:*`
label (`parked_lanes()`), for every cause. `blocked:in-flight` is what the
board and hostops put on an issue to mean "lanes are already working this; do
not dispatch another one", so it parked exactly the lanes it describes. Those
lanes were never resumed when their device runs finished. Each one needed a
hand-made `hakux-waiter-<lane>` unit, and `harness_health.py`'s
`parked-nowaker` fired for them.

## Change

- `ISSUE_NOT_PARKING="blocked:in-flight"`, a named exception with a comment
  on what the label means and who sets it. Only the ISSUE half uses it.
- `parked_lanes()`'s `--jq` now emits **every** `blocked:*` label on an issue,
  comma-joined, where it used to emit only `first`. The Python half takes the
  first label that is not in the exception. So an issue carrying both
  `blocked:in-flight` and `blocked:after-0.5` still parks, whatever order the
  labels are in.
- PR-level parking (`parked_label`) is unchanged: a PR that itself carries
  `blocked:in-flight` (#504's interim) stays parked.
- There is still one resume call site.

## Proof

`selftest.sh` with `SELFTEST_ONLY` set to all ten `99-handback*` fragments:
**309 passed, 0 failed.** New legs in `99-handback-parked.sh`, each starting
from clean markers (`hp_runs_world`):

| leg | world | expected |
|---|---|---|
| j | issue has only `blocked:in-flight`, run finished after the session ended | resumed, `draft-strand-runs` marker present, list does not say parked |
| k | issue has `blocked:after-0.5` | not resumed; list names issue #961 and that label |
| l | issue has `blocked:in-flight,blocked:after-0.5` (in-flight first) | not resumed; list names after-0.5 |
| m | PR labelled `blocked:in-flight`, issue clean | not resumed; list names the PR label |

Mutants, each red on its leg: `noinflight` (exception emptied: j goes quiet),
`firstonly` (only the first label read: l resumes), `prinflight` (exception
applied to the PR half: m resumes).

The gh shim answers the issue query with pre-formatted `number<TAB>labels`
lines, so the fragment never runs the `--jq`. I checked that expression by
hand against the live repo: it emits one line per issue that has a `blocked:*`
label.

### `handback.sh list` on the host, 2026-09-28

Eight open issues carry `blocked:in-flight`, not only #569: #569, #507, #482,
#462, #425, #413, #412, #372. On master's copy,
8 rows were parked by one of them:

- #580 litcompile569, #581 uberspike569, #594 gpl569 (#569)
- #590 memfast, #591 ibcache, battadmit (merged-runs), energymap507
  (merged-runs) (#507)
- slowtier2 (merged-runs) (#462)

With this branch, none of those rows is parked. Each shows its real state:
waiting on its in-flight request, or merged with nothing new. The only rows
still parked are the three `blocked:after-0.5` drafts (#436, #439, #535).

## For the next lane / hostops

- Once this folds, the `hakux-waiter-<lane>` units are redundant. They do not
  double-resume: handback skips a lane whose unit is active. Hostops can
  retire them.
- Do not put the exception back into the `--jq` as `first` plus a filter.
  Keeping it in the Python half is what lets the fixture exercise it.
