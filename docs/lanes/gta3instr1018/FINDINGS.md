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

The six scripted drives into a car (gta3drive1017) were all void. So there is no `[dipwin]` window from inside
the car. The numbers that exist are lane.xbox's perflog run b3-B (R1+R2, 0 copies/flip, the owner's state,
10-18 01:29), from the older `hakuX-phase` line, over the 11 windows of its parked phase:

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
from 7.6 to 52 is the measurement this line was built for. It needs one in-car run.

Ranked by expected impact (probability it works times the size of the win):

1. **Attribute the in-car render passes, then remove the dominant cause.** Size: GPU 19.6 ms of render at
   52 passes. If the extra ~45 passes cost in proportion, removing most of them is several ms a frame of GPU
   time, the largest single thing between 25 fps parked and the 30 fps bar. Probability: the attribution
   itself is certain (every end is claimed, section 1). Whether the dominant cause can be removed is not known
   until it is named. On foot the two largest are the binding gate after an unbind (`bsnb`) and non-draw work
   (`bnd`: surface-to-texture copies and deferred downloads), which point at different code.
   *Run:* the perflog APK at ref 25915ae59e (or any later head of this branch), lane.xbox's protocol (debug
   slot 5, 28 s parked, RT held 60 s; `captures/lanexbox-fps1018/scripts/`). Read it with
   `dipwin_read.py --from <park start> --to <RT down>`.
2. **Stale vertex-RAM copy by page, not by span.** File and functions:
   - `hw/xbox/nv2a/pgraph/vk/vertex.c` `pgraph_vk_update_vertex_ram_buffer()`, lines 232-243: mark the other
     slots' pages in a per-slot bitmap (as `uploaded_bitmap` is kept) instead of widening `stale_min/max`;
   - `hw/xbox/nv2a/pgraph/vk/draw.c` `pgraph_vk_finish()`, the rotation block: copy the set runs, then clear;
   - `renderer.h` `FrameStagingState`: the bitmap, sized like the vertex-RAM buffer (`memory_region_size(d->vram)`).

   The page form copies what was written since the slot was last current: ~2 rotations of uploads,
   ~0.2-0.8 MB page-rounded, against 20 MB.

   Expected: on foot, `stale` 2.19 → ~0.05 ms/flip and `Fen:` 2.36 → ~0.2 ms/flip on the PFIFO thread.
   In the car it removes the stale share of the 7.1 ms `Fen:`, which is unmeasured. Probability that the copy
   goes: ~0.95. These are the only writers of the per-slot copies (vertex.c:222 and the two rotation copies;
   the render thread's `RCMD_VERTEX_RAM_UPDATE` handler is never enqueued). Whether it moves the parked frame
   depends on whether the PFIFO thread is the stage that sets it there. The in-car run of lever 1 also reads
   `stale` against `rotfen`, which decides that before any code.
3. **Full-path pipeline binds.** On foot, 351 a flip at 4.6 µs each (1.60 ms/flip), and 3.5 ms a frame in the car
   (`Pipe:`). `drawrec1010` found a stale `shader_bindings_changed` sending 31% of NFS draws down this path
   (`HAKUX_DRAWREC=1`, default off). Size about 1-2 ms a frame. It is on neither thread's critical path in the
   numbers above.

## 5. Fable

Run `1792340341-gta3instr1018-509423` (same build and apk, `GPU: PurpleVK` checked, Nova) did not reach gameplay.
Its route ended on the main menu ("Default / Continue Game") at 147.8 s because its screen classifier was
unavailable. There is no gameplay window, so this section holds no Fable cost numbers. The fabledip1018 figures
(render-thread CPU 19.45 ms of a 57 ms frame, 148-283 full-path binds a frame) still have no `[dipwin]` split.

What the run does show is that the line holds on a second title. It has 122 windows (7,320 flips) from one tid,
and they are monotonic and flip-contiguous, with every end attributed. The menu runs at 16.7 ms/flip with
2.0 render passes/flip: one clear, one non-draw and one flip finish per two flips.

A Fable gameplay window needs a route that reaches the village without the classifier, or a run with the
classifier's model available. Read it with `dipwin_read.py --from <first gameplay time>`.
