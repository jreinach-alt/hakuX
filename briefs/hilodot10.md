# lane.hilodot10 -- name the mechanism for the two remaining bump-mapping classes

Issue: #10 (HILO dot mapping / bump mapping)
Base: master @ bb4b78689e253675fe5d026fbab0fbed8a12c2a0
Files: docs/testing/bump_sign_quads.py, docs/lanes/hilodot10/NOTES.md

## What's already done

Read nv2a_issues.toml's issue.10 entry in full first. R16B16 (the HILO path)
and the luminance literal (A8/Y16) are FIXED and verified. `blocked_on`
records that the three remaining pieces have NO MECHANISM IN HAND -- this is
not queued fix work, it is the measurement that would produce a mechanism.
Corpus-wide finding already established: Y16/YUV do NOT go through HILO
(`tex_hilo16` is never set for them); the briefed premise that they did was
wrong and is withdrawn in the tracker.

Three open pieces, do not conflate them:

1. **YUV** -- decode is bit-exact, masks byte-identical, zero one-step
   error. There is nothing to predict yet.
2. **Y8/AY8/A8Y8** -- real stored data in component 0 (swizzle `{R,R,R,ONE}`
   / `{R,R,R,R}`), all four sign quads wrong with one-step error spread
   EVENLY across them (~6,829-7,079 each) -- a rounding-phase question, not
   the already-fixed literal.
3. **BumpEnvLum_R16B16** -- component 0 is the G swizzle, ~20,800px wrong in
   all four quads, a third and separate shape from both of the above.

## Goal

For each of the three: name the mechanism, or name the next measurement
that would narrow it, the way `bump_sign_quads.py` already separated the
luminance-literal mechanism from the HILO one. Do not guess a fix without a
falsifier that would distinguish it from the other two shapes.

## Falsifier

Per issue.10's own `blocker_falsifier`: if "no mechanism in hand" is false
for any of the three classes, the post-fix per-sign-quad decomposition on
that class would show a signature CONCENTRATED in the flagged quads (the
shape the fixed luminance literal had: 310/14,241/422/14,187) rather than
spread evenly across all four the way the un-fixed classes currently read.
Run `bump_sign_quads.py` against fresh captures for whichever class you
make progress on and quote the per-quad numbers, not a summary.

## Done when

At least one of the three pieces has either a named mechanism with a
prediction ready to register, or a concretely named next capture/measurement
(not "more investigation needed"), posted to #10 with the per-quad numbers
that support it. Leave nv2a_issues.toml's issue.10 update to the board --
do not edit nv2a_issues.toml or territory.toml yourself, no lane may.

## Out of scope

R16B16 (HILO) and the luminance literal (A8/Y16) are closed -- do not
re-verify them. Do not touch gl/draw.c or the clear-alpha path (#164);
unrelated and currently held by another lane.
