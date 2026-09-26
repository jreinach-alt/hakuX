# lane.aasample -- #286 class A: our CENTER_CORNER_2 path is not transparent

**Outcome.** The mechanism is measured on silicon, not assumed from the mode
name. The fix is a half-AA-pixel x offset on the host viewport. Priced over
the 120 AA captures, it is **+258,221 structural px net**. The 48 inert
captures go from 517,872 px moved to 24. The helper is in `pgraph.h` (this
lane's file). **It does nothing until two viewport initialisers in
`vk/draw.c` call it.** That file is lane.vtxarr262's (PR #264), so the hunk is
in `draw-c-viewport.patch` and the grant is requested. There is no arm yet: an
arm on the `pgraph.h` commit alone would measure a no-op.

## Data, dated

| set | where | date |
|---|---|---|
| goldens | `/home/justin/goldens/results/{3D_primitive,Antialiasing_tests}` | abaire `6e159f1532` (2026-08-11) |
| ours | `dispatch/results/0-a-now-8e683b3a26-00{2,4}-*` | ref `8e683b3a26`, Thor, 2026-09-25 |

These are the captures cloud-286 scored. Their 517,872 px "ours moved" figure
reproduces to the pixel.

## 1. Mechanism, re-derived

**Silicon's sample layout** (`cc2_samples.py`). `Antialiasing_tests/
FBSurfaceWithCenterCorner2` draws a flat diamond into a CC2 surface and
displays the raw 1280-px rows at a 640-px pitch. Un-interleaving the rows
gives the AA surface. The diamond's offset was calibrated on
`FBSurfaceWithCenter1` (0 mismatches at offset 0). I then fitted each column
parity's sample over a quarter-pixel grid (131,200 px per parity):

| AA column | silicon best | mismatched | runner-up | ours best | mismatched |
|---|---|---:|---|---|---:|
| 2x+1 | **(x+0.5, y+0.5)**, the pixel centre | **0** | 96 | (x+0.75, y+0.5) | 0 |
| 2x | **(x, y)**, the corner | 16 | 64 | (x+0.25, y+0.5) | 0 |

So `CENTER_CORNER_2` means what its name says, and the centre is the **odd**
column. Ours matches NOTES' model exactly: `pgraph_apply_anti_aliasing_factor`
only doubles the width, so column k is shaded at k/2 + 0.25.

**The resolve tie** (`tiedir.py`). The guest's resolve (`three_d_primitive_
tests.cpp:1023-1059`) point-samples u = 2x+1. That is a texel tie between 2x
and 2x+1. Our capture says which texel we take. Along a horizontal gradient,
ours(X) - ours(P) has the gradient's sign on **505,476 channel-px and the
opposite sign on 10,768**. The fitted shift is **+0.239 guest px**, which is
0.25 less 8-bit rounding. So our resolve takes **2x+1**, consistent with
`texelTieBias` rounding u ties up (#282: u ties round up on 99.8% of silicon's
pixels too). Silicon's own X-P difference is 0 on both counts. The instrument
can see a shift, and silicon has none.

Silicon's resolve is transparent either way, because the texel it picks holds
the centre sample. Ours picks 2x+1, which holds x+0.75.

## 2. The change, and every consumer of the AA factor

Shift the host viewport by +0.5 AA pixel in x for CC2 (times
`surface_scale_factor`). Column 2x+1 is then shaded at exactly (x+0.5,
y+0.5), and column 2x at (x, y+0.5). Silicon's corner is at y, not y+0.5. That
needs a per-column sample offset, which a viewport cannot express. It is the
remaining 272 px of `FBSurfaceWithCenterCorner2`, below.

For a guest that resolves with a bilinear tap at u = 2x+1 (the usual game
resolve), the mean sample is (x+0.25, y+0.5) after the change and
(x+0.25, y+0.25) on silicon. Today it is (x+0.5, y+0.5). The change is right in
x for any resolve, not just this test's point sample.

| consumer | file:line | holder | changes? |
|---|---|---|---|
| `pgraph_anti_aliasing_viewport_offset_x` (new) | `pgraph/pgraph.h:609` | **lane.aasample** | added, unused until the next two rows |
| Vulkan viewport, pipeline bind | `vk/draw.c:4496` | lane.vtxarr262 (PR #264) | **yes: `.x = offset * surface_scale_factor`** |
| Vulkan viewport, reorder-window snapshot | `vk/draw.c:5621` (replayed at `:5992`) | lane.vtxarr262 | **yes, same line; the two must agree** |
| vertex `surfaceSize` (guest to NDC scale) | `glsl/vsh.c:1160` | lane.wparam223 | no: the width stays 640, and the offset is the viewport's |
| geometry-stage line NDC scale | `vk/draw.c:2765` | lane.vtxarr262 | no: widening is in guest px before the viewport, so the shift applies to it too |
| scissor (x2, reorder x2) | `vk/draw.c:4512, 5630, 7058, 7143` | lane.vtxarr262 | no: integer AA-px rectangle, and the guest pixel edge is still at 2x |
| window clip / `surfaceScale` | `glsl/psh.c:4033, 4052` | lane.wbufdepth24 | no: `gl_FragCoord` is per AA pixel and unchanged |
| surface allocation | `vk/surface.c:3399` | lane.fix311 | no: size only |
| clear | `vkCmdClearAttachments` rects | -- | no: clears ignore the viewport |
| resolve | the guest's own textured quad | -- | no: it samples the AA surface as a texture, and the fix is in what is written there |
| GL renderer viewport | `gl/draw.c:689` | [free] or unclaimed | **not changed**: `glViewport` takes ints, and GL is not the Android renderer; it would need `glViewportIndexedf`. Named, not done. |

`SQUARE_OFFSET_4` is left at 0. No capture on disk shows its sample layout.

## 3. Priced (`price.py`, all 120 AA captures)

Fixed ours(X) = ours(P) below the label band. The +0.5 shift makes column
2x+1 the non-AA sample for triangles, and for lines too: the geometry stage
emits every line as a filled parallelogram in guest px (`glsl/geom.c:67`,
`vk/draw.c:2511`). We emulate no smoothing. The exception is **points**,
below. Structural means |d| > 1 in any colour channel, against golden(X).

| primitive (x4 paths, 3 flags) | struct now | struct fixed | net | differing now | differing fixed |
|---|---:|---:|---:|---:|---:|
| TriFan | 175,560 | 65,068 | **110,492** | 414,708 | 360,732 |
| TriStrip | 121,264 | 52,392 | **68,872** | 531,240 | 381,528 |
| QuadStrip | 127,956 | 71,816 | **56,140** | 880,588 | 835,736 |
| Polygon | 40,296 | 13,216 | **27,080** | 474,500 | 435,216 |
| Triangles | 27,896 | 12,148 | **15,748** | 121,356 | 109,412 |
| Points | 84 | 24 | 60 | 84 | 24 |
| Lines | 21,013 | 21,369 | -356 | 21,316 | 21,812 |
| LineLoop | 39,369 | 39,856 | -487 | 42,263 | 42,947 |
| LineStrip | 34,820 | 35,236 | -416 | 37,144 | 37,680 |
| **Quads** | 17,040 | 35,952 | **-18,912** | 187,280 | 255,396 |
| **all 120** | 605,298 | 347,077 | **+258,221** | 2,710,479 | 2,480,483 |

cloud-286's estimate was ~242,288, counted outside the smoothing footprint
only. This table counts the whole image, so it is not the same cut.

- **Quads' loss, owner #38.** Quads' plain arm is wrong only at exactly
  |d| = 2: 7,600 px over 4 paths, and 0 at |d| > 2. That is the Gouraud floor
  #38 holds. Today's quarter-pixel shift happens to cancel part of it in the
  AA captures. A transparent path gives that back, x3 flags.
- **Lines: -1,259, owner #13.** It is the same give-back: ours(P)'s line error
  shows through.
- The remaining 347,077 is the smoothing footprint (#286's 165,144 ceiling),
  which we do not draw, plus ours(P)'s own error.

**Points leg: 9 of 12, not 12 of 12** (`points.py`). A 1-px Vulkan point is 1
AA pixel, which is half a guest pixel, so it lands on column 2x+1 only when
its fractional x f is in [0.25, 0.75) after the shift. Today the range is
[0.5, 1). The 12 screen positions were computed from the XDK camera and
truncated to 1/16. That model predicts **today's 7 dropped points exactly
(12/12 agree with our capture)**. After the shift, points 3 and 5 (f = 0.0625)
and point 4 (f = 0.9375) still drop. Fixing those needs a point footprint of
2 AA px by 1 guest row. A square Vulkan point cannot express that, so it would
need geometry-stage point expansion. Not done here. It is 24 px.

**Antialiasing_tests** (must-not-move, #274). Only one capture there draws
geometry into a CC2 surface: `FBSurfaceWithCenterCorner2`. The others are
CPU-write or NoOpDraw (degenerate), or `FramebufferNotModifiedBySurfaceState`,
whose triangle is overwritten by a full-screen CPU write. So
`FBSurfaceWithCenterCorner2` **will move**. Coverage mismatches against the
golden over the visible AA rows go from **352 to 272**. Odd columns go from
96 to 0. Even columns go from 256 to 272, which is the corner's y above. The
other 10 must not move. Every other suite: the offset is exactly 0.0f unless
the surface is CC2, so nothing moves.

## 4. The arm, when the grant lands (not registered)

Refs: a_ref = the fold base; b_ref = `pgraph.h` + `draw-c-viewport.patch`
applied.

- must_move: `3D_primitive/TriFan-ls`, `TriStrip-ls`, `QuadStrip-ls`,
  `Polygon-ls`, `Triangles-ls` (inert: falsifier, ours(X) == ours(P) byte-exact
  below the band), and `Antialiasing_tests/FBSurfaceWithCenterCorner2` down.
- must_move up (named loss): `3D_primitive/Quads-ls`, `Quads-ps`,
  `Quads-ls-ps`.
- must_not_move, discriminating: the 40 plain `3D_primitive` captures. A
  viewport change that leaked into CENTER_1 would move every one of them.
  `Antialiasing_tests/FBSurfaceWithCenter1` would move under the same leak.
- Points: 9 of 12 points present in every AA Points capture.
- Read `status` for `unreadable` and the coverage line before reading a
  mover.

## Do not repeat

- Do not put the centre on column 2x. Silicon's centre is 2x+1, and so is the
  texel our resolve picks.
- Do not "fix" this by halving `surfaceSize` or any other scale. A scale
  cannot introduce an offset, and the defect is an offset.
- Do not expect points to come right from the viewport alone. See the
  Points leg above.

## State at end of session 1 (2026-09-25)

Waiting and blocked: CI on the head (aa805678dd or later), and the `vk/draw.c` grant (board request
`board-requests/aasample.md`; asked on PR #264). On a resume with the grant, apply
`draw-c-viewport.patch`, commit and push it, then register the section 4 arm on
those refs. Do not rebase after that.

## Session 2 (2026-09-26, resumed by job.handback)

**Why session 1 did not finish.** It ended correctly, waiting on two things:
CI on the head, and the `vk/draw.c` grant. It left the PR in draft, though. A
draft is skipped by the board and the fold, so nothing could act on it.

**This session.** CI was green on `337f0b5632`. The grant has **not** landed:
`vk/draw.c` is still lane.vtxarr262's on `origin/board`. Master had moved 110
commits and conflicted only in the generated `nv2a_index.json`. I merged
master in (no rebase) and rebuilt the index against the pinned tests tree
(`6743b6ab16`). `check` passes. `draw-c-viewport.patch` still applies cleanly,
and the line numbers in section 2 are unchanged.

The PR is marked ready as an analysis and helper PR with `Prediction: none`.
Folding it is safe: the helper is unused, so no binary changes. The arm in
section 4 is owed by whoever applies `draw-c-viewport.patch`: this lane with
the grant, or lane.vtxarr262 carrying it in PR #264. Register it after that
commit, on those refs.

## Session 3 (2026-09-26, resumed by host: `vk/draw.c` granted at wave 223)

**Why session 2 did not finish the fix.** It could not: `vk/draw.c` was still
lane.vtxarr262's until PR #264 folded (72e479ec59). Session 2 finished what it
held. PR #332 (helper and analysis) was marked ready and folded as b9a1e501f1.

**This session.**

- Merged `origin/master` (18a0ab9387, which contains the #332 fold). The tree
  was identical to master afterwards.
- Applied `draw-c-viewport.patch` unchanged. It applied cleanly at the same
  lines (`vk/draw.c:4497` pipeline bind, `:5624` reorder-window snapshot, which
  is replayed at `vkCmdSetViewport` `:6100`). Commit `57e46af766`.
- Before registering, I re-read the Antialiasing_tests source. It confirms
  section 3's must-not-move reasoning. `CreateSurfaceWithCenterCorner2` only
  NoOpDraws in CC2, then draws into the non-AA framebuffer.
  `FramebufferNotModifiedBySurfaceState` draws a triangle into CC2 at 256 px,
  but a CPU write replaces the displayed framebuffer. The
  `SQUARE_OFFSET_4` tests get offset 0.
- Registered `docs/testing/predictions/aasample-cc2-viewport.json` with
  `register_arm.py` (a_ref 18a0ab9387, b_ref 57e46af766, disc
  `3D primitive` + `Antialiasing tests`). It has 50 must-not-move keys: the 40
  plain 3D_primitive captures and 10 Antialiasing_tests captures. The movers
  and the named Quads/Lines loss are bound in prose, from section 3.
- The viewport is only re-set under `must_bind_pipeline`. A surface change
  begins a new render pass, which forces that path, so the offset follows the
  surface exactly as the width already does.

After this PR folds, `vk/draw.c` passes to lane.remote (#274 GPUAA).
