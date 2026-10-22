# p9pipekey1022: a draw whose pipeline-key inputs match the bound pipeline's keeps it without building the key (#433)

State: draft

Lane: p9pipekey1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/p9pipekey1022/PR.md
Prediction: Fable under =1: `pipe_skipped` about 400-460 per flip (the draws that today build a key equal to
  the bound one), `key` count 714 -> about 260 per flip, key+lru+pkc ms down by 0.05-0.17 ms per flip, `pipe`
  3.72 -> 3.55-3.70 ms; `pipe_mismatch` = 0 under =2; no pixel change. PLAN.md's "pipe 6.1 -> <= 1" (Fable)
  and "3.91 -> <= 1" (GTA III) are out of reach of this item (premise check below)
Needs device: yes, for the A/B only
Needs NDK: yes

Item P9 of the fps30 plan (handoffs/fps30-1022/PLAN.md): "pipeline lookup per draw: key only when a
key-feeding register changed".

## Step 0. Already tried

Searched: `docs/lanes/*/{PR,NOTES}.md` for `init_pipeline_key`, `pipeline key`, `samekey`, `same key`,
`notdirty`; `git log --all -i -E --grep="pipeline key|pipe_key|pipekey|pipeline lookup|must_bind|init_pipeline_key|samekey"`
(the hits are #59's pad-stamp series and the line-rasteriser series, which change what the key holds, not
whether it is built); `git log 72af9cb92c..b944110629 -- hw/xbox/nv2a/pgraph/vk/draw.c` (empty: draw.c has not
changed since the 10-18 captures PLAN.md quotes).

| What | Where | Result | Bearing on P9 |
|---|---|---|---|
| Fast path that skips the key build when no key-feeding state changed | audit C6 (fps-code-audit-1019.md, "a draw-state dirty-bit fast path"), PLAN.md P9 | proposed, never built; C6 itself asks for an identical-key counter first | this lane. The census below is that counter |
| create_pipeline outcome census (`HAKUX_DRAWCENSUS`) | drawrec1010 NOTES 5.2 (NFS MW race start) | not entered 31.9 %, not dirty 8.2 %, same key 48.3 %, LRU 11.6 %, miss 0 | same key is the largest outcome: the key is built and matches the bound pipeline's. That is the part P9 can remove |
| Clear the stale `shader_bindings_changed` after the full path consumed it (SHC) | drawrec1010 R1, `drawrec_shc_consumed()` draw.c:6382, in fastpaths (`HAKUX_DRAWREC`) | kept, default-on via fastpaths | orthogonal: SHC lets later draws reach SFP/MFP/EARLY; P9 acts on the draws that still reach the key. P9 must keep SHC's input: a skipped draw reports `DCEN_CP_SAMEKEY`, as the key path would |
| Per-draw uniform cuts (`HAKUX_UNI_BULK/UBERCACHE/FOGCACHE`) | perdraw1009, perdrawon1010 | kept, in fastpaths | orthogonal: the `bind` term (bind_shaders + uniforms), not the key |
| Push changed uniform rows instead of UBO binds | bf2push656 | no GPU time saved; emulator change reverted | not the key path |
| #274 early-return uniform refresh | draw.c:3181-3186 | kept | the EARLY exit stays as is; P9 sits after check_pipeline_dirty |
| GPL / uber pipeline swap (`gpl_take_next_pipeline`) | #569 P5/P6, draw.c:2686 | kept | the swap replaces `snode->pipeline` on the same node with the same key; a skipped draw must still call it, as SAMEKEY does |
| PFIFO CPU savings absorbed by `rotfen` when GPU-bound | fpsnext1019 C2 ("third strike") | measured | any P9 saving on GTA III shows only once the frame is not GPU-bound (PLAN.md orders P9 after P1) |

No recorded reason was found that the per-draw lookup must stay. Nothing above refutes the skip; nothing above
built it.

## Premise check: does master still pay the per-draw lookup?

Yes, but the term P9 can remove is about a twentieth of the `pipe` figure PLAN.md quotes.

Newest Fable perflog capture: `captures/fpsnext1019/runs/fable-h2/logcat.txt` (10-19, pid 25524, gameplay
window 12:29:05.770-12:30:40.701, 27 `[dipwin]` windows, 1620 flips; fastpaths on, so SHC is on):

