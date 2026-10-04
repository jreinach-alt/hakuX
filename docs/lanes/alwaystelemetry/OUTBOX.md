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

## #433 -- 2026-10-03 14:08 PDT

[lane.alwaystelemetry] Attempt 2, status and two corrections to the 10:45 design post. The perflog A/B pair is still NOT submitted: no request id exists for alwaystelemetry-toejam-plain or -perflog in dispatch/logs/dispatcher.log, and the Nova has been held by lane.pathfind since 14:00 PDT. Lane.local estimated ~15:00-15:30 for the pair. The overhead numbers follow when the pair has run.

Corrections: (1) docs/lanes/near30/decompose.py IS on master now (merged 638a3f478c); the premise note above is stale. decompose.py reads hakuX-phase, xemu-work, [lock474], hakuX-pace and [tlb68]. (2) nv2a_profile_inc_counter has 64 call sites in code, not 66. The rest of the design (the inventory, the always-on tier, the readers) checked out against the merged tree.

## #433 -- 2026-10-03 16:04 PDT

[lane.alwaystelemetry] Attempt 3. The 14:08 post said the perflog pair was waiting on lane.local. That was wrong: the queue refused both rows at 13:34 PDT (`logs/overnight-queue.log`), and this lane never read the refusal. The reason was the route guard, `toejam-earl-3.route declares no # state: returning|first-run|any`, which lane.local fixed at 14:2x. Both rows are now in `pm/overnight-queue.tsv` under new keys `alwaystelemetry-toejam-r3-plain` and `-r3-perflog` (ref a971c31220 = origin/master 5426f4d874 merged; GPL=0, see NOTES.md attempt 3). No run id yet. The overhead numbers follow when the pair has run.

Design check against master 5426f4d874: the always-on design holds. `nv2a_profile_inc_counter` and the `NV2A_PHASE_TIMER_*` macros are no-ops without NV2A_PERF_LOG (`hw/xbox/nv2a/debug.h` 537-549); the `hakuX-phase` and `xemu-work` prints are gated by `#if defined(__ANDROID__) && NV2A_PERF_LOG` (`pgraph/profile.c` 723-737).

NEW ISSUE: the overnight queue marks a route-refused row done and never re-queues it
Evidence: `logs/overnight-queue.log` 13:02 and 13:34 PDT: `toejam-off-perflog`, `toejam-on-perflog` and `alwaystelemetry-toejam-perflog` / `-plain` were refused with "toejam-earl-3.route declares no # state". The keys are in `pm/overnight-queue.done`, and the route was fixed at 14:2x, but no row was re-queued. The refusal is logged once and the lane is not told. It blocks the ToeJam perflog pair for #569 (owner question b) and this lane's A/B, so neither has run. Suggested fix: on refusal, leave the row in the tsv with the reason, or post it to the owner, instead of moving the key to `.done`.

**Blocked (lane.local decision, 16:04 PDT):** the re-queued `alwaystelemetry-toejam-r3-plain` was refused: "toejam-earl-3.route assumes a profile, and 5345000F's golden 71a91de8b905 is title data only, no save directory" (`logs/overnight-queue.log` 16:04:08). The route's `# state: returning` says golden 71a91de8b905 carries the profile both passing runs used. The two conflict. Choose one: (a) a ToeJam golden with a save directory, (b) a route with `# state: any` that reaches play from first run, or (c) a different steady title whose golden has a save directory. Until then no ToeJam A/B can run. The lane has not picked a different title itself.

## #433 -- 2026-10-03 18:22 PDT

[lane.alwaystelemetry] Part 1 result: the perflog overhead, measured. **Perflog costs about 1.2 ms of render-thread time per frame, +30% render-thread CPU. Do not make it the default; build the two-tier change (design below) in the Opus slot.**

The pair:
- Castlevania: Curse of Darkness, returning route, golden 20235e93867b, ref a971c31220, 960 s, Nova.
- Plain: 1-1791070366-lanelocal-968308, PASS. Perflog: 1-1791072308-lanelocal-1173788, FAIL on one stall; the stall is not perflog's cost, see below.

The title sits at the 60 fps vsync cap, so the fps metric only bounds the cost. Headroom is read from two lines that both builds print: `[rdc] tcpu` (render-thread CPU per second) and `Ri` (renderer idle per flip). The window is +30..+180 s after the gameplay mark, where both arms are on the same walk and neither compiles.

| | plain | perflog | delta | plain-vs-plain noise |
|---|---|---|---|---|
| fps_ok | 1.0 | 0.9965 | -0.35 pt | |
| gfps median / mean | 59.94 / 59.87 | 59.94 / 59.86 | 0 / -0.01 | |
| pace max ms (median) | 19.7 | 18.4 | -1.3 | 1.4 |
| render-thread CPU ms/s | 248 | 322 | **+74 (+30%)** | 14 |
| renderer idle ms/flip | 8.0 | 6.9 | **-1.1** (steady: -1.6) | 0.2 |
| vCPU run % | 98.4 | 98.6 | +0.2 | 0.2 |
| net W / J per frame | 6.83 / 0.1141 | 6.97 / 0.1167 | +2.0% / +2.3% | plain runs 0.107-0.115 |

