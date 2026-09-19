# lane.blendrace50 -- settle #50's disc-composition confound with a full-disc measurement

Issue: #50 (DrawColorAndAlphaStack's stack wrong on 1,567/1,568 captures; a
6.5M-channel structural entry, not a blend defect -- 1_ADD_0 is src=ONE
dst=ZERO)
Base: master @ f1de5b953570a62ce40eea53a2761bac5eb4587d
Files: none yet -- the mechanism is unknown and no source file is implicated.
Claim files only once a specific site is named; do not hold source
speculatively.

## What's already done

Read nv2a_issues.toml's issue.50 entry in full before doing anything else.
The 7.7% race rate previously posted is WITHDRAWN: it pooled three disc
compositions (full 1,673-test, 5-test, 1-test) under one disc_id, which
turned out not to include only_tests, so incomparable runs looked like one
population (fixed in 63db4e4211). On narrowed discs the four "device-stable"
movers read a fixed value across 5 runs; on the FULL disc, one of them
(1-srcRGB_SADD_0) took two different values across three arms. Narrowing
also REMOVED a RenderTextureLoop-class predecessor effect (documented in
make_test_iso.py) that the full disc carries.

## Goal

Get an honest measurement of the race rate on the disc composition that
actually matters: 5 runs on the FULL 1,673-capture disc (~28 min each).
Report, per capture that moves, its value on each of the 5 runs -- do not
collapse to a mean or a single rate number the way the withdrawn 7.7% was.

## Falsifier

If "disc composition is the active variable, not a genuine device race"
were false, the same captures that are stable across 5 runs on a narrowed
disc would ALSO be stable across 5 runs on the full disc. Any capture that
disagrees with itself across the 5 full-disc runs is a live race; any that
agrees is not evidence either way (composition, not the race, may be why).

## Done when

5 full-disc runs are on record with a table of every capture that showed
more than one value, and #50 is updated with: which captures actually race
(vary run-to-run on the SAME disc), which only vary BETWEEN disc
compositions (a composition effect, not a race), and which candidate site
(if any) explains the difference. Do not attempt a fix in this pass --
naming the mechanism is the deliverable, matching #89's precedent of
splitting measurement from remediation.
