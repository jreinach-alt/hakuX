# lane.gta3instr1018 -- what the GTA III dip frame spends its time on (#1049, #433)

Status (10-18, attempt 1): Step 0. Nothing built yet.

## 0. Already tried

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| Parked dip scene, three perflog arms (R1, R1+R2, R1+R3) | `docs/lanes/gta3dip1018/FINDINGS.md` 1.1-1.5 (lane.xbox runs) | B (R1+R2, 0 copies/flip): G 38.1 ms, Tot 21.0, GPU 25.1, Fin 7.8, Draw 8.9; RP/frame 52.5 in every arm, against 22-30 while driving (pilot 343857) | copies are not the parked cost. **Do not re-run the copy arms.** The RP count and Fin are what to split |
| `hakuX-stall RPBreaks:/Finish:` and `hakuX-rpbrk` as the break breakdown | gta3dip1018 FINDINGS 1.3 | two tids print in one park window; values swing ~4900 to ~9500 | not citable. Cause read in the code: section 1.1 |
| Arm A's parked window | gta3dip1018 FINDINGS 1.4 | cold pipeline compile (lib_ms 50445) in the window | the parked phase must start after the compile settles; check `lib_ms` before reading a window |
| Fin/Fen against G, window by window | gta3dip1018 FINDINGS 1.5 | Fin tracks G (B: 48.1/14.7 ... 33.2/3.3) | Fen is a sum of several things (section 1.3); split it before naming it a fence wait |
| The owner's two long stalls | gta3dip1018 FINDINGS 2 | cold shader/pipeline compile | not this lane's cost |
| Fable / Blinx 2 gameplay dips | `docs/lanes/fabledip1018/FINDINGS.md` | render-thread CPU 19.45 ms of a 57 ms frame; the TLB walk 0.13 ms/frame; 148-283 full-path draws/frame; 340-730 KB/frame vertex redo | rank "time the copy and the full-path bind" first; **`tlbmap.mbox` stays parked** |
| Forza / Buffy dips | `docs/lanes/fpstel1018/FINDINGS.md` | Forza vCPU-bound (v_run 92-94% of F, GPU clock pinned 401 MHz); Buffy F-vs-Tot gap 7-9 ms steady; lockw, Flip, Fin ruled out for Buffy | a title-specific answer; not transferred here |
| R2 (direct-bind the forced-alpha copy), R3 (share one copy per surface state), default off | `docs/lanes/gta3fps1017b/NOTES.md` 0-6 | R2 takes on-foot copies 2.00/flip to 0; R3 never shares on the desktop | **do not rewrite**; R2 on is arm B's condition above |
| R1 (skip the #474 drain ahead of a plain colour copy) | `origin/lane/gta3drive1017` NOTES 6.2, 7-8; folded via gta3fps1017 | removed ~11.6 ms/flip of fence wait in the driving dips (perflog pilot 343857) | folded; not a lever here |
| Six scripted drive routes into the Kuruma | gta3drive1017 NOTES 8.2-8.7 | all VOID (help-box gate, mission restart, flips on the bridge ramp, Y out of the car) | **no scripted driving**; the driving phase comes from the owner's in-car save state with the trigger held |
| pgraph.lock (D7), vertex hazards (D6), pipeline compile as an ongoing cost (D8), guest work (D4), sysmem mode, faster clock | gta3drive1017 NOTES 3-4, 6.2 | ruled out in the dip windows | not levers |
| Per-draw recording census at the NFS race start; `HAKUX_DRAWREC=1` (VTX: one TLB re-arm walk per flip; SHC: clear the stale `shader_bindings_changed`) | `docs/lanes/drawrec1010/NOTES.md` 5, 8, 16-17 | the stale flag sends 31% of draws down the full path with a fresh UBO set; DRAWREC -1.5 ms/frame warm at NFS; default off | full-path binds in Fable may be this flag; the census counters (`shc_*`) already exist and are not re-built here |
| Recorder-thread probes (`probe_finish_book`, nd/rot waits) | drawrec1010 NOTES 13, 16 | DO NOT BUILD the recorder thread | the probe timing sites in `pgraph_vk_finish` are reused as a pattern, not re-run |
| The perflog runtime switch (pause-menu toggle) | `origin/lane/perflog1016:docs/lanes/perflog1016/NOTES.md` | waiting on a lend; **not on master** (`nv2a_perflog_on` has 0 hits) | this lane's instrument is compile-time `NV2A_PERF_LOG` only, so a release build carries none of it |

**Stop rule:** the same failure twice for one cause means stop, write what it was and what would change, and
report. No third try.

## 1. What the code says before any run

### 1.1 Why the break counters swing

`opt_stats_log_and_reset()` (`vk/draw.c` ~940) counts its 60-frame window with one `static int frame_counter`
and is called from `pgraph_vk_finish()` for two reasons (draw.c ~5423):

- `VK_FINISH_REASON_FLIP_STALL`, on the PFIFO thread (renderer.c ~4033), once per flip;
- `VK_FINISH_REASON_PRESENTING`, from `render_display()` (display.c ~1729) when the displayed surface was drawn
  in the current command buffer. That runs on the render thread (`RCMD_PROCESS_PENDING`/`RCMD_SYNC_DISPLAY`
  with `is_render_thread_context`).

So a "60-frame" window is 60 finishes of either kind: 60 flips when no presenting finish lands, 30 when each flip
has one. That is the 2x swing, and the two tids are the two callers. The `++`/`memset` on `g_opt_stats` are also
plain stores from both threads. The two callers are mostly serialised (the PFIFO thread waits on `pending_event`
while the render thread runs `RCMD_PROCESS_PENDING`), so lost increments are not the main error; the window
definition is.

A presenting finish also ends the render pass mid-frame (`rp_break_finish`) and submits. If the parked scene
takes one per flip, that is a break and a submit per flip that driving may not take: a candidate, to be counted.

### 1.2 What is already timed, and what is not

- `Syn:` is `draw_vtx_sync` (EMA per frame). It covers two of the seven `sync_vertex_ram_buffer()` call sites and
  includes the dirty-bitmap walk; the copy itself (`pgraph_vk_update_vertex_ram_buffer`) is not separated.
- `Sh:` (`pipe_bind_shd`), `Lu:` (`pipe_lookup`) and `Desc:` exist as EMA phase timers, not as per-60-flip sums
  with call counts, and do not separate the key build from the hash/LRU, or the UBO set write from the rest.
- `Fen:` is `finish_fence`. It is not only a fence wait (section 1.3).

### 1.3 What `Fen:` holds

`NV2A_PHASE_TIMER_BEGIN(finish_fence)` (draw.c ~5712) to its END (~5892), on the PFIFO path:

1. `pgraph_vk_staging_reset`, `vmaSetCurrentFrameIndex` (each flip);
2. `wait_frame_submitted(next_frame, RWAIT_ROTATE)` (waits for the render thread's submit);
3. `vkWaitForFences` on the next slot (the real GPU wait);
4. `pgraph_vk_complete_staged_downloads` (copies downloads into VRAM);
5. `vkDestroyFramebuffer` per framebuffer, and the deferred texture/surface release drains;
6. `memcpy` of the uploaded bitmap and of the next slot's stale vertex-RAM span (a span, min to max, not a sum).

Item 6 can be large: with three slots, every vertex upload while a slot was not current is re-copied into it at
rotation, over the whole span.

## 2. Territory (board, origin/board wave 310, 2026-10-18 03:11Z)

| file | live row | state |
|---|---|---|
| `hw/xbox/nv2a/pgraph/vk/draw.c` | none (lane.x1port1012 lists and released it) | free |
| `hw/xbox/nv2a/pgraph/profile.c` | lane.perflog1016 (GRANTED 10-16, waiting on a lend) | held: **not edited here** |
| `hw/xbox/nv2a/pgraph/vk/shaders.c`, `hw/xbox/nv2a/debug.h` | lane.perflog1016 | held: not edited here |
| `hw/xbox/nv2a/pgraph/vk/vertex.c` | lane.fps1015 (folded; row still lists it) | not edited here |
| `hw/xbox/nv2a/pgraph/vk/texture.c` | lane.gta3fps1017b | not edited here |

The whole instrument goes in `draw.c` (and one new header), emitted under the existing `hakuX-rpbrk` tag, so
profile.c is not needed. The row `[lane.gta3instr1018]` (lane.local, 09:15 PDT) says the lane claims its pgraph
files on the board before editing them; this lane adds `draw.c`, the new header and its selftest fragment to its
own row and nothing else.

## 3. Plan

1. One per-flip window, race-free: relaxed atomic adds, read and zeroed by exchange from one place (the
   FLIP_STALL finish on the PFIFO thread), windowed by flips, with running totals so monotonicity can be read off
   the log. The old `opt_stats_log_and_reset()` window keys on FLIP_STALL only.
2. In the window, per 60 flips, ms and calls: render-pass begins; break reasons (finish by finish reason,
   fb-dirty, query, clear, nondraw, external ensure) with the nondraw and external callers bucketed by caller
   address, symbolised offline; the vertex copy (calls, bytes, ns); the full-path shader bind, key build and UBO
   set write; and `Fen:` split into items 2-6 above, plus the PFIFO thread's waits on the render thread.
3. Selftest fragment: a threaded test of the counter header (window sums equal the increments; a plain `++`
   mutant fails), and a structural check that the window has exactly one emitter, on the flip path.
4. Perflog APK, Nova runs (GTA III parked then RT held from the owner's in-car save; Fable gameplay if on the
   device), FINDINGS.md.
