# lane.blendarm50

Issue #50 (DrawColorAndAlphaStack's stack is reversed). Base: 28531197b6
(origin/master). Files: docs/lanes/blendarm50/NOTES.md,
docs/testing/swatchorder50_readings.py.

## What is already settled (read before touching anything)

Read `docs/lanes/swatchorder50/NOTES.md` (PR #186, merged) in full first. The
mechanism is render-target aliasing: stack C's blit shows the render target
`DrawColorStack` left at the same guest address. Both other readings
(reversed y placement, reversed colour order) are measured dead --
9/1120 vs aliasing's 1119/1120 against the goldens, scored on
`swatchorder50_readings.py --score --unsigned`. **Do not build the
unequal-height/3-swatch disc variant** -- it would separate two models that
are both already refuted.

## What is not settled, and is this lane's

`771c8eb4f1` ("record queued draws before a synchronous surface download") is
already an ancestor of master, but no arm has run it against these models --
the 1,568 captures at `~/hakux-work/res_oldblend/` all predate it. Goal:
build master, dispatch a fresh `Blend tests` `TestDetailed` run on device (the
interactive-disc plumbing landed -- request with `--base-iso` the interactive
ISO; see #50's `status_note` in `nv2a_issues.toml` for the `disc_id` and why a
narrowed disc is not a substitute), then run `swatchorder50_readings.py
--score --unsigned` against the NEW captures. Register a bound prediction:
post-fix stack C should move toward the control (correct-stack-C, currently
0/1120) and away from the aliasing model (currently 1119/1120).

Falsifier: if post-fix stack C still scores near 1119/1120 against the
aliasing model rather than moving toward control, the flush does not fix the
bulk of captures and the aliasing site is elsewhere -- say so, do not force a
PASS.

Done when: the prediction is registered and judged (ab_compare
PRE-REGISTERED or a verdict), the result is written to
`docs/lanes/blendarm50/NOTES.md`, and a PR is opened naming the arm result
either way. Do not edit `nv2a_issues.toml` -- board-only; note the finding in
NOTES.md and the PR body instead.
