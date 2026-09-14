# Line_width under OpenGL, measured for the first time

`iso_line` aborted until `5b707602`, so this suite had never been scored under
the GL renderer. Measured on that commit: **61 captures, 1 exact, 4,514,611
differing channels**, of which 4,462,131 is structural and discriminating
(`golden_colours` ~ 2,990 on the large captures, so these captures have real
discriminating power -- see `corpus-residual-triage.md`).

This is a first baseline and a characterisation, not a fix.

## The error is monotonic in width, and there are two clean boundaries

| width | differing channels | painted px (ours) | painted px (golden) | ours/gold |
|---:|---:|---:|---:|---:|
| 0.0 | **0** | 3,104 | 3,104 | **1.000** |
| 1.0 | 5,737 | 6,155 | 6,677 | 0.922 |
| 4.0 | 21,075 | 14,524 | 16,192 | 0.897 |
| 8.0 | 42,095 | 24,105 | 26,827 | 0.899 |
| 16.0 | 76,243 | 38,926 | 42,870 | 0.908 |
| 32.0 | 129,362 | 59,581 | 64,780 | 0.920 |
| 63.0 | 201,403 | 84,938 | 90,802 | 0.935 |
| 63.7 | **202,486** | | | |
| 64.0 | **5,737** | 6,151 | 6,673 | 0.922 |
| 64.7 | 5,737 | | | |
| `FFFFFFFF` | 5,737 | | | |

**Width 0 is byte-exact.** 3,104 painted pixels on both sides, zero differing
channels -- the only exact capture in the suite.

**Everything at width >= 64 collapses**, and collapses on BOTH sides. 64.0
through 64.7 and the `FFFFFFFF` capture all give *exactly* 5,737 differing
channels, and 5,737 is also width 1.0's figure. Ours paints 6,151 against the
golden's 6,673 there -- the same ratio as width 1. So the hardware collapses at
64 too, and this range is very nearly right; it is not where the defect is.

## The defect is the 1.0 to 63.7 range, and we paint too FEW pixels

Ours is smaller than the golden at every width from 1 upward, by 6% to 10%,
and the absolute gap grows with width: 522 px at width 1, 2,722 at 8, 5,199 at
32, 5,864 at 63. The tallest painted column grows the same way -- 120 against
the golden's 125 at width 1, 310 against 348 at width 63.

Our lines are systematically **thinner than the hardware's**.

## The obvious cause is ruled out, from this data alone

`gl/draw.c` clamps to `supported_aliased_line_width_range[1]` /
`supported_smooth_line_width_range[1]`, so a driver whose maximum line width is
below 63.7 would make us draw too thin -- exactly the symptom.

**It is not that.** If we were clamping at some maximum W, every width above W
would paint IDENTICALLY. The painted count rises without a plateau all the way
to 63.0 (6,155 -> 84,938, monotone), so no clamp is binding below 63.7. No probe
was needed to rule this out; the curve already says so.

So the deficit is a rasterisation difference rather than a clamp, and that is
where the next instrument goes.

## Not concluded

Whether the deficit is in the line's WIDTH, its LENGTH, or its end caps. The
tallest-column figures point at width, but "painted pixels" confounds all three
and this document does not pretend to separate them. Nor is it established
whether the 4.46M is one mechanism or several -- 60 of 61 captures classify
structural, which says only that they are not one-step or boundary-shift.

`Line_FFFFFFFF`, `Fill_0000.0` (41,533), `Fill_0001.0` (43,083) and
`Fill_0032.0` (70,357) are in this suite too and are not analysed here.

## Reproduce

    bash /tmp/pgraph-run/runx_gl.sh <bin> /tmp/pgraph-run/iso_line.iso <tag> line

then score `score_<tag>/<tag>` against `/tmp/goldens/results/Line_width`. The
captures used here are `/tmp/pgraph-run/score_lfix/lfix` at `5b707602`.
