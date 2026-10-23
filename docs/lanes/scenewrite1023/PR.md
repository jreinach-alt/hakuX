# scenewrite1023: a scene load opens the app-only states dir before it writes there, and a failed park fails the run

State: ready

Lane: scenewrite1023            Issue: none (harness defect, dispatched directly)
Base: master @ 1b616ee718
Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-load-state.sh, docs/testing/request.sh, docs/lanes/scenewrite1023/**
Prediction: none: no arm (a harness defect with a falsifier fragment, not a pixel or perf claim)
Needs device: yes (one proof run after the fold, queued by lane.local; the lane touches no device)
Needs NDK: no
Selftest: 99-load-state 99-battery-admit 99-disc-hdd -- 99-load-state: a scene write into an app-only states dir
  (fake dirs host mode 555, plain-shell writes refused), a dir run-as cannot open, a failing park, with four mutants;
  and (l), a request that loads a state gets no recorded boot route from request.sh or at claim, with two mutants;
  99-battery-admit and 99-disc-hdd: the neighbours that source the same dispatcher.sh functions

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

| 10-17 | 9a177a6f82 (dispatchdoctor1017 Section 1b); docs/lanes/dispatchdoctor1017/{NOTES,PR}.md; request.sh "dispatchdoctor1017 Section 1b", dispatcher.sh `ensure_route_attached` | A soak that typed no `--route` (or `survey`) gets the title's `suggest-route` answer attached, at queue time and again at claim; skipped for `--find-route`, `--remake-profile`, `--path-broken`. Owner 10-17: "no route (or only survey)" | Built and selftest-green for a cold-boot soak. Its skip list names three deliberate intents; it names no load | Does not cover a load. A `--load-state`/`--scene` request starts mid-game, and nothing in either guard asks. The two places are fixed here (A) |
| 10-23 | coordinator addendum ce679c6d30 (the lane.local replay of heavy2.hxs, `--load-state`, no `--route`) | request.sh attached `gta-3.route` (A x16, steering from 55 s, recorded from a cold boot) to a request that loads a mid-game state; the replay was void | The failure A fixes | The fix is a guard in the attach condition, not a new flag: an explicit `--route` still attaches, and a scene's own input is `--hold-trigger` |

| 09-26 to 10-22 | dispatcher.sh LOGCAT_SPEC history (hakuX-tier1 #81, hakuX-stall/rpbrk/cpu/xemu-gpu/sfp #372, xemu-surf #413); lane/heavycap1022 8d27d8fe54 | Each new telemetry tag was added to the allow-list by hand, after a capture showed zero lines for a mechanism the filter silenced; heavycap1022 adds `hakuX-heavy:I` on its own branch | The allow-list is edited per tag, and the comment above it says why | `hakuX-gpubrk` (gpubreak1022) and `hakuX-heavy` are not on master and `*:S` would silence both. Added here ahead of their builds, as the addendum asks; heavycap1022's own `hakuX-heavy:I` on the same line will conflict at fold |

No row is a states-dir write that already worked from code. The earlier lanes handled the mode of a pushed file
(hddperm, devpushro), or the app's own writes (savestate1011); the open dir on the Nova was a hand step. No row is a
route guard for a load: dispatchdoctor1017 skipped three intents and none was a load.

## What this lane builds

1. **dispatcher.sh `set_scene_pref` opens the title's states dir** to `adb shell` (`run-as <pkg> chmod g+w`) before its
   first write, when the app left it closed. One log line names the dir and its mode before and after. If the dir is
   still closed it fails with `SCENE: <sdir> is not writable by adb shell; run-as chmod g+w did not open it` and writes
   nothing. The marker records whether this call opened the dir; `restore_scene_pref` closes it again (`chmod g-w`) only
   if it did and every restore step succeeded. A missing dir is refused with a named reason (decision in NOTES.md).
2. **A failed park fails the run.** `mv ... && parked+=` is gone; a failed park, or a slot file still in the dir after
   the parks, calls `scene_abort`, which restores what was moved and returns 1 with the reason in `SCENE_WHY` (serve_one
   puts it in the request's ERROR).
3. **The comment at dispatcher.sh ~1032** no longer says the dirs are shell-accessible "confirmed by reading those
   functions"; it states what was measured.
4. **chmod, not a run-as copy**, argued in NOTES.md.
5. **99-load-state.sh falsifier.** The fake device has app-only dirs (host mode 555, a plain-shell write fails); cases
   k0-k7; four mutants (`dropopen`, `noclose`, `silentpark`, `nolisting`) each cmp-verified and each turns its case red.
6. **A: a request that loads a state gets no recorded boot route.** request.sh's Section 1b attach block skips
   `--load-state`/`--scene` requests (`&& [ -z "$LOAD_SLOT" ]`); an explicit `--route` still attaches. dispatcher.sh
   `ensure_route_attached` returns before its own attach when the request has a `load_slot` (the claim-time twin,
   not in the addendum: a route-less request from an older request.sh would otherwise get gta-3 there) and says why
   in the inputs note. Falsifier (l) in 99-load-state.sh, against the real `suggest-route`, `targets.toml` and
   `routes/`; two cmp-verified mutants (`noqueueguard`, `noclaimguard`).
7. **B: `hakuX-gpubrk:I hakuX-heavy:I` in dispatcher.sh's LOGCAT_SPEC**, before `*:S`, with a dated paragraph. Both
   tags log at INFO (draw.c:4207, profile.c:520 on their lane branches; neither is on master). No mutant: an allow-list
   entry. The other copies (soak_title.sh:36, run_disc.sh:82, titles/pathfind.py:91, HakuXApplication.kt:18) are named
   in NOTES.md and not edited; a dispatched run inherits the dispatcher's spec.
