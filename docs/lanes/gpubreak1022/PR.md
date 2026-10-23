# gpubreak1022: where GTA III's GPU time per draw goes in the main pass -- a `hakuX-gpubrk` breakdown line and the arms that separate the candidates (#433)

State: draft

Lane: gpubreak1022            Issue: #433 (0.5)
Base: lane/drive1022 @ 03e01c3aad
Files: docs/lanes/gpubreak1022/PR.md (Step 0); the build commit lists the rest
Prediction: (filled at the build commit)
Needs device: yes (filled at the build commit)
Needs NDK: yes
Selftest: (filled at the build commit)

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
