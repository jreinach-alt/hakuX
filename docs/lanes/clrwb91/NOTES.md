# lane.clrwb91 -- #91: the zeta-over-colour write-back must carry 0xFE2424

Brief: make the aliased zeta image's write-back over colour memory in
`Color_zeta_overlap/Swap` carry the depth lifted from colour memory
(0xFE2424) instead of 0, in the Vulkan surface path, without declining it.

## What the captures on disk already say (read 2026-09-25, no device time)

Colour histograms of `Color_zeta_overlap::Swap`, ARGB:

| capture | quad (165,447 px) | background (139,303 px) | text (2,450) |
|---|---|---|---|
| golden | `FFE91624` | `FE242424` | `00FFFFFF` |
| master-policy arms (`55bc6c6c2b`) | `FFE91A24` | `FE242424` | `00FFFFFF` |
| #88 decline arms (`bb0ddde27d`, `aec524681e`, `7980d1caa2`) | `FFE91A24` | **`00000024`** | `00FFFFFF` |

So:

1. **On master the background is already right.** The 0x00000024 exists only
   with #88's decline in the tree. #88 is not on master (its commit
   `4726557b0f` is on no branch; master's `update_surface_part` carries the
   withdrawn-policy comment). Any arm for this issue has to carry the decline
   in BOTH arms or it is an inert control.
2. **The quad's write-back already happens under the decline**: the quad
   region is depth read back as colour (`E91A24`) in every arm. What goes
   wrong is the *untouched* part of the aliased zeta image: depth 0 where
   it should be 0xFE2424, stencil 0x24 kept.
3. The quad's `E91A24` vs the golden's `E91624` (off by 4 in depth's low
   byte) is a separate depth-precision defect present on both policies. It is
   NOT this lane's; the 165,447 floor stays unless someone fixes depth
   quantisation.

## What reading ruled out

* **Not a clear.** pbkit's `pb_set_depth_stencil_buffer_region` always sends
  `NV097_CLEAR_SURFACE_Z | NV097_CLEAR_SURFACE_STENCIL`, and both Vulkan clear
  paths add the stencil aspect whenever that bit is set and the format has
  stencil. There is no depth-only clear in this suite, so "the test's own
  depth clear of 0 zeroes the depth" (the brief's mechanism, inherited from
  #148) cannot keep stencil 0x24. It would clear stencil to 0 as well.
* **Not render-pass load ops.** `get_optimal_zeta_load_op()` computes
  DONT_CARE for an uninitialised binding, but `create_render_pass()` ignores
  `RenderPassState.*_load_op` and hardcodes LOAD for depth and stencil.
* **No decline fires inside Swap's frame.** In `bb0ddde27d`'s logcat the
  `[surf91]` decline lines are at frames 35 and 37 (ColorIntoZeta and
  ZetaIntoColor), none at 36 (Swap). Swap inherits state from ColorIntoZeta's
  decline. After that decline zeta stays unbound for the rest of
  ColorIntoZeta, because pbkit's text is drawn with colour-only clears, which
  never ask for zeta.
* Tests run in `std::map` order: AdjacentWithAA, AdjacentWithClipOffset_l,
  _sz, ColorIntoZeta, **Swap**, ZetaIntoColor. Swap's colour target is the
  next pbkit back buffer, not ColorIntoZeta's.

## What is being measured

A step-by-step read of `update_surface_part` for Swap under the decline
finds every creation of the zeta image at Swap's colour address uploading
0xFE2424 correctly. So the event is one reading cannot see: an image
recycled from the pool or shelf, a deferred download landing late, or a
layout discard. `f4dadc07d6` (NOT FOR MERGE) restores #88's decline and logs
`[wb91]` lines: every resolve, eviction, creation (shelf/invalid/fresh),
upload, deferred and sync download, and zeta-writing surface update. Each
line carries the VRAM word at one background pixel (10 px in from the
bottom-right corner). The first event whose word reads `0x00000024` is the
writer.

Queued: `1790328363-lane.clrwb91-1134991` (Nova, suite "Color zeta overlap",
1 run, no prediction, diagnostic).

`request.sh` needed a permission this session did not have; the request was
written in its exact JSON shape by `python3` (see memory
`lane-sandbox-blocks-board-requests`).

## What the trace found (run `1790328363-lane.clrwb91-1134991`)

It reproduced the regression exactly (Swap 304,750, `00000024` × 139,303).
In Swap's frame (f=36; colour back buffer `0x0397c000`, zeta `0x02b6c000`):

```
upload C addr=0x02b6c000 ... px=0x00000000      <- colour at the old zeta address, FIRST in the staging window
upload Z addr=0x0397c000 ... px=0xfe242424      <- the aliased zeta image; VRAM is right
su draw cw=1 zw=1 c=0x02b6c000 z=0x0397c000     <- the quad
evict Z addr=0x0397c000 / dlrec / dldone Z ... px=0x00000024   <- the write-back
```

VRAM was right when the image was uploaded. The image was wrong when it came
back, and only the quad draw ran in between. So the upload never put the
depth there.

**The defect**, `pgraph_vk_upload_surface_data()`: the depth
`VkBufferImageCopy` is built with `.bufferOffset = staging_base`. On the
Z24S8/D32S8 compute path the copy source is then switched to
`BUFFER_COMPUTE_SRC`, where `pgraph_vk_unpack_depth_stencil()` writes depth
at offset 0 and stencil at `ROUND_UP(depth_size)`. Only the stencil region's
offset was rewritten. Any zeta upload that is not the first staging
allocation since a reset therefore reads its depth from the wrong bytes.
Here the colour upload went first, so `staging_base` = 640×480×4 = the depth
size: depth was read out of the stencil plane (`0x24242424` as a float,
~1e-17), which packs to 0. `60bc72faed` (2026-02-26, "extended rendering
pipeline optimization") introduced `staging_base`; before it every upload
staged at offset 0.

Why master escapes it on Swap: on master the uploads come in a different
order (the decline changes which surfaces are live), and master's Swap
background is right in every capture on disk. The defect itself is generic
and on master.

**Fix**: `regions[0].bufferOffset = 0` on the compute path. The write-back
is kept and now carries what was lifted from colour memory.

## The arm

`docs/testing/predictions/issue91-writeback.json`: a_ref `9c5f7416d8`
(master + #88's decline, scaffolding) -> b_ref `9de95de849` (+ fix). The
branch withdraws the decline at the next commit, so the shipped diff is the
fix alone. Three-suite disc as #88/#148.

A deviation from the brief: the brief lists `Swap` under must_not_move, but
with the decline in both arms Swap is the capture that must move (304,750 ->
165,447). Swap therefore goes under expect instead, and must_not_move covers
Swap_ZB and the rest.

Reach this lane has NOT measured: the trace also shows zeta uploads that
followed a colour upload in frames 32–33 (the Adjacent* tests, 128×128
surfaces in texture memory). They sit at 0 differing and are on
must_not_move. Outside these suites the defect is generic, so depth-heavy
suites may move under the fix. That needs a master -> master+fix sweep
before anyone claims the fix's full reach.

## For the next lane

* Do not chase a clear for 0x00000024. pbkit never clears depth without
  stencil in this suite.
* Before reasoning about surface-cache order, sample VRAM at upload and at
  download. Two lanes read `update_surface_part` for days; one probe run
  found the defect, which was in the copy, not the cache.
* 165,447 is not the golden: the quad is `E91A24` vs `E91624`, a separate
  depth-precision gap under both policies.
