# lane.foldcancel -- fold.sh must resolve a multi-fold record whose trunk CI was cancelled

Lane: foldcancel
Issue: none (harness defect; host-created 2026-09-26 11:55 PDT by hostops)
Base: origin/master (merge origin/master first; never rebase)
Files: docs/testing/jobs/fold.sh, docs/testing/jobs/selftest.d/74-fold-multi.sh, docs/lanes/foldcancel/NOTES.md

## Why (evidence)
After a tick that folds more than one PR, fold.sh writes `$WORK/fold/multi/<tip sha>`. attribute_multi()
then holds folds to at most one per tick (`HOLD=one`) until trunk_ci() on that exact sha says GREEN or RED.

android.yml and desktop.yml run with `concurrency: cancel-in-progress: true` on the ref. When another fold
pushes master before those runs finish, GitHub CANCELS the runs on the older tip. TRUNK_CI_JQ drops CANCELLED
check runs, so trunk_ci() returns NONE for that sha forever. The record never gets a `done` line, and fold stays
throttled to one per tick for good.

Observed twice on 2026-09-26:
- `993c5fe4b5` (#354 #355 #359, 04:10 PDT): both runs were cancelled. hostops appended `done superseded-green` by
  hand at 04:13.
- `7039df1d24` (#364 #383 #390, 05:46 PDT): both runs were cancelled (`gh api repos/jreinach-alt/hakuX/actions/runs?head_sha=7039df1d24...`
  shows total_count 2, Android and Desktop build both `cancelled`). logs/fold/tick.log logged "master CI NONE on 7039df1d24
  ... at most one fold until it reports" on every tick from 10:51 to 11:50 PDT. hostops marked it done by hand at 11:52.
  Its descendant `11a7dbe537` is green on Android and Desktop.

## Build
1. In attribute_multi(), when trunk_ci "$sha" is NONE (or PENDING, but only after every run on the sha has
   completed as cancelled), find the nearest first-parent descendant of `$sha` on origin/$TIP whose trunk_ci is
   GREEN or RED:
   - GREEN: the batch is attributed green. Append `done superseded-green <descendant sha>` and say so in the log.
   - RED: attribute the red to this batch exactly as if `$sha` itself were red. The existing base-red and revert
     path applies, and the descendant's sha is named in the message. If the descendant also carries later folds,
     the existing one-revert-at-a-time attribution still converges. Say in NOTES why that is safe, or choose a
     safer rule and say why.
   - No descendant has reported yet: keep HOLD=one, as today.
2. Distinguish "cancelled" from "never ran". A sha with zero runs whose descendant is green is resolved the same
   way. Keep the gh calls bounded: at most one check-runs call per descendant, and walk no more than 20 descendants.
3. The same NONE-forever wait may exist in the reverted branch of attribute_multi (trunk_ci "$rv"). Apply the
   same rule there if it is reachable, or say in NOTES why it is not.

## Proof
- Extend `selftest.d/74-fold-multi.sh`. The gh shim already reads a trunk commit's CI from `$FM/ci.<sha>`: add a
  word for cancelled, or make the shim return no runs. Cover three cases:
  - a multi-fold tip whose CI is cancelled, with a green descendant: the record gets `done superseded-green`, and
    the next tick folds more than one PR;
  - the same with a red descendant: the attribution revert happens;
  - no descendant reported yet: still at most one fold per tick.
  Assert on the output words.
- `bash docs/testing/jobs/selftest.sh` green, preflight green.
- Read-only replay: run the new resolution logic against `7039df1d24` with the real gh. It must name `11a7dbe537`
  (or a later green master commit) as the green descendant. Record the output in NOTES.

## Do not
- Edit board files (territory.toml, nv2a_issues.toml).
- Touch `$WORK/fold/multi` on the host, or run fold.sh against the real origin.
- Trigger GitHub Actions as a self-check (CI minutes are finite).
