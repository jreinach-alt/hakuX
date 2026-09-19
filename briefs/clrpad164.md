# lane.clrpad164 -- #164: port the clear half of #59's write side to GL

Base: origin/master (fetch it; your worktree is already on it, at 11ddd94a66
or later -- PR #162 folded there).

Files: hw/xbox/nv2a/pgraph/gl/draw.c. Nothing else without a grant.

Issue: read `gh issue view 164 --comments` in full before writing any code --
it is short and it is the whole investigation, written by lane.remote (the
author of #59/#158's raster-half port) after PR #162 audit pass 1 (finding
M1) split it out.

The mechanism, already named: `gl/draw.c:259` calls `pgraph_get_clear_color()`
raw. Its alpha switch (`pgraph.c:4599`) has no case for the pad formats and
falls through to `default: *a = 1.0f`. `pgraph_vk_get_clear_color()`
(`vk/draw.c:894-907`) already overrides alpha to 0.0 for `PSH_PAD_ALPHA_ZERO`
and 1.0 for `PSH_PAD_ALPHA_ONE`. So on GL an `X8R8G8B8_Z8R8G8B8` surface
holds alpha 1 where `CLEAR_SURFACE` wrote and 0 where the raster drew --
hardware holds 0 in both.

Goal: add `pgraph_gl_get_clear_color()` mirroring the Vulkan function,
called from `gl/draw.c:259` in place of the raw call:

```c
static void pgraph_gl_get_clear_color(PGRAPHState *pg, float rgba[4])
{
    pgraph_get_clear_color(pg, rgba);
    switch (pgraph_glsl_surface_pad_alpha_mode(pg->surface_shape.color_format)) {
    case PSH_PAD_ALPHA_ZERO: rgba[3] = 0.0f; break;
    case PSH_PAD_ALPHA_ONE:  rgba[3] = 1.0f; break;
    default: break;
    }
}
```

Gate it exactly the way the raster half is gated, on
`pgraph_glsl_dual_src_pad_supported()` -- ungated, a GL part without
`GL_ARB_blend_func_extended` would clear to the stamp while drawing without
it, the same inconsistency with the operands swapped. Do not compile this on
GLES, for the same reason the blend path is not (audit H1, `5031a612`).

Before writing the fix, confirm the call site is actually reached for the
pad formats on a live path -- lane.remote's own caution on the issue,
learned from a #62 finding that was a fix to unreachable code. Reading that
`gl/draw.c:259` calls `pgraph_get_clear_color()` raw is not the same as
confirming that code executes for a pad-format clear.

Falsifier: register a prediction against `Clear::SCF_X8R8G8B8_Z8R8G8B8` and
`Clear::SCF_X1R5G5B5_Z1R5G5B5` with absolutes -- the goldens are already
quoted on the issue: 98,342 px differing pre-fix (RGB identical, alpha
255 vs 0) on the 8888 pair, 49,274 px on the 1555 pair, every difference
exactly the bit-15/bit-31 alpha constant. Pin `Blend_surface/*` and
`Surface_format/*` as must-not-move -- #158's nine recovered captures must
read exactly what they read now.

You need a device: the fleet's stock `nxdk_pgraph_tests_xiso.iso` already
carries the `Clear` suite (no NDK build, no disc build needed -- that
caveat on the issue body applied only to lane.remote's own no-device cloud
container, and was corrected there).

Done when: the fix is pushed on `lane/clrpad164` with the prediction
committed, the PR body follows `roles/lane.md`'s template and quotes the
measured before/after on both prediction keys plus the must-not-move set,
and the PR is marked ready.