| field | per flip | ms/flip | us each |
|---|---|---|---|
| `full` (full-path draws) | 724 | | |
| `pipe` (all of create_pipeline) | 724 | 3.72 | 5.1 |
| `bind` (pgraph_vk_bind_shaders, incl. its uniform update) | 718 | 1.53 | 2.1 |
| `key` (init_pipeline_key + the same-binding memcmp) | 714 | 0.27 | 0.37 |
| `lru` (fast_hash + lru_lookup) | 253 | 0.16 | 0.62 |

- The key is built on 98.6 % of full-path draws (714 of 724): `check_pipeline_dirty()` almost never says
  "not dirty", because `texture_bindings_changed` / `pipeline_state_dirty` / `shader_bindings_changed` are set on
  most draws, and none of those three feeds the key.
- 64.5 % of the key builds (461 of 714 per flip) match the bound pipeline's key (SAMEKEY); 35.5 % go on to the
  hash and the LRU (253 per flip) and bind another pipeline. Those are real pipeline changes; no skip applies.
- So the ceiling of a key skip on Fable is the SAMEKEY key builds: 461 x 0.37 us = **0.17 ms/flip**, less the
  cost of whatever decides to skip. `bind` (1.53) and the rest of `pipe` (3.72 - 1.53 - 0.27 - 0.16 = 1.76:
  bind_textures, the uniform refresh on the non-bind branch, check_pipeline_dirty, synchronous misses; not
  split by `[dipwin]`) are outside P9: they run before the key is reached, whatever the key does.
- PLAN.md's "Fable pipe 6.1 -> <= 1" and "GTA III 3.91 -> <= 1" read the whole `pipe` timer as key + lookup. The
  code shows they are unreachable by this item; the prediction below is restated on the terms P9 does touch.

## Prediction and falsifier

Under `HAKUX_PIPEKEY_DIRTY=1`, on the Fable gameplay window above:

- `pipe_skipped` about 400-460 per flip. A skip needs the same pipeline binding, the same shader binding, and
  equal render pass formats, key registers and vertex descriptions. Those are the draws that today build a key
  equal to the bound one (SAMEKEY, 461 per flip), less the first draw after a lookup that did not end on an LRU
  hit (pending, miss, cache full).
- `pipe_forced` about 250-310 per flip, almost all of it `pf_shd` / `pf_reg` / `pf_vtx` / `pf_rp`: the draws
  that go on to the hash today. `pf_nob` is small: once per lookup that ends on a miss, a pending pipeline or a
  full cache, once after an eviction of the bound pipeline, and once after a clear pipeline or a reorder-window
  flush rebinds `r->pipeline_binding`.
- `key` count 714 -> about 260 per flip. The `key` time falls by up to 461 x 0.37 us = 0.17 ms per flip; the new
  `pkc` timer (pipekey_check, on every draw that gets past check_pipeline_dirty) gives some of that back.
  Expected net: 0.05-0.17 ms per flip off `pipe`, i.e. `pipe` 3.72 -> 3.55-3.70 ms.
- No pixel change: every skipped draw binds the pipeline the key path would have bound.

Under `=2`: `pipe_skipped` as above (now "would have skipped"), `pipe_mismatch` = 0, no
`nv2a: pipeline key mismatch` line, `key` count back at the =0 figure, `pipe` at the =0 figure plus `pkc`.

GTA III: the same mechanism. Its SAMEKEY share has not been measured; while the frame is GPU-bound a CPU saving of
this size is absorbed by the wait on the GPU (fpsnext1019 C2), so no fps change is predicted there.

Falsified by any of:

- `pipe_skipped` near 0 under =1 on Fable (under 100 per flip) while an =0 census shows SAMEKEY draws;
- any `pipe_mismatch`, or any `nv2a: pipeline key mismatch` line, under =2;
- a pixel difference over the noise floor between =0 and =1 on the same scene;
- `key` count under =1 not below the =0 count.

## The change

All in `hw/xbox/nv2a/pgraph/vk/draw.c`; line numbers are at this commit.

