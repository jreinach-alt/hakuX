# lane.wbuf31fix NOTES (#31)

2026-09-24, master @ 76e973ebeb. Brief: find the selector between the 2x2-quad
anchor snap and the absolute 4-grid (phase 2), prove it offline against every
recovered anchor, then implement it in `wbufSlopeStep`.

## Result: no selector fits. There is a fourth input.

No selector framed over the geometric inputs reproduces every anchor. The
closest miss exactly one anchor, and it is always the same one:
**ClipF-150-032's first triangle** (silicon: 32). The rules that do reproduce
it add a clause that nothing else in the corpus tests. So **psh.c is not
edited, and no arm is registered.** The brief says a selector that misses one
observation is wrong, and this lane agrees: the best candidate would fix
ClipF's second triangle (about 189k px at clip_top 32) by breaking its first
(16,801 px), which is currently right.

## Inputs

- The goldens (`/home/justin/goldens/results`).
- Console run clip_top 35, PR #218:
  `/home/justin/hakux-work/hardware/runs/2026-09-25-wbuf31-clipf35/console-run/console`.
- Console run clip_top 4, PR #221:
  `/home/justin/hakux-work/hardware/runs/2026-09-25-wbuf31-clipf04/console-run/console`.

Reproduce:

    python3 docs/testing/wbuf_anchor_recover.py \
      --goldens /home/justin/goldens/results \
      --goldens <clipf35 run>/console-run/console \
      --goldens <clipf04 run>/console-run/console --selectors

The console runs have the goldens' layout, so the tool now takes
`--goldens` more than once, and the first root that holds a capture wins.
`ClipF-150-004` is in `PRIMS`. On the goldens alone the default output is
unchanged: 66 anchors, the same 25/64 and 37/64 scores.
`wbuf31_blocker_audit.py` and `wbuf_clip_phase_choice.py` import this
module; their output is byte-identical before and after the change.

Anchors recovered: 44 (LargeZ and TriV excluded, as before). All 44 fit one
of the two rules inside hardware's interval, and **none fits neither**. 26 are
informative, meaning the quad snap and the 4-grid disagree on them.

## Fit table

"ok" = reproduces the recovered anchor inside hardware's interval.

| observation (silicon anchor) | n | all quad | all 4-grid | shipped: grid iff uncut | best 2-literal: grid iff uncut OR the window clip's top edge cut it |
|---|---:|---|---|---|---|
| TriH, 24 triangles (4-grid) | 24 | 12 miss | ok | ok | ok |
| Floor t0/t1 at clip_top 0 (0, 0) | 2 | ok | miss | ok | ok |
| Roof t0 (0), Roof t1 (366) | 2 | ok | t0 miss | ok | ok |
| Wall t0 (col 636), Wall t1 (150) | 2 | ok | t0 miss | ok | ok |
| ClipW t0 x3 (636), t1 (158, 260, 362) | 6 | ok | 4 miss | ok | ok |
| ClipF t1 at 32 / 128 / 224 (34, 130, 226) | 3 | miss | ok | **miss** | ok |
| ClipF t1 at 35 (34), at 4 (6) | 2 | at 4: miss | ok | at 4: miss | ok |
| ClipF t0 at 35 (34) | 1 | ok | ok | ok | ok |
| ClipF t0 at 4 (6) | 1 | miss | ok | **miss** | ok |
| **ClipF t0 at 32 (32)** | 1 | ok | **miss** | ok | **miss** |
| total | 44 | 27 | 35 | 39 | 43 |

The candidates the brief names:

- **Plane.** ClipF-032's t0 and t1 are one planar quad: same plane, anchors
  32 and 34. Refuted.
- **Top vertex.** They share v0 as top vertex. Refuted by the same pair.
- **First covered pixel.** Same first covered row (32), different column
  (294 against 150). The row alone is refuted. The row plus the column is in
  the literal search below; no rule of up to three literals fits.
- **Whether the clip cut it** (the shipped rule, and lane.xbox's hypothesis
  that clip_top 4 does not cut t0). Geometrically, clip_top 4 does cut t0:
  its top vertex is at y = -34.31, so the clip removes 38 of its rows, and
  the hypothesis reduces to the shipped rule. That rule misses 5 of 44: four
  ClipF t1 anchors and ClipF-004 t0.

### The literal search (`--selectors`)

