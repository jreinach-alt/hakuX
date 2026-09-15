# #49: the two `Viewport` offsets at n + 9/16

Written 2026-09-12 against the Adreno capture set
`hakux-work/res_Viewport/` (mtime 08:41 today, APK `baab83e2b733`) and the
hardware goldens `goldens/results/Viewport/` (Sep 9). Both sets are newer
than the last change to the vertex path, so neither is stale.

**Result: no change available in `glsl/vsh.c`, `glsl/vsh-ff.c` or
`glsl/vsh-prog.c` can fix these two captures.** The snap grid, the snap
direction, the sample point and the fill rule are all pinned exactly by the
ten captures that pass, and the two that fail need two vertices carrying the
*same* post-offset coordinate to resolve in *opposite* directions. That is
not expressible as a rule on the coordinate. The residual lives one step
upstream, in the last bit of the fixed-function transform, where hardware
uses a reciprocal and we use a divide.

This supersedes nothing in `edge-defect.md`; it is the same conclusion
reached from a per-vertex measurement instead of a CPU replication, plus a
number for the best rule-shaped change anyone could ship.

## What the test draws (relevant structure only)

`viewport_tests.cpp` lays eight 100 px quads in two rows of four, at screen
x = 120, 220, 320, 420, 520 and y = 140, 240, 340. Four quads are drawn
through a programmable shader carrying its own D3D-style viewport, then four
through the fixed-function pipeline, in this arrangement:

| band | 120–220 | 220–320 | 320–420 | 420–520 |
|---|---|---|---|---|
| y 140–240 | prog q0 | **FF q1** | prog q2 | **FF q3** |
| y 240–340 | **FF q4** | prog q5 | **FF q6** | prog q7 |

Each corner is built by unprojecting an integer screen point through the
inverse composite matrix, so the fixed-function pipeline projects it back to
(within rounding of) that integer. Top corners sit at world z = 10 and
bottom corners at z = 0, so the two vertices that share a screen coordinate
across a band boundary have different w. FF is drawn last, so the FF colour
0xFF0033BB is the exact extent of FF coverage and the prog quads are eroded
where FF overlaps them.

`SetXDKDefaultViewportAndFixedFunctionMatrices` puts the whole viewport
transform in the projection matrix, sets `VPSCL` to zero and `VPOFF` to
0.53125; the test then overwrites `VPOFF` with the swept value. The five
captures with scale 2.0 render identically to their scale-0 twins on both
sides, so `VPSCL` is inert in this configuration — consistent with our
shaders never reading it.

## MEASURED: the per-vertex table

Both failing offsets are ≡ 9/16 (mod 1): +9/16 and −7/16 = −1 + 9/16. So at
every FF vertex the post-offset coordinate is exactly n + 9/16 — one snap
step above the sample at n + 0.5, and exactly *on* a 1/16 grid line, where
`trunc(pos*16)/16` is the identity. Coverage is therefore decided entirely
by whether the transform output is ≥ n or < n. Writing HIGH for ≥ n (the
edge stays at n + 9/16, pixel n uncovered on a left edge) and LOW for < n
(the snap drops it to n + 8/16, pixel n covered):

| vertex | gold | ours |
|---|---|---|
| x = 120 | HIGH | HIGH |
| x = 220 | HIGH | HIGH |
| x = 320 | **LOW** | HIGH |
| x = 420 | **LOW** | HIGH |
| x = 520 | **LOW** | HIGH |
| y = 140 (z = 10) | LOW | LOW |
| y = 240 (z = 0) | **LOW** | HIGH |
| y = 240 (z = 10) | LOW | LOW |
| y = 340 (z = 0) | LOW | LOW |

Read off the FF extents in both captures, which agree with each other
vertex for vertex on both sides
(`docs/testing/probe_viewport_ff_extents.py` reproduces the whole table from
the PNGs; regions, not point samples — every extent below is the end of a
full 99–100 px run of one colour along a scan line that crosses only the
quads being measured):

| offset | quad | nominal | gold | ours |
|---|---|---|---|---|
| +9/16 | q1 | x 220–320 | x **221..319** | x 221..320 |
| +9/16 | q3 | x 420–520 | x **420..519** | x 421..520 |
| +9/16 | q4 | x 120–220 | x 121..220 | x 121..220 |
| +9/16 | q6 | x 320–420 | x **320..419** | x 321..420 |
| +9/16 | q1 | y 140–240 | y **140..239** | y 140..240 |
| +9/16 | q4 | y 240–340 | y 240..339 | y 240..339 |
| −7/16 | q1 | x 220–320 | x **220..318** | x 220..319 |
| −7/16 | q3 | x 420–520 | x **419..518** | x 420..519 |
| −7/16 | q4 | x 120–220 | x 120..219 | x 120..219 |
| −7/16 | q6 | x 320–420 | x **319..418** | x 320..419 |
| −7/16 | q1 | y 140–240 | y **139..238** | y 139..239 |
| −7/16 | q4 | y 240–340 | y 239..338 | y 239..338 |

The HIGH/LOW distinction only means anything at these two offsets. At 0,
±17/32 and ±1 the two hypotheses predict the same coverage — that is exactly
why those ten captures cannot see this — so the probe's labels for them
carry no information and only their gold-equals-ours verdict does.

698 px per capture, `max_rgb` 224, nothing within one step: the differing
pixels are whole 99-px columns and 100-px rows where a quad edge lands one
pixel over, plus the backdrop (0xFFE0E0E0) exposed or covered behind it.

