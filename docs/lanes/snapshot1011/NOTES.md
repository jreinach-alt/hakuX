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

## 3. Runs

(Filled in as results arrive.)
