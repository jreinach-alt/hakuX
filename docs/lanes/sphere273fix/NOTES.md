# lane.sphere273fix -- #273 SphereMap on R, the landing lane

Base: master @ 90a8dc1c1a (contains PR #288's fold, e4e532cca8).
Mechanism and price: docs/lanes/spheremap273/NOTES.md (+ price.py). Not redone.

## What changed

`hw/xbox/nv2a/pgraph/pgraph.c` `kelvin_map_texgen`, commit 0965b30a26: SPHERE_MAP
on channel 2 (R) maps to REFLECTION_MAP. vsh-ff.c's REFLECTION_MAP case already
emits `oT.z = r.z` for j == 2 (checked by reading, vsh-ff.c:848), so vsh-ff.c is
untouched. Channel 3 (Q) stays DISABLE + UNIMPLEMENTED. The comment above the
switch is narrowed to Q.

## Prediction

`docs/testing/predictions/sphere273fix-rz.json`, a_ref 90a8dc1c1a, b_ref 0965b30a26,
disc `Texgen,Texgen with texture matrix`.

- The must-move legs are judged BY HAND: SphereMap_RotateX and SphereMap_Arbitrary
  131,495 -> <= 1,000 differing, max_rgb <= 2. An exact `--expect-value ...=0` would
  be a wrong leg: the `differing` column counts 1-LSB pixels, and the other nine
  SphereMap captures sit at 56-603 on the c866527e03 baseline
  (`z-repeat-c866527e03-067-Texgen_with_texture_matrix`). The machine check is
  `expect_counts` better=2, worse=0.
- must_not_move: the other 64 captures in the suite plus `Texgen/*`, bit-identical.
  The prediction says which patch change would move each group.

## No evidence yet (do not read the arm as settling these)

- Q under sphere, normal or reflection mapping: nothing on the disc tests it.
- r.z vs -u.z: on this quad n = (0,0,1), so r.z = u.z - 2 u.z = -u.z *exactly*. The
  goldens cannot separate them. A tilted-normal test would be needed.
- Whether CSV1 keeps 3 or 5 for R: not observable by any test (spheremap273 section 4).

## Preflight

- nv2a index: my pgraph.c hunk moved 257 sites. I regenerated it over the
  fold-pins trees at tests_commit 6743b6ab (80ef756386), and `check` matches.
- coverage: FAILED, and it is the board's to fix. #273's blocker in
  nv2a_issues.toml (origin/board) names only lane.vshsubneg255, which retired
  when PR #288 folded. Lanes may not edit that file. CI does not run this gate.
  Everything else passes.

## Attempt 2 (2026-09-26): why attempt 1 did not finish

Attempt 1 did everything it could before the arm. It ended waiting on the arm,
with the PR still in draft. Handback resumed this lane at 02:22Z (CI GREEN on
a3f2437ccf). Both arm requests
(`1790377428-arms-sphere273fix-{base,fix}`) were still in the device queue then,
and no `[job.arms]` verdict had posted, so the arm leg is still open.

Master had moved 128 commits in the meantime, and the PR had become unmergeable
(`dirty`) on `docs/testing/nv2a_index.json`. I merged origin/master in, without a
rebase, so a_ref and b_ref are still ancestors. I took master's index and rebuilt
it over the fold-pins trees (tests_commit 6743b6ab), and `check` matches. The
pgraph.c hunk merged without a conflict. With `--allow-tracker`, preflight now
passes on every gate, `coverage` included: hostops had cleared #273's stale
blocker on origin/board.

## State

Waiting on the arm. The arms job queues it from the committed prediction and
posts a `[job.arms]` verdict on PR #330. When it lands, judge the two must-move
legs by hand (<= 1,000 differing, max_rgb <= 2), read the status column for
`unreadable`, then mark the PR ready.