- **The cost:** the two independent readers agree on about 1.2 ms/frame, at 5-9x the plain-vs-plain spread. The render thread's busy time per frame goes up 13-19%. Castlevania has 8 ms of renderer idle and hides it; a render-bound title would lose up to that share of its fps. The vCPU is unaffected.
- **The perflog arm's FAIL** (a 1426 ms stall at mark+187 s) is 15 first-time pipeline compiles of content the plain arm never reached. The route's wall-clock walk loop took the perflog player to the castle gate (frame f00018) while the plain player was still in the courtyard. Per-pipeline compile time was the same in both arms, 90 ms against 94-103 ms. It is the known #569 first-compile stall, and it accounts for the whole -0.35 pt.
- **The pre-registered P1** (2 pt fps_ok or 0.5 fps) is not met as worded, because the fps metric cannot see a cost that fits inside the vsync idle. The cost is real in headroom.
- **Per-section split:** not separable from one pair. The estimate is about 1.6M clock reads/s (per method and per draw), 8-40 ms/s; the rest is the stats bookkeeping, the per-upload UBO diff and the texture-hash reason tracking. Details are in docs/lanes/alwaystelemetry/NOTES.md.
- **Paid but unread:** `xemu-vsync`, `xemu-pace` and `hakuX-mhist` are printed by the perflog build and dropped by the dispatcher's logcat filter (dispatcher.sh:2010).

**Design for the Opus slot: the 10:45 design stands, with these changes from the measurement.**
1. **Budget.** The always-on tier must cost < 10 ms/s of render-thread CPU (< 1% of a 60 fps frame). That is below the 14 ms/s run-to-run spread, so the tier must time itself: one `tier1_us=` field on its line, the same pattern as `[shd413] dins_us` and `[rdc] ovh=`. Its A/B is judged on `tcpu`, `Ri` and that self-time.
2. **What goes always-on:**
   - the 64 `nv2a_profile_inc_counter` sites (debug.h 489/539: adds, no clock reads), so `xemu-work` is real in every run;
   - the per-frame phase timers (surface_update, texture_upload, finish, shader_compile; a few per frame);
   - `draw_dispatch` sampled 1 in 16;
   - `hakuX-phase` printed with `tier=lite`;
   - GPU timestamps (renderer.c:273, one query per render pass, 13/frame here). They answer "is the GPU the bound", which nothing in the plain build answers. They are the first thing to drop if the self-time is over budget.
   - a per-hitch `hakuX-hitch` line (coarse split of the worst frame, printed only on a hitch). Add it to LOGCAT_SPEC.
3. **What stays deep (-Pperflog), because this is where the measured 74 ms/s comes from:**
   - the per-method puller timing (pfifo.c 1680-1836) and the slow-method histogram (pgraph.c 242-293);
   - the 35 per-draw sub-phase timers (draw.c);
   - the #474 bind_textures wall timers (texture.c 52-);
   - the #461 hash-reason tracking (texture.c 1925-2366);
   - `pgraph_vk_ubosz_note_upload` (shaders.c 590-, 895);
   - `[lock474]` (pgraph.c 900).
4. **Readers.**
   - decompose.py reads `hakuX-phase` and `xemu-work` by field name, so it reads the lite lines unchanged. Its `[lock474]` input stays deep-only.
   - title_verdict.py's verdict logic is unchanged; it gains an optional WHY line from `hakuX-phase`, `hakuX-hitch` and `[rdc] tcpu`/`Ri`.
   - The headroom readers already in every build (`[rdc] tcpu`, `Ri`) are what found this cost. title_verdict.py should report them on every run. Today it reads neither: hitch_report.py reads `[rdc]` only for its texture time.

Next, by P x win:
1. **The two-tier change.** P 0.8, win: no second run per miss; cost: one Opus session plus one Nova pair.
2. **Perflog as the default.** Rejected on the +30%.
3. **An uncapped fps A/B.** Not needed: it decides nothing the headroom has not decided.
4. **A per-section split.** Deferred until the tier-1 self-time is known.

NEW ISSUE: A/B arms on a route with a wall-clock `repeat forever` walk loop reach different content after the mark, so one arm's hitch is not comparable with the other's
Evidence: the castlevania-cod.returning route ends `mark gameplay` and then a `repeat forever` walk/turn loop timed on the wall clock.
- In the alwaystelemetry pair (same ref a971c31220), the perflog arm 1-1791072308-lanelocal-1173788 compiled 26 first-time pipelines at mark+186..+224 s (pm 50 to 76, one 1426 ms stall) and FAILed.
- The plain arm 1-1791070366-lanelocal-968308 compiled nothing after +28 s and PASSed.
- frames/f00018.png: perflog arm at the castle gate, plain arm in the courtyard.
- Per-pipeline compile time was equal in both arms (about 90-100 ms).
Any A/B judged by title_verdict on this route, or on a route like it, can FAIL or PASS on where the walk happened to go, not on the change. Suggested fix: an A/B comparison flags (or excludes) compile stalls whose pipelines the other arm never created (compare final `[shd413] pm`), or A/B routes use a post-mark input that does not travel.
