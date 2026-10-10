# OUTBOX: lane.nightlynotes1009 -> lane.local

## 1. File this lane needs changed but does not own

- `docs/testing/systemd/hakux-nightly.service` line 26, `SuccessExitStatus=75` -- needs `9` added
  (`SuccessExitStatus=75 9`). This PR makes a build whose window has no player-facing change exit 9 instead of
  publishing a no-op release (item 2 of the brief). `run-nightly.sh` propagates that exit code unchanged (see
  section 2), so nothing there needs to change -- but the systemd unit only whitelists 75 (the fold-lock-busy
  code) as a non-failure exit. Without this line, every night the publish gate holds (which, going by the five
  windows read for this PR, is every night since 10-05) `systemctl --user` marks `hakux-nightly.service` FAILED,
  and `status.sh:485-486` turns that into `attn timer "hakux-nightly.service has FAILED ..."` -- a false alarm
  for a deliberate no-op, exactly the thing item 2 says to avoid leaving. Not edited: outside this lane's
  territory (board 193794ade6 names `docs/testing/nightly_build.sh`, `docs/testing/jobs/selftest.d/86-nightly-notes.sh`,
  `docs/lanes/nightlynotes1009/**` only).

## 2. Read, not edited, and found fine as-is

- `docs/testing/jobs/run-nightly.sh` -- the brief named this as in-territory-if-needed. It is not needed: the
  script's own exit handling (`rc=$?`; special-case only `[ "$rc" = 75 ]`; else `exit "$rc"`) already propagates
  any exit code, including the new 9, unchanged. The only gap is the systemd unit in section 1.
- `docs/lanes/nightlynotes/release_notes.tsv` ($MAP, the curated-line file `nightly_build.sh` reads) -- the brief
  named this as `[free]`. Nothing in this PR needed a new row: the fixtures and the five evidence windows below
  are all covered by `Release note:` lines already in the folded lanes' own `PR.md` files, read straight off the
  commit via `lane_body_line()`. Not touched.
- Searched for anything else reading `nightly/<date>.log` or a nightly's exit code for an alarm or a check-in
  (`docs/testing/dispatcher.sh`, `dx_pass.sh`, `version_stamp.sh`, `install-host.sh`, `localtime.sh`,
  `selftest.sh`): none of them read the nightly's exit code or log content for pass/fail. Only `status.sh`'s
  failed-unit scan (section 1) is affected.
