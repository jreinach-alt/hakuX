# lane.shaderfb569 -- #569 P1: measure the pipeline create call, per stage

Base master 01e62d8d1c. Plan: `docs/lanes/shaderplan569/NOTES.md` §7 P1 (PR #570). PR #574.

## 1. The instrument (a073e39676, 84c865c37d)

Every graphics pipeline create now goes through `pgraph_vk_create_graphics_pipeline_fb()`
(`vk/compile_worker.c`, outside the `OPT_ASYNC_COMPILE` block). That covers the sync draw path
(`vk/draw.c`, `create_pipeline`), the clear path (`create_clear_pipeline`) and the async worker
(`process_pipeline_job`). The wrapper:

- times the call with `nv2a_clock_ns()`, giving `pipeline_create_us`, pipeline413 §9's
  accumulator;
- on a device reporting Vulkan >= 1.3, chains `VkPipelineCreationFeedbackCreateInfo` (core
  1.3, no feature bit) in front of the caller's `pNext`, and accumulates the whole-pipeline
  duration, the whole-pipeline cache hit, and the duration of each stage (vs/gs/fs);
- for draw pipelines (not clears, whose built-in modules are always "reused"), splits the
  stages by whether an earlier pipeline had already used the stage's `VkShaderModule`. For each
  side it counts the stages, the stages without `APPLICATION_PIPELINE_CACHE_HIT`, and their
  duration. That is C3, with a duration cross-check: a reported miss that costs ~0 ms is not a
  real recompile.

Module handles are remembered by value in a hash set and never forgotten. A module freed and
replaced by a new one with the same handle therefore reads as reused. Shader-module eviction is
rare enough that this is noise.

Also:
- `vk/glsl.c`: `glslang_us` around both `pgraph_vk_compile_glsl_to_spv` calls, and
  `shader_module_us` around the whole GLSL -> `VkShaderModule` (SPIR-V cache load and store,
  module creation, reflection). Both run on a module miss only.
- `vk/draw.c`: `plc_save_us` around `save_pipeline_cache_to_disk`.
- **Key-diff classes** (`nv2a_profile_shader_keydiff`, `pgraph/profile.c`). On a sync draw miss,
  just before the create, the new key's `ShaderState` is compared with the `ShaderState` of the
  pipeline bound before, as a class bitmask:
  - VP: vertex program words, or programmable <-> ff;
  - FF: fixed-function vsh, plus the vsh fields both paths share (lighting, material sources,
    fog, attrs);
  - CB: combiner stages and the final combiner;
  - TX: psh texture fields, the stage program included;
  - FL: floats (point size and params, aa offset, border sizes);
  - PO: the rest of `PshState`;
  - GE: `GeomState`;
  - NONE: identical, i.e. a miss on a non-shader field;
  - NOPREV: no comparable previous binding (none, the same node, or a clear pipeline).

  **Deviation from the brief:** the brief says "for each shader-cache miss". The only lent draw.c
  hunks are the create sites, and a shader-cache miss happens in `vk/shaders.c` (not lent). So
  this counts per pipeline miss. pipeline413's dsm/dpm is 0.73-1.0, so the two populations
  nearly coincide, and NONE counts the pipeline misses whose shader was unchanged.
- The `[shd413]` line keeps every existing field, in order, and appends:
  `pc_ms dpc_ms dpn dfb dfbh dfb_ms dvs_ms dgs_ms dfs_ms dsru dsrum dsru_ms dsnu dsnum dsnu_ms
  dgl_ms dsmod_ms dsv_ms kd=VP/FF/CB/TX/FL/PO/GE/NONE/NOPREV dins_us`. The meaning of each is in
  the comment above the emitter. `shdwin.py` (pipeline413) still parses the line; its regex is a
  search, not anchored at the end.
- **Overhead.** Everything added is on a miss path or wraps a create call. A pipeline hit, a
  shader hit and a SPIR-V hit run no new code. The instrument times its own bookkeeping (the
  lock, the hash set, the class compare) into `instr_ns`, printed as `dins_us`. So the brief's
  "a few clock reads per miss" is measured by leg O, not asserted.

`debug.h`: fields added to `ShaderPipelineStats` only. `vk/draw.c`: the two create sites, the
`save_pipeline_cache_to_disk` body, and two prototypes above it (the lent hunk). Nothing else.

### Checks run (no device)

- `syncheck.py`: `-fsyntax-only` on the four C files with the NDK clang and an arm64 release
  build's flags (`/home/justin/hakuX/android/app/.cxx/Release/135r5t6d/arm64-v8a`, `__ANDROID__`
  defined, so the `[shd413]` emitter and its format are checked by clang's `-Wformat`), and with
  the desktop gcc build's flags. 0 errors; every warning is in lines this lane did not touch.
- `keydiff_test.py`: builds `keydiff_test.c` against the real `ShaderState` with the classifier
  cut from `profile.c`. It has 19 cases, each changing a field in the middle of its class. PASSED.
  With `KD(TX, psh.dim_tex)` deleted, the test fails on `tex dim_tex[2]` (it lands in PO). The
  test can fail.
- `fbwin.py --selftest`: PASSED. It includes a decoy menu miss after `mark play`. With the
  quiet-run rule disabled, it fails 5 checks.
- `fbwin.py`'s fight-load rule was run on pipeline413's ring-out logcat
  (`1-1790579572-pipeline413-1715785`, padded with zero #569 fields). It picks 09:37:30-09:37:49:
  5 windows, dpm 19, own excess 14,932 ms. That is the span pipeline413 read from the frames
  (black screen -> `GET READY`, 19 misses, 14.8 s). A first rule ("first miss after `mark play`")
  picked the post-title menu miss at 09:37:00 and was replaced before registering.

## 2. Predictions (registered 2026-09-28, before any run)

- `docs/testing/predictions/shaderfb569-pixels-inert.json` (sha256 `e61d09cd5a0c...`): a
  01e62d8d1c, b 84c865c37d. The must-not-move set is the eight-suite set tbchurn424 used. The
  arms job queues it; its verdict comes back as a `[job.arms]` comment.
- `docs/testing/predictions/shaderfb569-doa-feedback.json` (sha256 `50023759ac46...`): the
  one-arm soak on cf5144dddb (the same hw/ as 84c865c37d, plus the reader). It uses a different
  ref from the arms' B, so its apk is not the one the arms may run first, and the dispatcher
  clears the shader cache for it. Legs: M0, C1 (vs 14.8 s) and C1' (vs this run's own excess),
  C2, C3 (with the duration cross-check), C4, and O (< 100 us of instrument time per create).

## 3. Runs

| id (under `$DISPATCH_DIR/results/`) | what | state |
|---|---|---|
| `1-1790621694-shaderfb569-1529058` | cf5144dddb, Nova (ee317437), DOA, survey, 440 s | done; `shader_cache: cleared: apk 32c8a1eb5468 -> 17fff996dc38`; battery start 32% |
| `1-1790623783-arms-shaderfb569-base-3041077` | A 01e62d8d1c, Thor, 8 suites | done, 593 captures, 257 exact |
| `1-1790623783-arms-shaderfb569-fix-3041536` | B 84c865c37d, Thor, 8 suites | done, 593 captures, 257 exact |

## 4. Result

### Why the first attempt did not finish

It did not fail. It ended in a `waiting:` state (PR comment 2026-09-28 18:56Z), on the soak, which
sat behind the Nova's battery hold, and on the arms verdict. Both runs finished by ~23:25Z, and
this resume reads them. There is still no `[job.arms]` comment on the PR at 23:30Z, so the
arms verdict below is this lane's own `ab_compare.py` read of the two result dirs.

### Arms: pixel-inert, PASS

`ab_compare.py --a <base> --b <fix> --expect shaderfb569-pixels-inert.json`, output in
`arms-abcompare.out`. Of 593 captures, 0 better, 0 worse and 593 same. All 593 are
**byte-identical** between the arms. `VERDICT: PASS -- all 593 registered checks hold.`
ab_compare exits 1 on its UNBOUND note: the arms job queued the pair from the committed file, so
no `request.sh --expect` names it. That is the arms job's normal path. The official verdict is the
`[job.arms]` comment when it posts.

### Soak: the reader's output

`fbwin.py <soak dir> --span 16:20:15 16:20:31` gives `soak-fbwin.out`. `spantotals.py <logcat>`
gives `soak-spans.out`. The times below are the device's logcat clock. Every number traces to
`1-1790621694-shaderfb569-1529058/logcat.txt`.

**The registered fight-load rule found nothing.** Both of its assumptions failed on this run:
- It assumed the load comes after `mark play`. Here the route's menu presses reached Story mode,
  character select and a fight *before* `mark play`. `mark booted` is at logcat line 1021, 16:19:08.
  `mark play` is at line 5149, 16:22:05. Frame `162013-menu-start` shows character select,
  `162019-menu-a` is black, and `162025-menu-start` is the fight's intro pose.
- It assumed a steady fight window is at least 4000 ms. The fight ran at ~20-30 fps: 60 flips
  took 2.0-3.1 s after the first load and 3.4-3.9 s in the stage-2 fight. pipeline413's run
  measured about 11 fps.

So C1, C2 and C4 are **VOID as the rule scores them**. The registered judge covers this case:
"if the frames place it elsewhere, the frames' span is scored as well and both are reported". The
frames' span is scored below. The frames put it after the fact, so treat it as a hand-placed
read, not a blind one.

**The frames' fight load** runs 16:20:15.217 to 16:20:30.886, logcat lines 2319-2602. That is
character select to the fight, 6 windows, 16.9 s of wall time, 21 misses.

| window closes | line | dt_ms | dpm | dpc_ms | dvs | dgs | dfs | reused stg (miss) | new stg (miss) | dgl_ms | kd VP/FF/CB/TX/FL/PO/GE/NONE/NOPREV |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 16:20:15.217 | 2319 | 1213 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - |
| 16:20:20.681 | 2389 | 5463 | 13 | 4061.4 | 2264.7 | 1120.3 | 79.4 | 28 (28) | 8 (8) | 49.8 | 0/10/8/3/1/2/0/1/0 |
| 16:20:22.646 | 2434 | 1965 | 1 | 499.9 | 321 | | 8 | | | 11.7 | 0/1/1/1/0/0/0/0/0 |
| 16:20:25.385 | 2483 | 2738 | 2 | 1373.5 | 1051 | | 13 | | | 14.3 | 0/2/2/0/0/0/0/0/0 |
| 16:20:27.199 | 2531 | 1814 | 1 | 503.6 | 370 | | 7 | | | 7.0 | 0/1/1/1/0/0/0/0/0 |
| 16:20:30.886 | 2602 | 3687 | 4 | 1838.9 | 1158 | | 25 | | | 21.6 | 0/4/4/1/0/1/0/0/0 |
| **span** | | 16880 | 21 | **8277.3** | 5165.3 | 1818.8 | 132.4 | 46 (46) | 14 (14) | 104.4 | 0/18/16/6/1/3/0/1/0 |

`soak-fbwin.out` does not print the blank cells (dgs and the reused/new split per window). They
are on the cited logcat line of each window. Line 2389, as an example of the full field set:

```
09-28 16:20:20.681 I/hakuX-perf( 5225): [shd413] ... dpm=13 ... pc_ms=28791.0 dpc_ms=4061.4 dpn=13 dfb=13 dfbh=0
dfb_ms=4061.2 dvs_ms=2264.7 dgs_ms=1120.3 dfs_ms=79.4 dsru=28 dsrum=28 dsru_ms=3023.1 dsnu=8 dsnum=8
dsnu_ms=441.2 dgl_ms=49.8 dsmod_ms=55.6 dsv_ms=0.0 kd=0/10/8/3/1/2/0/1/0 dins_us=37.2
```

Two other load-like spans are in `soak-spans.out`:
- 16:19:30.068 (line 1232), the attract/intro: one window, 26 misses, dpc 12,271 ms in a
  13,826 ms window.
- 16:23:21-16:24:08, the win, the title, then the stage-2 load: 59 misses, dpc 19,673 ms.

### The legs

| leg | registered | read | verdict |
|---|---|---|---|
| M0 | cold, >= 20 lines, all parse, pc_ms monotonic, feedback reported | cleared; 216 lines, 0 unparsed; monotonic; 164 creates, **164 with valid feedback**. Turnip on the Nova reports creation feedback | PASS |
| C1 | load dpc_ms within 20% of 14.8 s | the rule's load: VOID. The frames' span: 8,277 ms, ratio 0.56 | rule VOID; frames' span **FAIL** (low) |
| C1' | load dpc_ms within 20% of this run's own excess | 8,277 vs 9,602 (15,667 of miss-window dt, minus 5 x 1,213), ratio 0.86 | frames' span PASS |
| N1 (post-hoc, not registered) | - | Each dpc > 0 window's dt against the median of its 2+2 nearest quiet windows. Over 27 windows, dpc 59,851 ms vs excess 50,336 ms (1.19). The largest stalls agree window by window: 16:19:30 has excess 11,984 and dpc 12,271; 16:20:01 has 5,550 and 5,954; 16:23:59 has 5,070 and 4,882 | reading |
| C2 | glslang <= 5% of load dpc_ms | 104.4 / 8,277 = 1.26%. Over the whole run it is 731 / 59,851 = 1.2% | PASS |
| C3 | share of reused-module stages Turnip reports as a cache miss | 246 of 246 = **100%**. The cost is real: 164.4 ms per reused stage vs 108.7 per new one. Reused stages are 40,438 of the 52,716 ms of stage time (77%) | **>= 50%: P5 stays, GPL's bound is 1/2-2/3 of a miss** |
| C4 | the load's key-diff classes | the 21 misses: FF 18, CB 16, TX 6, PO 3, FL 1, NONE 1, VP 0. Over the whole run's 164: CB 115, FF 98, TX 67, PO 32, NOPREV 18, VP 15, FL 4, GE 4, NONE 4 | reading |
| O | < 100 us of instrument time per create | 416.1 us over 164 creates = **2.54 us each**. A create averages 365 ms | PASS |

What it means:
- **C1 fails, but not in the world its falsifier named.** The falsifier's world was "the stall's
  time is outside the create call". That world is refuted two ways. C1' is 0.86 on the load's own
  excess. N1 puts the whole run's create time at 1.19x the per-window excess, and the big stalls
  match window by window. C1 fails on size alone: this load cost 8.3 s over 21 misses, 394 ms per
  miss. pipeline413's 14.8 s over 19 (<= 780 ms each) came from a different run, at ~11 fps and
  on an older master. So the stall is inside `vkCreateGraphicsPipelines`, and this run's
  per-miss price is about half pipeline413's upper bound.
- **The vertex stage is the compile.** Of the stage time, vs is 41.2 s (78%), gs 10.8 s (20%) and
  fs 0.8 s (1.5%). glslang (0.7 s), module creation (0.8 s) and cache saves (0.3 s) together are
  3% of dpc.
- **The misses are fixed-function vsh and combiner variants, not vertex programs.** The load has
  0 VP diffs. FF 18 and CB 16 of 21 misses are what moves.
- **C3 limit.** The split is per stage (per `VkShaderModule`). A GPL pre-rasterization library
  holds vs and gs together, so its reuse needs both unchanged. The fields do not pair them, so
  77% is an upper bound on what GPL could skip, before link cost. Turnip's monolithic path may
  never set a per-stage hit bit when the pipeline misses. The duration evidence (reused stages
  cost full price) is what makes the 100% a real recompile rather than a flag that never sets.

### After the soak

The board request for the Nova's `files/spv_cache/` pull (for lane.turnipcost569, P2) is routed
to lane.local on #569 with `deliver.sh send`.

## Do not repeat

- Do not score a DOA load by a fixed "steady fight >= 4000 ms" window. On this build the fight
  runs at 20-30 fps. On the survey route the menu presses can reach a fight before `mark play`.
  Place the load from the route frames. `fbwin.py --span` scores a given span.

- Do not define the fight load as "the first miss after `mark play`". On the survey route, the
  menus after the DOA2U title miss first (09:37:00 in pipeline413's run).
- `ab_compare --register` asks for the file to be committed before the arms land. The soak
  prediction is hand-written (a_ref == b_ref; the arms job skips it), so it is queued with
  `request.sh --expect`.
