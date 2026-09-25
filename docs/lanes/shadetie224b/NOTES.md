# shadetie224b: #224 family B, the Celsius LT port

The full analysis is in `docs/lanes/shadetie224/NOTES.md` section 8, which
covers the pricing table, the model, the change and the offline checks. This
file records the lane's state and the arm verdict.

## Why attempt 1 did not finish

It ended correctly, waiting on the device arm. The prediction was committed
with live refs at ca9d8dbe04, and the waiting state was written into section 8
at cc146663d9. It did not post a `[lane.shadetie224b] waiting:` comment, so the
PR sat in draft until `jobs/handback.sh` resumed the lane (attempt 2,
2026-09-25).

## The verdict: FAIL, 1 of 370 legs

`[job.arms]` on #263: prediction `shadetie224b-celsius-lt.json` (sha256
a023d0f61f3d), a = 2b04d4d422, b = fe07f11f50, one run per arm.

- **Before believing it:** `scores1.tsv` has no `unreadable` status in either
  arm, and `run1.log` has no PARTIAL COVERAGE and no UtilAcceptVsock. The disc
  is identical in both arms, and so is the 370-capture count.
- **The violated leg:** must_not_regress
  `Specular_back/SpecParams_FF_Pow0_1` went from 1259 to 1280 (+21). The
  structural count stayed at 32, so all 21 are off-by-one pixels.
- **It is not device noise.** That capture reads exactly 1259/32/314 in every
  run on disc since #58's fix. Seven distinct apks, including shadetie224's
  own two arms, all read the same, and it has never scattered. The +21 comes
  from the candidate.
- **Everything else held or improved:** 104 better, 1 worse, 265 same.
  Exact went from 46 to 64: all 18 B captures were repaired to exact, and 0
  regressed from exact. Differing fell from 4,944,186 to 3,842,426. Among the
  captures that improved:
  - Lighting_range/Directional stayed at 224, the world-in-which-it-fails
    did not happen;
  - Lighting_accumulation improved on 7 of 10;
  - Lighting_control improved on 16 of 32, NoSpec rows included;
  - Lighting_spotlight improved on 20 of 24;
  - Specular improved on 10 of 22;
  - Specular_back improved on 9 of 17.
- **Byte-level note:** `Lighting_spotlight/FoFixed_-0.993286_...` moved pixels
  at an unchanged score (11,656). No leg tests that.

## What the one regression names

The front-face twin, `Specular/SpecParams_FF_Pow0_1`, improved from 2296 to
1979. Only the back-face evaluation at the lowest exponent (0.1) got worse,
and all eight other Specular_back params rows improved. That points at a
stage the back side does differently in the port, not at the LT arithmetic as
a whole. Candidates, in order:

1. The back material's specular params. Check whether `k = lt(specularParams)`
   uses the back set, and whether the back set reaches `xf_s2lt`.
2. The negated normal for the back face. Check whether the port negates
   before or after `lt()`. The two orders agree only if every LT rounding
   step treats +x and -x alike (sign-symmetric), which has not been checked.
3. The pow-0.1 fit itself. At small exponents k1/k2 make S(x) steep near
   x = 1, so a 1-LSB input difference moves the output most.

## For the next lane

- Do not re-run the whole port unchanged. The verdict above is its result,
  and one run per arm is enough here because the regressing capture is
  deterministic on disc.
- Do not re-run lt(N) or the four curve-fit rules from the section 8 table.
- Read the back-face path of fe07f11f50's vsh-ff.c against envytools
  `pgraph_celsius_lt_full` for the two-sided case, and price Pow0_1 back vs
  front offline with `celsius_lt.py` before building. Once that model
  reproduces the +21 direction, the fix is a single-stage edit. Register it on
  fresh refs.
- Before calling this a fold candidate: the arm is otherwise a large, clean
  improvement, so accepting the one leg would be a decision for the board.
  This lane does not make it.

## State (2026-09-25, attempt 2)

The PR is ready, labelled `regressed` by the arms job. Its head is
MERGEABLE/CLEAN against master, and `preflight.sh` passes on it (nv2a index ok).
