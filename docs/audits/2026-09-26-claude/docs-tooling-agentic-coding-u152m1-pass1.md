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

---

# Audit pass 1: PR #389 (claude/docs-tooling-agentic-coding-u152m1), #274 SFP guard

Head audited: `a6a47f4e70`, compared with `origin/master` (which is in its
ancestry). Against master, `hw/` differs by one 7-line hunk in
`hw/xbox/nv2a/pgraph/vk/draw.c` `begin_pre_draw_inner()`. The rest of the
diff is six prediction files and the regenerated `nv2a_index.json`.

**Verdict: no HIGH, no MEDIUM, three LOW.** Next state: `needs-audit-2`.

## What was checked

1. **Every writer of the four flags only sets them on a real change.**
   The writers are `pgraph.c`, the fixed-function setters at 3212-4058,
   `SET_TRANSFORM_CONSTANT` at 3554, the state-program constant writes at
   4487, and `rdi.c:62`. Each one is either `|= (parameter != old)` or sits
   behind an inequality. The one unconditional set is
   `pgraph.c:5037`, after a vertex-state program runs, and a `v0` hash that
   has not changed returns before it. So no path raises a flag on every
   draw, and the guard cannot turn the SFP off for good. The soaks agree:
   all three legs PASS on both titles and both handhelds (lane.remote,
   17:19Z).
2. **A missed draw clears the flags.** A draw that misses the SFP goes to the
   MFP or to the full path. The MFP (`draw.c:4155`) calls
   `pgraph_vk_update_shader_uniforms()` without a condition. The full path
   reaches it through `create_pipeline()`: from the early hit (`draw.c:2093`),
   from the `else` branch at 2123, or from `pgraph_vk_bind_shaders()`
   (`shaders.c:1443`). When the refresh runs, `shaders.c:1363-1374` sets
   `uniforms_changed` and clears all four flags. So after one missed draw
   the SFP is open again, as the PR says.
3. **Where the test sits.** It comes after `r->uniforms_changed` and before
   the descriptor, generation and prim-mode tests. Every test in that chain
   only sets `sfp_ok = false`, so adding one more cannot let a draw through
   that the old chain refused.
4. **The render thread.** `render_thread.c:77-87` copies the flags into a
   snapshot. Nothing outside that file reads the snapshot back, so the
   guard reads the live `pg`, which is also the struct the refresh clears.
5. **Prediction files.** All six parse. `a_ref` `6c25a829ef` and `b_ref`
   `1d9c3e4c0f` are both ancestors of the head. The four desktop files have
   empty `expect` and `must_not_move: ["*"]`, and they are hand-queued;
   `[job.arms]` SKIPPED them as designed. The PR body reports all four PASS
   on the registered refs and on both merged trees.

## Findings

### LOW 1: the new miss is counted in `sfp_miss_uniforms`, which it shares with `r->uniforms_changed`

`draw.c:3905`. **Scenario:** someone prices the guard from an `OPT_STAT`
dump on a title, for example to see whether it is what keeps a scene off the
SFP. The count mixes the old cause, where a refresh detected a change, with
the new one, where a setter ran and nothing has refreshed yet. The two
cannot be separated without a rebuild. This is observability only, with no
behaviour at stake. A separate counter such as `sfp_miss_ff_dirty` would
split them.

### LOW 2: the comment says a missed draw's path "refreshes the block", but the refresh can return early

`draw.c:3899-3903` against `shaders.c:1313-1322`. **Scenario:** with async
compile on, the bound shader is not `ready` yet. `pgraph_vk_update_shader_uniforms()`
returns before it clears anything, and the full path then skips the draw
(`draws_skipped_pending`). The flags stay set, so later draws keep missing
the SFP until the shader is ready. That is the safe direction, and the
behaviour is correct. But the comment's promise that a miss clears the
flags does not hold on this path, and a reader who relies on it when
reasoning about SFP hit rates will be misled. One clause naming the
async-pending case would fix it.

### LOW 3: no scored capture can detect the guard being reverted

**Scenario:** a later change drops or reorders this test. The desktop
goldens stay byte-identical, because the PR's own probe shows that no test
draw takes the SFP on these discs: with `skip_boot_anim` there are zero SFP
hits, and every hit falls in the boot animation. The soaks measure frame
rate only. So the defect #274 names could return without any golden or arm
moving. The PR says this under "Not covered". I record it here so that the
gap has a home: a coverage gap, not a defect in this diff.

## Not findings

- `GPUAAWriteAfterCPUWrite`'s white 2×2 block, seen on B only, in 2 of 29
  runs. The PR's third probe build puts every B SFP hit in frames 1-7, and
  no hit in either arm falls after frame 40. So during the tests B runs A's
  code, and the guard cannot be what draws the block. This is a timing race
  for `KNOWN_UNSTABLE`, as the PR says, not a finding against the diff.
- The index regeneration is tool output (`nv2a index: regenerate after
  folding #389`). I did not hand-review it.
