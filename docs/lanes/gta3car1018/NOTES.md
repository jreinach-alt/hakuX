# lane.gta3car1018 -- GTA III in the car: what the extra render passes are, and removing them (#1049, #433)

The bar is 30 fps while driving. On-foot numbers are not evidence about it and are not reported as progress here.

## 0. Already tried

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| `[dipwin]` line: race-free per-60-flip render-pass-break counters (`bsnb`, `bnd` by caller, `bclre`, finish by reason ...) and timed vertex copy / shader bind / fence split | `docs/lanes/gta3instr1018/` (lane/gta3instr1018 9eabf6a463, merged here) | only ever run on foot (run 1792340293-gta3instr1018-503029): 7.64 passes/flip, `bsnb` 4.02, `bnd` 1.99, `bclre` 1.01; `fen` 2.36 ms/flip of which `stale` 2.19 | the instrument this lane runs in the car; **not rebuilt**. On-foot numbers are a cost at a capped frame, not the dip |
| Parked dip scene, three perflog arms (R1, R1+R2, R1+R3), old `hakuX-phase` line | `docs/lanes/gta3dip1018/FINDINGS.md` 1.1-1.5 (lane.xbox b3) | B (R1+R2, 0 copies/flip): G 38.1 ms, GPU 25.1 (render ~20), Fin 7.8; RP/frame 52-55 in every arm | copies are not what holds the pass count. **Do not re-run copy arms** |
| `hakuX-stall RPBreaks:` / `hakuX-rpbrk` as the break breakdown | gta3dip1018 FINDINGS 1.3 | two tids, 2x swing, not citable | read `[dipwin]` only |
| Arm A's parked window after a shader-cache clear | gta3dip1018 FINDINGS 1.4 | cold pipeline compile (lib_ms 50 s) in the window | first arm after an install is a warm-up (W), not scored; check `lib_ms` flat before reading a window |
| R2 (direct-bind the forced-alpha copy), R3 (share one copy per surface state) | `docs/lanes/gta3fps1017b/NOTES.md`; lane.xbox b2/b4 palindromes | R2 copies to 0, fps -0.3/-0.9; R3 dup 0, nothing to share | not levers |
| R1 (skip the #474 drain ahead of a plain colour copy) | `origin/lane/gta3drive1017` NOTES 6.2, 7-8; folded via gta3fps1017 | +1.9/+2.7 fps parked (lane.xbox b2/b5) | folded; the baseline here |
| Six scripted drive routes into the Kuruma | gta3drive1017 NOTES 8.2-8.7 | all void | **no scripted driving**; the car comes from the owner's in-car state (slot 0, copied to debug slot 5) with RT held |
| pgraph.lock, vertex hazards, pipeline compile as an ongoing cost, guest work, sysmem mode, a faster clock, the TLB walk | gta3drive1017 NOTES 3-4, 6.2; fabledip1018 | ruled out | not levers |
| Stale vertex-RAM copy by page, not by span | `docs/lanes/vtxstale1018/` (lane/vtxstale1018 4507b8f2fa, draft; measured branch lane/vtxstale1018-m 54c0b3ee95) | selftest byte-identical, 7.5x fewer bytes on scattered writes; on foot ~2 ms/flip of PFIFO time; in the car unmeasured | merge it here only if the in-car `stale` share is real (brief step 3) |
| Per-draw recording census; `HAKUX_DRAWREC=1` (one TLB re-arm per flip; clear the stale `shader_bindings_changed`) | `docs/lanes/drawrec1010/NOTES.md` 5, 8, 16-17 | the stale flag sends 31% of NFS draws down the full path; -1.5 ms/frame warm at NFS; default off | a candidate for the full-path bind cost if the car shows it; the recorder thread is NOT to be built |
| Perflog runtime switch (pause-menu toggle) | `origin/lane/perflog1016:docs/lanes/perflog1016/NOTES.md` | not on master | this lane's instrument is compile-time `NV2A_PERF_LOG` (debug perflog APK) |

**Stop rule:** the same failure twice for one cause means stop, write what it was and what would change, and
report. No third try.

## 1. Base

`lane/gta3car1018` started at master 343221f6fc. The `[dipwin]` line is not on master, so the branch merges
lane/gta3instr1018: first `origin/lane/gta3instr1018` (25915ae59e, the instrument), then the lane's local head
9eabf6a463 (FINDINGS.md and `dipwin_read.py`, committed in its worktree but not pushed). Both are plain merges, so
master's history and gta3instr1018's are both ancestors and nothing was rebased.

## 2. Territory

Board at 9edbaaa813 (lane.local's row for this lane, 10:41 PDT): `docs/lanes/gta3car1018/**`, `captures/gta3car1018/**`.
The pgraph/vk files are claimed on the board when an edit needs them (section 5 says who holds each).

## 3. Device window

The owner released the Nova for the in-car work only (hakux-0b, 10-18): no on-foot runs, no parked-for-its-own-sake
runs. Hold `lane.gta3car1018` taken 10:45 PDT (device clock), wait-idle passed. The release app was alive at its
library screen with the display asleep; it was left alone.

Protocol: lane.xbox's (`captures/lanexbox-fps1018/scripts`), copied to `captures/gta3car1018/scripts` with paths and
hold name changed only: owner state in debug slot 5 (md5 c1978f47... equal to the release slot 0), pause-menu load
with an image check before every tap, 28 s parked (P+2..P+30), then RT held 60 s, screenrecorded. APK: the
dispatcher's perflog build of 25915ae59e (sha256 67f93c3b4c86), installed with `install -r`, shader caches cleared,
so the first arm (W) is a warm-up.

Released 10:56 PDT (`hold.sh release nova lane.gta3car1018`), prefs restored (RESTORE_OK), hakux-0b told.

## 4. In-car run, batch c1 (Nova, 10:46-10:56 PDT, perflog 25915ae59e)

Four arms on one APK: W (warm-up after the cache clear, not scored), A1, A2, A3. Every arm logged
`GPU: PurpleVK-public Adreno (TM) 740 (git-62ac221a33)`. Logs, screenrecords and contact sheets:
`captures/gta3car1018/runs/c1-*`.

| arm | PID | park start | RT down | moving span (from the screenrecord) |
|---|---|---|---|---|
| W | 5526 | 10:46:56.931 | 10:47:26.919 | RT+0..~40 |
| A1 | 12160 | 10:49:30.859 | 10:50:00.912 | RT+0..~10, then a crash and Wasted (on foot after) |
| A2 | 17031 | 10:52:04.947 | 10:52:35.148 | RT+0..~22 |
| A3 | 20714 | 10:54:39.032 | 10:55:09.011 | RT+0..~14 |

fps (hakuX-pace, windows wholly inside the span; `movescore.py`):

| arm | parked | moving (span) | RT hold incl. crash/Wasted |
|---|---|---|---|
| W | 20.2 | 20.7 (RT+1..41) | 20.0 |
| A1 | 20.6 | 23.0 (RT+1..11, 3 windows) | 28.6 (mostly on foot after Wasted: not the scene) |
| A2 | 20.2 | 24.5 (RT+1..23, 8 windows) | 25.1 |
| A3 | 19.2 | 19.4 (RT+1..15, 3 windows) | 17.7 |

No moving window reaches 30 fps; the bar is not met by this build.

### 4.1 The cause, counted (`dipwin_read.py`, A1 parked 10:49:32.9-10:50:00.9)

49.25 ms/flip, **151.65 render passes a flip** (on foot: 7.64).

| pass end | per flip | code that asks for it |
|---|---|---|
| `bnd` +0x5a6fac | 141.43 | `copy_surface_to_texture` (texture.c:1311, `pgraph_vk_begin_nondraw_commands`), called from create_texture's cache-hit copy (texture.c, the `copy_surface_to_texture` call after `TXW_BEGIN(CP)`) |
| `bnd` +0x590e6c | 0.98 | `download_surface_record_deferred` (surface.c:1276) |
| `bsnb` | 5.57 | surface.c binding gate, no binding |
| `bclre` | 2.00 | clear |
| finishes | vtx 0.61, present 0.43, stalled 0.59, flip 1 | |

Timers, ms/flip: `fen` 15.57 (of which `rotfen` 11.03, `stale` 4.00 at 49.8 MB/flip), `pipe` 4.21 at 1086 full
binds/flip, `bind` 2.02. Finish time: stalled 10.53, vtx 2.22, flip 1.96, present 1.17.

W's RT hold reads the same (50.81 ms/flip, rp 146.27, `bnd` 137.25, `fen` 15.32, `rotfen` 10.86). A2's RT hold,
with less traffic in view, 40.37 ms/flip at rp 68.92 (`bnd` 59.90).

**What is copied**: `[s2c]` pair #1, one 128x128 X8R8G8B8 colour surface @0x038aa080, sampled as texture
format 0x7 (component map forces alpha to one: reason `map`), about 230 copies/flip in W, `dup` 0 (every copy at
a new draw_time). `[surf92]` in A1 parked holds colour 0x038aa080 bound in 95 of ~352 samples and its zeta
0x0389a000 in 128 of ~378, while render-target switches are only 5.5-7.6 a flip. A surface's draw_time moves only
on a draw into it, so ~140 copies at ~140 new draw_times between ~6 switches means the target is sampled while it
is the bound colour target: **a feedback loop, one copy and one render-pass break per sampling draw**. It is
absent on foot and when the car is wrecked, and scales with the traffic in view (A2's lighter road: rp 69).

**Pass count against frame time**, 46 windows of A1-A3 (parked and moving), `rpfit.py`:
ms/flip = 30.89 + 0.1309 x rp/flip (r^2 0.66).

| rp/flip | windows | ms/flip | fps | fen | stale | full/flip |
|---|---|---|---|---|---|---|
| 0-30 | 1 | 33.0 | 30.3 | 2.77 | 2.27 | 396 |
| 30-60 | 3 | 39.4 | 25.4 | 8.23 | 3.38 | 716 |
| 60-90 | 5 | 44.3 | 22.6 | 12.67 | 3.91 | 844 |
| 90-120 | 6 | 42.5 | 23.5 | 11.16 | 3.93 | 921 |
| 120-150 | 11 | 45.6 | 21.9 | 12.67 | 3.80 | 1022 |
| 150+ | 20 | 56.7 | 17.6 | 19.36 | 4.10 | 1218 |

`hakuX-phase` in A1: windows with the copies run GPU 34-43 ms (render 20-24, transfer 7-20); copy-free windows
run GPU 21-23 ms (transfer ~1) with the PFIFO thread idle 13-15 ms at the 33.3 ms cap.

**stale against rotfen in the car**: `stale` ~4 ms/flip (50 MB/flip) against `rotfen` ~11 ms/flip. `rotfen`
and the stalled finishes are GPU waits that grow with the copy breaks; `stale` is the vertex-RAM memcpy and stays
~4 ms whatever the pass count. vtxstale1018's change is worth at most ~2-4 ms of PFIFO time here: a second lever,
not the cause.

## 5. The lever

Ranked by probability x size of win:

| lever | where | expected | probability / evidence |
|---|---|---|---|
| **A1**: while the surface stays the colour target, a slot that holds a copy of it from this run keeps sampling that copy (HAKUX_S2T_FB=1) | texture.c, create_texture's cache-hit surface-to-texture branch; `s2t_fb_keep()` / `s2t_fb_record()` | rp ~150 -> ~10/flip; by the fit 49 -> ~32 ms/flip parked; copy-free windows already run at the cap | high: the removed call is the measured 141/flip; R2 showed the pass break, not the copy, is the cost, and A1 removes the break |
| A0: the same keep, only for a stage whose shader program does not read its texture (HAKUX_S2T_FB=2) | texture.c, same site; `s2t_fb_stage_reads()` | as A1 if GTA's sampling stages are NONE/PASS_THROUGH/CLIP_PLANE/DOT_PRODUCT; exact in pixels | unknown: the census line in this build (`[s2c] ... fb[n nos keep]`) counts it |
| B: in-pass feedback (attachment feedback loop layout + self-dependency) | draw.c / surface.c render pass | removes the break with exact per-draw reads only for same-pixel reads | low: non-local reads are undefined in Vulkan; a 128x128 env target is sampled at other texels |
| vtxstale1018 merge | vertex.c, draw.c | 2-4 ms PFIFO | high, small |

A1's pixel argument: within one run of draws into the target, a draw reads the target as it stood at the run's
first sample instead of after the draw before. A read of the surface after the run (the main scene sampling the
finished target) copies as before and sees every draw. On the hardware the texture cache is not coherent with the
colour writes of a running draw sequence either. `Texture render target::RenderTextureLoop` (the suite's only
test that samples the bound target) draws once per binding, so the first sample copies and nothing is kept.

Why bind_textures runs at every one of those draws: each draw into the target while a stage is bound over its
memory calls `pgraph_vk_surface_written_while_sampled()` (draw.c), which bumps `texture_state_gen` and drops the
stage's register cache, and GTA re-writes the stage's registers per draw, so the next draw re-enters
create_texture, sees a new draw_time and copies. The same hook makes the draw after the target's last draw run
bind_textures, which is where the switch sees the colour target change and ends the run.

Run boundary, stated: a run is per slot; it ends at the flip, at a bind_textures pass that sees another colour
target, when the slot binds anything else (`s2t_fb_check_slots()` after the bind loop), and when the node is
written or released or the surface view retires. Not covered: a target left for another one by a draw that wrote
no colour, then re-entered, with the slot bound to it throughout and no bind_textures in between. Closing that
needs a run boundary in bind_surface (surface.c); the switch is off by default meanwhile.

### 5.1 Builds

The `[dipwin]` line is under `#if NV2A_PERF_LOG`, so the arms run a perflog build of this branch. The dispatcher
builds `$D/builds/<sha>-perflog.apk` when it serves a request with `--perflog --ref <sha>`; the in-car arms then
run that APK under a Nova hold, the switch set per arm through the env_vars pref (`arm.sh` writes and restores it).
