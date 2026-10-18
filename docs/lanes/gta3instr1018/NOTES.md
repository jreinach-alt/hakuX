# lane.gta3instr1018 -- what the GTA III dip frame spends its time on (#1049, #433)

Status (10-18, attempt 1): instrument built (section 4) and run on the Nova (section 5). Selftest
`99-dipwin-counters.sh` 13/13. FINDINGS.md has the numbers. The parked in-car window, which the brief's step 5
asks for, is **blocked**: a dispatched run cannot load the owner's in-car state (5.3).

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
| `hw/xbox/nv2a/pgraph/vk/surface.c` | none (lane.defaulton1017 released it) | free: claimed 10-18 09:01 PDT (board 7a3f87c1f5) |

The instrument goes in `draw.c` (and one new header), emitted under the existing `hakuX-rpbrk` tag, so
profile.c is not needed. The row `[lane.gta3instr1018]` (lane.local, 09:15 PDT) says the lane claims its pgraph
files on the board before editing them; this lane added `draw.c`, the new header and its selftest fragment to its
own row, then `surface.c` for one perflog-only call at the binding gate (it ends the render pass for three causes
that the draw.c side cannot tell apart).

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

## 4. What was built

`[dipwin]`, one line under `hakuX-rpbrk` per 60 flips, perflog builds only (`#if NV2A_PERF_LOG`; the release
object has none of it). Field list: the comment above `DW_TIMERS` in `vk/draw.c`.

- **Counters** (`vk/dipwin.h`): `dipwin_add` is a relaxed `__atomic_fetch_add`, `dipwin_take` an
  `__atomic_exchange_n` against 0. The non-draw callers go in a 24-slot address table whose addresses are claimed
  by CAS and never cleared; only the counts are windowed. The line prints them as offsets from the library base
  (`nd=+0x...:n`), for `llvm-addr2line -f -e <unstripped libxemu .so>`.
- **The window**: `dipwin_flip()`, called only from the `VK_FINISH_REASON_FLIP_STALL` finish. Under perflog,
  `opt_stats_log_and_reset()` moved into that same branch, so `hakuX-stall RPBreaks:` and the old `rpbrk` line
  are 60-flip windows now too (still plain increments; `[dipwin]` is the one to cite). The non-perflog path is
  unchanged.
