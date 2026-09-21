# lane.fulldisc50 -- the cheapest honest #50 instability measurement

Issue: #50
Base: master @ 7ec5f8e42d747b6bdcf2679f34db4d7228a937d5
Files: docs/lanes/fulldisc50/NOTES.md only.

## Read first, in order

1. nv2a_issues.toml's `[issue.50]` `blocked_on` field in full -- it names this
   exact measurement and withdraws an earlier 7.7% rate as pooling three
   incomparable disc compositions.
2. `docs/lanes/blendarm50/NOTES.md` (PR #205, merged) and its retirement note
   in territory.toml. The aliasing mechanism is settled there (stack C
   matches the aliasing model on 1,119/1,120 unsigned captures against 9/1,120
   for both rival readings). **Do not build the unequal-height/3-swatch disc
   variant** -- blendarm50's own brief forbids it explicitly: it would
   separate two models that are already refuted.

## Goal

Dispatch 5 fresh device runs of the FULL 1,673-capture `Blend tests` suite
(the interactive disc, not a narrowed one -- request with `--base-iso` the
interactive ISO per #50's `status_note`, so `disc_id` tags `iso:85b525/...`
and cannot be silently pooled with a narrowed disc). ~28 min per run. Then
run `docs/testing/fulldisc_instability_50.py` (already on disk, no
arguments, discovers every result itself) against the 5-run set. It already
controls for binary, device and composition (keyed on `frozenset(scored
keys)`, not `disc_id` alone) -- do not re-derive those controls by hand.

## Falsifier

None of this is PRE-REGISTERED against a fix -- it is a measurement, not an
arm. State plainly whatever the 5 runs show: a rate, split by device, with
the per-capture spread. If fewer than 5 runs complete (device time, holds),
report what ran and do not extrapolate a rate from fewer runs than that.

## Done when

The 5-run rate (or the honest partial) is posted to #50 and recorded in
`docs/lanes/fulldisc50/NOTES.md`, in the same split-by-device,
split-by-composition shape `fulldisc_instability_50.py` already reports in.
Do not edit `nv2a_issues.toml` -- board-only; the finding goes in NOTES.md
and the PR body. Do not attempt a fix.
