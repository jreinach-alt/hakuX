# Audit pass 1 -- PR #343 (claude/docs-tooling-agentic-coding-u152m1, #274)

nv2a/vk: rebuild push infos when a slot's sampled view changes, and drop
retired views from them.

- Head audited: `dad040909e`
- Diff read: `hw/xbox/nv2a/pgraph/vk/texture.c` (+98 -9), four
  `remote-274-vk-push-refresh-*.json` predictions, `nv2a_index.json` regen,
  `docs/lanes/remote/NOTES.md`.
- Readers of the state the diff changes: `vk/shaders.c:534` (push-info
  rebuild), `vk/draw.c:1944` (`check_pipeline_dirty`), `:2078` (early hit),
  `:3890-3957` (SFP push path), `:4080-4139` (MFP push path), `:5288-5551`
  (deferred-queue replay save/restore), `vk/surface.c:2543,2585` (the two
  callers of the retire hook).

**Result: no HIGH, no MEDIUM, three LOW.** Next state `needs-audit-2`.

## What the diff does, checked against its readers

1. **Per-slot view compare in the bind loop.** `slot_view()` returns exactly
   the triple every rebuild site writes (`shaders.c:536-544`,
   `draw.c:3945-3953`, `draw.c:4126-4134`): direct view and direct layout
   while `tex_surface_direct[i]`, else node view with
   `SHADER_READ_ONLY_OPTIMAL`, and the node sampler in both. `prev_view` is
   captured by value before `create_texture()`, so an in-place rebuild of the
   node's image (same node pointer, new `image_view`) is seen. Both exits
   (bound and LRU-exhausted) test it. Correct.
2. **Retire hook scrubs pushed slots.** `pushed` is tested against
   `push_tex_infos[i].imageView`; the hook returns early on
   `VK_NULL_HANDLE`, so an unbuilt (zeroed) info never matches. A matching
   slot is pointed at the dummy (view, sampler, `SHADER_READ_ONLY_OPTIMAL`),
   which is a live, valid descriptor. Destruction of the retired view is
   already deferred to the frame fence (`surface.c` `DeferredSurfaceRelease`),
   so deferred-queue entries that copied `push_tex_infos` into
   `rw_push_tex_infos` before the retirement still name a live view. Correct.
3. **Rebuild request survives `bind_textures()`'s entry reset.** The entry now
   seeds `texture_bindings_changed` from `retired_view_rebuild_pending`, and
   the "Not dirty" early return keeps it. Correct.
4. **Every draw path sees the request.** SFP (`draw.c:3890`) and MFP
   (`draw.c:4080`) both refuse on `pipeline_state_dirty`; the full path's
   early hit (`draw.c:2078`) refuses on it too, and `check_pipeline_dirty`
   also reads `texture_bindings_changed`. For a slot that was pushed but not
   direct, the `texture_state_gen` bump sends the full path through
   `bind_textures()` (`draw.c:2094`). Correct.
5. **Prediction binding.** `git diff c6d14cad bcb7433f -- vk/texture.c` and
   `git diff origin/master...HEAD -- vk/texture.c` have the same patch-id
   (`6bf3083e70`), so the registered b_ref is the code on the head. The four
   arms are hand-queued desktop Vulkan guards (`must_not_move *`); the
   `[job.arms]` SKIPs are the soak-title refusal, and the lane reports all
   four PASS by hand in the PR body and on #274.

## Findings

### LOW-1 -- the pending request is not cleared by the rebuild that satisfies it

`retired_view_rebuild_pending` is cleared only in `pgraph_vk_bind_textures()`.
When the retirement hits a slot that is still direct, the hook does not bump
`texture_state_gen`, so on the next full-path draw `bind_textures()` is not
called (`draw.c:2094`); `shaders.c:534` rebuilds the infos from
`texture_bindings_changed` and clears that flag, but the pending flag stays
set. **Scenario:** a direct slot's surface is retired, the next draw rebuilds
correctly, and several draws later an unrelated register write moves
`texture_state_gen`; `bind_textures()` then starts with
`texture_bindings_changed = true`, which sets `pipeline_state_dirty` and
forces one redundant push-info rebuild (and on the non-push-descriptor path,
`need_new_tex_set` allocates one extra descriptor set). One spurious rebuild
per retirement, correct output. Clearing the pending flag wherever the infos
are rebuilt (the three sites listed above) would make it exact.

### LOW-2 -- the request lives in file-scope state, not in `PGRAPHVkState`

`retired_view_rebuild_pending` is a `static bool` in `texture.c`, while every
flag it cooperates with is a field of `r`. It is not reset by
`pgraph_vk_finalize_textures()`/init, so a renderer teardown with a pending
request carries it into the next renderer instance. **Scenario:** a surface
retires, then the renderer is finalized before any bind; the next instance's
first `bind_textures()` starts with `texture_bindings_changed = true`. That
first bind rebuilds everything anyway (NULL bindings are dirty), so the cost
is nil. Single-instance (`g_nv2a`), so no cross-instance race. Quality only:
a field in `PGRAPHVkState` would sit with its siblings and be reset with them.

### LOW-3 -- the replay window restores two of the three request channels

`draw.c:5288-5551` saves `pipeline_state_dirty` and `texture_state_gen`,
zeroes/rewinds them for the deferred-queue replay, and restores the saved
values at `flush_dq_restore`. If `pgraph_vk_texture_surface_view_retired()`
ran inside that window, its `pipeline_state_dirty = true` and its
`texture_state_gen++` would be overwritten by the restore. **Scenario, not
shown reachable:** a retirement inside replay on a pushed-but-not-direct slot
leaves only `texture_bindings_changed` and the pending flag; the SFP path
(`draw.c:3890`) reads neither, so it would push the dummy for that slot
(a wrong texture for some draws, not a use-after-free, because the hook
already scrubbed the view). I found no path from the replay body to
`destroy_surface_image()` or `migrate_surface_image()`, so this is a note
on the comment's "three ways" claim, not a defect.

## Not findings (checked)

- A direct slot retired and rebuilt via `shaders.c:534` without a
  `bind_textures()` samples its node's own image, not the surface, until the
  slot's `texture_dirty` is consumed. This is identical to master (the old
  hook did the same for direct slots) and outside the diff.
- `slot_view()` on a NULL binding returns the null triple; the bind loop never
  leaves a NULL binding after either exit, so the post-compare cannot
  dereference NULL.

## Process note (not a severity)

GitHub reports the PR as `CONFLICTING` against master at this head; CI is green
on the head. The fold job cannot fold it until the lane merges master again.
