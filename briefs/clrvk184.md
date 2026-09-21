# lane.clrvk184 -- issue #184

Base: master @ 28531197b6. Files: hw/xbox/nv2a/pgraph/vk/texture.c,
hw/xbox/nv2a/pgraph/vk/surface-compute.c, docs/lanes/clrvk184/NOTES.md.

## Goal

#184: on the `Clear` suite, Vulkan's surface-format captures are worse than
GL on four formats, two of which GL gets pixel-exact. `Clear` is in none of
the six suites `[job.arms]` scores and is not in the `iso_surf1` disc every
whole-disc number elsewhere on the board comes from -- it has never been
measured by anything until #184 filed it as a by-product of #60's X1A7 work.
This is an ANALYSIS lane first: land the instrumentation and a named
mechanism before touching any renderer code.

## What's already known (from #60's own investigation, not yet verified for
Vulkan's Clear path specifically)

`#60`'s comment on `[lane.remote]`'s territory found the X1A7 pair
(`SCF_X1A7R8G8B8_Z1A7R8G8B8` / `_O1A7R8G8B8`) reading far worse on Vulkan
than GL (81,936/98,208 wrong px vs GL's 65,568/65,472), and floated -- without
instrumenting or claiming it -- that the shape is consistent with **one
texture cache key reused across the suite's six `NV097_CLEAR_SURFACE`
calls**, keyed at `GetTextureMemoryForStage(0)` in `vk/texture.c`. Four
distinct golden swatch colours coming out as one repeated colour
(`bacada`) with alpha forced to 0 is the signature to check for.

## Falsifier

Build `docs/testing/x1a7_clear_bytes.py`-style instrumentation (that script
already exists on master from #60/#183 for the X1A7 byte model; extend it or
add a sibling) that runs the `Clear` suite's `SCF_*` and `SFC_*` captures
(32 total, both renderers) against the goldens and reports, per capture:
differing px, and whether the output byte pattern matches a stale/aliased
cache entry from an earlier clear in the same run rather than the format
under test. If the cache-key theory is right, forcing a fresh texture
object per clear (or invalidating `GetTextureMemoryForStage(0)`'s entry
between `NV097_CLEAR_SURFACE` calls) should collapse the affected captures
toward GL's numbers; if it's inert, say so and name what the byte pattern
actually shows instead.

## Done when

- Instrument exists, runs with no device, and reports per-capture diffs for
  all `Clear` suite captures on both renderers against the goldens.
- The cache-key mechanism is either confirmed (with the specific call site
  and a measured before/after) or refuted (with what the data shows
  instead) -- do not leave it as an unverified guess repeated a third time.
- If a fix is confident and measured offline, propose it; if not, stop at
  the mechanism and hand back to the board with the numbers, same as #60's
  own lane did for the sibling X1A7 finding.
- No device time needed for this stage.
