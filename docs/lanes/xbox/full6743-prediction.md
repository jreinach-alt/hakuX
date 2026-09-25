# A complete silicon reference set at the pinned tests commit, registered before the run

**Status: PRE-REGISTERED.** This was committed and pushed before the XBE ran
the full disc anywhere. It is idle-time console work, at the owner's request.
The host welcomed more reference captures after #262.

## Why

The NV2A index pins nxdk_pgraph_tests `6743b6a` (2026-09-20). Nothing we can
score against was captured from that commit:

- the published goldens date from 2026-08-11;
- the 2026-09-19 calibration ran the older stock disc (built 2026-09-07).

Since 2026-08-11 upstream has changed most test sources: refactors (GPU M2M
copies, combiners replacing pixel-shader code), new tests (alpha X modes,
fog, surface as vertex array) and changed tests (the Clear checkerboard). So
some goldens are likely stale for the index's own tests tree.

One console run of the whole `6743b6a` disc does three things:
- it dates the stale goldens (silicon at `6743b6a` against the 1.0 goldens,
  where the calibration showed only 5 of 3,379 captures differing on
  unchanged tests);
- it gives every `6743b6a` test a silicon reference;
- through the Thor dry run's captures, it gives a first hakuX comparison
  for all of them, as #262 did for one suite.

## What runs

- **XBE:** pristine `6743b6a`, sha256 `8612681afa58…`. This is the same binary
  as PR #261, and its Thor dry run of four suites was clean.
- **Suites:** all 102 in the index, excluding:
  - `PVIDEO`, which writes `NV_PMC_ENABLE` directly and waits for the power
    switch;
  - `Clipping precision`, which is interactive-only and saves nothing;
  - `Texture render target::RenderTextureLoop` alone, excluded as in the
    calibration. It disables the texture stage for the tests after it.
- **Emulator dry run:** on the Thor through the dispatcher, in three requests
  so that each stays under the 1800 s disc timeout:
  - part 1 (1 suites): Blend tests
  - part 2 (51 suites): Depth buffer, Shade model, W param, Attrib carryover, Window clip, Texgen with texture matrix, Fog gen, Vertex shader rounding tests, Bump env lum, Fog coord vec4, Bump map, Depth buffer fixed function, ZPass pixel count, Blend surface, ZMinMaxControl, Lighting normals, Point params, Material alpha, Point size, Texture signed component tests, Color key, Specular back, 2D Lines, Attrib float, Antialiasing tests, Texture Matrix, Surface format, Stencil, Texture perspective, Color zeta overlap, Fog inf coord, Fog vsh, Stipple tests, Swath width, Texgen, High vertex count, Texture anisotropy, Texture BRDF, Attrib setter, Edge flag, Texture 3D as 2D, Texture palette, Vertex shader independence tests, Color mask blend, Degenerate begin end, Inline array size mismatch, Null surface, Surface pitch, Texture border color, TextureWrapMode, Color Zeta Disable
  - part 3 (50 suites): Texture shadow comparator, W buffering, 3D primitive, Fog exceptional value, Texture cubemap, Line width, Fog param, Surface clip, Image blit, Texture render target, Depth Clamp, Texture format, Front face, Lighting control, Vertex shader swizzle tests, Material color source, Lighting spotlight, Specular, Clear, Volume texture, Texture border, Alpha func, Texture DXT, Viewport, Fog carryover, Lighting accumulation, Combiner, Pixel shader, Stencil func, SetVertexData, Fog, Fog planar vsh, Material color, Surface as vertex array, Texture 2D as cubemap, Overlapping draw modes, DMA corruption around surfaces, Lighting range, Texture Framebuffer Blit, Smoothing control, Texture CPU Update, Texture perspective enable, Zero stride, Context switch, Depth function, Lighting Two Sided, Point sprite, Texture LOD Bias, Texture render update in place, Weight setter
- **Console run:** then one run via `tools/xbox/pgraph_run.py`, with the test
  list taken from the dry runs' `Starting` lines. Shutdown-on-completion off,
  network off, progress log on.

## Legs

- **Dry run (safety):** all three parts complete, with no crash signal.
- **C1 (instrument):** `Alpha func` on the console is 16/16 bit-identical to
  the goldens. The console also re-reproduces PR #261's `Fog planar vsh` and
  `Surface as vertex array` captures bit for bit.
- **Completion:** the console log says "Testing completed normally", and the
  console hands back to the dashboard.
- **Reported, not predicted:**
  - per suite, the captures that are identical to the published golden,
    differ from it, or have none;
  - where the stock-disc calibration has the same test, whether that
    capture differs too. A test that differs from both the golden and the
    calibration changed upstream; one that differs only from the golden is
    1.0-against-1.1 silicon or a changed test;
  - the first hakuX comparison, which is not an A/B.

The captures stay on the host under
`~/hakux-work/hardware/runs/2026-09-25-full6743/`.
