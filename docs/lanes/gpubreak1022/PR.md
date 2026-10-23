# gpubreak1022: where GTA III's GPU time per draw goes in the main pass -- a `hakuX-gpubrk` breakdown line and the arms that separate the candidates (#433)

State: draft

Lane: gpubreak1022            Issue: #433 (0.5)
Base: lane/drive1022 @ 03e01c3aad
Files: docs/lanes/gpubreak1022/PR.md, hw/xbox/nv2a/pgraph/vk/{gpubrk.h (new),draw.c,renderer.h,renderer.c,shaders.c},
  docs/testing/perf/gpubrk_sum.py (new), docs/testing/jobs/selftest.d/99-gpubrk-fit.sh (new),
  docs/testing/dispatcher.sh (LOGCAT_SPEC), android/.../HakuXApplication.kt (LOG_TAGS)
Prediction: GTA III on the heavy save state, perflog build, no env: the `hakuX-gpubrk` line's main pass reads
  `mrep` < 1.3 (sysmem, or one tile) in most windows, and `mus` lands within ±20% of the control's
  (R+Post)/full, 26-31 us (Step 0 row 60). `HAKUX_GPUBRK=0` moves hakuX-phase R/draw and fps by under 3%.
  Falsified when `mrep` >= 1.6 in most windows (the main pass is tiled after all, and `mus` is one tile's
  time), or when `mus` is off (R+Post)/full by more than 2x either way (the line does not measure what
  hakuX-phase does)
Needs device: yes. The Nova, perflog build of this branch, heavycap1022's heavy save state; the arm table
  below, `GPU: PurpleVK` in every run. No fix is built, so there is no fix A/B
