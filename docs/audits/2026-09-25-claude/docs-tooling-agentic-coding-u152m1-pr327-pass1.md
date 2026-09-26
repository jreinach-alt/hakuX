# Audit pass 1 -- PR #327 (lane.remote, #274): Vulkan refuses surface-to-texture at a mismatched linear pitch

Auditor: `[job.cloud]`, 2026-09-25. Head audited: `de292d14`.
Diff against `origin/master`: `hw/xbox/nv2a/pgraph/vk/texture.c` (+19),
`docs/testing/nv2a_index.json` (line-number regeneration), two prediction
files, and `docs/lanes/remote/NOTES.md`.

(The brief named `...-pass1.md` for this file. That path already holds the
PR #247 audit from earlier today, so this one uses the `-pr<n>-` form of
`-pr256-` and `-pr269-` instead of overwriting it.)

**Result: no HIGH, no MEDIUM, one LOW.** The LOW is a residual outside the
diff and pass 2 has nothing in the diff to verify, so the recommendation is
`fold-ready`.

## What was checked

1. **The condition is GL's, and does what it says.**
   `if (!surface->swizzle && surface->pitch != shape->pitch) return false;` is
   GL's own clause from `pgraph_gl_check_surface_to_texture_compatibility()`
   (`gl/surface.c:1487`). Both sides are in guest units:
   `SurfaceBinding.pitch` is copied from `pg->surface_color.pitch`
   (`pgraph.c:2534`), and `TextureShape.pitch` from the register
   (`texture.c:455`). Neither is scaled by `surface_scale`, so the test holds at
   any scale.
2. **It adds no refusal the old code did not already make, except for pitch.**
   - A linear surface over a swizzled texture was already refused by the
     layout test below it (`surface->swizzle == linear`). So the only new
     refusals are linear over linear with differing pitch, and the pitch of a
     swizzled texture shape never decides anything.
   - A swizzled surface skips the test (#109: it has no pitch).
   - Zeta keeps its early `return true`. This is deliberate, stated in the
     comment, and listed under Not covered.
3. **What a refusal does at the call sites.** There are two:
   - **The active surface (`texture.c:1806`).** On refusal, a `draw_dirty`
     surface is downloaded to VRAM at its own pitch
     (`pgraph_vk_surface_download_if_dirty`), and the texture then uploads from
     VRAM at the texture's pitch. That is the hardware's view of the memory, so
     it is the right fallback.
   - **The shelved surface (`texture.c:1856`).** A refused shelved surface
     falls through to `pgraph_vk_download_surfaces_in_range_if_dirty`, which
     covers it by address range.

   Neither path leaves the texture reading stale VRAM.
4. **Refs.** `b_ref` `2c94b7ed` is the fix commit and an ancestor of the head.
   `a_ref` `9eaae944` is on master. The diff from `2c94b7ed` to the head
   touches no `hw/`. PR #327 is `MERGEABLE`/`CLEAN`, and build and check are
   green on `de292d14`.
5. **The FAIL is reported as a FAIL.** `remote-274-vk-s2t-pitch.json` failed on
   the `GPUAAWriteAfterCPUWrite` leg, and the pre-registration named exactly
   that outcome in advance. The PR does not reinterpret it. Its follow-up
   two-test discs attribute the 2,540 px carry-over to the FBSurface tests,
   because Center1 then GPUAA reads 134 on master. That explanation is
   consistent with the code: this change cannot reach a test that never binds a
   linear surface at a mismatched pitch. The surf1 guard (236 captures, `*`
   must-not-move) PASSED, which covers #88's and #109's guards.
6. **Index.** Mechanical line moves for `vk/texture.c`, plus the `vsh-ff.c`
   moves the PR attributes to #263. The suite, site and symbol counts are
   unchanged (104 / 2845 / 951). The regeneration is the branch's `f8a4af20`,
   and GitHub reports the PR as mergeable against the current master.

## Findings

### LOW-1 -- the carry-over mechanism that spread Center1's error is untouched

The NOTES say CenterCorner2 and SquareOffset4 never take the shortcut: their
AA-scaled surfaces fail the extent test. They still read 78,496 in sequence
"because they reuse the binding it leaves". The fix removes the one known
*producer* of a wrong surface-to-texture binding. It does not touch the path by
which a binding made while the shortcut was taken is picked up by a later bind
that did not take it: `tex_binding_cache` / `texture_cache` keyed on
`key_hash`, where `surface_to_texture` itself is not in the key, only
downstream effects like `expected_fmt`.

**Failure scenario, outside this diff.**
1. A legitimate surface-to-texture binding is made: the pitch matches.
2. The surface is later retargeted, or the CPU rewrites the memory.
3. A later texture at the same address and shape does not take the shortcut.
4. That texture can hit the same cached binding and sample the old surface
   image, not VRAM.

`GPUAAWriteAfterCPUWrite`'s FBSurface carry-over, which is Vulkan-only, is
plausibly this mechanism with a different producer. Not a defect of this PR.
Recommend that the board give the carry-over (already listed under the PR's Not
covered) an issue of its own. It should name the cache reuse, not the producer,
as the thing to find.

## Routing

No HIGH or MEDIUM. LOW-1 is a residual outside the diff, so pass 2 would have
no scenario in the diff to re-check. The label goes from `needs-audit-1` to
`fold-ready`.
