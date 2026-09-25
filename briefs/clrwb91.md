# lane.clrwb91 -- #91: make the zeta-over-colour write-back land the golden's value

Issue: #91 (gates #88's fold)
Base: master @ 0940056bf6
Files: hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/draw.c,
       docs/testing/predictions/issue91-writeback.json, docs/lanes/clrwb91/NOTES.md

## Read first
#91's last three comments, PR #148 (closed by owner decision #207) and its
top "VERDICT IN, CLAIM WITHDRAWN" section, and #88's row. Branch
`lane/clrsurf91` is kept for salvage (its pass-1 M1 repair is independent).

## What is known
Swap's background is 0xFE242424 on silicon and 0x00000024 (139,303 px) on
ours. Mechanism: a zeta image is uploaded from colour VRAM (depth 0xFE2424,
stencil 0x24), the test's own depth clear of 0 zeroes the depth, and the image
is packed back over colour memory as depth<<8|stencil. TestSwap() swaps BOTH
DMA channels, so the golden's quad region is depth read back as colour: the
write-back is REQUIRED. #148 declined it and was pixel-inert on 11 captures.

## Goal
Find why the write-back carries depth == 0 where silicon carries the 0xFE2424
lifted from colour memory (the depth clear of 0 must not reach the aliased
image, or the image must be re-derived from colour memory), and fix it in the
Vulkan surface path. The fix must PRODUCE the write-back, not decline it. Do
not touch GL.

## Falsifier
Registered before any arm, absolutes from the goldens' colour histograms, not
from GL's score file: `Swap` 165,447 -> at or below its current value with
the 139,303 px background moving to 0xFE242424; `ColorIntoZeta_ZB` and
`ZetaIntoColor` must not leave their #88 arm-B absolutes (10,766 / 71,663).
`ab_compare` must_not_move on `Swap` and `Swap_ZB`; note Swap is deterministic
on silicon but ColorIntoZeta_ZB/ZetaIntoColor are not (see #88's hardware
comment). Name the world in which each leg fails.

## Done when
Prediction registered after the last rebase, arm verdict PASS or a refuting
reading on the PR, PR marked ready.
