# Audit pass 1: PR #473 (lane.remote, #461 texture-bind count)

Head audited: `47a3ce8e85`. Diff read: `hw/xbox/nv2a/pgraph/vk/{texture.c,draw.c,renderer.h}`,
`docs/lanes/remote/tex461_read.py`, `docs/lanes/remote/NOTES.md`; `docs/testing/nv2a_index.json`
is regenerated output and was checked with `nv2a_index.py check` only.

**Verdict: no HIGH, no MEDIUM. Two LOWs.** Next state: `needs-audit-2`.

## What was checked

1. **Default-build inertness.** Every added statement is either inside `#if NV2A_PERF_LOG`
   or inside `TEX_PERF(...)`, which expands to `do { } while (0)` without it. The new
   enums (`renderer.h:57`), the `OptBisectStats` fields (inside the existing
   `#if NV2A_PERF_LOG` at `renderer.h:189`), the `TextureBinding` fields, `txk_converted()`,
   and `tx_dl0` are all under the guard. `tx_dl0` is referenced only inside `TEX_PERF`, so
   a default build neither declares nor reads it. No path found by which a default build
   changes.
2. **I2 (new/rb hashes == new/rb uploads) is exact.** On a miss, `possibly_dirty` is forced
   true, so a hash runs whenever `!surface_to_texture`. Between the hash and the miss-path
   upload (`texture.c:2687`) the only `return` is the final one at `:2693`, and the upload
   is in the `else` of `if (surface_to_texture)`, which is the hash's own condition.
   `tx_rb` feeds both the `why` and the `TXU_RB/TXU_NEW` choice.
3. **I3 (found hashes == eq + chg) is exact.** On the found path with `!surface_to_texture`,
   a hash runs iff `possibly_dirty`. Then `eq` counts `possibly_dirty && !vram_changed`
   and `TXU_CHG` counts `vram_changed` (which implies `possibly_dirty`), and every
   `vram_changed` reaches `upload_texture_image`. The two are disjoint and cover the hash.
4. **I1 (`oth` == 0).** With `binding_found`, `possibly_dirty` can be raised only by the
   direct surface download (`tx_srf`), `snode->possibly_dirty` (`pending_mark`), the memo
   (`tx_memo`) or a fresh bitmap hit (`tx_bit`). A rebuild clears `binding_found`, and
   `possibly_dirty_checked` is never set true. So every `why` falls in a named reason.
   The confirmed-clean cancel runs before the hash, so counting at the hash is correct.
5. **I4.** `upload_texture_image` has two callers (`:2274`, `:2687`), and each is followed
   by exactly one `txu_n[]` increment. `get_texture_layout` has one caller (`:683`), so
   `txk_b` is not inflated by other paths.
6. **The range-scan difference.** `dif_other` and `sd_shelved_lazy_dl` are raised in
   `surface.c` at `:404`, `:415` and `:427` inside the scan. The direct
   `pgraph_vk_surface_download_if_dirty` call runs before `tx_dl0` is read, so it cannot
   leak into `scdl`. `g_opt_stats` is reset only from `opt_stats_log_and_reset`
   (`draw.c:3488`, at a flip or presenting finish), never inside a scan, so the difference
   cannot go negative.
7. **The print.** It sits inside `#if NV2A_PERF_LOG` / `#ifdef __ANDROID__` in
   `opt_stats_log_and_reset`. Each `%d` is an `int` field and each `%llu` goes through
   `TX_KIB`, which casts to `unsigned long long`. `tex_cache_uploads`, `tex_pool_hits` and
   `tex_pool_misses` are `int`. The reader's regexes match the format strings field for
   field.
8. **Reader.** `tex461_read.py --selftest` prints PASS here. Grouping resets on an
   out-of-order line and counts it as dropped, so a lost line cannot splice two groups.
   A truncated `txr` line is dropped without zeroing its group's earlier lines, and the
   next `txh` starts a new group.
9. **Gates.** CI: `build` ×2 and `check` SUCCESS; the PR is MERGEABLE.
   `nv2a_index.py check` passes on the symbol and site halves.

## Findings

### LOW-1: a reused direct view is not counted in `s2td`
`txr_s2td` is incremented in `bind_surface_as_texture` and `bind_zeta_surface_as_texture`
only. The found path's "same draw_time" branch (`texture.c:~2244`) also sets
`tex_surface_direct[texture_idx] = true` and binds the surface's view directly, but it
counts nothing. **Scenario:** a title that samples an unchanged render target every frame
shows `s2td` near 0 in the reader's "direct binds per frame". The binds are still
happening, so a reader could conclude surface-as-texture is rare when it is the common
case. The cost is small, because that branch does no work beyond the assignment. The fix
is to rename the field "direct binds made (view changed)" in the comment and the reader,
or to count the reuse separately.

### LOW-2: `--window` timestamps are parsed with no year
`stamp()` uses `%m-%d ...`, so every timestamp lands in 1900. **Scenario:** a capture that
spans New Year (12-31 → 01-01) gives a negative `t - t0`, and the lines after midnight fall
outside any window. This is harmless for 240 s soaks at any other time. The fix is to add
a year rollover, or to document the limit.

## For pass 2
Neither LOW blocks folding. Pass 2 only needs to confirm that neither scenario has become
worse, or that each is fixed or explicitly accepted. No device run is needed.

---

# Earlier audit at this path: PR #449 pass 1 (kept verbatim)

This lane branch carried PR #449 before PR #473, so both pass-1 audits share this path.

## Audit pass 1: PR #449, lane `claude/docs-tooling-agentic-coding-u152m1` (#426 items 1, 2, 4)

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
