# GTA III dip frame (#1049): what the `[dipwin]` line measured

The `[dipwin]` line (perflog builds, `hakuX-rpbrk`, one per 60 flips on the PFIFO thread) is described in
NOTES.md section 4. `dipwin_read.py` in this directory reads it out of a logcat:
`python3 dipwin_read.py logcat.txt --from HH:MM:SS` (the logcat's own clock).

## 1. The line is citable

GTA III, 172 gameplay windows (10,320 flips):
- the running totals `cfl`/`crp`/`cbrk` grow by exactly one window each time, from one tid;
- every render-pass end is claimed by a counted cause (`unattributed 0.00`);
- `[dipwin] fen` (2.36 ms/flip) agrees with the older `hakuX-phase` `Fen:` EMA over the same span (2.4 ms).

## 2. GTA III on foot (Nova, PurpleVK)

Run `1792340293-gta3instr1018-503029`:
- build: ref 25915ae59e, perflog, apk 67f93c3b4c86, `GPU: PurpleVK` checked (custom `vulkan.purple.so` loaded,
  `PurpleVK-public Adreno (TM) 740` selected);
- route: `gta-3`, Portland street on foot, `mark gameplay` 09:21:52 PDT, route end 09:27:33, adb failures 0;
- GPU clock 401-615 MHz, no thermal pause.

The game holds its 30 fps cap on foot (33.39 ms/flip), so these numbers are costs, not the cause of a dip.

### 2.1 Render-pass ends, per flip (7.64 begun, 7.64 ended)

| cause | per flip | what it is |
|---|---|---|
| `bsnb` | 4.02 | surface binding gate, no current colour/zeta binding (`update_surface_part()`, vk/surface.c) |
| `bnd` | 1.99 | non-draw commands: `copy_surface_to_texture` (vk/texture.c:1311) 1.12, `download_surface_record_deferred` (vk/surface.c:1276) 0.81, `upload_texture_image` (vk/texture.c:896) 0.06 |
| `bclre` | 1.01 | the clear path |
| finish (present) | 0.53 | `render_display()` presenting a surface drawn in the open command buffer |
| finish (vtx) | 0.09 | vertex-buffer-dirty finishes |
| query, fb-dirty, render-pass change, surface dirty | 0.00 | |

### 2.2 Costs, per flip

| item | calls/flip | ms/flip |
|---|---|---|
| finish, fence phase (`fen`) | 1.4 | **2.36** |
| of which: the stale vertex-RAM span copy (`stale`) | 1.4 | **2.19** |
| of which: `vkWaitForFences` on the next slot (`rotfen`) | 1.4 | 0.04 |
| of which: downloads, drains, deferred waits | | 0.13 |
| full-path pipeline bind (`pipe`) | 351 | 1.60 |
| of which: `pgraph_vk_bind_shaders` (`bind`) | 350 | 0.81 |
| of which: pipeline key build and compare (`key`) | 349 | 0.14 |
| of which: UBO descriptor writes (`descf`) | 350 | 0.20 |
| vertex-RAM sync (`vsync`) | 362 | 0.17 |
| vertex dirty copy (`vcopy`) | 20 | 0.02 (129 KB) |
| finish, submit (`sub`) | 1.4 | 0.11 |

**`Fen:` is not a fence wait.** 93% of it is one `memcpy`: at each frame-slot rotation, `pgraph_vk_finish()`
(vk/draw.c, the `vertex_ram_stale_min/max` block) brings the incoming slot's vertex-RAM copy up to date over
one span, from the lowest to the highest byte uploaded while it was not current. Uploads are scattered, so
129 KB/flip of real uploads becomes 30 MB/flip of copy: 14-23 MB per rotation in every window, 117-508 times
the uploaded bytes (median 242). The GPU wait itself is 0.02 ms/flip (median window).

## 3. The parked in-car phase

The owner's in-car state cannot be loaded by a dispatched run:
- the route grammar has no verb for the pause menu's Load row (a tap, or Android BACK);
- nothing in the dispatch path writes `savestate_auto_load`.

The six scripted drives into a car (gta3drive1017) were all void. This lane's own device runs therefore have no
`[dipwin]` window from inside the car; **section 6 has one**, reusing lane.gta3car1018's direct-adb runs of this
same instrument. The numbers below predate that: lane.xbox's perflog run b3-B (R1+R2, 0 copies/flip, the owner's
state, 10-18 01:29), from the older `hakuX-phase` line, over the 11 windows of its parked phase:

