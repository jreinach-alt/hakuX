# Audit pass 1: PR #256 (lane.remote, #184). A write to a surface rebuilds every stage sampling its memory

Auditor: `[job.cloud]`, 2026-09-25. Head audited: `f5bfe715`.

This file sits beside `docs-tooling-agentic-coding-u152m1-pass1.md` and does not replace it. That name already holds PR #247's pass 1, which was written on the same branch the same day.

**Verdict: no HIGH, no MEDIUM, two LOWs. Next state: `needs-audit-2`.**

## Scope read

- The diff: `hw/xbox/nv2a/pgraph/vk/draw.c` (+48 -4, body of `pgraph_vk_surface_written_while_sampled()` only), three prediction files, the regenerated `nv2a_index.json` (line numbers only), and `docs/lanes/remote/`.
- The callers, which are unchanged: the reorder-window flush (`draw.c:6304/6308`) and `post_draw` (`draw.c:6549/6553`). Each runs once per draw that writes colour or zeta.
- What the change reaches:
  - `pgraph_vk_bind_textures()`, `check_textures_dirty()` and the `tex_reg_cache` shortcut (`vk/texture.c:2585-2735`).
  - The two readers of `texture_state_gen`: `create_pipeline()` (`draw.c:2077-2098`) and the single-frame fast path (`draw.c:3897`).

## Checked and correct

- **The overlap test compares like with like.**
  - `key.texture_vram_offset` comes from `pgraph_get_texture_phys_addr()`, which is a VRAM offset. `surface->vram_addr` is a VRAM offset too.
  - `ranges_overlap()` (`include/qemu/range.h`) takes `(start, len)` pairs.
  - Both lengths are checked for zero before the call, so a zero-length key cannot match.
- **No bad pointer is dereferenced.** `texture_bindings[i]` is checked for NULL and for `&dummy_texture` before `key` is read. A disabled or undecodable stage is always the dummy (`texture.c:2608`), so the scan cannot invalidate a stage the draw has turned off.
- **The direct-view branch keeps its old effect.** It still bumps the gen once. `return` becomes `continue`, so a copy of the same surface on another stage is also reached. The branch leaves `tex_reg_cache` alone for the direct view, which is right: a direct view samples the live image and needs no rebuild.
- **The invalidation is confined to the shortcut.**
  - `tex_reg_cache[i].valid = false` is read only by the shortcut at `texture.c:2632`. It is re-stamped on the next successful `create_texture()`.
  - On the `!bound` path (LRU exhausted) the cache stays unstamped, which keeps #56's repair intact.
  - `texture_dirty` is not set, as the comment says. A stage whose registers are not rewritten is therefore not rebuilt.
- **The gen is bumped once per call,** not once per matching stage.
- **The predictions are sound.**
  - Both were registered before the code they judge (`b_ref 1213f50c`), and both name their uncomfortable outcomes.
  - v2's `expect` holds six real capture keys. Every value is an absolute measured on the Vulkan path, not derived.
  - The surf1 guard is `must_not_move: ["*"]` with `better = 0, worse = 0`. It names the world in which it fails: a mid-pass download on a VRAM-path stage.
  - The failed v1 registration stays in the tree as judged, which is the right record.
- **The comment states the fix's limit honestly.** A stage sampled while its own memory is written, with no register write in between, is not reached. That case is stale on master too, and prediction outcome (4) says so. It is not a defect of this PR.

## Findings

### LOW 1: every draw into a surface that an enabled stage overlaps now misses the pipeline early-out (`draw.c:6776-6787`)

**What changed.** Before this PR, only a direct view of the written surface bumped `texture_state_gen`. Now any enabled stage whose copied or uploaded memory overlaps the written surface bumps it too, on every draw that writes colour or zeta.

**What that costs.** `create_pipeline()` misses its early-hit (`draw.c:2081`), and without push descriptors the single-frame fast path misses at `draw.c:3897`. `bind_textures` then returns at `check_textures_dirty()`, because nothing is dirty, so the output is unchanged. The cost is a pipeline lookup and a descriptor rewrite per draw.

**Failure scenario.** A title renders a pass into surface S while a stage is still enabled on a texture copied from S. That can be a leftover binding from the previous pass, or a deliberate read of the last frame. Every draw of that pass now takes the slow path.

**Why it is only LOW.** The cost is performance only. Master already behaves this way for the direct-view case. The surf1 guard measures pixels, not frame time, so it cannot see this, and a CPU-heavy title is where it would show.

**Not required for fold.** A lane that wants the cost gone could bump only when some stage's `tex_reg_cache[i].valid` was true before this call. A stage already invalidated has already been signalled.

### LOW 2: the script's stale flag is a point sample (`docs/lanes/remote/clear_swatch_quads.py`)

The script decides a swatch is "stale" from one pixel, `(8, 8)` of the swatch. That flag backs the prose leg "every swatch shows its own clear colour".

The per-swatch error counts printed beside the flag are region counts, and they are the registered absolutes. A stale swatch would move a count off its registered value, so it cannot pass through this gap. This is quality only.

## Nothing HIGH or MEDIUM

- No incorrect behaviour, crash path or unsafety was found.
- The one widening of behaviour (LOW 1) is bounded to performance.
- On the pixel side, the widening is covered by the PR's own guard: 236 captures from the 14 suites most likely to reach it, byte-identical between master and the fix.

## For pass 2

- Confirm that `vk/draw.c` at the head it audits still differs from `5eab6a87` only in this function, because the arms were measured against `5eab6a87`.
- Confirm that neither LOW has become worse.
