# #88: re-apply the colour-wins same-offset decline on Vulkan, now that #91 is fixed

Lane: clrwin88            Issue: #88 (Color_zeta_overlap, Vulkan)
Base: origin/master 0a4e284536
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/testing/predictions/issue88-*.json,
docs/lanes/clrwin88/**
Needs device: yes (Thor iso_surf1 arm, three suites). Needs NDK: no.

## Why now

#88 was held because the colour-wins decline cost Swap (#91). PR #237
(af5bedd1b0) fixed #91's root cause -- a Z24S8 depth-copy offset in vk/surface.c
-- and its own arm ran WITH the decline applied: Swap stayed at 165,447, the
golden's background word. The trade owner decision #207 declined no longer
exists. `vk/surface.c` is free (lane.clrwb91 retired).

## The job

Re-apply on current master the change PR #148 carried (branch
`lane/clrsurf91`, tip fb41f3505a, closed unmerged): in Vulkan's same-offset
surface policy, COLOUR WINS -- colour may take a surface zeta holds, zeta
declines one colour holds. It is four lines, policy only. **The gate half of
#66 must NOT be ported**: Vulkan's gate is already `!current_binding || (upload
&& ...)` (upstream 9161e3e14a) and is more permissive than GL's. Read
`docs/investigations/color-zeta-same-surface.md` and the #88 tracker text first.

Rebase the port onto #237's vk/surface.c; do not reintroduce the write-back
path #237 replaced.

## The arm (register BEFORE building, and after the last rebase)

`docs/testing/predictions/issue88-vk-same-offset-colour-wins.json` is already on
master with the bound values -- re-point its refs, do not re-derive.
- **must_move:** ColorIntoZeta_ZB 131,495 -> 10,766; ZetaIntoColor
  102,255 -> 71,663 (both hit to the digit in the old 3-suite arm).
- **must_not_move:** Swap at 165,447 (the #237 background word); the nine
  controls in the JSON, including Color_Zeta_Disable/MaskOff_ZB and
  Null_surface/XemuBug893, which live in OTHER suites -- queue
  `--suites 'Color zeta overlap' 'Color Zeta Disable' 'Null surface'` or drop
  those keys with a reason.
- **Swap_ZB** (GL 0, Vulkan 141,125): PREDICT it. It is the one unexplained
  capture. Note it scored 0 across six handheld runs before (141,125 is the
  golden's own black-pixel count: a nothing-rendered signature) -- check the
  status column before believing any Swap_ZB number.
- **The world in which must_move fails:** the decline is announced only by a
  no-op `NV2A_UNIMPLEMENTED`; if the site never fires on the device the counts
  do not move. Add a counter (as #148's `[dl91]` did) and report it.

**Before trusting the verdict:** check both arms' `scores1.tsv` status column
for `unreadable`, and `run1.log` for "PARTIAL COVERAGE" and UtilAcceptVsock. An
unreadable capture scores as 0, so it reads as "fixed".

## Do not

- Port the gate half. Read vk/surface.c first.
- Score a desktop/lavapipe capture against device goldens.
- Touch vk/draw.c (lane.remote's) or gl/*.
- Trigger CI as a self-check.

## Done when

- The arm verdict is on your PR with its status column checked, Swap and its
  neighbours held.
- NOTES record the Swap_ZB prediction and the counter.
- `nv2a_index.json` is regenerated over the tests tree at
  `provenance.tests_commit`; preflight passes; the PR is marked ready with
  its `Files:` line.
