# statusalloc1013: status.sh no longer opens a status issue the gh shim would refuse (#433, 0.5)

State: ready

Lane: statusalloc1013            Issue: #433
Base: master @ 38bd86f2eb
Files: docs/testing/jobs/status.sh, docs/lanes/statusalloc1013/PR.md
Prediction: none: harness
Needs device: no    Needs NDK: no
Release note (none): harness

## Why

lane.forgealloc1013 (folded 38bd86f2eb) made the gh shim refuse `gh issue create`:
a number taken on the forge can run ahead of GitHub's and block every later
issue. Its NOTES.md named one legitimate caller outside its territory as
WAITING: `status.sh`, which recreated the "harness: live status" issue with
`gh issue create` when the query for it came back empty. After that fold, the
call can only fail.

## Change

When no harness-status issue is open, `status.sh` now prints that it is not
creating one and names the replacement (`issue_mirror.py new`, run by
lane.local), then exits 0. A failed query still exits 0 and retries next
tick. Nothing else in the script changes.

## Tests

- `bash -n docs/testing/jobs/status.sh` passes.
- The selftests that run `status.sh` under a stubbed `gh`
  (`62-status-freshness.sh`, `64-status-html.sh`) always answer the
  harness-status query with issue 107, so neither reaches the changed branch;
  their unused `issue create` stub cases are left alone (not this lane's
  files). The fold's selftest run covers them.
- `status.sh` itself is not run by hand: it publishes.
