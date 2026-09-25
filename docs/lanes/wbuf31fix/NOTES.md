# lane.wbuf31fix NOTES (#31)

## Attempt 2, 2026-09-25: silicon answered, and a selector now fits

**Why attempt 1 stopped.** It did not run out of turns. It stopped by design,
blocked: no selector of three or fewer literals fitted, and the best rule
missed ClipF-032 t0, which is correct today (see "Attempt 1" below). It asked
for ClipF at clip_top 8, 12, 16 and 64. lane.xbox measured them on the console
(PR #226, `/home/justin/hakux-work/hardware/runs/2026-09-25-wbuf31-t0`).

Base: merged origin/master @ 82e460e863 as `1883f0fd52`, which is `a_ref`.
The fix is `63a24f9834`, which is `b_ref`.

### The fit over 52 anchors

`wbuf_anchor_recover.py` now lists ClipF at 4, 8, 12, 16, 32, 35, 64, 128 and
224 in `PRIMS`. To reproduce, pass all four roots:

    python3 docs/testing/wbuf_anchor_recover.py \
      --goldens /home/justin/goldens/results \
      --goldens .../2026-09-25-wbuf31-clipf35/console-run/console \
      --goldens .../2026-09-25-wbuf31-clipf04/console-run/console \
      --goldens .../2026-09-25-wbuf31-t0/console-run/console --selectors --simulate

- 52 anchors (LargeZ and TriV excluded), 34 of them informative. 0 fit
  neither rule.
- 1, 2 and 3 literals: 0 fits among 201,348 selectors.
- 4 literals, `a | (b & (c | d))`: **93 fit.** lane.xbox counted 75 with the
  same tool at `37192979a2`. This lane did not chase the difference, because
  the conclusion below holds for every one of the 93.
- **All 93 give the same anchor on every existing capture, and at every
  informative ClipF clip_top from 1 to 127** (the tool's own scan). No existing golden separates them, so the arm has
  no discriminator among them. The only split is TriV, where 3 of the 93
  (the `c%8<4` ones) vote differently. That split is on the column, and TriV
  has pb == 0, so no rule that edits the row can reach it.

What each anchor needs (y-dominant only; x-dominant anchors are columns and
stay on the 2x2 snap in every rule):

| observation | clip_top | silicon row | needs | cut by |
|---|---|---|---|---|
| TriH x24 | 0 | 4k+2 | grid (12 informative) | nothing |
| FloorQuad t0, t1; RoofQuad t0 | 0 | 0 | quad | surface edge |
| ClipF t1 | 4, 8, 12, 16, 32, 35, 64, 128, 224 | 4*floor(ct/4)+2 | grid | window clip top |
| ClipF t0 (flat-topped) | 4, 12 | 6, 14 | grid | window clip top |
| ClipF t0 (flat-topped) | 8, 16, 32, 64 | ct | quad | window clip top |
| ClipF t0 | 35 | 34 | either | window clip top |

### The chosen selector, and why

    grid = !cut || (topCut && !(flatTop && clip.y % 8 == 0))
    topCut = clip.y > 0 && ytop < clip.y        (the window clip's own top edge)

It is one of the 93, in the family
`!cut | (cut_top_by_clip & (!flat_top | !ct%8==0))`. Reasons for choosing it:

1. **It keeps the shipped term.** `!cut` is the rule measured on 24 TriH
   triangles. The new clause adds only what silicon forced.
2. **Its mechanism is about the clip edge, as the brief asked.** "Which edge
   made the first row" separates the surface edge (Floor/Roof, 2x2 snap) from
   the window clip's top (ClipF, 4-grid). The exception is "the window clip's
   top is 8-row aligned", which is a property of the clip rect, not of the
   anchor column. The `r%8` twins are the same rule on these data (r == ct
   for every ClipF t0 that has a vote). I took `ct` because a clip rect is
   what a coarse-tile rasteriser would align to.
3. **Its inputs are ones the shader already has.** It needs the three
   vertices and the clip rect, and nothing from the span walk. Two rivals fail
   here: `second_of_quad` (which half of a QUAD) cannot be seen from three
   vertices, and `B_quad_covered_at_c` / `span_starts_at_clip` depend on the
   traversal-derived anchor column.
4. **Real games see it least.** With no window clip, region 0 is the whole
   surface, `clip.y` is 0, `topCut` is false, and the behaviour is exactly
   the shipped code's. The new clause fires only on a triangle cut by a
   window clip whose top edge is below row 0.

**Weakest part: `flatTop`.** It is interchangeable with `span_starts_at_clip`,
`B_quad_covered_at_c` and `second_of_quad` on every capture that exists: all
four separate ClipF t0 from t1, and nothing else tests them. **The silicon
capture that would separate them:** ClipF with clip_left 300 at clip_top 8.
There t0's first span starts AT the clip, so `span_starts_at_clip` would vote
grid (row 10) while `flatTop` votes quad (row 8). This is a one-line change to
`wbuf31_clipf_phase.patch` (clip_left for one variant). This lane has not
requested it.

`wbuf_anchor_recover.py` has the rule as anchor mode `sel`, scored in the
summary line (`sel ... reproduces 52/76`; the 24 misses are all TriV, which
every rule misses) and in `--simulate`.

### Offline prediction (float32 emulation, `--simulate`, WBuf24D ZB0)

exact / +-1 / wrong, per capture. `row4` is the code on master.

| capture | row4 (master) | sel (this change) |
|---|---|---|
| ClipF-150-032 (golden) | 281 / 16,520 / 189,489 | 162,240 / 44,050 / 0 |
| ClipF-150-128 (golden) | 0 / 0 / 159,250 | 134,750 / 24,500 / 0 |
| ClipF-150-224 (golden) | 0 / 0 / 112,210 | 97,510 / 14,700 / 0 |
| ClipF-150-004 (console only) | 0 / 0 / 220,010 | 67,391 / 152,619 / 0 |
| ClipF-150-008 (console only) | 21,093 / 5,097 / 191,860 | 21,093 / 180,357 / 16,600 |
| ClipF-150-012 (console only) | 0 / 0 / 216,090 | 23,546 / 192,544 / 0 |
| ClipF-150-016 (console only) | 13,056 / 9,774 / 191,300 | 117,657 / 96,473 / 0 |
| ClipF-150-064 (console only) | 4,553 / 2,960 / 183,097 | 113,941 / 76,669 / 0 |
| every other capture | unchanged | unchanged |

The +-1 remainder depends on one float32 ULP of the offset in the driver, so
the arm's pixel counts are prose bands. The decisive leg is M in the
prediction: the recovered t1 offsets must land within 1.0 of hardware's
intervals. ClipF-008 still has 16,600 "wrong" pixels in the emulation, even
though its anchor is right. That capture is not on the golden disc, so the
arm cannot read it. It is worth a look if the optional variant-disc run below
ever happens.

### The arm

`docs/testing/predictions/wbuf31fix-topcut-grid.json`, a `1883f0fd52` ->
b `63a24f9834`. Movers: the three ClipF depth captures, each predicted to
improve by at least half (must_not_regress, plus prose sizes). Guards: eight
must_not_move globs, each tied to the patch change that would move it
(Floor/Roof: the `clip.y > 0` guard; TriH: the `!cut` term; TriV/Wall/ClipW:
a leak into the column; ZS0/Depth_Clamp: a broken emitted shader). ZBuf*,
LargeZ, LineStrip and the non-W blast-radius suites were dropped, with the
reason in the prediction.

### Not done, and what the next lane should know

- **glslc was not permitted in this sandbox,** so the emitted GLSL has only
  been checked by reading it (`.scratch/emit_wbuf.py` extracts it; scratch,
  not committed). The ZS0 and Depth_Clamp legs catch a compile error.
- The optional emulator-side check of the -035/-004 variants was not built.
- `wbuf31_blocker_audit.py` and `wbuf_clip_phase_choice.py` produce
  byte-identical output against master's tool and this one.
- Do not "tidy" `flatTop` into `second_of_quad`: the shader cannot see it.
- The nv2a index was regenerated (`979d57c41e`), and only psh.c sites moved.
  preflight passes.

### State at the end of attempt 2: waiting

PR #222 is in draft. It is waiting on two things: CI on the head, and the
arms job's `[job.arms]` verdict for `wbuf31fix-topcut-grid.json`. On resume,
read the verdict and run `wbuf_anchor_recover.py --ours <arm B result>` for
leg M. Then mark the PR ready if M holds and no guard moved. If M fails, read
it as a diagnosis first; do not revert on reflex.

---

## Attempt 1, 2026-09-24, master @ 76e973ebeb

Brief: find the selector between the 2x2-quad anchor snap and the absolute
4-grid (phase 2), prove it offline against every recovered anchor, then
implement it in `wbufSlopeStep`.

### Result (superseded by attempt 2): no selector fitted the 44 anchors of the time.

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