- **Break attribution**: `rp=` begins, `brk=` ends; `bfin=` finishes by reason; `bfbd`/`bpd` (draw setup:
  framebuffer dirty / render-pass change); `bqry` (the three occlusion-query sites); `bclr`/`bclre` (the clears);
  `bnd` (`pgraph_vk_begin_nondraw_commands`, its 12 callers in surface.c and texture.c by address); `bsnb`/
  `bsbd`/`bsmd` (surface.c's binding gate: no binding / surface buffer dirty / guest memory dirty).
  `brk` minus their sum = ends nothing claimed.
- **Timers**, each `n/ms`: `vsync` (sync_vertex_ram_buffer with ranges), `vcopy` (pgraph_vk_update_vertex_ram_buffer,
  with `vcopyK=` bytes), `vclr`; `pipe` (the full-path create), `bind` (pgraph_vk_bind_shaders), `key`
  (init_pipeline_key and the compare), `lru`; `descf`/`descm` (UBO descriptor writes, full / MFP path, `ubo=` the
  full-path ones that take a new set); `sub`, `fen` (finish_submit / finish_fence), and inside them `rtfen`, `ndw`,
  `defw`, `rotw`, `rotfen`, `dl`, `drain`, `stale` (with `staleK=`), and `fall` (flush_all_frames); `fin=` all
  finishes by reason. Timers marked x in the source subtract any finish nested inside them (`dw_fin_cum_ns`), so
  `fin=` is not counted twice.
- **Clock**: `nv2a_clock_ns()`, which is `cntvct_el0` on arm64, a register read.

Checks: draw.c and surface.c built with the compile line of an existing NDK perflog tree
(`wt/gta3fps1017b-apk`, NDK 29, `-O3 -march=armv8.2-a`), sources from this tree, with `NV2A_PERF_LOG=1` and with
it removed: both clean (the only warnings are in code this lane did not touch). Selftest: section 0's plan item 3,
as `docs/testing/jobs/selftest.d/99-dipwin-counters.sh`. The plain `+=` mutant mostly over-counts (its stale store
puts back a value the reader already took: 391 M against 8 M adds), so the check is "windows sum to the adds", not
"fewer".

## 5. Device runs (Nova, 10-18)

The dispatcher built both from ref 25915ae59e with `perflog: true` (debug package, apk 67f93c3b4c86). The
installed release build was not touched. Pilot use for requester `gta3instr1018` was 1080 of 1800 s
((480 + 90) + (420 + 90)).

| run | title / route | live, end | `GPU: PurpleVK` | gameplay | `[dipwin]` windows |
|---|---|---|---|---|---|
| `1792340293-gta3instr1018-503029` | GTA III / `gta-3` (on foot) | live listing, route end 09:27:33, adb failures 0 | yes | `fist-hud` MATCH, `mark gameplay` 09:21:52 | 172 in gameplay |
| `1792340341-gta3instr1018-509423` | Fable / `gen-fable` (`drive generic`) | ROUTE FAIL 147.8 s, "unknown screen for 91 s (model unavailable)" | yes | **no**: main menu | 122, menu and intro only |

The logcat has no literal `GPU: PurpleVK` string. The check used instead is the driver's own two lines: the
custom driver loads (`Loading custom Vulkan driver: vulkan.purple.so`) and `Selected physical device:
PurpleVK-public Adreno (TM) 740` appears. Both runs show both lines.

Reader: `dipwin_read.py` (this directory). The GTA III numbers and their reading are in FINDINGS.md sections 1-2.
The full reader output is not committed. Re-run it with `--from 09:21:52` on that run's `logcat.txt`.

### 5.1 What the GTA III run says (short)

- The line is citable. Running totals are monotonic and flip-contiguous from one tid, every end is attributed,
  and `fen` 2.36 ms/flip matches the `hakuX-phase` `Fen:` EMA of 2.4.
- On foot the game holds its 30 fps cap with 7.64 render passes/flip. The ends are `bsnb` 4.02, `bnd` 1.99,
  `bclre` 1.01, present 0.53 and vtx 0.09.
- `Fen:` is 93% the stale vertex-RAM span memcpy (2.19 of 2.36 ms/flip). That is 30 MB/flip copied for
  129 KB/flip uploaded. The fence wait is 0.04.
- The nd offsets were symbolised against the unstripped `libxemu.so` from the same build (linked 09:18:50,
  `.cxx/Release/6c4c3x1x`), with `llvm-addr2line -f -i -C -e <so> <off-4>`. The library's first PT_LOAD has
  vaddr 0, so the offset is the vaddr.

### 5.2 Step 5 of the brief: the parked in-car phase is blocked

The brief's step 4 runs GTA III "from the owner's in-car save state", with the parked phase first. That state
cannot be reached through `request.sh`:
- the route grammar has no tap verb and no Android-BACK verb (MainActivity toggles pause on KEYCODE_BACK,
  line 604), so a route cannot open the pause menu and press Load;
- no request field writes `savestate_auto_load`, and no request field stages a state file into a slot.

lane.xbox did it with direct adb (captures/lanexbox-fps1018/scripts: the state copied read-only into debug slot 5,
`input keyevent 4`, taps), which a lane may not do. Scripted driving is already void six times over
(gta3drive1017), so it was not tried a seventh time.

So the dominant parked cost is named from the existing b3-B `hakuX-phase` numbers: GPU 24.6 ms a frame, at 52.4
render passes against 7.7 on foot. The `[dipwin]` split of those 52 passes does not exist yet. FINDINGS.md
section 4 has the levers with file, function and expected number.

**No fix was made.** The one small, certain change the data shows is the page-granular stale copy (FINDINGS 4,
lever 2). It is not in this PR, for two reasons:
- (a) it edits `vk/vertex.c` (and `renderer.h`), which lane.fps1015's row still lists;
- (b) the brief asks for a before/after parked-phase number from the same protocol, and that protocol is the
  blocked one.

On foot it would save about 2 ms/flip of PFIFO-thread time at a frame that is already capped. That is a cost,
not the dip.

**Unblock**, either of:
1. a device-holding lane (lane.xbox) runs the perflog APK at 25915ae59e, or this branch's head, with its own
   in-car protocol and hands over the `logcat.txt`, read with
   `dipwin_read.py --from <park start> --to <RT down>`;
2. a dispatcher capability to load a save state: a request field that stages a state into a slot and sets
   `savestate_auto_load`, or a route verb for the pause menu's Load row.

### 5.3 Fable: void, and the cause was known

`gen-fable` is a `drive generic` route: it steers by the pathclass screen classifier plus a model. Memory
`gen-routes-die-without-a-model-key` (the 10-18 overnight: 8 of 10 `gen-*` routes voided on the classifier)
says that kind of route dies without a model key. It died exactly that way. **That is a process failure:** the
route kind should have been checked before queueing.

It was not retried. The cause is known, and it is not something this lane can change.

The 122 windows do show the line holds on a second title: monotonic, one tid, unattributed 0. In the menu that
is 16.7 ms/flip and 2.0 RP/flip. These are not gameplay numbers and are not used as such (FINDINGS 5).

### 5.4 Do not repeat

- Do not queue a `gen-*` route for a measurement while the classifier has no model. Record a route first.
- Do not try to reach the GTA III in-car state with a scripted drive (six void, gta3drive1017) or a dispatched
  run (no load path, 5.2).
- Do not re-read `Fen:` as a GPU wait. On foot it is the stale-span memcpy. In the car the split (`stale`
  against `rotfen`) is the first thing the in-car `[dipwin]` run decides.
- Do not re-run on-foot GTA III for `[dipwin]`. It is capped at 30 fps; its costs are in FINDINGS 2.

[lane.gta3instr1018] blocked: the parked in-car `[dipwin]` window. It needs either a device-holding lane to run
the perflog APK at 25915ae59e with lane.xbox's in-car protocol, or a dispatcher save-state load (5.2). The Fable
gameplay window needs a recorded route or the classifier's model.

## 6. Attempt 2 (10-18, resumed with a hostops addendum) -- why it did not continue

The resume brief carried an addendum (hostops, ~10:55 PDT) saying not to resume: lane.gta3car1018 was already
holding the Nova and running exactly the in-car `[dipwin]` protocol this lane's 5.2/5.4 named as the unblock,
reading this lane's FINDINGS.md. Checked before doing anything else:

- `origin/lane/gta3car1018` (head `1a68e4853b`) is still a draft (`State: draft` in its PR.md) and not an
  ancestor of `origin/master` -- the device work the addendum described is live, not finished and folded.
- It answers this lane's own blocker directly: the in-car parked scene is 151.65 render passes/flip (on foot
  7.64), 141.43/flip from one site (`copy_surface_to_texture`, texture.c) -- GTA III samples a 128x128 colour
  render target as a texture ~140 times a flip while it is still the bound colour target, so every sampling
  draw copies and ends the render pass: a feedback loop, not the vertex-copy or shader-bind cost this lane's
  step 2 instrumented for. Its NOTES.md section 0 already logs `[dipwin]` (this lane's instrument) as "run in
  the car; not rebuilt" and credits `vtxstale1018`'s page-granular copy as a second, smaller lever (~2-4 ms),
  not the cause.
- It has an opt-in fix built (`HAKUX_S2T_FB=1/2` in texture.c, off by default) and two golden-check requests
  queued against `RenderTextureLoop` (`1792347481-gta3car1018-2028877`, `1792347484-gta3car1018-2030801`) to
  confirm the pixel argument before the in-car A/B.
- `hw/xbox/nv2a/pgraph/vk/draw.c`, `surface.c` and `texture.c` are all live in that lane's working tree (its
  PR.md Files line) for this exact issue. Editing them here now would be a second writer on the same files for
  the same cause mid-measurement, not a second lever.

Nothing today's resume turned up should change the hostops call: no new addendum, no fold, no stall on
gta3car1018 visible from its branch (most recent commit 10:56 PDT area, PR.md ready, golden requests already
queued -- an active lane, not a stuck one). This attempt made no code or territory changes; it only re-verified
the reason to stay stopped and extended this table.

**Do not repeat:** re-reading the same in-car blocker and re-deciding to wait is not new work. The next useful
resume point is stated once, below.

[lane.gta3instr1018] waiting: for lane.gta3car1018's PR (`lane/gta3car1018`) to fold, or for its NOTES.md to
report its golden-check requests (1792347481-gta3car1018-2028877, 1792347484-gta3car1018-2030801) judged and the
in-car A/B run. Either resolves the in-car `[dipwin]` measurement this lane was blocked on and tells the next
resume whether `HAKUX_S2T_FB` closes the dip or whether this lane's own instrument still has unread numbers to
contribute (e.g. splitting `rotfen` further, or the Fable gameplay window once a route is recorded). Until then,
this lane should stay stopped rather than duplicate a live writer on `draw.c`/`surface.c`/`texture.c`.