Note q1 at +9/16: gold has its **left** vertex (x = 220) HIGH and its
**right** vertex (x = 320) LOW, in the same quad, at the same y and w. Every
vertex that two quads share carries the same direction in both (x = 220 in
q1 and q4; x = 320 in q1 and q6; x = 420 in q3 and q6), so the direction is
a property of the transformed vertex, not of the edge or the fill rule.

## MEASURED: the ten that pass pin the rasteriser exactly

Reconstructing all twelve captures from "snap to 1/16 by truncation, sample
at pixel + 0.5, left and top edges inclusive, pre-snap value = n + offset"
reproduces gold's extents in all ten passing captures and both of ours, for
every edge of every quad, at offsets 0, ±17/32, ±1 and both scales. In
particular ±17/32 rendering identically to 0 needs truncation (17/32 → 8/16)
and the +0.5 sample; round-half-up or any other sample point moves one of
the ten. The grid size is bracketed from both sides by the earlier
measurement in #11 (1/32 worse, 1/8 costs nine exact `Texture_render_target`
captures).

## MEASURED, by deduction from the above: no coordinate rule exists

Every candidate snap rule — truncate, floor, round, round-half-down, any
grid size, any pre- or post-snap bias, any sample point, and applying the
snap before rather than after the viewport offset (9/16 is on the grid, so
the two orders are identical here) — is invariant under integer translation
of its input. Gold resolves 120 + 9/16 and 320 + 9/16 in opposite
directions. So no such rule reproduces gold, whatever its parameters. The
three shader files own nothing but such a rule.

The strongest rule-shaped change available is a tiny negative pre-snap bias
(0 < ε < 1/32), which is invisible in the ten passing captures — it drops
every grid-exact value one step and every passing offset has ≥ 1/32 of
margin — and turns every vertex LOW in the two failing ones. That makes
+9/16 render exactly as offset 0 does and −7/16 exactly as −17/32 does, and
both of those renders are already bit-identical to their own goldens, so the
residual is computable without a device:

| | current | with the bias |
|---|---:|---:|
| +9/16 | 698 px | **428 px** |
| −7/16 | 698 px | **460 px** |
| total | 1,396 px | **888 px** |

It fixes x = 320/420/520 and y = 240, breaks x = 120/220, and leaves 64 % of
the pixels. A correct mechanism would collapse this to zero; a 36 %
reduction with two new wrong vertices is the signature of the wrong one. Not
shipped.

## INFERRED: where the last bit comes from

Extending the earlier CPU replication (`docs/testing/viewport_ff_roundtrip.py`
on branch `claude/docs-tooling-agentic-coding-u152m1`) with an exact
rational evaluation of the forward transform: where that model's own fp32
unproject contributes little it puts the vertices +1.1 to +2.3 ULP above n,
which is the direction we measure; where its unproject dominates it puts
them 300–1,400 ULP (0.005–0.010 px) below n, and there it contradicts both
hardware and us. So the model's world coordinates are wrong at those
vertices — the Xbox toolchain keeps x87 intermediates through
`UnprojectPoint` — and the true vertices sit within a few ULP of n, with the
sign set by the GPU-side transform.

The structural difference at that magnitude: our fixed-function path does a
correctly-rounded fp32 division, `oPos.xy /= oPos.w` (`vsh-ff.c:677`), so a
true quotient within half an ULP of an integer returns that integer exactly
— which is why we are HIGH at all five x. The NV2A vertex ALU has no
divide; it has an RCP of limited precision followed by a multiply, whose
relative error at 2⁻²² is a few ULP of a coordinate near 320, enough to land
below it. Modelling it would require the NV2A reciprocal's rounding, which
is not characterised; and a uniformly low reciprocal predicts every x LOW,
i.e. the 888 px above, not zero.

## Ruled out

- **A different snap grid, direction, or sample point.** Bracketed by the
  ten passing captures (above) and by #11's 1/32 and 1/8 measurements.
- **Snapping before the viewport offset instead of after.** Arithmetically
  identical at these offsets: 9/16 is exactly on the grid.
- **A half-pixel convention missing from one of the two paths.** The prog
  quads sit at their offset-0 extents in all twelve goldens and in all
  twelve of our captures, and every FF extent in the ten passing captures is
  gold-exact, so the FF-adds-`VPOFF`/prog-does-not split and the absence of
  any half-pixel term in either path are both confirmed to the last visible
  bit. A constant bias of half a pixel, or of anything ≥ 1/32, moves the ten.
- **`VPSCL`.** Inert here on both sides; the five scale-2.0 captures are
  identical to their scale-0 twins in gold and in ours.
- **Host or lane.** #11 measured the same two captures failing on lavapipe
  (600 non-precision channels) and Adreno (698 px each); this set is Adreno.
- **A stale capture or golden.** Captures 2026-09-12 08:41, goldens Sep 9,
  both newer than the last vertex-path change.
- **Cross-test contamination.** The two failures are the two offsets ≡ 9/16
  (mod 1) wherever they sit in the disc's order, and the other ten are
  bit-identical in the same run.

## What would move them

A disc that sweeps a fixed-function vertex across n + 9/16 ± 2⁻ᵏ and reports
which side each lands on, which characterises the NV2A transform's rounding
directly instead of guessing it. Same recommendation as `edge-defect.md`;
this document adds the per-vertex table such a disc has to reproduce, and
the 888 px figure that says a rasteriser constant is not the answer.

Until then #49 is `unmodelled-hardware` at 1,396 px across two captures, and
the three vertex-shader generator files are not where it lives.
