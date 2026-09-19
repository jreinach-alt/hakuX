# lane.dualsrc59 -- is dualSrcBlend available for #59's write-side fix?

Issue: #59 (surface pad bits written by the raster, read wrong by the
texture unit on R5G6B5/A1R5G5B5/etc -- #48's read-side swizzle is exact on
rendered pixels, wrong on the rest)
Base: master @ f1de5b953570a62ce40eea53a2761bac5eb4587d
Files: hw/xbox/nv2a/pgraph/vk/instance.c only. Do not touch psh.c or draw.c
this pass -- psh.c is lane.remote's and the write-side fix (if reachable)
needs a second dispatch once this answer is in.

## What's already done

Read nv2a_issues.toml's issue.59 entry in full first -- it is long, and the
tail is what matters: the write-side fix needs the source alpha forced to 1
without changing what the colour blend consumes, which VK_BLEND cannot do
without dual-source blending. `vk/instance.c`'s desired_features table lists
nine features and dualSrcBlend is not among them, so nothing in this tree
has ever asked the device whether it has it.

## Goal

Add `F(dualSrcBlend, false)` (matching the table's existing entries' shape)
to instance.c's desired_features table, boot once on a device, and read the
feature-support boot log for whether dualSrcBlend came back true or false.

## Falsifier

If dualSrcBlend availability were unrelated to this device's blend
capabilities, then the presence/absence of this one line would not decide
between two answers already written down: "the fix is psh.c + draw.c +
instance.c" (if true) or "the write side is unreachable on this renderer,
the read-side approximation is the best available" (if false). One boot
answers which.

## Done when

The boot log line naming dualSrcBlend's reported value is quoted in #59,
with which of the two outcomes above it settles. No shader or blend-state
change in this pass -- this is a measurement, not the fix. If true, say so
and stop; a second lane claims psh.c+draw.c next. If false, say so and
close this angle on the issue.
