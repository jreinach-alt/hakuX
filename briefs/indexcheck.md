# lane.indexcheck -- #157: nv2a_index check cannot tell a stale index from a stale test checkout

Base: origin/master @ 415dcc6997.

Files: docs/testing/nv2a_index.py only. (docs/testing/preflight.sh is
lane.toolsmith's -- do not touch it; a failure-text pointer there is optional
and out of scope.)

## The defect

`nv2a_index.py check --tests DIR` reports only `suites differ (committed N,
tests tree M)` with no sign. Its own suggested remedy, `build --tests DIR`,
regenerates the index from whatever suite count the tests tree currently has
-- so a checkout that is BEHIND the committed index silently produces a
SMALLER index, deleting real suites from master with nothing downstream to
flag it. This already happened once in miniature: five commits behind, one
suite short, see issue #157's body for the reproduction
(`Surface_as_vertex_array`, nxdk_pgraph_tests commit `0a441e0`).

## Goal

Make the check state the DIRECTION of the mismatch, not just that one
exists: name which side is short and which suite(s) are missing from which.
Either (a) say so in the check's own failure text (`the tests tree is
MISSING N suite(s) the index has: <names> -- your nxdk_pgraph_tests checkout
is probably behind`), or (b) refuse to `build` a smaller index than the
committed one without an explicit `--allow-suite-removal` flag, or both.
Read the full issue body (`gh issue view 157`) for the exact repro and the
two proposed options before choosing.

## Falsifier

Construct (or point at) a tests tree with one fewer suite than the
committed index. `check --tests DIR` must name the missing suite and the
direction, not just print a bare count mismatch. `build --tests DIR` against
that same tree must refuse (or require the new flag) rather than silently
writing a smaller index.

## Done when

The falsifier above passes, the existing `nv2a_index.py` test/selftest
coverage (if any) still passes, and the PR's own description states the
before/after failure text for both the "index ahead" and "index behind"
directions.
