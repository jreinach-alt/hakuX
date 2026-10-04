# dispatcher: a soak from a pre-libfolders ref still finds its games folder
State: draft

Lane: dispatchguard (on branch lane/toolsmith)            Issue: none (harness defect, hostops addendum 2026-10-04, lane.local's 14:58 harness item)
Base: master @ 10f14d301d
Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-folder-pref.sh, docs/lanes/dispatchguard/NOTES.md, docs/lanes/dispatchguard/PR.md, docs/lanes/dispatchguard/OUTBOX.md
Prediction: none: harness only, no pixels and no arm
Needs device: no    Needs NDK: no

Territory: the hostops addendum directs this change to `docs/testing/dispatcher.sh`, which is free on the
board (released by [lane.hddperm]). It is not in [lane.toolsmith]'s row, and neither is the new fragment
`selftest.d/99-folder-pref.sh`. The fold needs both granted.

## What changed

`GamesFolders.read()` (libfolders, 10f14d301d) moves `gamesFolderUri` into `gamesFolderUris` and deletes
the old key. After a libfolders build has run on a handheld, a soak from an older ref opens the setup
wizard and reports "title did not boot". On the Thor that voided lane.fmv303c's `1791149862` and
`1791149866` (ref cf328d86f7, 14:43 and 14:45 PDT).

`ensure_legacy_folder_pref` runs before every soak, ahead of `titles_disk_prepare`. When the array has
entries and the old key is absent, it adds `gamesFolderUri` = the first entry, keeps every other byte,
and reads it back. A lost read-back fails the request with a named ERROR. No folders, or an unreadable
prefs file, means no write and the soak goes on. The state goes into result.json as `folder_pref`.
A libfolders build ignores the old key while the array is present.

## Tests (local; no CI while GitHub is suspended)

- `SELFTEST_ONLY="99-folder-pref" bash docs/testing/jobs/selftest.sh`: 15 passed, 0 failed.
- Same fragment against master's dispatcher.sh: 13 of 15 FAIL (the falsifier).
- `SELFTEST_ONLY="99-folder-pref 99-hdd-split"`: 78 passed, 0 failed. The hdd split edits the same
  prefs file in the same branch.
- Full `bash docs/testing/jobs/selftest.sh`: see below.

Release note (none): harness only; old-build soaks on a migrated handheld boot again.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
