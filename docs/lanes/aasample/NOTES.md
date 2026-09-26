# lane.aasample -- #286 class A: our CENTER_CORNER_2 path is not transparent

**Outcome.** The mechanism is measured on silicon, not assumed from the mode
name. The fix is a half-AA-pixel x shift of every vertex on a CC2 surface.
Priced over the 120 AA captures, it is **+258,221 structural px net**, and the
viewport form of it measured -258,224 (session 4). **Since the 2026-09-26
remediation the shift is applied in clip space** (`glsl/vsh.c`
`gl_Position`, `glsl/geom.c` `line_clip`), not by moving the Vulkan viewport:
the viewport form moved the clip volume's left edge off the surface and lost
host column 0 at `surface_scale >= 2` (audit pass 1, MEDIUM-1). See the
remediation section at the end; sections 2-4 below it describe the viewport
form as it was measured.

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

**This table is the remediated head's (2026-09-26).** The viewport form it
replaced is described in the sessions below; its two `vk/draw.c` hunks are
gone.

| consumer | file:line | changes? |
|---|---|---|
| `pgraph_anti_aliasing_sample_offset_x` | `pgraph/pgraph.h:619` | **yes: now 0.25 guest px (half an AA px) for CC2, 0 otherwise; renamed from `_viewport_offset_x`** |
| `VshState.aa_offset_x`, set per draw | `glsl/vsh.h:83`, `glsl/vsh.c:116` | **added: part of the shader key** |
| vertex `gl_Position` (Vulkan) | `glsl/vsh.c:1012` | **yes: `+= 2 * aa_offset_x / surfaceSize.x * w`; no text emitted at 0** |
| `GeomState.aa_offset_x`, wide-line rebuild | `glsl/geom.h:36`, `glsl/geom.c:48`, `line_clip` `:636`, `line_clip_lerp` `:685` | **yes: `aaScreen(screen)` adds the same 0.25 in guest px, because the footprint is rebuilt from `v_vtxPos`, which is taken before the shift** |
| shader dirty check | `glsl/shaders.c:128` | **yes: compares the offset** |
| `SET_SURFACE_FORMAT` | `pgraph.c:2517` | **yes: an AA-mode change bumps `shader_state_gen`, as zeta's does, so the cached-state path in `pgraph_vk_bind_shaders()` cannot reuse a stale key** |
| persisted shader-key cache | `vk/renderer.c:67` | **yes: `SHADER_STATE_LAYOUT_VERSION` 2 -> 3** |
| **view-volume clipping** (x/y clip to the viewport, not optional in Vulkan) | the viewport, `vk/draw.c:4496, 5621` | **no, and this is the point: the viewport stays at `.x = 0`, so the clip volume's left edge is the surface's left edge at every scale. Any future offset (SQUARE_OFFSET_4's x and y) must also go in clip space, or it loses a column and a row.** |
| vertex `surfaceSize` (guest to NDC scale) | `glsl/vsh.c:1180` | no: read, not changed |
| geometry-stage `lineNdcScale` | `vk/draw.c:2760` | no |
| scissor (bind, reorder snapshot) | `vk/draw.c:4518, 5634` | no: integer AA-px rectangle, and the guest pixel edge is still at 2x |
| window clip / `surfaceScale` | `glsl/psh.c` | no: `gl_FragCoord` is per AA pixel and unchanged |
| clear | `vkCmdClearAttachments` rects, `vk/draw.c:7176, 7262` | no: clears ignore the viewport |
| resolve | the guest's own textured quad | no: it samples the AA surface as a texture |
| GL renderer | `glsl/vsh.c` non-Vulkan branch, `geom.c` (`widen_lines` is Vulkan-only) | **not changed**: the shift is emitted for Vulkan only. GL is not the Android renderer and nothing measured it. Named, not done. |

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

**State at end of session 3.** Waiting, and said so on PR #366: for CI, and
for the arms job's `[job.arms]` verdict on `aasample-cc2-viewport.json`. The PR
stays in draft until the verdict. If it matches, mark it ready. If a
must-not-move row moves, diagnose it first. Do not re-register or rebase: the
refs are live.

## Session 4 (2026-09-26, resumed by host after the verdict)

**Why session 3 did not finish.** It was not stuck. It ended waiting for two
things outside the session: CI on `4b27c52b0f` and the arms job's verdict. It
posted `[lane.aasample] waiting:` on #366, which was correct, but the PR was
still in draft. CI came back green and the verdict was PASS. After that, only
this resume could mark it ready.

**Arm verdict: PASS, all 50 registered checks hold.** Prediction sha256
`0e52f821fa1a`. The runs were `1790403104-arms-aasample-{base-1752501,fix-1752631}` on nova,
171 of 171 captures in each arm, with no unreadable rows. The full text is in
`$WORK/arms/pairs/0e52f821...verdict.txt`.

| | priced (sec 3) | measured |
|---|---|---|
| structural px, both suites | -258,221 | **-258,224** (676,578 -> 418,354) |
| differing px | | -230,092 (3,504,926 -> 3,274,834) |
| better / worse / same | | 89 / 24 / 58 (171) |
| exact | | 13 -> 13, 0 regressed from exact |
| 40 plain 3D_primitive + 10 other Antialiasing_tests | must not move | none moved |
| `Antialiasing_tests/FBSurfaceWithCenterCorner2` | better | 352 -> 256 differing |

Per primitive, differing px on one capture, grouped by variant. Each
primitive has 12 captures, 4 draw paths x 3 variants.

| primitive | -ls | -ps and -ls-ps |
|---|---|---|
| TriStrip | 43,876 -> 31,168 | 44,467 -> 32,104 |
| TriFan | 34,191 -> 29,515 | 34,743 -> 30,334 |
| QuadStrip | 72,989 -> 69,158 | 73,579 -> 69,888 |
| Polygon | 39,065 -> 35,644 | 39,780 -> 36,580 |
| Triangles | 9,517 -> 8,411 | 10,411 -> 9,471 |
| Points | 7 -> 4 | 7 -> 4 |
| **Quads (named loss, owner #38)** | 14,858 -> 20,499 | 15,981 -> 21,675 |
| LineLoop (owner #13) | 4,678 -> 4,662 | -ps 1,215 -> 1,418 |
| LineStrip (owner #13) | 4,120 -> 4,099 | -ps 1,052 -> 1,228 |
| Lines (owner #13) | 2,332 -> 2,332 (pixels moved) | -ps 671 -> 795 |

The byte check found 8 `Lines-*-ls*` captures whose score held while their
pixels moved. That is expected: the offset moves every CC2 draw. The arm had
one run per side, so these 8 are not attributable on their own. They are not
a registered leg.

**Flake to know about (relayed from lane.remote, #274).** On desktop Vulkan,
`Antialiasing_tests/FramebufferNotModifiedBySurfaceState` is flaky. In 2 of
19 runs, pixels (0,0) and (1,0) keep the 0x050505 clear where the CPU
checkerboard wrote 0x222222. That is a race between the CPU write and the
surface write-back. It is on this arm's must-not-move list and did not move
on the device. If a future re-run trips it, read it as that race, not as this
hunk. On desktop, lane.remote also saw this hunk move exactly one AA-suite
capture, `FBSurfaceWithCenterCorner2` 352 -> 256 (2 of 2 runs), which
matches the device.

**This session.** I merged `origin/master` (8afcc8d404) with no rebase, so
the registered refs stay live. The merge conflicted only in the generated
`nv2a_index.json`. I rebuilt it with `build --tests fold-pins/nxdk_pgraph_tests
(6743b6ab16) --support fold-pins/pbkitplusplus`. Leaving out `--support`
drops the pbkitplusplus tables. After the rebuild the index differs from
master's only in `draw.c` line numbers and `emulator_commit`, and `check`
passes. Master also changed `vk/draw.c`; both hunks (`:4497`, `:5624`)
merged cleanly.

## Remediation (2026-09-26, cloud, after audit pass 1)

Audit `docs/audits/2026-09-26-aasample-pass1.md` raised one MEDIUM and two
LOWs.

**MEDIUM-1 (column 0 lost at `surface_scale >= 2`). Fixed with the audit's
remedy (a).** Vulkan clips x/y to the viewport, so the viewport at
`.x = 0.5 * sf` put the clip volume's left edge at host x = 0.5 sf, and every
host column centred left of it produced no fragments (column 0 at sf 2,
columns 0-1 at sf 4). Remedy (b), a widened viewport, also needs the NDC scale
compensated in `glsl/vsh.c`, so both options leave this lane's files; (a) is
the smaller and exact one. The two `vk/draw.c` hunks are reverted. The shift
is now added to the vertices in clip space, where it does not move the clip
volume:

| sf | viewport `.x` | clip volume, host x | host columns lost |
|---|---|---|---|
| 1 | 0 | [0, W] | none |
| 2 | 0 | [0, 2W] | none |
| 4 | 0 | [0, 4W] | none |

Geometry whose guest x reaches [-0.25, 0) now fills host column 0 at every
scale, as silicon's corner sample at (0, y) is covered.

Equivalence with the measured viewport form at sf = 1: the viewport moved
window x by 0.5 sf host px. The vertex shader adds 2 * 0.25 / surfaceSize.x
NDC, with surfaceSize.x = W_aa / 2 guest px, which is 1 / W_aa NDC, which the
viewport maps to W_aa * sf / 2 * (1 / W_aa) = 0.5 sf host px. The geometry
stage adds 0.25 guest px before `lineNdcScale = 2 / (W_aa / 2)`, the same
1 / W_aa. Depth and 1/w are untouched, so every interpolant sees the same
affine window shift as before. What can differ is float rounding: the
viewport added an exact 0.5; the vertex shader adds an inexact NDC term. Its
error is about one ulp of NDC, roughly 4e-5 guest px at 640, against a
rasteriser grid of 1/16 px or finer, and vertices sit on the 1/16 grid, so
snapping takes them to the same point.

Two things the viewport got for free and the shader form had to add. The
shader key now carries the offset (`VshState` / `GeomState.aa_offset_x`), so
a CC2 draw and a CENTER_1 draw get different shaders; non-CC2 shader text is
byte-identical to master's, because nothing is emitted at 0. And an AA-mode
change must invalidate the bound shader: `SET_SURFACE_FORMAT` now bumps
`shader_state_gen` on it and the dirty check compares the offset.
`SHADER_STATE_LAYOUT_VERSION` is bumped so a persisted key cache from either
side of this change is wiped, not regenerated.

**LOW-1 (stale line numbers).** Section 2's table is rewritten for this head.

**LOW-2 (no clip-volume row).** Added to the table, with the SQUARE_OFFSET_4
consequence named.

**Arm.** `aasample-cc2-clip.json` (`register_clip_arm.py`): a_ref is the fold
base `db73a7fb99`, b_ref the remediated head `2f98d87e20`, and the prediction, must-not-move list and disc are session
4's, because at sf = 1 the two forms place every sample identically. The
viewport arm's verdict (PASS, -258,224 structural) is the number this one must
reproduce.

**Gap: no sf = 2 arm.** `ab_compare.py --register` has no render-scale
setting, and the dispatcher runs at scale 1, so no registered arm can read
host column 0 at scale 2. The table above is the argument for sf >= 2, not a
measurement. The run that would settle it: one CC2 capture at scale 2 whose
geometry crosses guest x = 0 (any `3D_primitive/*-ls` background), reading
host AA column 0 in the raw surface.