Every selector of the form "grid iff P", over 27 boolean geometric features
and their negations (54 literals). The features: which clip side cut it
(window clip or surface edge), flat top, top vertex inside the clip, top
vertex column inside the first span, whether the span starts or ends at the
clip, clip_top 0, dominant axis, second triangle of a QUAD, rows removed by
the clip and mod 4, the first row and anchor column mod 2/4/8/16/32, clip_top
mod 8, and whether the B quad-row (4k+2) or the A quad-row (4k) is covered at
the anchor column.

| selector size | tried | fit all 26 informative |
|---|---:|---:|
| 1 literal | 54 | 0 |
| 2 literals (AND / OR) | 2,862 | 0 |
| 3 literals (8 forms) | 198,432 | 0 |
| 4 literals, `a \| (b & (c \| d))` | -- | 333 |

- **Nine two-literal rules miss exactly one anchor, and it is ClipF-032 t0
  for all nine.** They are all the same rule written nine ways:
  `(uncut, or top vertex inside, or xtop in the first span) OR (the window
  clip's top edge cut it, or clip_top != 0, or rows removed by the clip)`.
- Of the 333 four-literal fits, **288 carry ClipF-032 t0 by their exception
  clause alone**. The remaining 45 split the same data another way: every
  quad-rule anchor at clip_top 0 goes into the exception clause, which is no
  better supported. The exception literals that do the work are
  interchangeable on every capture that exists: row or clip_top aligned to
  8/16/32, anchor column parity, column phase mod 4 or mod 8, flat top,
  "second of quad", and B quad-row coverage. Off the data, they disagree
  with one another.
- **All 333 agree on ClipF's second triangle:** 4-grid at every informative
  clip_top from 1 to 451 (checked by a scratch scan over the same
  `features()`; they first split at 452). They disagree only on its first triangle. So t1's rule is as
  settled as the brief says. What is missing is whatever puts t0 at 32
  rather than 34.

## The measurement that would find the fourth input

The exception clause needs something true for ClipF t0 at clip_top 32 and
false at clip_top 4. On ClipF's first triangle, `--selectors` prints how many
of the 333 vote grid at each clip_top. These are the literals that separate
the families:

| ClipF t0 at clip_top | 4 | 8 | 12 | 16 | 32 | 64 |
|---|---|---|---|---|---|---|
| first row, anchor column | 4, 193 | 8, 207 | 12, 222 | 16, 236 | 32, 294 | 64, 409 |
| row aligned to 8 / 16 / 32 | - / - / - | T / - / - | - / - / - | T / T / - | T / T / T | T / T / T |
| column even | - | - | T | T | T | - |
| column mod 4 < 2 | T | - | - | T | - | T |
| silicon | 6 (grid) | ? | ? | ? | 32 (quad) | ? |

**ClipF variants at clip_top 8, 12, 16 and 64** separate row alignment (8,
16 or 32), column parity, and column phase, all from their first triangle.
Each is one line in lane.xbox's existing patch
(`clip_top = (i < 3) ? ... : 35`). The first triangle survives up to
clip_top ~128, so all four have a t0 region. If all four come back and none
of these families fits, the fourth input is not geometric either. The next
things to vary would then be draw order and the primitive type, meaning t0
drawn alone or as TRIANGLES rather than QUADS.

## What the next lane should not repeat

- Do not implement "grid iff uncut OR the window clip's top edge cut it".
  It is 43/44, and the 44th is a capture that is correct today (ClipF-032
  t0, 16,801 px). The brief rules out shipping it, and so do the numbers.
- Do not re-run lane.xbox's hypothesis that clip_top 4 leaves t0 uncut.
  Geometrically it does cut it (38 rows removed).
- Do not add a literal to the search to rescue ClipF-032 t0 without a new
  capture. Any one of about a dozen will do it, and that is exactly the
  problem.
- Not done (optional in the brief): building the -035/-004 disc for an
  emulator-side check. With no selector to implement there was nothing new
  for the emulator to check. The shipped code's -035/-004 anchors can be
  read from the table above: t1 at 4 gets 4 (silicon 6), t0 at 4 gets 4
  (silicon 6), and both at 35 get 34 (right).

## Outcome

`Prediction: none: analysis-only`. psh.c is untouched. The PR carries the
extended `wbuf_anchor_recover.py` and these notes. It is blocked on the
four ClipF captures above; `[lane.wbuf31fix] blocked:` is posted on the PR
and on #31.