| per frame | on foot (this run, 172 windows) | parked in car (b3-B, 11 windows) |
|---|---|---|
| frame (G / flip interval) | 33.4 ms (cap) | 37.2 ms (24.9 fps) |
| GPU, total / render / transfer | 11.9 / 8.4 / 3.5 ms | **24.6 / 19.6 / 5.1 ms** |
| render passes | 7.7 | **52.4** |
| PFIFO thread busy (Tot - Idle) | 7.4 ms | 17.7 ms |
| Draw / Pipe | 4.2 / 1.6 ms | 8.9 / 3.5 ms |
| Fin / Fen | 2.6 / 2.4 ms | 7.6 / 7.1 ms |

## 4. The dominant cost, and the levers

In the parked car the largest measured cost is **GPU execution, 24.6 ms a frame (19.6 ms of it rendering), with
52.4 render passes a frame against 7.7 on foot**. On Turnip each render pass pays its own setup and, when it
runs in tile memory, a load and store of its attachments. Seven times the passes is what the car scene adds, and
the copies are not it (R2 takes them to 0 and the 52 stay; gta3dip1018). Which of the counted causes in section 2.1 grows
from 7.6 to 52 is the measurement this line was built for. **Section 6 now has it**, from a live in-car run
(`[dipwin]` reused by lane.gta3car1018 with its own direct-adb save-state protocol, not a dispatched run — this
lane's unblock option 1, NOTES.md 5.2).

Ranked by expected impact (probability it works times the size of the win):

1. **Attribute the in-car render passes, then remove the dominant cause.** Done (section 6.1): `bnd`
   (`copy_surface_to_texture`, the surface-sampled-as-its-own-texture feedback loop) is 80-141 of the
   66-152 render-pass ends a flip, depending on scene traffic. gta3car1018 built and ran the fix
   (`HAKUX_S2T_FB`, texture.c, off by default); it cuts `rp`/flip by a quarter to a half and `fen` with it
   (section 6.2), but does not reach 30 fps alone.
2. **Section 6.3: the untimed majority.** New from this attempt. Every named `[dipwin]` timer together
   (`fen` + `pipe` + `vsync` + `vcopy` + `sub`, not double-counting their nested children) accounts for only
   ~30-38% of the measured frame interval in the car; the rest (~24-27 ms/flip) is not inside any timer this
   line has, and it does not shrink when `HAKUX_S2T_FB` cuts the render-pass count. It is now the larger of
   the two known costs. Section 6.4 names where to put the next timer.
3. **Stale vertex-RAM copy by page, not by span.** File and functions:
   - `hw/xbox/nv2a/pgraph/vk/vertex.c` `pgraph_vk_update_vertex_ram_buffer()`, lines 232-243: mark the other
     slots' pages in a per-slot bitmap (as `uploaded_bitmap` is kept) instead of widening `stale_min/max`;
   - `hw/xbox/nv2a/pgraph/vk/draw.c` `pgraph_vk_finish()`, the rotation block: copy the set runs, then clear;
   - `renderer.h` `FrameStagingState`: the bitmap, sized like the vertex-RAM buffer (`memory_region_size(d->vram)`).

   The page form copies what was written since the slot was last current: ~2 rotations of uploads,
   ~0.2-0.8 MB page-rounded, against 20 MB.

   Expected: on foot, `stale` 2.19 → ~0.05 ms/flip and `Fen:` 2.36 → ~0.2 ms/flip on the PFIFO thread.
   Probability that the copy goes: ~0.95. These are the only writers of the per-slot copies (vertex.c:222 and
   the two rotation copies; the render thread's `RCMD_VERTEX_RAM_UPDATE` handler is never enqueued).
   **`stale` against `rotfen` is now measured in the car** (section 6.2): `stale` holds flat at ~3.5-4.0 ms/flip
   whether `HAKUX_S2T_FB` is off or on, while `rotfen` scales down with the render-pass count (7.56 → 3.72
   ms/flip). So `stale` is a real, separate cost from the feedback-loop bug, worth the same ~3.5-4 ms/flip here
   that section 2.2 measured on foot (there, 2.19 of 2.36). vtxstale1018's fix stands on its own merits either
   way; it does not compete with `HAKUX_S2T_FB` for the same ms.
4. **Full-path pipeline binds.** On foot, 351 a flip at 4.6 µs each (1.60 ms/flip), and 3.5-4.2 ms a flip in the
   car (`pipe`, section 6.2; 773-867 full binds/flip, far more than the 66-90 render passes/flip — most binds
   are not one per pass). `drawrec1010` found a stale `shader_bindings_changed` sending 31% of NFS draws down
   this path (`HAKUX_DRAWREC=1`, default off). Size about 1-2 ms a frame on foot; in the car it is smaller than
   the untimed majority (lever 2) but a candidate for the same instrument if that majority turns out to be
   draw-call issue cost rather than render-pass setup.

## 6. The in-car `[dipwin]` window: the fen split, and the untimed majority (brief step 2c/2d)

This lane could not reach the owner's in-car state through a dispatched run (section 3; the route grammar has
no Load verb). lane.gta3car1018 reached it with a direct-adb protocol on a device hold, running this lane's own
`[dipwin]` instrument (merged to master at `25915ae59e`/`b8f0b7349c`), and left the logcats on disk:
`captures/gta3car1018/runs/c2-{O1,F1,S1,F2}/logcat.txt` (`HAKUX_S2T_FB` off / 1 / 2 / 1, same owner save state,
same protocol as section 3's table). Re-reading them with this lane's own `dipwin_read.py` is the measurement
brief step 2(c)/(d) asked for; it needed no new device time, so none was spent. Two arms, full park+hold window:

| arm | `HAKUX_S2T_FB` | window | flips | ms/flip | fps | rp/flip |
|---|---|---|---|---|---|---|
| `c2-O1` | off | 11:24:34-11:26:02 | 2040 | 43.70 | 22.9 | 90.00 |
| `c2-S1` | `=2` | 11:29:42-11:31:12 | 2400 | 38.53 | 26.0 | 66.11 |

Both are one tid, running totals monotonic and flip-contiguous, every render-pass end attributed (section 1's
checks, run again on these logs).

### 6.1 Render-pass ends, per flip

| cause | O1 (off) | S1 (`=2`) | what it is |
|---|---|---|---|
| `bnd` | 80.83 | 57.74 | non-draw commands, almost all `copy_surface_to_texture` (texture.c:1311; +0x5a78d8 alone is 79.41 / 56.56) — the surface-sampled-as-its-own-texture feedback loop gta3car1018 names (its NOTES 4.1, 5) |
| `bsnb` | 5.61 | 5.15 | surface binding gate, no current binding |
| `bclre` | 2.11 | 1.92 | the clear path |
| finish (stalled) | 0.56 | 0.30 | a flip that had to block on the GPU to free a slot (6.2) |
| finish (vtx / present) | 0.42 / 0.48 | 0.35 / 0.65 | |

`HAKUX_S2T_FB=2` cuts `bnd` by 29% in this stretch of road (the lighter traffic of batch c2's route segment,
not gta3car1018's heavier A1 segment where it predicted a bigger cut) — consistent with gta3car1018's own
reading that the gain tracks scene traffic, not a fixed ratio.

### 6.2 The fence split (brief step 2c): `fen`'s children, measured, not inferred

`fen` (`finish_fence`) holds nine sub-timers (draw.c `DW_TIMERS`); none were read against a live in-car run
before this attempt. Per flip, ms (not double-counted: `fen` is the parent, these are its children):

| | O1 (off) | S1 (`=2`) | what it is |
|---|---|---|---|
| `fen` (total) | 11.92 | 7.53 | |
| `rotfen` | 7.56 | 3.72 | `vkWaitForFences` on the next slot — a real GPU-execution wait |
| `stale` | 3.93 | 3.47 | the stale vertex-RAM span `memcpy` at rotation (section 2.2's cost, now priced in the car) |
| `rotw` | 0.00 | 0.00 | `wait_frame_submitted` for the next slot, *before* `rotfen` |
| `rtfen` | 0.00 | 0.00 | render-thread-context `vkWaitForFences` |
| `defw` / `ndw` | 0.17 / 0.06 | 0.12 / 0.06 | deferred-finish waits |
| `dl` / `drain` / `fall` | 0.30 / 0.01 / 0.03 | 0.23 / 0.01 / 0.02 | downloads, framebuffer destroys, flush-all |

`rotw` (the software wait for "has the render thread submitted yet") costs nothing in either arm — cross-checked
against the pre-existing `[rwait526]` line (draw.c, independent of `[dipwin]`, unconditionally compiled), which
reports the same site by name: every 10 s window in both logs shows `rotate calls=400-500 waits=0 blocked=0`.
The render thread has always already submitted by the time the PFIFO thread asks. So `rotfen`'s cost is not a
software/scheduling stall — the submission already happened; the thread is blocked in the kernel on a fence that
the GPU has not yet signalled. `finish (stalled)` (6.1) tracks `rotfen` almost exactly (7.54 vs 7.56; 3.61 vs
3.72), which is the same fact from the other side: a "stalled" flip is one where the fence forced a real wait.

This answers the open question from section 4 lever 2: `stale` (3.5-4.0 ms/flip) does not move with the
render-pass count the way `rotfen` does (7.56 → 3.72 as `HAKUX_S2T_FB` cuts `rp` by a quarter) — it is a separate
cost, present whether or not the feedback loop runs, in the same ms/flip range this lane measured on foot.

### 6.3 What `[dipwin]` still doesn't time: the untimed majority

Summing every *top-level* `[dipwin]` timer (not its nested children, to avoid double-counting: `fen`, `pipe`,
`vsync`, `vcopy`, `vclr`, `sub`) against the measured frame interval:

| arm | ms/flip (measured) | named timers, summed | named share | untimed |
|---|---|---|---|---|
| O1 (off) | 43.70 | 16.68 (`fen` 11.92 + `pipe` 4.15 + `vsync` 0.27 + `vcopy` 0.05 + `sub` 0.29) | 38% | **27.02 ms/flip** |
| S1 (`=2`) | 38.53 | 11.38 (`fen` 7.53 + `pipe` 3.33 + `vsync` 0.25 + `vcopy` 0.03 + `sub` 0.24) | 30% | **27.15 ms/flip** |

The untimed span is the larger of the two costs in both arms, and it does **not** shrink when `HAKUX_S2T_FB`
removes most of the feedback-loop render-pass breaks and cuts `fen` by 37% — it holds flat at ~27 ms/flip while
`rp`/flip drops by a quarter and the measured frame drops by 5.2 ms. Whatever this is, it does not scale with
the render-pass-break count the way `rotfen` does.

A corroborating, independent signal: the pre-existing `[rwait526]` line (6.2) also reports each reporting
thread's own CPU time (`thr_cpu_ms`, `CLOCK_THREAD_CPUTIME_ID`, not wall time — it excludes real blocking like
`rotfen`'s `vkWaitForFences`). Near the main menu, before the save state loads, that thread's CPU duty is
~4-6% of wall time (`thr_cpu_ms` 417-600 per 10.0 s window). Once the car scene is parked, it jumps to ~55-64%
(`thr_cpu_ms` 5400-6358 per ~10.0 s window) — in **both** arms, on or off the switch, matching the untimed
majority's refusal to move with `HAKUX_S2T_FB`. The thread is not idle or scheduled out for that time; it is
busy doing something `[dipwin]`'s timers don't wrap.

### 6.4 The lever this leaves for the next lane

`[dipwin]`'s timers cover: vertex sync/copy, full-path pipeline/shader-bind/descriptor-set, finish/fence
phases. They do **not** wrap the render-pass begin/end and draw-call issue path itself — the actual
`vkCmdBeginRenderPass`/`vkCmdEndRenderPass`/`vkCmdDraw*`/state-tracking cost of walking 66-152 render passes and
773-1086 full-path binds a flip. That is where the next timer goes: `hw/xbox/nv2a/pgraph/vk/draw.c`, around
whatever function issues the per-draw command-buffer work between a render-pass begin and its matching end (not
instrumented by this attempt — the board claim for this lane covers `draw.c`; a resume should re-claim it the
same way section 2 of this file's NOTES.md describes before adding a tenth `DW_TIMERS` entry).

Named cost, with the bar in view: 30 fps needs 33.3 ms/flip. `HAKUX_S2T_FB=2`'s best clean reading (gta3car1018
NOTES 6.1, `S1`) is 35.89 ms/flip dipwin-measured, 27.9 fps. The untimed ~27 ms/flip here is already most of
that budget on its own, before `fen`, `pipe`, or anything else — larger than the fence wait `HAKUX_S2T_FB`
already cuts. **This is now the dominant unattributed cost**, and it is not small or certain enough to fix
blind: the next lane needs to time it before naming a lever inside it.

## 7. Fable

Run `1792340341-gta3instr1018-509423` (same build and apk, `GPU: PurpleVK` checked, Nova) did not reach gameplay.
Its route ended on the main menu ("Default / Continue Game") at 147.8 s because its screen classifier was
unavailable. There is no gameplay window, so this section holds no Fable cost numbers. The fabledip1018 figures
(render-thread CPU 19.45 ms of a 57 ms frame, 148-283 full-path binds a frame) still have no `[dipwin]` split.

What the run does show is that the line holds on a second title. It has 122 windows (7,320 flips) from one tid,
and they are monotonic and flip-contiguous, with every end attributed. The menu runs at 16.7 ms/flip with
2.0 render passes/flip: one clear, one non-draw and one flip finish per two flips.

A Fable gameplay window needs a route that reaches the village without the classifier, or a run with the
classifier's model available. Read it with `dipwin_read.py --from <first gameplay time>`.