| Lines | What |
|---|---|
| 1215-1221, 1233, 1264-1266, 1393-1400 | `[dipwin]`: new `pkc` timer; counters `pipe_skipped`, `pipe_forced` (sum of the reasons), `pf_nob`, `pf_shd`, `pf_rp`, `pf_reg`, `pf_vtx`, `pipe_mismatch`, all under `#if NV2A_PERF_LOG` and through `dipwin_add(&dw_c[...])` / `DW_INC` |
| 1685-1727 | `pipekey` state: mode, the binding whose key the last built key matched, the shader binding that key came from, the vertex description counts it was built with; `pipekey_drop()` |
| 1733-1735 | `pipeline_cache_entry_init`: a reused node that is `pipekey.binding` drops it |
| 1779-1781 | `pipeline_cache_entry_post_evict`: an evicted node that is `pipekey.binding` drops it |
| 1876-1887 | `init_pipeline_cache`: reads `HAKUX_PIPEKEY_DIRTY` once (1 or 2, anything else 0), drops, and logs `nv2a: pipeline key ... (HAKUX_PIPEKEY_DIRTY=N)` |
| 1953-1954 | `finalize_pipeline_cache`: drops after the entry array is freed (`lru_flush` keeps entries `pre_evict` refuses, which get no post_evict) |
| 2596-2677 | `init_pipeline_key_regs()`: the register part of `init_pipeline_key()`, moved out unchanged so the key and the check share one copy of the register list and masks |
| 2679-2693 | `init_pipeline_key()`: same output as before (memset, render pass, shader state, vertex descriptions, then the registers) |
| 2695-2724 | build-time layout guard: `PipelineKey` must be exactly clear, render_pass_state, shader_state, regs, binding_descriptions, attribute_descriptions in that order with only alignment padding; a new key field fails the build until the check covers it |
| 2726-2764 | `pipekey_check()`: returns SKIP or the first reason it cannot skip (see the table below) |
| 2766-2773 | `pipekey_confirm()`: records the binding, shader binding and vertex counts after a built key matched |
| 2785-2855 | `pipekey_mismatch()` (=2): counts and logs the first differing key field, on the 1st, 2nd, 4th, 8th ... mismatch |
| 3479-3482 | create_pipeline, after `pgraph_vk_bind_shaders()`: drop when it set `shader_bindings_changed` |
| 3509-3531 | create_pipeline, after the NOTDIRTY return: run the check; under =1 a SKIP returns as SAMEKEY does (`dcen_cp = DCEN_CP_SAMEKEY`, `gpl_take_next_pipeline`, `pipeline_cache_hits++`) |
| 3543-3545 | =2: a would-skip draw whose built key differs from the bound one is a mismatch |
| 3550-3552 | SAMEKEY: confirm |
| 3560-3563 | before the hash: drop (only an LRU hit confirms again) |
| 3599-3601 | LRU hit: confirm |

Under =0 the only additions on the draw path are the `pipekey.mode` tests, plus a pointer compare against a
NULL `pipekey.binding` in entry_init and post_evict; no key, lookup or counter changes.
Under =2 every draw builds the key exactly as under =0; the extra cost is pipekey_check() and, on would-skip
draws, one compare of `same_key`.

## Key inputs and where they change

Every input of `init_pipeline_key()`, and how the check covers it. All but one are compared by value against
`r->pipeline_binding->key`, so no input needs a write site or a dirty bit: a write that bypasses the dirty map
(the replay at draw.c 8790-9050 sets `pg->regs_` directly and restores them after; `pgraph_vk_reg_r()` reads
`r->active_snap` when one is set) is still seen. Nothing is forced for lack of a write site.

