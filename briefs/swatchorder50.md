# lane.swatchorder50 -- separate DrawColorAndAlphaStack's two surviving readings

Issue: #50 (DrawColorAndAlphaStack, [accuracy])
Base: master @ 4c28b2d352c7d8d371a8aa187911cef3254cde8c
Files: docs/lanes/swatchorder50/NOTES.md
       (plus whatever nxdk_pgraph_tests source holds blend_tests.cpp -- ask if
       that tree is not already in your worktree; it is outside this repo)

## What's already done

Read nv2a_issues.toml's issue.50 entry in full first. Five mechanisms are
measured dead (fifth-draw-carries-first-colour, unimplemented method,
draw-queue merging, blend arithmetic, two-draw blend_en pairing) -- do not
re-derive any of them. `DrawColorAndAlphaStack`'s four swatches come out as
the golden's own sequence in exact reverse (white/blue/red/green vs
green/red/blue/white), on `1_ADD_0` alone -- no blending contributes, so the
defect is placement or per-draw colour assignment for four consecutive
identical-state draws. Two readings remain, both consistent with the one
existing capture:

1. the four quads land at reversed y positions;
2. the four quads land correctly and receive the diffuse colours in reverse
   order.

## Goal

Separate reading 1 from reading 2. The issue's own next step: add a
`DrawColorAndAlphaStack` variant to blend_tests.cpp that makes the four
swatches unequal in height, or draws three instead of four -- either change
makes the two readings predict different framebuffers where they currently
predict the same one.

## Falsifier

Build the modified disc, capture `1_ADD_0` (or the renamed equivalent) on
device against the corresponding silicon-side expectation derived by hand
from the two models, and read which reading the capture matches. A result
that matches neither is itself informative -- report it rather than forcing
a fit.

## Done when

The new capture exists on disk, the verdict (reading 1, reading 2, or
neither) is posted to #50 with the capture and the reasoning, and
nv2a_issues.toml's issue.50 status_note is left for the board to update --
do not edit nv2a_issues.toml yourself, no lane may.

## Out of scope

Do not attempt a fix for #50 in this pass -- this brief is one measurement
that decides which model a fix would need to implement. The five dead
mechanisms above are closed; do not reopen them.
