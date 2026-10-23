# scenewrite1023: a scene load opens the app-only states dir before it writes there, and a failed park fails the run

State: draft

Lane: scenewrite1023            Issue: none (harness defect, dispatched directly)
Base: master @ 1b616ee718
Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-load-state.sh, docs/lanes/scenewrite1023/**
Prediction: none: no arm (a harness defect with a falsifier fragment, not a pixel or perf claim)
Needs device: yes (one proof run after the fold, queued by lane.local; the lane touches no device)
Needs NDK: no
Selftest: 99-load-state -- (to be filled when the fragment is extended)

## Step 0: already tried

Sources: `git log -i -E --grep='run-as|ext_data_rw|chmod|states/|permission|660|dev_make_660|hld'` on master (about
60 hits; the 11 that touch the harness are in the table, the rest are upstream QEMU merges and unrelated
android/ commits), docs/lanes/savestate-req1019/{NOTES,PR}.md, docs/lanes/savestate1011/{NOTES,PR}.md, and a grep
of docs/lanes/*/ and docs/testing/ for `ext_data_rw`, `chmod g+w`, `run-as .* states` and `4d530065`.

| Date | Commit / doc | What it measured or changed | Verdict | Meaning here |
|---|---|---|---|---|
| 09-29 to 10-04 | e369f56af2, c817b59a59, f3bd87638e (hddperm, #397); docs/lanes/hddperm/NOTES.md | `adb push` lands a file `rw-r--r--` shell:ext_data_rw; the app reaches `files/x1box` through `ext_data_rw`, so `dev_push` now `chmod 660`s `<path>.new`, reads the mode back, and removes `.new` on a failed push | Handled the pushed file's mode, in `x1box/` (which shell can write) | Does not cover this. It makes the file group-writable; it cannot make the directory `states/<ttid>/` (`drwxr-s--- u0_a145`) writable, and `dev_push` needs that dir for its `.new` file and its `mv` |
| 10-18 | 0eb452498b, 62181bc0a9, f473f6b4c4 (mkdawhite1018, devpushro1018, #1058) | `dev_push`'s mode-660 check failed twice on the SD-card disc (the mount pins every file at 770); a read-only push skips the 660 step and keeps the sha check | Fixed, for disc pushes onto the SD card | A mode problem on another mount. Not a states-dir problem: no directory write was involved, and the scene push goes through the normal (660) path |
| 10-11 | docs/lanes/savestate1011/{NOTES,PR}.md | Built the save-state store: the app writes `states/<ttid>/slot0..9.hxs`, `auto.hxs`, `undo-save.hxs` (`st_mkdir` 0755); host tests write a scratch dir through HAKUX_STATE_DIR | Works; every write is the app's | Never needed an adb write into `states/`, and records no `chmod`/`run-as` on it. The lane that worked in `states/4d530065` left no record of how that dir was opened |
| 10-14 | docs/lanes/savestateconv1014/NOTES.md:111-155 | Listed the debug package's `x1box/states/`: every title dir `drwxr-s--- u0_a145 ext_data_rw` (e.g. `41560037`, `4d570029`) | Measured, 9 days before the failure | The closed mode was the app's default on every dir, in the record. Nobody drew the consequence for an adb write |
| 10-19 | docs/lanes/fpsnext1019/NOTES.md:34, :602 | The owner's Blinx 2 island state sits in the debug package's `states/4d530065/slot5.hxs`; lane.xbox loaded it on 10-18 through the pause menu | The only dir found open (`drwxrws---`, 10-23); no lane doc or commit message says who put the file there or how | Shows an opened dir persists, and that an earlier hand step existed. Nothing automated opened it, so no code covers a closed dir |
| 10-23 | 1b616ee718 (fold of lane/savestate-req1019); docs/lanes/savestate-req1019/{NOTES,PR}.md; dispatcher.sh:1032-1035 | Built `set_scene_pref`/`restore_scene_pref`. The comment says the dir is "shell-accessible -- dev_push/dev_pull/dev_sha256 already reach them with plain `adb shell`, no run-as (confirmed by reading those functions)". `99-load-state`'s fake adb runs every `shell` and `push` as the host user. The 10-19 device proof (1-1792450834-savestate-req1019-3775536) logged no `SCENE` line and no `[savestate] op=` line | The scene path had never run on a device; the host-file push (`--load-state <file>`) was never exercised against a permission | This is the code being fixed. `dev_push`/`dev_pull`/`dev_sha256` read, or write into `x1box/`; reading the functions proved reads only, and a fake that cannot refuse a write could not have shown the split |
| 10-23 09:45 | dispatch/logs/dispatcher.log; result 1-1792773923-fps30replay1023-2457071 | First real `--load-state <host .hxs>`: `SCENE: push of .../heavy2.hxs -> .../states/5454000E/auto.hxs failed`, `SCENE SETUP FAILED` before anything was parked | The failure this lane fixes | `adb shell` (uid shell, group `ext_data_rw`) reads the dir but cannot create in it |
| 10-23 09:47-09:49 | lane.local, in the brief | `x1box/` shell-writable; `states/` and `states/5454000e/` not (`drwxr-s--- u0_a145`); `states/4d530065/` writable (`drwxrws---`); `run-as <debug pkg>` is u0_a145 and writes; `run-as ... chmod g+w states/5454000e` made shell `test -w` yes, and it persists | The recipe, applied by hand to one title | Built here as the automatic step, for every title. Only 5454000e is open on the Nova; every other dir is still closed, so the fake must not assume an open dir |

No row is a states-dir write that already worked from code. The earlier lanes handled the mode of a pushed file
(hddperm, devpushro), or the app's own writes (savestate1011); the open dir on the Nova was a hand step.

## What this lane builds

(Filled in when the change is done.)
