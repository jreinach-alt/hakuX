# snapshot1011: save states, phase 0 (#433)

A save and a load of the whole machine, stored as an internal snapshot in the
qcow2 hard-disk image, made to work on Android and proved on the Nova with a
fixed test sequence. No player-facing control: phase 1 (harness), phase 2
(player UI) and phase 3 (raw-disk conversion) are not started here.

## 1. What changed, item by item

| Item | Finding in the code | Change |
|---|---|---|
| Port | `CMakeLists.txt` excluded `ui/xemu-snapshots.c`; the stub's save/load/list did nothing and `xemu_snapshots_offset_extra_data` returned false, so every load failed with -EINVAL (`migration/savevm.c:3049-3053`). | The exclusion is removed. `xemu_snapshots_stub.c` keeps only the three thumbnail stand-ins (`ui/xemu-thumbnail.cc` stays out: desktop GL). The GL calls in `ui/xemu-snapshots.c` are compiled only off Android; an Android state has no thumbnail. |
| Running only | `do_vm_stop` notifies the state handlers only when the old state is live (`system/cpus.c:309`): from PAUSED, `vm_stop(RUN_STATE_SAVE_VM)` or `(RUN_STATE_RESTORE_VM)` changes nothing, so the nv2a SAVE_VM handler never locks the FIFO while `nv2a_post_save` still unlocks it, and the RESTORE_VM handler never halts PFIFO. | `xemu_snapshots_save`/`_load` start a paused machine first and pause it again after. A load restarts the machine itself, so the frontend's resume path (`ui/xemu.c:1546-1580`, which clears the flip/NOP/context-switch waits, runs only when the machine is not running) does not run on the loaded state. A load asked for while paused runs 250 ms before pausing, so the loaded waits are consumed first. Any other state (for example a failed load) is refused. |
| Vertex attributes | `nv2a.c` had an empty vertex-attribute description under a FIXME. | `nv2a/pgraph/vertex-attr` v2 carries dma_select, offset, inline_array_offset, inline_value, format, size, count, stride, needs_conversion. `compressed_attrs` is rebuilt in post_load; the inline buffer is not saved (a save between BEGIN and END loses that one batch's vertices). |
| Lighting ring (#53), fog (#41) and other unsaved pgraph state | `ff_lit_ring`, `ring_pos`, `last_ff_radial_fog_coord`, the material/light/specular/point parameters, texture-matrix enables, line width, stipple, solid-line, clip-rectangle and beta state, the subchannel/graphics-class cache and the flat-panel PRAMDAC timing registers were not in any section. | New subsection `nv2a/pgraph-state` (always sent). post_load also moves every renderer generation counter and marks every dirty map (constants, light contexts, registers, textures, program), so the first draw after a load rebuilds from the loaded state instead of skipping on an unchanged generation (`pgraph/vk/draw.c:2943-2951`). That fix lives in `nv2a.c`; no vk file is edited. |
| APU FIFO | `mcpx_apu_pre_load` reset the APU but not the monitor FIFO. | The monitor FIFO is emptied under its lock in pre_load. |
| Version 2 header | | `XEMU_SNAPSHOT_DATA_VERSION` 2. After version 1's disc path, title name and thumbnail come six key/value fields: `schema` (sha256 over every registered section's name, instance, version and field layout, and the migrated RAM blocks' names and sizes, sorted; `xemu_savevm_schema_fingerprint`), `build` (the commit and the native library's GNU build ID: the library is what decides state compatibility), `title_id`, `disc` (sha256 of the disc's length and 1 MiB at its start, middle and end), `controllers` (per port: the bound driver and its two peripheral types, or `-`), `region` (the display-region hash at the save). |
| Refuse before reset | `load_snapshot` resets the machine before it reads the stream. | `xemu_snapshots_load` first opens the image read-only, reads the snapshot's header with `bdrv_snapshot_load_tmp` + `bdrv_load_vmstate`, and compares build, title, disc, controller layout and schema with the running machine, in that order. A mismatch logs `[snap] refuse reason=<field>` and returns an error; the machine is never stopped. A version 1 state is refused (`reason=header`). |
| pmc-enable `.needed` | A subsection without `.needed` is always sent (`migration/vmstate.c:414-417`). | `.needed` is set to an always-true function, which states the intent; the stream does not change. |
| xemu #2241 | A state saved with a controller on a port the running machine leaves empty fails inside the load, after the reset. | The controller layout is part of the identity and is checked before the reset. |
| xemu #1717 | `-loadvm` runs before input exists. | Not added. |
| Renderer | `nv2a_reset` (run by `qemu_system_reset` inside `load_snapshot`, before the RAM is read) flushes every surface and waits for it (`nv2a.c:1388-1392`), so no surface is dirty when the loaded RAM arrives. `HAKUX_REPORT_ASYNC` (`pgraph/vk/reports.c:397, 410`) is off unless set. | Nothing edited in `pgraph/vk/*` or `pgraph.c`. |

The desktop build was not used. `/home/justin/hakuX/build-desktop` is a meson build of the source tree at
`/home/justin/hakuX` (`meson-info.json`), so a rebuild there compiles that checkout, not this branch. Building
this branch on the desktop means configuring a new build directory and compiling all ~3,760 build steps, well
past the ~15 min limit for one rebuild. The changed C files were checked with the NDK compiler and the Android
build's own flags (`-fsyntax-only`) instead.

## 2. The test sequence

`HAKUX_SNAPSHOT_TEST=<seconds>` arms a main-loop timer (QEMU_CLOCK_REALTIME, so it runs while paused, with the
BQL held) that starts that many seconds after the GPU is created. Every step logs one `[snap]` line under the
`hakuX-lane` tag:

- `start`: build, title ID, disc hash, controller layout, schema fingerprint, snapshot count; stale slots `a`
  and `b` are deleted.
- c1: save `a` (ms, bytes, region hash), 20 s of play, hash scene B with the surfaces downloaded, load `a`,
  hash the region right after the load (before the machine restarts). Pass: the after-load hash equals A's,
  A's is not 0, and B's differs.
- c2: six hashes, 10 s apart, after that load. Pass: more than one distinct hash and still running.
- c3: 20 cycles of save `b`, 2 s, load `b`, 2 s; min/median/max of save_ms and load_ms.
- c4: pause, save `b` (paused after?), load `b`, 1 s later check paused again with the flip/NOP waits, resume,
  hash after 10 s.
- c5: save `b` with a different controller layout written into the header, load `b`. Pass: refused with
  `reason=controller-layout`, still running, and the region hash moves over the next 5 s.
- `done`: slots `a` and `b` deleted; the remaining snapshot count is logged (0 expected).

A hash taken while the game runs (scene B, c2, c4, c5) pauses the machine for the write-back and starts it
again. The write-back (`nv2a_lock_fifo`) releases the BQL to wait for the GPU and retakes it while holding the
FIFO lock, and a vCPU in a PFIFO register access holds the BQL while it waits for the FIFO lock; with the vCPUs
stopped that cannot happen. Every other caller of `nv2a_lock_fifo` (reset, the run-state handlers, pre_load)
already runs with the vCPUs stopped. The VBLANK timer has no run-state gate (`nv2a_vblank_timer_cb`), so a pause
does not strand a flip wait.

The state goes into the hard-disk image: the CD-ROM drive is read-only (`media=cdrom`), and the hard disk is
attached as `index=0,media=disk` with its format probed (`system/vl.c:3078-3090`), so on a title run the snapshot
lives in `titles.qcow2`. The 187 route has no `mark profile-saved`, so the run cannot make a golden from its
harvest (`titles_first_run_golden`, `dispatcher.sh`).

## 3. Runs

Reference for the disk checks: 1-1791713584-fastpaths1010-1525919 (187: Ride or Die, Nova, first-run):
`hdd.json` sha256_at_start `40b403228897...`, bytes_at_start 18808832; `hdd.after.json` harvests 55530036 as
`fa079adf42d5`.

| Run | Ref | Result |
|---|---|---|
| 1-1791753422-snapshot1011-2350466 | a8c3031263 | 187: Ride or Die, `HAKUX_SNAPSHOT_TEST=120`, 600 s. Every step passed in logcat; the frames do not show a scene change for c1 (below). |
| 1-1791764800-snapshot1011-813455 | 4c4e5f98a9 (master merged) | 187: Ride or Die, `HAKUX_SNAPSHOT_TEST=76`, 360 s. Every step passed; A is the pre-race cutscene, B the race, and the first frame after the load is the cutscene again. |

The first session ended at its turn limit right after queueing run 1, before the run started; the second session
picks up from its result.

### Run 1 (1-1791753422-snapshot1011-2350466)

Logcat (`hakuX-lane`, `[snap]` lines 96-11655):

| Step | Result |
|---|---|
| start | 17:12:10.6, snapshots=0, controllers `usb-xbox-gamepad,0,0;usb-xbox-gamepad,0,0;-;-` |
| c1 | save `a` 263 ms, 59,018,555 B, hash `cfa6aa04b442993c`; scene B `3cc306e84e841b48`; load `a` 116 ms (header check 3 ms), after-load `cfa6aa04b442993c`: match |
| c2 | 6/6 distinct hashes over 60 s after the load, running throughout |
| c3 | 20 cycles, 40/40 ok. save_ms min 190, median 307, max 489; load_ms min 101, median 107, max 116; state 59.07-59.09 MB |
| c4 | paused, save 296 ms (paused after), load 107 ms, paused 1 s later, resumed; hash moved 10 s later |
| c5 | header written with layout `-;-;-;-`: `refuse reason=controller-layout` after a 5 ms header check, load 0 ms, machine running, hash moved over 5 s |
| done | slots `a`, `b` deleted, snapshots=0 |

No `hakuX-crash`, `libc` or `DEBUG` line. Frames continue to the end of the run (224 frames, 600 s).

The frames do not prove c1. The route fell one screen behind: where it expected the race
(`171134-race-start.png`) the game showed the mission briefing ("Press A to continue"), and from the race start
on (f00048, 11 s before the sequence began) the car sat on the start line at 0 mph with its rear wheels smoking
for the rest of the run. Scenes A and B are the same place: the hashes differ (smoke, opponents leaving), and
the frame after the load (f00060) looks like the frames before it. Every load in the run went back to that same
spot. The after-load hash reads guest RAM at PCRTC_START right after `load_snapshot`, before the machine
restarts, so it shows that RAM and the scanout address came back, not that the renderer drew A again. Run 2
saves A on a different screen.

Disk: `hdd.json` plan build/keep, 19,070,976 B at start (the same size as the day's other built disks:
nfsdefault1011 and gtasagpu1011 runs; the sha256 differs per build). `hdd.after.json`: no errors, 94 titles
harvested; the 92 titles the reference run harvested have identical hashes, including 55530036 `fa079adf42d5`.
The other two (5454000E, 5454000F) are goldens added to the store since the reference.

### Run 2 (1-1791764800-snapshot1011-813455)

The branch with master merged (4c4e5f98a9; master's only emulator change in the merge is the `submit_frames`
default, 2 to 3, in `xemu_android.cpp`). The sequence starts 76 s after the GPU, 44 s earlier than run 1, so A
falls before the race.

c1 in the frames (`frames/index.tsv` times, which agree with the logcat clock):

| Frame | Time | Shows |
|---|---|---|
| f00034 | 18:22:17 | LOADING screen |
| (save `a`) | 18:22:17.8 | |
| f00035 | 18:22:20 | pre-race cutscene: the convertible outside BODY PAINT |
| f00036-37 | 18:22:23-25 | the grid, countdown "1" |
| f00038-41 | 18:22:28-37 | scene B: the race, HUD up, opponents gone up the road, the car on the line at 0 mph |
| (load `a`) | 18:22:38.1 | |
| f00042 | 18:22:39 | the BODY PAINT cutscene again |
| f00043-45 | 18:22:42-48 | the grid with the opponents, countdown "2", the race |

The renderer drew A's scene on the first frame captured after a load from a different 3D scene, with no black
frame (xemu #1500 not seen). No renderer fix was needed, so no grant was asked for. Then 60 s of play: the
countdown and race run again, six distinct hashes, and frames continue to the end of the run (f00134 at 18:27:09,
94 s after the sequence ended). Logcat at 18:27:08 shows VBLANK at 59.94 Hz. No `hakuX-crash`, `libc` or `DEBUG`
line.

| Step | Result |
|---|---|
| c1 | save `a` 338 ms, 58,387,943 B, hash `13a044252d30e57b`; scene B `a6e7a9412f954f47`; load 123 ms (check 3 ms), after-load `13a044252d30e57b`: match |
| c2 | 6/6 distinct, running |
| c3 | 20 cycles, 40/40 ok. save_ms 270 / 291 / 443 (min / median / max); load_ms 93 / 98 / 114 |
| c4 | paused, save 261 ms, still paused; load 98 ms (check 2 ms), paused again 250 ms later; resumed, hash moved |
| c5 | `refuse reason=controller-layout` after a 5 ms check, no reset, running, hash moved |
| done | snapshots=0 |

Disk: plan build/keep, 19,070,976 B at start; `hdd.after.json` no errors, 94 titles harvested, identical to run 1's
harvest and, on the 92 titles it shares, to the reference run's (55530036 `fa079adf42d5` in all three). The
deleted snapshots leave nothing in the harvest.

## 4. Phase 0 criteria on the Nova

| # | Criterion | Run 1 (2350466) | Run 2 (813455) |
|---|---|---|---|
| 1 | save A, play to B, load A: hashes match, frames show A | hashes match; frames cannot tell (same spot) | pass: hashes match, frames A = cutscene, B = race, after load = cutscene |
| 2 | 60 s after the load, no hang or crash, moving frames | pass (6/6) | pass (6/6, countdown and race replay) |
| 3 | 20 cycles in one run | pass, 40/40 | pass, 40/40 |
| 4 | save and load while paused | pass | pass |
| 5 | different controller layout refused before reset, game runs | pass | pass |

Across both runs (46 saves, 44 loads):

| | save_ms | load_ms | header check | state size |
|---|---|---|---|---|
| c1 | 263, 338 | 116, 123 | 3 ms | 59.02 MB, 58.39 MB |
| c3 (20 cycles each) | median 307, 291; max 489 | median 107, 98; max 116 | 2-12 ms | 58.4-59.1 MB |
| c4 (paused) | 296, 261 | 107, 98 | 10, 2 ms | 59.09, 58.85 MB |
| c5 | 294, 466 | refused, 0 ms load | 5 ms | 59.08, 58.83 MB |

A state is 58.4-59.1 MB in this title (the `bytes` the `[snap]` lines report: the vmstate written into the
image). save_ms includes the GPU write-back of dirty surfaces that every save starts with.

## 5. For phase 1

- **The build field refuses every other APK.** `build` is the commit plus the native library's build ID, and a
  mismatch is refused. A state made with one APK cannot be loaded by any other build, so a harness that wants to
  skip a route's first ~200 s with a stored state has to make the state with the same APK in the same install,
  or decide which fields may differ (the schema fingerprint is the field that decides whether the stream parses).
- **Where states live.** On a title run the state is inside `titles.qcow2`, which the dispatcher rebuilds from the
  goldens before every run (plan `build`). Nothing survives from one run to the next. Keeping a state across runs
  needs its own image, or phase 3's raw-disk work.
- **Controller layout is identity.** The harness must attach the same controllers when loading as when saving
  (the dispatcher's runs show `usb-xbox-gamepad` on ports 1 and 2).
- **Not saved:** the inline vertex buffer between BEGIN and END (one batch's vertices lost if a save lands
  there), and thumbnails on Android.
- **The route keeps going.** A load rewinds the game but not `route.sh`, which keeps sending its inputs on its own
  clock. Phase 1 needs a route verb that loads a state and starts the route's steps from the mark.
- **The 187 route.** In both runs the car never left the start line (rear wheels smoking, 0 mph, from the race
  start until the run ended, before and after any load); run 1 also met a mission briefing where the route
  expected the race. The reference run (1-1791713584-fastpaths1010-1525919) drove at 35 mph. This is the
  route's input timing in the race, not save states, and it is a weak scene for a test that needs movement.