| Key field | Read from | Changed by | Check | Forced as |
|---|---|---|---|---|
| `clear` | constant false (memset) | only `create_clear_pipeline` builds true | `b->key.clear` must be false | `pf_nob` |
| `render_pass_state.color_format`, `.zeta_format` | `r->color_binding` / `r->zeta_binding` `->host_fmt.vk_format` (init_render_pass_state, 2123) | surface rebinds, surface format changes (surface.c) | value: zeroed `RenderPassState` + init_render_pass_state, memcmp | `pf_rp` |
| `render_pass_state` load ops | 0 (memset; init_render_pass_state does not write them) | not written for these keys | in the same memcmp (0 = 0) | `pf_rp` |
| `shader_state` | `r->shader_binding->state` | `r->shader_binding`: shaders.c:2201 only; `ShaderBinding::state`: shaders.c:1346 only, when the lookup at 2201 (re)initialises a node; that branch sets `shader_bindings_changed` | identity: `r->shader_binding == pipekey.shader`, and pipekey dropped after any bind_shaders call that set `shader_bindings_changed` | `pf_shd` |
| `regs[0]` | effective BLEND (`pgraph_vk_effective_blend_reg`, 642): BLEND, the destination-alpha fold, `pg->surface_shape.color_format`, `pgraph_glsl_dual_src_pad_supported()` | NV097 methods, replay | value: `init_pipeline_key_regs()` into a local array, memcmp | `pf_reg` |
| `regs[1..5]` (`[1..8]` without OPT_DYNAMIC_STATES) | CONTROL_0, CONTROL_2, CONTROL_3, SETUPRASTER, CONTROL_1 (+ BLENDCOLOR, ZOFFSETBIAS, ZOFFSETFACTOR), masked | NV097 methods, replay | as `regs[0]` | `pf_reg` |
| the masks | `r->extended_dynamic_state_supported`, `r->eds3_blend_supported` | renderer init only | same code as the key | - |
| `binding_descriptions[0..n)` | `r->vertex_binding_descriptions`, `r->num_active_vertex_binding_descriptions` | vertex.c 352-353, 396-397, 511, 578 (every draw's vertex setup) | value: count equal to the matched key's, memcmp of the active entries (the key's entries past them are zero) | `pf_vtx` |
| `attribute_descriptions[0..n)` | `r->vertex_attribute_descriptions`, `r->num_active_vertex_attribute_descriptions` | as above | as above | `pf_vtx` |
| padding | zero (memset) | - | the layout guard (2695-2724) admits only alignment padding | - |

Why shader identity is enough: when `pipekey.binding` was confirmed, its key's `shader_state` was copied from
`pipekey.shader->state`. `b->key` is written only at the miss path's memcpy (3625, and 2375 for clear keys), on a
node that is either fresh (entry_init drops pipekey) or was found by an equal key (same bytes). `pipekey.shader->state`
is written only by the shader lookup, which only runs in the call that sets `shader_bindings_changed`, and
create_pipeline drops pipekey right after that call (3479-3482). `pgraph_vk_bind_shaders()` is called only from
create_pipeline (`bind_shaders` clears the flag on entry, shaders.c:2149).

## What drops the bound pipeline

Each was checked in the code; "value" means the check catches it by comparison and no drop is needed.

| Event | Where | How it is handled |
|---|---|---|
| LRU eviction (cache full, `lru_get_one_free` -> `lru_evict_one`) | include/qemu/lru.h:117-131 -> `pipeline_cache_entry_post_evict` | drop if the evicted node is `pipekey.binding` (1779) |
| `lru_flush` (renderer finalize) | lru.h:229-246; skips entries `pre_evict` refuses | post_evict drop for the evicted ones; finalize drops after freeing the array (1954) |
| node reuse for a new key | `lru_lookup` -> `init_node` = `pipeline_cache_entry_init` | drop if the reused node is `pipekey.binding` (1733) |
| a lookup that ends on a miss, a pending pipeline or a full cache | create_pipeline 3573-3619 | dropped before the hash (3560); only an LRU hit confirms (3599) |
| async miss binding a node whose key was never copied | create_pipeline 3612-3618 | not confirmed; the next draw builds the key as today (its stale-key compare is unchanged) |
| clear pipeline bound | `create_clear_pipeline` sets `r->pipeline_binding` (2367, 2532) | identity: `pipekey.binding != r->pipeline_binding` -> `pf_nob` |
| reorder-window flush restoring `r->pipeline_binding` | flush_reorder_window_internal, 10097 | identity on the binding, value on everything else |
| draw replay overriding `pg->regs_` and the gens around begin_draw | flush_draw_queue_internal, 8790-9050 | value (`pf_reg`); the shader identity argument does not depend on how `r->pipeline_binding` was set |
| GPL / uber -> LTO swap | `gpl_take_next_pipeline` | swaps `snode->pipeline` on the same node with the same key; the skip still calls it, as SAMEKEY does |
| pipeline handle replaced on a node (compile completion 4123, 4257; LTO swap 2954) | same node, same key | nothing to drop; the cache itself is only rebuilt by finalize/init (2060, 2093) |
| render pass change, surface rebind, ZETA_D24 host format | `r->color_binding` / `r->zeta_binding` | value (`pf_rp`) |
| shader rebind | shaders.c:2201 | drop (`pf_shd`) and identity |
| frame / command buffer boundaries | no key input changes | nothing to drop; `pre_evict` already keeps in-use nodes |
| renderer init / reset | `init_pipeline_cache` | drop (1882) |

Downstream readers of the outcome are unchanged: a skipped draw reports `DCEN_CP_SAMEKEY`, so
`drawrec_shc_consumed()` (6680) clears `shader_bindings_changed` exactly as after a SAMEKEY, and
`pipeline_binding_changed` is untouched as on the SAMEKEY return.

## Not changed here: an uninitialised compare in check_render_pass_dirty

`check_render_pass_dirty()` (2539-2549) does `RenderPassState state; init_render_pass_state(pg, &state);` and
memcmps the whole struct against the key's. init_render_pass_state writes only the two formats; the three load-op
fields (added in 876942ca09) stay uninitialised on the stack, while every created key has them 0. Where the stack
bytes are not zero the EARLY exit and `check_pipeline_dirty()` report "dirty" when nothing is. That sends a draw to
the key path that could have returned earlier: a performance leak, not a correctness one. Fixing it changes the
=0 path, so it is left out of this lane; pipekey_check() zeroes its struct before the compare.

## Checks

Compile, both perflog settings (`python3 -I /home/justin/hakux-work/tools-p/cc_wt.py <wt> hw/xbox/nv2a/pgraph/vk/draw.c -DNV2A_PERF_LOG=N`):

| | exit | warnings | vs master b944110629 draw.c |
|---|---|---|---|
| `-DNV2A_PERF_LOG=1` | 0 | 16 | identical warning set |
| `-DNV2A_PERF_LOG=0` | 0 | 16 | identical warning set |

Selftest fragments that name `draw.c`, `pipeline` or `dipwin`
(`grep -l -E "draw\.c|pipeline|dipwin" docs/testing/jobs/selftest.d/*.sh`), run with
`SELFTEST_ONLY="<those 14>" timeout 900 bash docs/testing/jobs/selftest.sh`:

```
selftest: 582 passed, 7 failed, PARTIAL: 14 of 160 fragments
```

| Fragment | Result |
|---|---|
| 99-dipwin-counters | all ok, mutants included: one `dipwin_flip()` caller in the FLIP_STALL branch; the plain `dw_c[]` increment, `+=` writer, read-then-zero reader, presenting-window and second-caller mutants each fail as they must. The new counters go through `dipwin_add(&dw_c[...])` and `DW_INC`, so its `dw_c[` rule holds |
| 65, 66, 73, 76, 86, 88, 96, 98-fleet-queue-stall, 98-lane-shape, 99-fleet-absent-device, 99-fpsdiag, 99-handback | all ok |
| 51-dispatch-hardening | 7 FAIL, all in E/E2: `clear_markers` / `finish_queue: command not found` and "fixture not as 50 leaves it". 51 sits after 50-arms-requeue in a SHARD_CHAINS chain and reads 50-arms-requeue's helpers and fixture; it matches the grep only for `vk_pipeline_cache.bin` in an adb fixture. Run with its chain prefix (`SELFTEST_ONLY="10-arms-list 20-arms-queue 30-arms-error 40-arms-refusal 50-arms-requeue 51-dispatch-hardening"`): `97 passed, 0 failed`, 51's sections A-J all ok |

No anchor moved; no check was changed.

## Device A/B

Perflog build of this branch, fastpaths as usual, Nova, the Fable gameplay window (and GTA III driving if a second
title is wanted). Three runs on the same scene:

| Arm | Env |
|---|---|
| A | `HAKUX_PIPEKEY_DIRTY=0` |
| B | `HAKUX_PIPEKEY_DIRTY=1` |
| V | `HAKUX_PIPEKEY_DIRTY=2` |

Read, from `hakuX-rpbrk` `[dipwin]` lines: `pipe`, `key`, `lru`, `pkc` (n/ms), `full`, `pipe_skipped`,
`pipe_forced`, `pf_nob`, `pf_shd`, `pf_rp`, `pf_reg`, `pf_vtx`, `pipe_mismatch`. From `hakuX-stderr`: the init line
`nv2a: pipeline key ... (HAKUX_PIPEKEY_DIRTY=N)` (confirms the arm), and under V any
`nv2a: pipeline key mismatch #N (HAKUX_PIPEKEY_DIRTY=2): <field>`. Pixels: A vs B frames on the same scene.

## Risks

- The gain is small: at most 0.17 ms per flip on Fable, less the check's cost on the roughly 35 % of draws that
  are not skipped. On a GPU-bound frame it may not show in fps at all.
- The shader-state part of the check is by identity. Its proof rests on the shader binding write sites in
  shaders.c (1346, 2149, 2201), which this diff does not touch; a new writer of `ShaderBinding::state` or of
  `r->shader_binding` outside the bind_shaders lookup would break it. The =2 run is the guard against that.
- `init_pipeline_key_regs()` carries a comment that every new key input must be compared by the check, and the
  layout guard fails the build on a new key field; an input added inside an existing field (a new register read
  into `regs`, a new render pass format source) is covered because both sides call the same function.
- Compile-checked with the desktop gcc only, not the NDK clang. The layout guard uses `_Alignof` and
  `__typeof__` at file scope, which nothing else under hw/ or include/ uses; both are C11/GNU forms clang accepts,
  but the first NDK build is the first time this code meets clang.
- The check_render_pass_dirty uninitialised compare above stays as it is.
