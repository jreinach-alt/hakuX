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
