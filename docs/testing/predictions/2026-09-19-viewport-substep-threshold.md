# Prediction: the Viewport sub-step rounding threshold θ

Registered 2026-09-19 on `01047cf32c` by `lane.cloud-112`, for issue #112 item 1
(and #49), **before any hardware run and before any emulator run of the discs
below**. Nothing in this file has been measured.

Derivation, and the two arguments that are already settled offline:
[`docs/investigations/2026-09-19-viewport-substep-threshold.md`](../../investigations/2026-09-19-viewport-substep-threshold.md).
The per-vertex tables it rests on are in
[`viewport-9-16-boundary.md`](../../investigations/viewport-9-16-boundary.md).

**This prediction registers no arm and queues nothing.** It names no `a_ref`
or `b_ref` and no golden key, because **every capture it predicts is of a test
that does not exist yet**: it needs `viewport_tests.cpp` extended with seven
offsets, and a golden set produced on silicon. `request.sh` would correctly
refuse a key matching no golden. It is a registered expectation, not a queued
A/B, and it is written now so that whoever runs the disc scores against this
table instead of rewriting it.

---

## 0. The quantity

**θ** is the threshold, in units of one 1/16 step, at which the NV2A's
reduction of a screen coordinate to four fractional bits rounds **up**:

    k = floor(pos * 16);  snap = (k + (pos*16 - k >= θ)) / 16

| model | θ | status |
|---|---|---|
| **T** -- truncation, this tree's model (`glsl/vsh.c:548`) | **1** | incumbent |
| **R** -- #112's "the rounding threshold is 9/16" | **9/16** | untested; invisible in the whole corpus |
| **H** -- round-half-up | 1/2 | **already refuted on silicon**: the `+17/32` golden renders `LOW`, and this tree measured θ = 1/2 at ~820,000 px across five suites |
| **S9** -- "9/16" read as a *sample position* rather than a threshold | n/a | **already refuted by the goldens**, offline; see §5 |

So the run measures θ over **(1/2, 1]**, and T and R are two points in it.

## 1. The run this binds

`viewport_tests.cpp` sweeps `NV097_SET_VIEWPORT_OFFSET` and draws four
fixed-function quads at integer screen x = 120, 220, 320, 420, 520 and
y = 140, 240, 340. Seven offsets are **added** to the existing twelve; nothing
else about the test changes, and the existing twelve are re-run in the same
session as the validity gate.

| id | offset (exact) | `offset*16` | remainder of a step | why |
|---|---|---:|---:|---|
| **D1** | **+0.548828125** (281/512) | +8.78125 | **25/32** | primary discriminator: the window's midpoint |
| **D2** | +0.53515625 (137/256) | +8.5625 | **9/16** | θ = 9/16 exactly: inclusive vs exclusive |
| **D3** | +0.5390625 (69/128) | +8.625 | 5/8 | ladder rung |
| **D4** | +0.55859375 (143/256) | +8.9375 | 15/16 | ladder rung |
| **D5** | −0.451171875 (−231/512) | −7.21875 | 25/32 | D1's negative twin -- direction control |
| **D6** | +1.548828125 | +24.78125 | 25/32 | D1 translated by one pixel -- invariance control |
| **C1** | +0.234375 (15/64) | +3.75 | 3/4 | a large remainder **outside** the window. Must not move under any θ |

Offsets are given exactly because they must be transcribed as literals; all
seven are dyadic and exact in fp32. The suite names a capture from its own
`printf`, so the golden keys will be `Viewport/<offX>_<offY>-<sclX>_<sclY>`
with the offsets printed to three places -- **the exact spelling is the
suite's, not this file's**, and must be read off the run rather than assumed.

Scale is 0 throughout. `VPSCL` is inert in this configuration on both sides
(the five existing scale-2.0 twins are bit-identical to their scale-0 twins in
gold and in ours), so a scale-2.0 twin of any offset here carries nothing and
should not be added.

## 2. What each model predicts, per capture

Read as the first covered pixel of a left edge whose nominal position is the
integer n, in `viewport-9-16-boundary.md`'s vocabulary: **`LOW`** = the snap
dropped to 8/16 and pixel n is covered; **`HIGH`** = the edge stayed at 9/16
and pixel n is not.

| | **T** (θ=1) | **R** (θ=9/16) | **R'** (θ=9/16, exclusive) |
|---|---|---|---|
| existing `+17/32` (remainder 1/2) | `LOW` | `LOW` | `LOW` |
| **D2** (9/16) | `LOW` | **`HIGH`** | `LOW` |
| **D3** (5/8) | `LOW` | **`HIGH`** | **`HIGH`** |
| **D1** (25/32) | `LOW` | **`HIGH`** | **`HIGH`** |
| **D4** (15/16) | `LOW` | **`HIGH`** | **`HIGH`** |
| existing `+9/16` (1) | `HIGH` | `HIGH` | `HIGH` |
| **D5** (25/32, negative) | first covered n−1 | **first covered n** | **first covered n** |
| **D6** (25/32, +1 px) | n+1 | **n+2** | **n+2** |
| **C1** (3/4, remainder outside the window) | n | n | n |

More usefully, because it needs no arithmetic at scoring time:

> **Under T, D1's four fixed-function quad extents are exactly the existing
> `+17/32` capture's.**
> **Under R, they are exactly our current render of `+9/16`** -- not the
> `+9/16` *golden*, which carries #49's HIGH/LOW split and is a different
> picture.

**Do not compare those frames by hashing the whole image.** Each capture
prints its own offset into the frame, so two captures at different offsets
differ in the label rows whatever the rasteriser did -- the failure that cost
#43 three readings. Compare the fixed-function extents;
`docs/testing/probe_viewport_ff_extents.py` already reads exactly those, run
by run, as whole 99-100 px runs rather than point samples, and its `SWEEP`
table is where the seven offsets above are added.

### Must-move / must-not-move, stated per model

| | **must move** (differs from this tree's render) | **must not move** |
|---|---|---|
| **T** | nothing | D1-D6, C1, and all twelve existing |
| **R** | **D1, D2, D3, D4, D5, D6** -- each by one pixel on every fixed-function edge | **C1, and all twelve existing**, bit-identical |
| **R'** | D1, D3, D4, D5, D6 | **D2**, C1, and all twelve existing |

The pair that cannot both be satisfied by a trivial answer: **R requires D1 to
move and C1 not to.** A grid change, a different sample point, or any constant
bias moves C1 too, or moves one of the twelve; nothing that moves D1 alone is
available except θ.

## 3. Emulator-side companion -- no hardware, and it is the positive control

These need only the extended disc and the desktop lane under lavapipe. They
are derived by reading `glsl/vsh.c:548`, not measured, and they are registered
so that reading can be scored.

| | prediction |
|---|---|
| **E1** | Our renderer puts **all seven new captures in the T column**: D1-D4 with the same fixed-function extents as our `+17/32`, D5 one pixel left of them, D6 one pixel right, C1 unmoved |
| **E2** | Our D1 and our `+17/32` have **identical fixed-function extents** on all four quads, and our D1 and our `+9/16` do **not** |
| **E3** | Our twelve existing captures are unchanged by adding the seven -- the suite is not order-dependent within itself at these offsets |

**E2 is the instrument's control, and it is the reason to run the emulator
half first.** If a new offset lands in neither column, the disc is not
programming `VPOFF` with the value this file names -- an fp32 literal
mistyped, or a `%.3f` name colliding with an existing capture -- and every
hardware reading from that disc is void before it is taken. Stated the way
this repository asks for: *if θ were 9/16 in our renderer, E1 would show D1
with our `+9/16` extents; it will not, because our renderer truncates.*

## 4. Falsifier: which offsets carry no information, and why

The expensive part is silicon time; offsets are free. So this is the half
worth registering in advance.

1. **Any offset whose `floor(offset*16) mod 16` is not 8.** Coverage changes
   only where the snapped edge crosses a pixel centre, and on a 1/16 grid the
   only crossing is 8/16 -> 9/16. C1 has a remainder of 3/4 -- well past every
   candidate θ -- and **T and R still render it identically**, because the snap
   moves from 3/16 to 4/16 and no sample lies between. This is the obvious
   family to reach for and it buys nothing. C1 is in the set only as the
   control that proves it.
2. **Any offset exactly on the 1/16 grid.** Remainder 0, so every θ is the
   identity. That is exactly what both of #49's failing offsets are, which is
   why they cannot see this and why re-running them settles nothing about θ.
3. **Any remainder at or below 1/2.** Already answered on silicon by the
   `+17/32` golden. A second such offset is a second measurement of a bound
   that is not in doubt.
4. **Any scale-2.0 twin.** Inert on both sides across all five existing pairs.
5. **A denser ladder than five rungs.** Rungs cost one capture each and the
   useful range is 1/32 of a pixel wide; below about 1/512 px the transform's
   own last bit (§6) dominates and a finer rung measures that instead of θ.

So the capture budget is: **D1 first** -- it is the single capture that splits
T from R with the largest margin from both. Then C1, which is what makes D1's
movement readable. Then D2 (inclusive vs exclusive), then D3/D4 to localise θ,
then D5 and D6 as the direction and translation controls.

## 5. What this run cannot decide, and what is already decided without it

**Already decided, offline, and not worth silicon time:**

- **S9** -- "9/16" read as the rasteriser's sample position rather than as a
  rounding threshold. It moves coverage only where the snapped edge's position
  *within its own pixel* is exactly 9/16, which on this sweep is #49's two
  captures (`+9/16` and `−7/16`, whose edges sit at `n + 9/16` and `n − 7/16`
  and so share that fractional position) and nothing else,
  and it predicts **every vertex `LOW`** in both. Gold has x = 120 and x = 220
  `HIGH` there. S9 is the same frame as the small negative pre-snap bias
  `viewport-9-16-boundary.md` already priced at **888 px** against today's
  1,396. Refuted, with a number, by data on disk.
- **θ = 1/2.** See H in §0.

**Not decided by any value of θ:** #49 itself. Both T and R predict all nine
vertices `HIGH` at `+9/16` and `−7/16`; gold splits them 2 `HIGH` / 7 `LOW`
with two vertices carrying the same post-offset coordinate resolving in
opposite directions. No rule on the coordinate does that, whatever θ is. A
result of θ = 9/16 would mean this tree has a second, independent defect on a
1/32-wide band of viewport offsets **and** would leave #49 exactly where
`viewport-9-16-boundary.md` left it: in the reciprocal-versus-divide of the
fixed-function transform.

**Blast radius of θ = 9/16, if it is true, stated as the bound it is.** The
snapped *value* would differ from ours for any coordinate whose sub-step
remainder is ≥ 9/16, i.e. 7/16 = 43.75% of coordinates. The *coverage* would
differ only where that coincides with the 8/16 -> 9/16 crossing:
7/256 = **2.7% of edge coordinates**. The second number is the observable one;
the first bounds nothing visible on its own and must not be quoted as though
it did.

## 6. Validity gates -- what voids the session

| | gate |
|---|---|
| **V0** | The twelve existing offsets, re-run in the same session on the same binary, must reproduce the 2026-09-09 `goldens/results/Viewport/` set **bit-identically outside the label rows**. They are predicted unchanged by T, by R and by R'. A difference there means the rig, the display mode or the test build is not the one that made the goldens, and no new capture from that session is readable |
| **V1** | **C1 must not move.** If it does, the mechanism is not a sub-step threshold at all and §2's whole table is void rather than partly wrong |
| **V2** | Within one capture, the five x vertices (120, 220, 320, 420, 520) must all read the same column. A split means the transform's own last bit exceeds this probe's 0.01367 px margin -- see §7 -- and the ladder must be re-run at coarser spacing. **That split is itself the measurement #49 wants**, so record it rather than discarding the run |
| **V3** | The programmable quads must sit at their offset-0 extents in all seven new captures, as they do in all twelve existing ones on both sides. They do not take `VPOFF`; if they move, the disc is changing something this file did not name |

## 7. Known risk to the run

**R1 -- the transform's last bit.** D1 asks about 1/256 px.
`viewport-9-16-boundary.md` puts the true vertices "within a few ULP of n"
(~1e-4 px near a coordinate of 320) and separately reports its CPU
replication's own fp32 unproject contributing 0.005-0.010 px where that
replication dominates -- a figure that document concludes bounds *the model*
rather than the silicon. D1 sits `7/512 = 0.01367 px` from θ = 9/16 and the
same distance from θ = 1, which clears the first figure by two orders of
magnitude and the second by 1.4x. V2 is what detects the case where the
pessimistic figure was the right one.

**R2 -- the printed label.** Every capture carries its own offset in white.
Two offsets three decimal places apart could collide in the printed name and
overwrite each other's golden; D2 (`0.535`), D3 (`0.539`), D1 (`0.549`) and
D4 (`0.559`) are distinct at three places, and the suite's rounding of
`0.5625 -> 0.562` and `-0.4375 -> -0.438` says it rounds half to even, so no
new offset collides with an existing one. Read the label before believing any
diff.

## 8. Outcome

Not run. No hardware, no disc, no emulator run of the extended sweep. This
section is left for whoever runs it, and the rule that applies is the one that
applies to every prediction here: score against §2 rather than rewriting §2 to
match what came back.
