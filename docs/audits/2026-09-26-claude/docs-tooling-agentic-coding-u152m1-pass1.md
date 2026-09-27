# Audit pass 1: PR #449, lane `claude/docs-tooling-agentic-coding-u152m1` (#426 items 1, 2, 4)

Head audited: `932ab471`, diffed against `origin/master` (merge base `c9331a68`). The fold job then merged master in (`45f62ce0`, `699c0e87`). That merge touches none of this PR's files except the regenerated index, so the audit holds for `699c0e87`.

**Verdict: no HIGH, no MEDIUM, two LOW.** Both LOWs are documentation. Nothing in the code needs changing.

## What was checked

**Default build.** Every new field, counter and bind note is inside `#if NV2A_PERF_LOG`. The two new `_EXCL_CHILD` macros have `do { } while (0)` stubs.
- The `NV2A_PERF_LOG` default moved above the structs in `debug.h`.
- Both CMake targets that include it (`xemu_core` at CMakeLists.txt:940, `xemu` at :1060) get the same `-D`, so no two TUs can disagree about the struct layout.
- The `pipe[...]` line is inside `opt_stats_log_and_reset()`'s `#if NV2A_PERF_LOG` / `#ifdef __ANDROID__`. `Lru::num_used` and `num_free` exist (`include/qemu/lru.h:47-48`).

**Timer pairing.** Every BEGIN has an END on every exit.
- `begin_pre_draw_inner()`: `Sfp` ends at both the hit `return` (draw.c:4160) and the miss fall-through (:4168). `Mfp` ends at the hit `return` (:4249) and at `mfp_miss` (:4253). The only `goto mfp_miss` (:4203) is after `Mfp`'s BEGIN, so the END never reads an uninitialised `_phase_t0_draw_mfp`.
- `create_pipeline()`: `pipe_lookup` now ENDs exactly once on each of its six exits. The async-compile miss (:2256) no longer ENDs a second time. `shader_compile` ENDs at all three exits in :2267-2794, including the new one at :2290.
- `pgraph_vk_clear_surface()`: its four `return`s (:7174, :7193, :7234, :7338) all come before the new `draw_dispatch` BEGIN (:7346). No path from there to the END (:7436) can return.

**Nesting.**
- `EXCL_CHILD` subtracts the finish in its whole window once, through `END_EXCL`. It then subtracts the child's delta, and the child is itself `_EXCL`, so a finish inside `FTx` is not taken off twice.
- The clear's new `Draw` span calls nothing that reaches `flush_draw_one_pass()`, whose `Draw` would nest in it. `surface_update` runs at :7185, before the span, so `Surf` does not land inside `Draw`.
- `pgraph_vk_bind_textures()` has exactly three callers: :2166 (`Tx`), and :4030 and :4221 (`FTx`). `upload_texture_image()` (`Tex`) and the hash (`TxH`) are reached only from `create_texture()`, so I5 holds by construction.
- `TxH` is a plain timer. That is correct, because `fast_hash()` cannot reach a finish.

**Eviction counter.**
- **Bind notes.** Every `vkCmdBindPipeline` of a `PipelineBinding` records the bind: `begin_draw` at :4590 and `emit_reorder_entry` at :6200. A new command buffer always begins a new render pass, and `begin_draw` then rebinds (:4575-4577). So the last command buffer to use a pipeline is always recorded.
- **Initial state.** `PGRAPHVkState` comes from `g_malloc0` (renderer.c:193). `cb_serial` starts at 0 and the first serial is 1, so `last_use_cb == 0` safely means "never bound".
- **Slot reuse.** A slot begins a newer command buffer only after `vkWaitForFences` on it (:3728-3733). So a serial mismatch does mean the old command buffer completed.
- **Unsubmitted command buffers.** A command buffer that is ended but not yet submitted could be missed. That state is never visible from the pgraph thread: the deferred path spins until `frame_submitted` is set (:3656), and the non-deferred path waits on `finish_event`. `pgraph_vk_submit_worker_enqueue()` has no callers.
- **Teardown.** `finalize_pipeline_cache()` flushes the LRU (:1465) before the frame fences are destroyed (:1575). So `vkGetFenceStatus` never sees a destroyed fence.

**Reader identity.** Expanding `rc + p + u` with the new `DRAW_SUB`, `POST` and `pipe_rest` gives exactly `Surf + Draw + Fin`.
- The old reader was off by `Pipe - (Tx+Sh+Lu+Shd)`, which `pipe_rest` now absorbs.
- The checker's I1, I4 and I5 are now one-sided and keep the rounding bounds. I2 stays an identity.

## Findings

### LOW-1: `phase_read_split.py` docstring says `Tx` is not exclusive of finish, but this PR makes it exclusive

- **Where.** `docs/testing/phase_read_split.py:41` says the binds' `rest` "also carries any finish nested in a Tx bind, since Tx is not exclusive of finish and Tex and FTx are". The same PR changes `pipe_bind_tex` to `NV2A_PHASE_TIMER_BEGIN_EXCL` (draw.c:2163).
- **Scenario.** On a new-format Crimson line with a high `rest` share, a reader who trusts the docstring attributes part of `rest` to nested finishes. The instrument has already removed those. The next lever for `Tx` (item 3) is then priced against a cause that is not in the number.
- **Fix.** Delete the clause, or say that `rest` holds no finish on new lines.

### LOW-2: the "compare with older soaks" caveat omits `Draw` and `BUSY`

- **Where.** The PR body's "Not covered" warns about `Pipe`, `Setup` and `Tx`. This PR also moves the fall-through clear's `begin_pre_draw()`, `begin_draw()` and clear commands into `Draw` (draw.c:7346-7436). That work was previously outside `Draw` and so outside `BUSY = Surf + Draw + Fin`.
- **Scenario.** On a clear-heavy title, `Draw` and `BUSY` read higher on a post-#449 soak than on an older one, and the rise is instrumentation. Someone comparing the two soaks reads it as a regression.
- **Fix.** Add `Draw` and `BUSY` to the caveat, in the PR body or in the `phase_read_split.py` docstring beside the existing old-line note.

## Not audited

- `docs/testing/nv2a_index.json` was regenerated by the tool, and CI gates it.
- `docs/lanes/remote/NOTES.md` is lane notes.
- The Android compile of the `pipe[...]` line was not checked. The PR says so itself: the perflog APK is its first real compile. A format or field error there fails that build loudly; it cannot mis-measure silently.
