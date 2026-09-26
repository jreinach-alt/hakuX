# Audit pass 1: PR #366, lane/aasample (#286 class A, CC2 viewport offset, live)

Head audited: `d7b25ec943`. Base: `origin/master` @ `6550967a5e` (0 behind, 7 ahead).
Mergeable, and CI (`build` x2, `check`) is green on this head.

**Verdict: 1 MEDIUM, 2 LOW → needs-remediation.** The shift is right at
`surface_scale = 1`, which is all the arm measured. At `surface_scale >= 2` it
moves the left clip edge off the surface edge, so the leftmost host columns of
every CC2 surface are never rasterised.

## What the diff is

GitHub's file list for #366 shows 34 files (pshqueue, cloud-13, statusdash, psh.c).
That list is stale: it was computed against an older merge base. The real three-dot
diff `origin/master...d7b25ec943` has 5 files, and they match the PR body's `Files:` line:

| file | change |
|---|---|
| `hw/xbox/nv2a/pgraph/vk/draw.c` | +4: `.x = pgraph_anti_aliasing_viewport_offset_x(pg) * pg->surface_scale_factor` in both `VkViewport` initialisers (`:4497` pipeline bind, `:5624` reorder snapshot) |
| `docs/testing/nv2a_index.json` | line-number shift regen |
| `docs/testing/predictions/aasample-cc2-viewport.json` | the registered arm |
| `docs/lanes/aasample/{NOTES.md, register_arm.py}` | notes, registration script |

`git diff 57e46af766 d7b25ec943 -- hw/` (b_ref to head) contains only changes that
came from master. So the arm's b_ref carries the same 4-line hunk as this head.

## Checked

- **The two initialisers agree.** Both use the same expression, and the replay at
  `:6100` sets `e->viewport` as it was captured. A reordered draw cannot get a
  different offset from an in-order one.
- **No pipeline-cache leak.** `VK_DYNAMIC_STATE_VIEWPORT` is in both pipeline
  dynamic-state lists (`:1875`, `:2486`). The offset is not baked into a cached
  pipeline, so a CC2 pipeline reused on a CENTER_1 surface does not carry it.
- **No stale offset across surfaces.** The viewport is re-emitted under
  `must_bind_pipeline`, and a new render pass forces that (`:4472-4475`). A
  CC2 surface and a non-CC2 one have different bound images, so switching between
  them starts a new pass.
- **Scissor unaffected.** It is an integer AA-px rectangle from `clip_x/width`, set
  next to the viewport. It does not read the offset.
- **The presentation blit is untouched.** The `vk/display.c` viewport does not take
  the offset, which is correct.
- **GL is not changed.** NOTES section 2 names this as not done (`glViewport` takes
  ints). GL is not the Android renderer. Noted; not a finding.
- **Arm.** `[job.arms]` PASS, 50/50 must-not-move held. That includes
  `FBSurfaceWithCenter1` and the 40 CENTER_1 captures, which would move if the
  offset leaked into non-CC2 surfaces.

## Findings

### MEDIUM-1: at `surface_scale >= 2`, the left `0.5*sf` host px of a CC2 surface is outside the clip volume

On Vulkan, `gl_Position = oPos` (`glsl/vsh.c:999`). The guest-to-NDC scale
(`surfaceSize`) maps the surface's left edge to NDC x = -1, and Vulkan cannot turn
off x/y view-volume clipping. So the clip volume's left edge is the viewport's `.x`.
After this hunk that edge is at host x = `0.5 * sf`, not 0.

Every host column whose centre is below `0.5 * sf` is therefore outside the clip
volume. Geometry reaching or crossing the guest's left edge still produces no
fragments there. Examples:

| sf | viewport `.x` | host columns lost (centre < `.x`) |
|---|---|---|
| 1 | 0.5 | none (column 0's centre is on the inclusive edge) |
| 2 | 1.0 | column 0 (centre 0.5) |
| 3 | 1.5 | column 0; column 1 is on the edge |
| 4 | 2.0 | columns 0 and 1 |

*Failure scenario:* a CC2 game (any title rendering to a 2x-wide AA surface) runs
with the render-resolution scale set to 2x or higher (`surface_scale`,
`vk/surface.c:56`). It clears the AA surface and draws a full-screen background.
Host AA column 0 keeps the clear colour, or the previous frame's contents.

At upscale, the guest's resolve pass is also drawn at host resolution. Its bilinear
tap for guest pixel 0 reads host AA columns 0 and 1. The output then has a thin
stripe along its left edge in the clear colour, in every frame. On silicon, the
guest's column-0 corner sample at (0, y) is covered by that background.

The arm cannot see this. It ran at scale 1, where column 0's centre lies exactly on
the inclusive edge and is kept. So this is wrong outside what the goldens exercise.
It is graded MEDIUM, not HIGH, only because the blast radius is bounded to a
sub-guest-pixel strip on one edge, in one AA mode, at non-default scales.

*Correction to a prior audit:* `docs/audits/2026-09-25-aasample-pass1.md`, "Edge
coverage after the shift", concludes "No column is lost". That holds for sf = 1
only. Its own interval, host x in [0.5sf, W+0.5sf], excludes host column 0 once
sf >= 2.

*Remedy options (the lane's choice):*
- **(a)** Keep the viewport at `.x = 0` and translate in clip space instead: add
  `2 * 0.5 / aa_width * gl_Position.w` to `gl_Position.x` for CC2. Here `aa_width`
  is `surface_binding_dim.width` in AA px, so `sf` cancels. The clip volume then
  stays on the surface, and geometry from guest x < 0 fills the strip.
- **(b)** Keep the viewport shift, but widen it by a guard of at least one AA px on
  the left, and compensate the NDC scale.

(a) touches `glsl/vsh.c`, which is outside this lane's grant. Say which in the
remediation. Either way, add an sf = 2 check: one CC2 capture at scale 2 with
geometry that crosses x = 0, reading host column 0. If no scale-2 arm is
available, name that gap in the PR body.

### LOW-1: NOTES section 2 still names moved line numbers
Section 2's table gives the reorder replay as `vk/draw.c:5992` and the scissors as
`7058, 7143`. On this head they are `:6100` and `:7171, 7256`, and the two edited
lines are `:4497` and `:5624`. The PR body has the right numbers. The same LOW was
raised on #332 and is still open.
*Scenario:* a reader checks the replay at 5992 and finds unrelated code.

### LOW-2: the consumer table has no row for view-volume clipping
Section 2 lists every consumer of the AA factor, but not the clip volume. The clip
volume is the consumer that MEDIUM-1 turns on. Add a row when remediating, so the
next change to the offset sees it.
*Scenario:* a later SQUARE_OFFSET_4 offset (x and y) is priced from the table and
loses a column and a row at every scale.

## For pass 2

Verify that at sf = 2 and sf = 4 no host column of a CC2 surface lies outside the
clip volume. Do it either by reading the remedy's arithmetic against the table
above, or with a scale-2 capture. Also check that the sf = 1 results of the
registered arm still hold on the remediated head.
