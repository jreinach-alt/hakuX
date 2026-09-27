[job.cloud] audit pass 1, PR #457 (lane.isoroots, #397), head 9e182d9ec1

**Verdict: no HIGH, no MEDIUM, three LOW.** Next state: `needs-audit-2`.

## What was read

The whole diff against master @ deb0903b51: `devices.sh` (DEVICE_ISO_ROOTS,
`device_iso_roots`, `device_title_path`, `device_title_miss`, `_dev_sq`,
`device_titles`), the soak hunk in `dispatcher.sh` (lines 749-757),
the `am start` line in `soak_title.sh`, and the new fragment
`jobs/selftest.d/99-iso-roots.sh`.

## Checks made

- **The found path reaches the launch.** `dispatcher.sh:767` passes `$tpath`
  to `soak_title.sh`, which uses it verbatim as `ISO=$1`. So a title found
  under the second root launches from the second root, not from
  `DEVICE_ISO_ROOT`. `soak_title.sh` sources `devices.sh` (line 29), so
  `_dev_sq` is defined where the `am start` line calls it.
- **Quoting.** Under this host's bash 5.2.21 (patsub_replacement on),
  `_dev_sq "a'b&c\d"` gives `'a'\''b&c\d'`: `&` and `\` in a title pass
  through unchanged, and the apostrophe is escaped correctly.
- **No stale state between devices.** Both `device_env` rows export
  `DEVICE_ISO_ROOTS` themselves. The unknown-device branch returns before
  the derived `DEVICE_ISO_ROOT`, so a Nova served after the Thor cannot
  inherit the Thor's second root.
- **Callers of DEVICE_ISO_ROOT.** `run_disc.sh` and the dispatcher's
  `run_disc` env lines (1040, 1063) read only `DEVICE_ISO_ROOT`, and it is
  still the first root: SD on the Thor, the one root on the Nova.
- **Readers of changed text.** Nothing in `docs/` or `host-tools/` parses
  the `title not on device` ERROR text or the `devices.sh titles` output.
  Only prose mentions them. The new format, with one header per root,
  breaks no reader.
- **stdin.** The `adb` calls inside `device_titles`' `while read` loop now
  read `</dev/null`, so adb cannot swallow the list of roots.
- **The fragment, re-run here.** Sourced alone with `ok`/`bad` stubs: on
  the branch, 10/10 ok. With `IR_TESTING` set to a master worktree it gives
  4 ok and 6 FAIL. The 6 FAILs are root 2, none, quote, the Nova miss,
  launch and titles, which matches the PR body's table leg for leg. The
  controls (root 1, Nova found, `devices.sh bdc158a5` unchanged) pass on
  both trees, as the PR says they should.
- **Merge and CI.** The branch merges into current origin/master
  (`git merge-tree`, 27 commits ahead of the base) with no conflict. build
  and selftest are green on the head.

## Findings

**LOW 1: an adb failure still reads as a missing title.**
`device_title_path` returns 1 both when no root has the title and when
`adb_call` times out. In both cases the dispatcher writes
`title not on device: ... -- searched ...`. Scenario: the Thor drops off
adb during the title check, and the ERROR says the title is missing when
it is not. `adb_error` still adds the hung-call line the comment promises,
and master behaved the same way, so this PR introduces no regression.

**LOW 2: the found path goes through `echo` in the device's shell.** In
`device_title_path`, `echo "=$p"` runs under Android's mksh, and mksh's
`echo` may expand backslash escapes (not checked on the device here). Scenario: a title with a `\` in its name
comes back altered, so the found path is wrong. The exFAT/FAT volumes these
roots sit on do not allow `\` in a filename, so this cannot happen today.
`printf '=%s\n' "$p"` would remove the dependency on the filesystem.

**LOW 3: comment reflow.** In the `device_titles` WHY comment, the edited
line runs past the width of the paragraph around it. This is cosmetic.

## For pass 2

None of the three LOWs blocks the PR. Pass 2 should check that the head it
reads still passes `99-iso-roots.sh` and still hands `$tpath` to
`soak_title.sh`, and that any LOW the lane chose to fix is fixed the way
this audit describes.
