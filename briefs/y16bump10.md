# #10: land the Y16 bump-source fix (horizontal offset from the low byte) and run its arm

Lane: y16bump10          Issue: #10 (Bump map / Bump env lum, the Y16 class, ~28,132 px per capture; game-visible)
Base: origin/master @ 09f3061bc5 (rebase to the tip before you register anything).
Files: docs/testing/predictions/y16bump10-*.json, docs/lanes/y16bump10/**
       LENT from lane.pshqueue (one disjoint hunk; its row keeps psh.c): hw/xbox/nv2a/pgraph/glsl/psh.c, the Y16 bump read
       (append_bump_channel and its callers, ~:1725-1830). pshqueue's hunks are the fog INF (~:1905), DOT_ZW, G8B8 and BRDF
       cases; if yours must sit inside one of those, stop and board-request.
Needs device: yes for the arm (Nova or Thor). Needs NDK: yes for the build.

## What silicon does (measured on the console)
PR #359 (the Y16 low-byte run): the LOW byte of a Y16 bump texel feeds one offset and the high byte the other; forcing low
bytes to 0 moves silicon 28,336 px and hakuX 112. PR #363 (docs/testing/xbox-y16axis-2026-09-26.md,
docs/lanes/xbox/y16axis.patch): the HORIZONTAL offset (m00) reads the filtered value's LOW BYTE (42,508 px vs Y8; native seam
sweep 26,254 px); the VERTICAL offset (m11) shows no sweep, so high byte or full value (registered verdict X by 88 px: treat
the vertical source as the open leg). Read both write-ups and #10's status_note first. The R16B16 class is already fixed; YUV
and Y8/AY8/A8Y8 have NO mechanism -- do not touch them.

## The job, in order
1. Give a Y16 bump source's horizontal offset its low byte and the vertical offset its high byte or full value (pick the one
   that reproduces the sweep-free vertical reading and say which in NOTES). Change the Y16 path only, in one commit.
2. Register the arm AFTER your last rebase (a_ref = the tip, b_ref = the fix commit) as
   docs/testing/predictions/y16bump10-y16.json. Commit it; the arms job runs it. Do not queue arms.

## Falsifier
must_move: Bump_env_lum Y16 and the Y16 Bump_map captures, toward 0 (or a stated residual).
must_not_move: A8 and R16B16 (the fixed classes, 1,576 px), YUY2_L/UYVY, Y8/AY8/A8Y8, every non-bump suite.
Failing world: Y16 moves but R16B16 or A8 move too (the hunk leaked outside the Y16 path). A Y16 leg that lands elsewhere
refutes the low-byte model: report the measured number, do not tune to it. Read `status` for `unreadable` before trusting
any `=0`.

## Done when
The arm verdict is PASS (or each refuted leg is named with its figure and its hunk is out) and the PR is ready for review with
the verdict cited. Do not edit the board files.

## Addendum (board wave 244, 2026-09-26T10:40Z): the fold refuses PR #367 on preflight
PR #367 is fold-ready, CI green, and the fold job has refused it five times (last 10:30Z): `preflight.sh` -> `psh_differ report FAILED`,
every baseline (basic/stages/textures/surface/clipplane/border/bumpenv/misc x gl/vk/gles) `does not generate`. The differ builds
and prints its table; only baseline generation fails. It is NOT the /tmp race: PR #384 (one mktemp dir per run) folded first and
the refusal recurred. Master @ e673558587 passed the same preflight for #373 at 10:20Z, so the failure lives in master + this branch.
1. Merge current master into `lane/y16bump10` (do not force-push), run `docs/testing/preflight.sh`, reproduce. Master's psh.c gained
   fog278's hunk (PR #373) and tiecode282 is editing psh.c too; suspect the interaction with your `append_bump_channel` hunk.
2. Find what the differ's baseline generation dies on (a child abort/assert, a carve.py boundary moved by your hunk, a new call the
   shim lacks) and fix it on this branch. If the cause is in `docs/testing/psh_differ/` and not your hunk, say so on the PR and
   make the smallest fix there; that path is not in your Files: line, so add it to the PR body's Files: line.
3. Push, wait for CI, leave the PR ready. Do not edit the board files.
