## #433 -- 2026-10-03 10:45 PDT

[lane.alwaystelemetry] Part 1, design and inventory. The perflog A/B pair is queued (rows in pm/overnight-queue.tsv, keys alwaystelemetry-toejam-plain and alwaystelemetry-toejam-perflog, ref 6c828f9860, 600 s each). Its result is pending; the overhead numbers follow in a second post.

**What the plain build already carries (no perflog needed):** the pace line (hakuX-perf gfps=, hakuX-pace f= v0..v4 vb max ms), the shader-cache line [shd413], [tlb68], [rdc], [idlehalt], [rr425w], [mf0], [rwait526] (hakuX-lane). near30's decompose.py reads all of these except [lock474], hakuX-phase and xemu-work, so its vCPU and idle half already runs on a plain log.

**What only the perflog build carries** (`-DHAKUX_PERF_LOG=ON` sets NV2A_PERF_LOG=1, android/app/src/main/cpp/CMakeLists.txt:947, 1067):

| Tag | Question it answers | Cost source | decompose.py / title_verdict.py |
|---|---|---|---|
| hakuX-phase | GPU-side phase split per frame: Surf, Tex, Shd, Draw parts, Fin, idle | per-draw timers (draw.c), per-60-frame print | decompose reads it; phase_read_split reads it |
| xemu-work | workload counters (draws, uploads, finishes, surface events): the instrumentation-independent control | counters no-op when plain (`nv2a_profile_inc_counter`, debug.h ~487-551), so plain reads 0 | decompose reads it |
| hakuX-cpu | vCPU-thread lock wait and puller time per method | per-method clock reads in the puller (profile.c, pgraph.c) | neither |
| xemu-vsync | vsync delivery | per-frame counters | neither |
| xemu-surf | Surf sub-split (#413): populate, lookup, create, upload, download | per-surface-event timers | neither |
| xemu-gpu | GPU ms/frame from timestamps | vkCmdWriteTimestamp per render pass, readback | neither |
| xemu-sfp | sfp/mfp draw path split | per-draw timers | neither |
| hakuX-stall | surface download sites (#372) | per-event counters | neither |
| hakuX-rpbrk | render-pass break reasons | per-break counters | neither |
| [lock474] | what the vCPU's PGRAPH MMIO waits for (lane.slowdown462) | wait timers, Android perflog only (pgraph.c:900) | decompose reads it |
| pgraph method histogram | slow-path method frequency | per-method increment | neither |

**Always on, both builds:** hakuX-perf gfps line (game frame EMA, display frame, swap, Ri), hakuX-pace, [shd413] (cache hit/miss/compile deltas), the vCPU lines and [rwait526] (render-wait site split, clock read only at waits). title_verdict.py reads hakuX-perf and hakuX-pace (FRAME RATE, HANG, AUDIO sections) and hakuX-route, hakuX-crash. It reads none of the perflog tags, so the always-on tier needs no change there.

**Design: always-on tier (plain build, target < 1% of a frame; cost estimates are from the code, not measured):**

1. **Counters always on.** Change `nv2a_profile_inc_counter` (`hw/xbox/nv2a/debug.h`, the `#else` branch ~537-551) to a real increment in every build. 66 call sites, each a single add to `g_nv2a_stats.frame_working.counters`. Expected cost: under 0.1%. The two counters incremented directly inside `#if NV2A_PERF_LOG` blocks (`texture.c`, `surface.c`) move out of the gate too. Also: `xemu-work` prints every counter the plain build now zeroes, which is what the plain run needs to say what the workload was.
2. **Coarse phase timers always on, the per-draw one sampled.** `NV2A_PHASE_TIMER_*` in `debug.h` (~462-550) become live in every build. The top-level phases (surface_update, texture_upload, finish, shader_compile) fire a few times a frame, so their cost is trivial. `draw_dispatch` fires per draw: time 1 draw in 16 (a counter modulo, the same gate tlb68 uses at 1 in 1024) and scale. Expected cost of the sampled timer: a few ns per sampled draw, under 0.05% of a frame at 3000 draws. The per-draw children (draw_vtx_attr, draw_setup, ...) stay deep.
3. **Emit hakuX-phase always on, same field names.** The print in `hw/xbox/nv2a/pgraph/profile.c` (`#if defined(__ANDROID__) && NV2A_PERF_LOG`, ~723-790) moves out of the gate for the always-on fields only. phase_read_split.py matches fields by name (`(?<![A-Za-z])Name:(-?[\d.]+)`), so the existing readers take the new lines unchanged. Add `tier=lite` or `tier=full` to the line so a reader can tell a sampled phase from a full one. Cost: one snprintf per 60 frames, which the pacing line already pays.
4. **Per-hitch worst-frame breakdown (new tag hakuX-hitch).** At the frame boundary in `profile.c` (where `frame_ms` is computed, ~600-620), keep a copy of the last frame's coarse per-frame totals (about 10 floats, memcpy per frame, negligible). When that frame's game time exceeds 1.5 times the gfps EMA, or 33 ms, print one `hakuX-hitch` line with the frame number, its game ms, and the coarse split (Surf, Tex, Shd, Draw, Fin, idle). Cost: zero off hitch frames. Needs the tag added to the LOGCAT_SPEC allow-list in `docs/testing/dispatcher.sh` (~2011), or the line is silenced; that is the lesson recorded there for hakuX-phase and xemu-work.
5. **Deep tier stays behind -Pperflog:** per-method puller histogram and timers (profile.c ~615, pgraph.c 242-293, 2406), `[lock474]` (pgraph.c 900), the draw sub-phases (draw.c 4578-4842 sfp/mfp/ftx, 8467-8689 vtx/setup/cmd), GPU timestamps (renderer.c:273, draw.c 3659-4512), `pgraph_vk_ubosz_*`. The GPU timestamps are the first candidate to promote, because they are one query per render pass and their cost is unmeasured. Promote only after the A/B says the deep tier costs something and the next run shows which part.

**Readers after the change:** decompose.py keeps reading hakuX-phase and xemu-work, now present in every run; `[lock474]` stays deep. title_verdict.py gains an optional WHY line that reads hakuX-phase and hakuX-hitch when present; the verdict logic is unchanged.

**Premise corrections:** the brief names docs/lanes/near30/decompose.py, which is not on master; it is on origin/lane/near30. The brief also says the perflog build is keyed as a separate binary by `build_ref` (dispatcher.sh ~883), which is correct.

**Recommendation pending the A/B:** if the perflog arm is within noise (under 2% fps_ok and under 0.5 fps median), make perflog the default for every run (one flag flip, and the deep tier reads for free). If not, the two-tier change above for the Opus slot.