Needs NDK: yes
Selftest: 99-gpubrk-fit -- builds vk/gpubrk.h on its own (fit, R², percentiles, the line's formatter) and reads
  the line back with gpubrk_sum.py; four mutants of gpubrk.h and one of the line's field names must fail

## Step 0: already tried

Sources:
- the brief's `git log -i -E --grep='perf.?query|timestamp|gpubrk|TU_DEBUG|sysmem|gmem|lrz|fragdepth|pipeline bind|bind'`
  over all refs since 09-01 (569 hits), read by subject, then by diff where the subject was a GPU change;
- the lane docs of gta3instr1018, gta3dip1018, fabledip1018, fpstel1018, fpsdiag1018 and fpsnext1019 (worktree copies
  and `git show lane/<name>:docs/lanes/<name>/...`), plus gpunonrender, fpsbelow1012, bf2push656, bf2stall433,
  drawrec1010, perdraw1009, p1zeta1022, p9pipekey1022, p10fragdepth1022, p11vtxbump1022 and gpuclock;
- /home/justin/hakux-work/captures/owner-play-20261023/drive1022/ (README.md, arm_sum.py, the four split logcats) and
  captures/fpsnext1019/runs/sys1-*, re-read here with a join of `[dipwin]`, `hakuX-phase` and `xemu-work` by second;
- the Mesa fork (/home/justin/hakux-work/mesa-turnipfork, read-only): tu_query_pool.cc, tu_cmd_buffer.cc,
  tu_autotune.cc, tu_pass.cc, tu_util.cc, tu_device.cc, tu_knl_kgsl.cc, ir3_compiler.c, and the a7xx perfcounter
  tables.

| date | commit/doc | what it measured or changed | verdict | meaning here |
|---|---|---|---|---|
| 10-06 | d946e1ba44, f4ffe285e7, folds 0342eba317, bf85412b88; gpunonrender/PR.md:43,:92 | `HAKUX_GPUXFR=1`: outer vs in-pass stamps, a census of loads/stores per pass (NG Black, DOA3) | Outer minus in-pass 11.7 ms (NG Black), 19.3 ms (DOA3); avoidable loads/stores < 0.4 ms/frame | On those titles the cost was per-tile replay, not bytes. GTA III never measured this way. The new line takes the outer/inner pair per pass |
| 10-06 | gpunonrender/NOTES.md:505-529 | `HAKUX_GPUTS_INRP=0` drops the in-pass pair (and its WFI per tile) | Below the ±10% resolution | In-pass stamps do not distort R much. K-draw stamps here are TOP (no WFI) by default for the same reason |
| 10-07 | fold c6298a383d | GMEM vs sysmem on replay-bound titles | Profiled autotune picks sysmem itself on DOA3 and NG Black | - |
| 10-11 | 40c67b354c, ede7c891c5; fpsbelow1012/NOTES.md:236-242 | D32S8's stencil plane gives tile_align_w 192, so 2 tiles at 640x480 and no binning; `HAKUX_ZETA_D24` | R x0.57 NG Black, x0.64 DOA3, x0.59 Buffy | Where the main pass replays per tile, the replay roughly doubles R |
| 10-22 | a16312d478 (p1zeta1022, lane) | D24 by title table, A/B on Blinx 2 and Fable | B/A 0.996 and 1.000: falsified | Not every title is replay-bound |
| 10-22 | drive1022 pid28042 (P1 arm, 03e01c3aad); drive1022/README.md:20-25 | GTA III owner drive with `HAKUX_ZETA_D24=1` (host format 0x81 logged) | R/draw 26.2 vs 26.0; GPU 26.3 vs 25.3 ms; no band faster | **Refuted for GTA III.** With control X at 4.4 ms against R 20.9 ms, an even two-tile replay (X >= R) is ruled out too: the main pass is sysmem, one tile, or very uneven tiles. The line's `rep` field answers which |
| 09-27..10-10 | d0efa4c1f3, 61e0edf87c, fold 26e8d1104c, 81ab5f3418; gmem474/NOTES.md:41 | Per-title `TU_DEBUG` render modes (kTitleRenderModes: nobin 0x4, sysmem 0x8, forcebin 0x10, gmem 0x1000) | Sysmem for AUF, DOA Ultimate, NFS MW; GTA III absent; forcebin never won on the Nova (fpsbelow1012/NOTES.md:272) | `TU_DEBUG` arms are cheap to run through env_vars |
| 10-01 | 6e2e81f7a0 (collapse433) | Sysmem on BF2 heavy views | No lift | - |
| 10-09 | fold cc775f16e8 (profileddefault1008) | `TU_AUTOTUNE_ALGO=profiled` | Default does not flip | - |
| 10-18 | lane/gta3dip1018 NOTES.md:17, FINDINGS.md:166 | Sysmem and the GPU clock in the dip frame | "not a lever here"; GPU busy 21.9 ms of a 47 ms frame | Dip frames then were CPU-paced |
| 10-19 | fpsnext1019 FINDINGS.md:8, NOTES.md:459-520 | `TU_DEBUG=sysmem` alone on GTA III | +3 fps (24.2 vs 21.3), rp 70.3 vs 130.2 | Not a per-draw result: the pass count changed with it |
| 10-19 | f93f9732e7 | Sysmem stacked on `S2T_WIDEN` | Worse (rp 148.4, 19.9-20.6 fps) | Do not stack |
| 10-19 | 5c9fc668cd (lane); fpsnext1019/NOTES.md:1331-1383 | G3 re-test, SYS vs Base | Never scored. Scored in this lane's Step 0: Base1 15.9 fps / R 24.3 ms / 20.1 us per draw / 1244 draws; SYS1 29.5 / 21.5 / 29.3 / 717; SYS2 21.8 / 21.6 / 22.9 / 1027; Base2 16.8 / 23.2 / 23.1 / 1046 | Sysmem R/draw 23-29 us against GMEM's last-tile 20-23: not the 2x a replay would show |
| 10-19 | 6e15857f0e, 401c075ef7 (fbfit, lane) | ms/flip against `full` and rp; `HAKUX_FBLOOP` | r² 0.80 against full, 0.70 against rp, 0.046 ms/draw. FBLOOP +1.31 ms (in-pass barrier forces disable_gmem + WFI) | Cost follows draws, not passes |
| 10-02 | 2d0d03edb6 (reverted b80a92b61f), fold 9550493846 (bf2push656) | Vertex uniform rows as push constants | UBO binds/draw 0.916 -> 0.453; GPU ms/draw 0.0153 -> 0.0149 | **Refuted:** a UBO descriptor bind costs at most ~1 us of GPU. A descriptor-rebind skip arm predicts < 3% |
| 10-02 | bf2stall433/NOTES.md:26-30, :211-230; fold 2790e4b700 | State emitted per draw; `TU_DEBUG=sysmem,syncdraw` | Pipeline bind on 808 of ~2150 draws; syncdraw adds only +3.8 us/draw | Draws already run close to one at a time on the GPU |
| 10-02 | bf2push656/NOTES.md:208-232 | Adreno CP/SP busy counters proposed | Never done | The line's optional KGSL counter sampler is that step |
| 10-10 | e7f2e720c8, b10dcdb737 (drawrec1010) | Full-path census | Same key 48.3%, not entered 31.9%, LRU 11.6% (CPU) | The key is often unchanged; whether the GPU sees a bind is a different question (next row) |
| 10-22 | this lane, code reading: vk/draw.c:7748-7782, :3277-3360, :2729-2752 | Is the "bind per draw" the same pipeline re-bound? | No. `vkCmdBindPipeline` runs only when `pipeline_binding_changed` (set when the LRU hit differs from the bound node, or on create/swap) or at a pass start. Not-dirty and same-key paths return before setting it. The control's `xemu-work` PBnd reads 0.3-0.5 x full | **Refuted as stated in the brief.** `[dipwin] bind` (~= full) is `pgraph_vk_bind_shaders` CPU time, not a GPU bind. About 40% of draws switch pipeline for real; the fix the brief names does not exist to build |
| 10-09 | 9bdfd6d4f0 (perdraw1009) | `HAKUX_UNI_BULK`, `_UBERCACHE`, `_FOGCACHE` | CPU-side uniform cuts | CPU only |
| 10-18 | 25915ae59e, fold ed00cc41e3 (gta3instr1018); FINDINGS.md:43-46,116 | `[dipwin]` CPU timers on GTA III | bind ~= full; in the car GPU 24.6 / R 19.6 / X 5.1 ms | GPU side not split |
| 10-22 | 08827e843a (p9pipekey1022, lane) | `HAKUX_PIPEKEY_DIRTY` | Built, not A/B'd; ceiling 0.17 ms/flip | CPU only |
| 10-18 | fabledip1018 FINDINGS.md:69,172; fpsdiag1018 FINDINGS.md:174 | A per-draw GPU timer | Proposed, never built | This lane builds it |
| - | uberspike569/NOTES.md:81; energymap507/NOTES.md:273 | gl_FragDepth write disables early Z | Observation | - |
| 09-10 | 9308e9eab5 (cited by p10fragdepth1022) | gl_FragDepth forced to 0.25 | No change in 144 captures | Pixel test, not timing |
| 10-22 | e72b4d798a (p10 arm A, lane) | Conservative depth | No code: tu_lrz.cc keeps LRZ under LESS/LEQUAL only with depth_greater | Cannot bring LRZ back |
| 10-22 | 31770d97e5, 14ed20a3df (p10 arm B, lane) | `HAKUX_FRAGDEPTH=off` | Built, no device A/B; PLAN.md:572-600 bounds the term at 5-7 ms/flip | The late-Z arm; not on this base |
| - | grep of docs/lanes, handoffs/fps30-1022, git log | `nolrz`, perfquery, VK_KHR_performance_query, KGSL counters | 0 hits | Never tried. Turnip on KGSL never exposes VK_KHR_performance_query (tu_device.cc:268 with tu_knl_kgsl.cc:1939) |
| 10-02 | 57fe561924 (bf2stall433); NOTES.md:175-195 | Vertex RAM from a device-local mirror | GPU B/A 1.004 | **Refuted on BF2:** fetch from host-visible memory is not the per-draw cost |
| 10-19 | fpsnext1019/NOTES.md:1270-1300 (C2 vtxstale) | Stale vertex copy removed | CPU saving absorbed by the GPU wait | - |
| 10-22 | 36db6869d2 (P11, on the base); drive1022 pid9072 | `HAKUX_VTXHZ_BUMP=1` | R/draw 21.9 vs 26.0 | Partly a measurement effect (next row), but real on GPU total: GPU/full 26.7 vs 31.8 us, 26.3 vs 31.3 at 800-1000 draws, 24.8 vs 28.4 at 1000-1200 |
| 10-22 | this lane: hakuX-phase re-read, pid21946 / pid9072 / pid28042; draw.c:4524-4562, :5405-5453 | Are R and X what they say in heavy windows? | Only the first 48 passes of a command buffer are stamped (`GPU_TS_MAX_RENDER_PASSES`); passes 49+ land in `Post` and so in X. Control Post: 0.6 ms at RP <= 30, 4.7 ms at RP > 48; by band 0.6 / 2.5 / 4.7 / 7.8 ms. (R+Post)/full is 30.7 / 29.0 / 27.9 / 26.2 us (-15%), where R/full falls 28.6 -> 22.5 (-21%) | "X grows in heavy windows" is mostly unstamped main-scene passes; R/draw under-reads heavy windows. Fits on the control: GPU = 10.0 ms + 19.7 us x full (r² 0.49); R+Post = 3.2 + 25.2 us x full (0.60). P11: 9.4 + 17.2. The new line stamps every pass (no 48 cap) |
| 10-05 | 521ea8a93e..bcd0848235 (gpuclock, lane, not folded); fpsdiag1018/NOTES.md:20-26 | kgsl gpuclk / busy telemetry | Nova at performance_mode 0 sits at the 401 MHz floor for all of gameplay; GPU time elasticity to clock 0.6-0.98 across titles | 26 us at 401 MHz is ~10.4k GPU cycles a draw. The line logs MHz per window; a pm=2 run is an instrument arm only, never a fix |

Nothing in the table timed the GPU inside the main pass, below the pass level, or read a hardware counter. Two
claims the brief started from do not hold: the pipeline is not re-bound unchanged (it changes on ~40% of draws),
and `R` is a truncated sum in the heavy windows. Neither is a reason to rebuild a refuted approach; the
instrument below is new.

## 1. What the line measures

**No counters, so stamps.** VK_KHR_performance_query is not exposed on KGSL Turnip (row 56). The line probes
it once, logs `perfquery unavailable` in its `on` line and as `perfquery=` on every window, and carries on.
Hardware counters come only through the optional KGSL sampler (`HAKUX_GPUBRK_KGSL=1`), below.

**Five stamps per pass, in a pool of the line's own.** Every pass `begin_render_pass()` opens is stamped
(draw.c:4045-4081), with up to 256 passes and 2048 stamps per command buffer. hakuX-phase stops at 48
(row 60), and the line has no such cap. The stamps:
- O0: TOP, before vkCmdBeginRenderPass;
- I0: TOP, first in the pass;
- Ie: TOP, just before Iw;
- Iw: BOTTOM, last in the pass;
- Ow: BOTTOM, after vkCmdEndRenderPass.

Inside the pass there is also one stamp every `HAKUX_GPUBRK_K` draw commands (default 16). These are TOP unless
`HAKUX_GPUBRK_WFI=1`. A draw command is one vkCmdDraw*, or one entry of an indirect or multi draw. Stamps tick
on the always-on counter, 19.2 MHz, so 52 ns a tick (tu_device.cc:1180, :1296).

**What Turnip does with a stamp inside a pass** (tu_query_pool.cc:2100-2171):
- It is a CP_REG_TO_MEM of the always-on counter, recorded into `draw_cs`.
- A sysmem pass runs `draw_cs` once.
- A GMEM pass replays `draw_cs` in the binning pass and in every tile, so each replay overwrites the value and
  the last tile's lands. The source comment says so ("the user gets the last one if we use GMEM").
- Anything but TOP_OF_PIPE first emits a WFI, which in a GMEM pass means a WFI per tile.
- O0 and Ow are in the primary stream, so they span binning, every tile, and the tile loads and stores.

**How the stamps combine.**
- `in` = Iw - I0. This is the whole pass on sysmem, and the last tile's draws (without its loads/stores) on GMEM.
- `out` = Ow - O0. This is the whole pass in either mode.
- `mrep` = Σout / Σin over the main passes. It is ~1.0 for sysmem or one tile, and ~n for n even tiles.
  - The line also logs the median and max of the per-pass ratio (`mrepmed`, `mrepmax`).
  - `mode` reads `mrep`: `s` < 1.3, `u` < 1.6, `t` above.
  - A single tile with heavy loads/stores reads `u`. Uneven tiles read between 1 and n. u_trace (arm C1d) gives
    the bin count for certain.

**How far a number can be trusted.**
- `mus` (in-pass µs per draw command, over the main passes) is exact on sysmem. I0 starts after the previous
  pass's BOTTOM Ow, and Iw waits for the work. On GMEM it is the last tile's time per draw. Read `mus` only
  together with `mode`.
- `muso` (the outer pair) is the pass's whole cost per draw in either mode. It includes the binning pass and
  loads/stores. On sysmem `muso - mus` is the pass's own begin/end overhead.
- **Segment times** are where the CP was, not where the shader cores were.
  - A TOP stamp records when the CP reaches it, and that runs ahead of the work by whatever is queued.
  - `drain` = Iw - Ie, in µs, is that lead at the pass end. Segments sum exactly to `in`, because the last one
    ends at Iw. One segment's split is smeared by up to `drain`.
  - When `drain` is small, the CP is not ahead: either it is the bottleneck, or each draw waits. The segment
    split is then the GPU's own.
  - When `drain` is large, run the WFI arm (I3) before reading `b=`/`sh=`.
- **The per-window fit** (gpubrk.h): least squares, with no intercept, of each main-pass segment's µs on what
  its commands carried. The features:
  - `cmd`: draw commands;
  - `pchg`: pipeline binds that changed the VkPipeline;
  - `fd`: the fragment shader writes gl_FragDepth;
  - `kill`: alpha test or alpha kill;
  - `blend`: blending on;
  - `zw`: depth test and depth write on;
  - `tex`: texture stages sampled;
  - `dtx`: texture descriptor binds;
  - `kvtx`: vertices or indices, in thousands;
  - `ukb`: uniform KiB uploaded.

  The fit is solved over the columns that moved, with a relative ridge of 1e-6 so that a collinear pair splits
  instead of failing. The line logs:
  - `b=`: µs per unit of each feature;
  - `sh=`: µs per draw command attributable to each feature;
  - `fx=`: each feature's mean per command;
  - `r2` (centred), `fn` (segment count), and `fit=ok|few|sing`.

  `sh` adds up to the fitted µs per command. It is attribution by correlation in one window: a feature that
  never varies apart from `cmd` lands in `cmd`. At K=16 a segment mixes ~16 draws, and `HAKUX_GPUBRK_K=1`
  (I4) gives per-draw rows.
- **Which passes count as main (M).** A pass is M when it has a depth attachment and its render area is at
  least 0.9 x the largest such area seen. The largest comes from this command buffer or the previous window.
  Everything else counts under `op/ocmd/oin/oout`. GTA III's main scene is many passes on one 640x480
  Z24S8 surface (row 60), so `mp` is passes per flip, not 1.

**Load/store ops are baked, and the line shows it.** `create_render_pass()` builds every pass with colour,
depth and stencil LOAD/STORE, whatever `begin_state` asked. `get_optimal_*_load_op` only reaches the
render-pass cache key. This change names those six constants (`RP_*`, draw.c:2093-2106, values unchanged)
so the line can print them: `ld=cL/zL/sL st=cS/zS/sS`. `mreqc=`/`mreqz=` count the M passes whose
`begin_state` asked for LOAD, which is how many could use DONT_CARE if the ops were honoured. On a GMEM main
pass, every tile loads and stores colour and depth/stencil, and `muso - mus` carries that cost. On sysmem the
ops cost nothing.

**Host-side counts per window.** These are plain counters in PGRAPHVkState, added in every build at the sites
listed in section 4:
- `pbind`: vkCmdBindPipeline calls;
- `pchg`: binds that changed the bound pipeline;
- `dub`: UBO descriptor-set binds;
- `dtx`: texture descriptor pushes or binds;
- `pushB`: push-constant bytes;
- `uboK`: UBO ring KiB;
- `nvK`: thousands of vertices or indices;
- `cmd`: draw commands.

All of these are per flip.

**System fields.**
- `mhz`: kgsl `gpuclk`.
- `busy`: `gpu_busy_percentage`.
- `drop`: passes not stamped (over the caps, or a result not read).
- `kg=`: `off`, `errN` (the ioctl's errno), or the deltas of the KGSL perfcounters this process could reserve,
  in thousands per flip. The counters are CP busy and WFI stall, PC busy and VFD stall, VFD, HLSQ, TP, SP busy,
  ALU and TP stall, RB busy and CCU stall, Z pass/fail, CCU GMEM read/write, and LRZ busy/visible (draw.c:4131).
  They are device-wide, they include the compositor, and an untrusted app may be refused.

**The line.** It is one `hakuX-gpubrk` INFO line per 60 flips, with fields in this order:
`fl s cb K wfi mp mcmd min mout mrep mrepmed mrepmax mode mus muso p50 p90 drain op ocmd oin oout fn r2 fit b sh fx
fmt wh ld st mreqc mreqz pbind pchg dub dtx pushB uboK nvK cmd mhz busy drop kg perfquery`.
- `min`/`mout`/`oin`/`oout` are ms per flip.
- `p50`/`p90` are µs per command over segments, weighted by commands.

It is on by default in the perflog build (`HAKUX_GPUBRK=0` turns it off) and behind `HAKUX_GPUBRK=1`
elsewhere. Its tag is in the dispatcher's LOGCAT_SPEC and the app's LOG_TAGS.

**Reading it.** Run `docs/testing/perf/gpubrk_sum.py --bands --min-cmd 800 A0=<logcat> SYS=<logcat> ...`.
- It prints one row per arm and per draw band, with the medians over windows of `fps`, `mus`, `muso`, `mrep`,
  the `mode` counts, `drain`, `r2`, the three largest shares, and more.
- It exits 2 when a window line lacks a field it reads, which means the format and the parser drifted, and
  1 when there is no window.
- Compare arms within a band, never by run median (drive1022/README.md).

## 2. Arms

The arms are run by lane.local on the Nova, perflog build of this branch, heavycap1022's heavy save state. Each
arm gets at least 3 minutes of gameplay, and every run shows `GPU: PurpleVK`.
- `TU_DEBUG` and `MESA_*` go in through the env_vars pref, one `TU_DEBUG` value per arm.

**Reference figures:**
- Control R/draw: 26.0 µs (drive1022, pid21946).
- Control, 1000-1200-draw band: 18.6 fps, which is 53.8 ms/flip, with a fence wait of 14.2 ms/flip.

**fps model.**
- A GPU saving of Δ µs per draw at ~1100 draws is 1.1Δ ms/flip. While the fence wait lasts, the frame
  shortens by that much, so fps ≈ 1000 / (53.8 - 1.1Δ).
- That gives +0.4 fps per µs/draw: Δ 4 → 20.3, Δ 8 → 22.0.
- The cap is about 25 fps at Δ 13, where the fence wait runs out. A GPU-only fix cannot reach the owner's bar
  in this band. The rest is heavycap1022's CPU side.

**Reading the cells.**
- The "if it dominates" column is the change in that arm against A0 when that candidate is most of the ~26 µs.
- The "expected" column is what the Step 0 rows predict.

| # | arm (env) | isolates | if it dominates | expected (from Step 0) |
|---|---|---|---|---|
| A0 | none (line on, K=16, TOP) | the baseline every arm is read against | - | `mrep` < 1.3, `mode` s; `mus` 26-31; R/draw 26.0 ±3%; 18.6 ±1 fps (1000-1200) |
| I1 | `HAKUX_GPUBRK=0` | the line's own cost: 2 WFIs + 3 TOP stamps a pass, 1 TOP stamp per 16 draws | - | R/draw and fps within 3% / 0.5 fps of A0. If A0 is slower by more, re-run A0 at `HAKUX_GPUBRK_K=64` and read `mus` from that |
| I2 | `HAKUX_GPUBRK_K=0` | the K stamps alone (pass stamps kept) | - | `mus`/`muso` within 3% of A0 |
| I3 | `HAKUX_GPUBRK_WFI=1` | the TOP lead in segment times | - | `drain` < 2 µs; `mus` up by at most 10% (a WFI per 16 draws; BF2's per-draw syncdraw cost was +3.8 µs, so ~+0.25 µs); `p50`/`p90` and `b=` become the GPU's own; fps −0.5 at most |
| I4 | `HAKUX_GPUBRK_K=1` | per-draw segments for the fit | - | `fn` x16, `r2` up; R/draw +5% at most, fps −1 at most; `drop` stays 0 (~1100 + 5 x 130 stamps per flip fits 2048 only if a command buffer holds about one flip) |
| I5 | `HAKUX_GPUBRK_KGSL=1` | hardware split, device-wide | CP busy ≈ pass time and SP/TP/RB low: CP or state bound (C2). SP/TP high: shading (C3). VFD/PC-VFD high: fetch (C4). GMEM r/w high: C1 | `kg=err1` or `err13` (the sandbox refuses the perfcounter ioctl) is the likely reading; timing ±1% |
| I6 | performance mode 2 (**instrument only, never a fix or recommendation**) | how much of the per-draw cost scales with GPU clock | - | `mhz` above 401; `mus` scales as (401/mhz)^e, e 0.6-0.98 (row 61). Near 1 means clocked work (CP, ALU); near 0 means memory |
| C1a | `TU_DEBUG=sysmem` | GMEM replay plus per-tile LOAD/STORE of the main pass | `mode` t→s; `muso` falls to ~`mus` (≥ 8 µs/draw); fps ≥ 22 | `mode` already s: `muso` ±5%, `mus` ±5%. Any fps change shows in `oin`/`oout` (other passes), as in fpsnext1019's +3 fps with rp 130→70 |
| C1b | `TU_DEBUG=gmem` | positive control: does `mrep` see a replay? | (A0 already t: no change) | `mrep` ≥ the u_trace bin count. With 2+ bins, `muso` +30-75% (row 32's x0.57-0.64 inverted), fps −2 to −5. With 1 bin, `mrep` 1.05-1.3 (loads, stores, binning) |
| C1c | `TU_DEBUG=nobin` / `forcebin` | the binning pass (only if A0 reads t) | `muso` falls (nobin) or rises (forcebin) by the binning time | not run if A0 reads s; row 35: forcebin never won on the Nova |
| C1d | `MESA_GPU_TRACES=print` `MESA_GPU_TRACEFILE=<app files dir>/utrace.txt` | ground truth per pass: `tiledRender`, `numberOfBins`, `binWidth/Height`, `drawCount`, `lrz`, `lrzDisableReason` (tu_tracepoints.py:128-154) | - | main pass `tiledRender`=0 or 1 bin; `lrzDisableReason` names the fragment shader. Not timed. Void if the shipped driver has no u_trace (no file). The file is flushed at exit, so stop the app, do not kill it |
| C1e | `TU_DEBUG=perf`, with `TU:W` in `LOGCAT_SPEC_OVERRIDE` | Turnip's own reasons (sysmem choice, "Disabling LRZ because…", "Skipping LRZ due to FS") | - | the LRZ-off reason on the main-pass pipelines. Logs per draw, so not timed |
| C2a | A0's fit | per-draw state: CP emission and WFI on state changes | `sh` pchg+dtx+ukb ≥ 40% of `mus` (≥ 10 µs); `drain` < 5 µs (CP not ahead); I5 CP busy ≈ pass time | < 15% of `mus`. Row 43 bounds a UBO bind at ≤ 1 µs, `pchg` is ~0.4 a draw (row 47) |
| C2b | `TU_DEBUG=syncdraw` | how much draws overlap today | draws already serial: `mus` +<1 µs, fps −0.4 at most | BF2: +3.8 µs/draw (+15%), fps −1.4 |
| C2c | `TU_DEBUG=flushall` | dependence on warm caches between draws (diagnostic) | flush cost only: `mus` +1-2 µs | `mus` +20-60%. A rise ≥ 10 µs points at fetch or texture (C4/C3), not state |
| C3a | A0's fit | late-Z from gl_FragDepth | `sh` fd ≥ 4 µs; I5 Z-pass ≫ visible pixels | `fx` fd ≈ 1 (every depth-tested shader writes it) leaves fd collinear with zw/cmd. Then C3c decides |
| C3b | `TU_DEBUG=nolrz` | is LRZ doing anything today? | LRZ already off (FS writes depth): R/draw ±3%, fps ±0.5 | same: no change |
| C3c | `HAKUX_FRAGDEPTH=off` (needs this branch merged with lane/p10fragdepth1022 31770d97e5; not on this base) | the gl_FragDepth write | `mus` −4 to −6 µs (PLAN 1.1: 5-7 ms/flip at ~1100 draws); R/draw ~20-22; fps +1.6 to +2.4 (~20.5) | open: the one candidate Step 0 leaves standing |
| C4a | A0's fit, I5 | vertex fetch from host-visible staging | `sh` kvtx ≥ 30% of `mus`; I5 VFD/PC-VFD stall high | small. Row 57 refuted host-visible fetch on BF2. No run-time switch on this base moves the fetch source (`HAKUX_VTX_MIRROR`, 57fe561924, is no longer in vk/*.c) |
| C4b | `HAKUX_VTXHZ_BUMP=1` | known-effect arm: what the line reads for a change with a measured result | - | measured: R/draw 21.9 vs 26.0, 22.4 vs 18.6 fps (1000-1200). The line: `mus` −10 to −16% (GPU/full 26.7 vs 31.8), `sh` kvtx unchanged. If `mus` does not fall, the R/draw drop was the 48-pass truncation |

**Not re-run.**
- `HAKUX_ZETA_D24=1`: refuted (row 34). Re-run only if A0 reads `mode` t.
- `HAKUX_GPUTS_INRP=0`: changes hakuX-phase's stamps only; the line has its own pool.
- `HAKUX_GPUXFR=1`: hakuX-phase's outer/inner pair over its first 48 passes. Use it to cross-check `muso`/`mus`
  on those passes, not as an arm.

**Order.**
1. A0 and I1 first: the instrument must not move the thing it measures.
2. Then C1a, C1b, C3b, C2b, C4b, I3.
3. Then C1d, C1e, I5, I4, C2c.
4. I6 last.
5. C3c needs the merged build.

**What each outcome points to.** No fix is built until one of these shows.
- `mode` t with C1a saving ≥ 8 µs points to the render mode: a per-title `TU_DEBUG=sysmem` (kTitleRenderModes,
  row 35), or honouring `begin_state`'s load ops on GMEM.
- An fd share ≥ 4 µs confirmed by C3c points to P10.
- C2a's signature with C2b +<1 µs points to fewer real pipeline changes per pass. Row 47 says ~40% of draws
  change pipeline, so that would mean ordering draws by pipeline (the reorder window, default off), not skipping
  re-binds.
- A kvtx share ≥ 30% would need written evidence of what differs from row 57 before a device-local copy is
  rebuilt.

## 3. The fix

None is built. The brief allows a fix only where code reading plus the numbers decide a candidate. They do
not.
- The example the brief gives, the same pipeline re-bound every draw, is refuted by code reading (row 47).
- Descriptor rebinding is bounded at ≤ 1 µs a draw (row 43).
- Tiling is ruled out as an even two-tile replay (row 34), but not as uneven tiles or per-pass load/store.
- Late-Z (P10) is already built on its own lane and waits for its A/B (C3c).

## 4. The change

**draw.c**
- :2093-2106: `RP_COLOR/ZETA/STENCIL_LOAD/STORE_OP`. `create_render_pass()` at :2124-2125 and :2142-2145 uses
  them, with the same values.
- :4045-4745: the gpubrk block.
  - `gb_on()` reads the env once, probes perfquery, and logs the `on` / `off:` line.
  - Stamping: `gb_stamp()`, `gb_pass_begin()` (O0), `gb_pass_begun()` (I0), `gb_batch_open()` (a batch's
    features, from the bound pipeline's key and the draw's blend and control_0), `gb_batch_fold()` (adds the
    batch to the segment, and stamps at K), `gb_pass_ending()` (Ie), `gb_pass_end_in()` (Iw),
    `gb_pass_end_out()` (Ow).
  - Readout and teardown: the KGSL sampler, `gb_win_check()` (the 60-flip window and the line),
    `gb_readback()` (stamps into M/O sums, ratios, the fit and the histogram), and
    `pgraph_vk_gpubrk_finalize()`.
- Hooks:
  - `begin_render_pass` :5238, :5254;
  - `end_render_pass` :5277-5278, :5292;
  - `gpu_ts_readback` :6161;
  - `pgraph_vk_begin_command_buffer` :7136 (it resets only the slot's used stamps);
  - `begin_draw` :8507 (bind), :8766 (batch);
  - `end_draw` :8781;
  - `emit_reorder_entry` :10357, :10372, :10640.
- Host counts:
  - push constants :4769, :4885, :10400, :10605;
  - texture descriptors :4916, :4967, :10581, :10590;
  - UBO binds :4937, :9239, :10566;
  - UBO bytes :8969;
  - draw commands and vertices, `gb_draw()` at every vkCmdDraw* site: :9432-9589, :10626-10637, :11749,
    :12232-12264, :12355, :12438-12441, :12535-12538.

**Other files**
- gpubrk.h (new): the features, the fit (pivoted Gaussian elimination over the columns that moved, with a
  relative ridge), centred R², shares, the 0.5 µs histogram and its percentiles, the render-mode reading, and
  the line's formatter. It is standalone C, so the selftest builds it.
- renderer.h:1691-1702: the eight `gb_*` counters. :2159-2160: the finalize prototype.
- renderer.c:538: finalize before the device goes.
- shaders.c:929: UBO bytes from `pgraph_vk_update_descriptor_sets()`.
- dispatcher.sh:3185-3190: `hakuX-gpubrk:I` in LOGCAT_SPEC.
- HakuXApplication.kt:18: `hakuX-gpubrk:V`.
- docs/testing/perf/gpubrk_sum.py: the reader.
- 99-gpubrk-fit.sh: the falsifier.

**Cost in builds where the line is off:** one add per counter site, plus a pipeline-handle compare per bind.
Every stamp and record sits behind `gb_on()` / `gb.cur`.

## 5. Checks

**Desktop.** cc_wt.py (p11vtxbump1022 §6: desktop flags, worktree headers), each touched C file with
`-DNV2A_PERF_LOG=1` and `=0`, against the base 03e01c3aad:

```
draw.c     perflog=1 EXIT=0  perflog=0 EXIT=0   15 warnings each; base 15, the same set: missing prototypes
                                                  :1455-1549, -Wshadow=local :6750 (base :6023), unused `r`
                                                  :8845 (base :8110)
renderer.c perflog=1 EXIT=0  perflog=0 EXIT=0   7 warnings each; base 7, the same set, shifted one line
shaders.c  perflog=1 EXIT=0  perflog=0 EXIT=0   2 warnings each; base 2, the same set, shifted one line
```

renderer.h is compiled by all three. gpubrk.h is compiled by draw.c and, on its own with `-Wall -Wextra
-Werror`-clean output, by the selftest.

**Android stub.** The log calls are Android-only, so draw.c was also compiled with `-D__ANDROID__ -Wformat=2`
and a stub `android/log.h` declaring `__android_log_print` with `format(printf, 3, 4)`.
- A `#warning` in the stub fires, which proves the stub was the header included.
- perflog=1 and =0 both gave EXIT=0, with 18 and 16 warnings. That is the stub's `#warning`, the 15 above, and
  at =1 the two nested externs at :1168-1169 (base code, under NV2A_PERF_LOG).
- There are no new warnings, so `gb_log`'s and the line's format strings match their arguments.

**Selftest.** `SELFTEST_ONLY=99-gpubrk-fit`:

```
  ok   gpubrk_test builds against vk/gpubrk.h with no warning
  ok   T1-T5: betas, zero columns, a collinear pair, an unexplained window, percentiles
       t1 beta cmd=12.000 fd=6.000 kvtx=9.000 shares=24.941/24.941 r2=1.00000
       t2 solved=7 beta cmd=12.000 fd=0.000
       t3 fd=5.000 zw=5.000 sum=10.000
       t4 r2=-2548.565
       t5 p50=2.25 p90=10.25
  ok   T6: gb_win_format writes a line
  ok   T6: gpubrk_sum.py reads the line (exit 0)
       arm=arm n=1 fps=30.0 cmd=1100 mcmd=1000 mp=1.00 min=26.00 mout=27.30 mrep=1.05 mode=s1 mus=26.00 muso=27.30 ...
  ok   T6: the summary carries the values the window was given
  ok   gpubrk_sum.py exits 1 on a capture with no window line
  ok   FALSIFIED: a fit that keeps never-moving columns fails (T2)
  ok   FALSIFIED: a fit with no ridge fails on a collinear pair (T3)
  ok   FALSIFIED: an uncentred R^2 passes an unexplained window and fails (T4)
  ok   FALSIFIED: a percentile that needs more than p of the weight fails (T5)
  ok   FALSIFIED: a line with a field renamed fails gpubrk_sum.py (exit 2)
selftest: 17 passed, 0 failed, PARTIAL: 1 of 161 fragments
```

(The five "falsification ran: the X mutant differs" lines are omitted above.)

**The fit test's ground truth.**
- True betas: {cmd 12, pchg 3, fd 6, kill 2, blend 1.5, zw 4, tex 2.5, dtx 0.8, kvtx 9, ukb 1.2} µs.
- 400 segments of LCG features, noise-free, so T1 holds every beta within 2% and every share within 1%.
- At the earlier ridge, 1e-4, ukb came back 1.2345, a 3% error. Every feature scales with `cmd`, which magnifies
  the ridge's bias on the small columns. At 1e-6 every beta is exact to three decimals, and T3's collinear pair
  still splits 5.000 / 5.000.

**Each mutant, run by hand, fails only its own test:**
- zeroskip fails T2 (solved −1);
- ridge fails T3 (singular);
- center fails T4 (R² 0.915 on a window the features do not explain);
- pct fails T5 (p50 10.25).

**Tag regex.** gpubrk_sum.py's tag regex was checked on threadtime, `-v time`, desktop stderr, and the `on` /
`off:` info lines.

**The fragments that read the tag list.** LOGCAT_SPEC gained `hakuX-gpubrk:I`, and 51-dispatch-hardening (I)
and 99-ownerplay-capture (a) source it.
- `SELFTEST_ONLY="50-arms-requeue 51-dispatch-hardening"` gave `selftest: 77 passed, 0 failed, PARTIAL: 2 of
  161 fragments`, with every `I: the dispatcher's LOGCAT_SPEC keeps ...` ok.
- 99-ownerplay-capture passed every check, including "(a) the capture used the dispatcher's own LOGCAT_SPEC".
  That was in a three-fragment run with 99-gpubrk-fit and 51 without 50.
- That run's 7 failures were all 51's E/E2. Those sections need 50's fixture ("fixture not as 50 leaves it";
  `clear_markers`/`finish_queue: command not found`), and they pass with 50 in the run above.

**Not run:** the full selftest, an NDK build, a desktop link, any device.

## 6. Risks

**Not run yet.**
- Not built with the NDK, and not run anywhere. A0 is the first execution.
- I1 is what shows whether the line's cost moves R. The two WFIs it adds per pass serialise pass ends. Iw sits
  next to hakuX-phase's own in-pass BOTTOM stamp on the first 48 passes; Ow is new.

**Gaps in what the line sees.**
- `pchg` sees binds in draw.c only. Pipelines bound in surface.c and display.c (blits, the display pass) are
  not counted, so the cached last pipeline can be stale after one, and a re-bind can read as a change.
- With the reorder window on (default off), a `begin_draw` batch can be open while an entry is emitted, and the
  two batches' features can mix in one segment.
- The vertex count of the reorder path's indirect draws is GPU-side, so it is logged as 0. `kvtx` under-reads
  there.

**How segments are cut.**
- UBO bytes uploaded before a pass's first draw count in its first segment.
- The last segment of a pass ends at Iw (BOTTOM), so it includes the drain. TOP segments measure CP progress
  (section 1).

**Caps and precision.**
- A command buffer with more than 256 passes or 2048 stamps stops stamping. Those passes show in `drop`, not
  in the sums. At K=1 a heavy flip comes close to the stamp cap.
- Features are stored as float. Exact for counts below 2^24.

**Classification.**
- The M rule (has depth, area ≥ 0.9 x the largest) can admit a full-size shadow or reflection pass with its
  own depth. Both `mp` and `fmt`/`wh` are logged so that shows.
- A window that starts in a menu holds `area_ref` from the previous window.

**Device-specific.**
- `kg=` counters are device-wide, and reserving them can fail in an app sandbox (`errN`). They are never a
  timing arm.
- u_trace (C1d) depends on the shipped driver being built with it. Unknown.

**Comparing with the control.** The drive1022 figures were taken without the line. The line changes R by
whatever I1 shows, so compare arms against this branch's own A0, not against drive1022's control.
