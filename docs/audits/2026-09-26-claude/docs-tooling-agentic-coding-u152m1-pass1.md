# Audit pass 1: PR #380 -- vk/draw.c: refresh the uniform block on create_pipeline()'s early return (#274 GPUAA)

Head audited: `fb5879944b` (branch `claude/docs-tooling-agentic-coding-u152m1`).
Auditor: job.cloud, 2026-09-26.

**Result: clean. 0 HIGH, 0 MEDIUM, 2 LOW, none asking for a change. Nothing to verify in pass 2, so the PR goes to `fold-ready`.**

## What the diff does

The only code change is six lines in `hw/xbox/nv2a/pgraph/vk/draw.c`, inside `create_pipeline()`'s early-return branch (`pipeline_early_hits`): a comment, then `pgraph_vk_update_shader_uniforms(pg)` before `NV2A_VK_DGROUP_END(); return;`. The other files are the four prediction registrations, the regenerated `nv2a_index.json`, and 92 appended lines in `docs/lanes/remote/NOTES.md`.

## What was checked

1. **The call is safe to make at that point.**
   - `pgraph_vk_update_shader_uniforms()` returns early on a NULL `r->shader_binding`. The early-return condition already dereferences `r->shader_binding->state.geom.primitive_mode`, so the binding cannot be NULL there.
   - Under `OPT_ASYNC_COMPILE`, an unready binding returns early with nothing written. `pgraph_vk_draw_begin` then skips the draw at `draw.c:4179-4186`, as it did before.
   - The `assert(r->texture_bindings[i] != NULL)` in the texScale loop cannot fire. The early return needs `r->pipeline_binding` and an unchanged texture generation, so the full path has already bound textures. The only NULLing of `texture_bindings[]` is in finalize (`texture.c:3273`). The MFP fast path (`draw.c:4148`) already makes the same call under weaker preconditions.
2. **The refreshed block reaches the GPU.** The function sets `r->uniforms_changed` when either block's hash moves. `pgraph_vk_update_descriptor_sets()` (`draw.c:4229`, after `create_pipeline()`) reads that flag at `shaders.c:513` and stages both blocks.
3. **The comment's claim "every other path through here refreshes the block" holds.** The non-early path either calls `pgraph_vk_bind_shaders()`, which ends in `pgraph_vk_update_shader_uniforms()` (`shaders.c:1443`), or calls `pgraph_vk_update_shader_uniforms()` directly (`draw.c:2123`).
4. **Blast radius.** No draw that already refreshed is touched. The SFP does not reach `create_pipeline()`. `create_clear_pipeline()` is a separate function. The only new work is a recompute plus hash on early hits, which the probe counted on 2 of 99 discs. The two device soaks show gfps equal between the arms (29 = 29 on both devices).
5. **Registrations.** The desktop registrations carry the hand-queue `title`, which the PR body discloses. The `aadma` leg has a numeric `expect`, an `expect_counts` and a `must_not_move` list, and it names its nondeterminism before measuring. The body's `Files:` line lists all seven changed files.
6. **CI** is green on this head: build ×2 and check.

## Findings

**LOW-1: the PR is `CONFLICTING` against current master, but only in `docs/testing/nv2a_index.json`.**
- `git merge-tree origin/master fb5879944b` conflicts on the index alone.
- `fold.sh` regenerates the index and never merges it (`fold.sh:66-68`), so fold should resolve this itself. Nothing for the lane to do.
- Failure scenario: none in the code. At worst the fold job hands the PR back for a merge.

**LOW-2: the change is hardening only on current master, as the PR says.**
- #366 bumps `shader_state_gen` on an AA-mode change, so GPUAA's triangle no longer takes the early return. The fix is measured to move 0 captures on the stock suite at this head.
- This is not a defect. It does mean no golden now exercises the new line, and a later regression that removed it would show on no suite.
- Failure scenario: a future edit drops the call and CI stays green. A regression test would need a draw that changes only an inline attribute while every generation holds. Not asked for in this PR.

No failure scenario was found in which the new line gives wrong output, a crash, or unsafety.
