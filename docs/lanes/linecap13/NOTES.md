# lane.linecap13 -- #13's cap/join residual

Brief: give `emit_line()` in `glsl/geom.c` correct cap geometry against the
goldens' `Line_*` captures, without moving the exact-extent cuts already
proven.  Base: master @ `38385b79c1`, merged forward to `415dcc6997`.

## Why attempt 1 did not finish

It did the work and did not publish it.  At the end of attempt 1 the shader
change was committed locally as `7ce57a799b` and **never pushed**, PR #141 was
left in **draft** with `Prediction: pending` in its body, and this file still
showed three unticked boxes that the commit had in fact done.  From outside
that is indistinguishable from a lane that got nowhere: `board.sh:107`,
`fleet.py` and `fold.sh` all skip drafts, so the PR sat.

Attempt 1 also ended waiting on CI, which is not a thing to wait for here --
CI was green on `c208fdfb78` before the session ended.  The one real defect it
left behind is the next section.

## What attempt 2 changed

1. **`geom_dump/build/` was committed** -- two generated `.c` files carved out
   of the tree, three `.o`, and an 82 KB binary.  `make` regenerates all six
   from `glsl/geom.c`, so a stale copy on disk reads exactly like the
   generator's current output.  `psh_differ`, which `geom_dump` is modelled
   on, ignores its `build/` for that reason; `geom_dump` now does too.
   `make clean && make run` rebuilds from nothing and prints all six cases.
2. **`line_cap_phase.py --vs-goldens`** added -- the leg the arm is scored on
   (whole-capture ink mismatch of a capture set against the goldens).  It was
   uncommitted in the worktree at the end of attempt 1.
3. **The predicted device number was wrong, and is now measured.**  See below.

## Where the residual was

`line_extent_phase.py --reconstruct` reproduces on this base, unchanged:

    48 captures, 1967133 golden ink px, 14 pixel-exact in coverage
      derived          495 mismatched px = 0.0252%
      ours           59605 mismatched px = 3.0300%

493 of the 495 are ours-only and sit within `w/2 + 2` of a vertex.  The
residual is concentrated at even integer widths (56 -> 32 px, 58 -> 35,
60 -> 41, 62 -> 45) against odd ones (57 -> 11, 59 -> 14, 61 -> 14, 63 -> 17),
which is the first sign that a *tie* rather than a shape is at stake.

## What the goldens say the cap is

Read off `docs/testing/line_cap_phase.py --anatomy` / `--corners`, and
confirmed pixel by pixel on four corners with `line_cap_map.py`.

The extent band and the perpendicular butt cap are both right.  What is
missing is a third constraint, and it is axis-aligned in the MINOR axis: the
footprint never reaches further, on the minor axis, than the endpoints' own
minor coordinates extended by **w/2** -- the line width, not the widened
extent `E` -- rounded OUTWARD to whole pixel indices:

    minor index i is lit only if   floor(m_min - w/2) <= i <= ceil(m_max + w/2)

with `m_min`/`m_max` the smaller/larger of the two endpoints' minor
coordinates on the same 1/16 grid the extent rule already uses.

It bites only at the two tips of the parallelogram, which is exactly where
the residual was: inside the segment the `E`-band and the perpendicular slab
are both tighter, so the constraint changes nothing there.

### The four corners it was read from (Line_0063.7, w = 63.875, w/2 = 31.9375)

| edge | side | endpoint minor | golden's outermost lit index | `floor`/`ceil` of m -+ w/2 |
|---|---|---:|---:|---:|
| Quad0  | low  | 388.0 | 356 | `floor(356.0625) = 356` |
| Quad3  | low  | 160.0 | 128 | `floor(128.0625) = 128` |
| LLoop4 | low  | 287.0 | 255 | `floor(255.0625) = 255` |
| QStrip3| high | 287.0 | 319 | `ceil(318.9375) = 319` |
| Poly3  | high | 477.0 | 509 | `ceil(508.9375) = 509` |
| LLoop0 | high | 356.0 | 388 | `ceil(387.9375) = 388` |

The low and the high side disagree by exactly one pixel at the same |slope|
and the same width (LLoop0 reaches 32.5 px past its endpoint, LLoop4 stops at
31.5), which is what forces the *outward* rounding rather than a centre
sampled band.

**Corrected in remediation, and the correction is why every figure below now
names its instrument.**  This paragraph used to say the centre-sampled band
scores 497 px against "the 412 px it was meant to fix", and `geom.c`'s comment
said 497 against 495.  Re-run on this tree, `--rivals` says:

| variant | mismatched px |
|---|---:|
| `perp` -- no cap clip at all | 495 |
| `pen ceil` -- **the shipped rule** | **102** |
| `pen` (`floor1`) -- the nearest rival | 115 |
| `pen floor` | 261 |
| `pen, centre band` -- the obvious reading | 645 |

So the centre-sampled band scores **645**, not 497, and the number it is worse
than is 495, not 412.  497 and 412 reproduce nothing on this tree and are
retired.  `--rivals` is the ANALYTIC MODEL with no tie bias; the polygon
rasterisation at the device's 1/256 bias is a different instrument with
different numbers (935 -> 544), and the two must never be quoted into one
sentence.

## The tie bias decides which offline number is the device's

This is the thing attempt 1 got wrong, and it would have been registered as a
prediction had this attempt not checked it.

The clip is scored offline by rasterising the polygon `emit_line()` emits and
XORing it with the golden ink.  That rasterisation takes a **tie bias**, and
attempt 1 measured at an epsilon bias to isolate the geometry:

    tie = 1e-9      before the cap clip  414 px     after  21 px

21 px is not a number the device can produce.  `vk/draw.c`'s
`geom_line_params()` sets `lineTieBias = 1 / (2^subPixelPrecisionBits *
surface_scale_factor)`; Adreno reports 8 bits, so at scale 1 the device pushes
**1/256**, not an epsilon.  At the bias the device actually pushes:

    tie = 1/256     before the cap clip  935 px     after 544 px
                    captures worse after: none

935 is the number to trust as arm A's predicted value, and it is corroborated
from outside this model: the extent lane measured ~908 px of whole-capture
residual on a real device arm.  A model that lands within 3% of an independent
device measurement of the same quantity is the one to quote.

So the cap clip is predicted to take the whole-capture coverage residual from
~908-935 px to roughly 544 px -- a 42% cut, **not** to near-zero.  The rest is
the tie bias interacting with the rasteriser's own vertex quantisation, which
is a separate question this lane did not open: the bias is not a free
parameter, it is worth 550-580 of the 8,890 fit-set cuts on the extent legs,
and trading those away to win coverage pixels would be a bad trade made
blind.

**The prediction is therefore registered as a BOUND (<= 600 px), not a value,**
and the bound is chosen so that it holds under either modelling of the tie:
21 px and 544 px both clear it, while doing nothing (908 px) does not.  That
is the property that makes it a discriminator rather than a formality.

## The shader draws the rule, checked rather than assumed

`line_cap_phase.py --shader` rasterises `emit_line()`'s own emitted polygon
and compares it against the model pixel for pixel, because a rule derived
offline and a shader that implements something next to it is a failure
nothing else here would catch.  The GLSL and the Python transliteration were
also read side by side this attempt: same `k`, same tie vector, the same two
`cap_clip()` calls on `floor(min(m) - w/2)` / `ceil(max(m) + w/2) + 1`, in the
same order, and the strip's zig-zag index covers the convex hexagon exactly.

`docs/testing/geom_dump` prints the GLSL the generator emits, because neither
CI job compiles it and a geometry shader that fails to compile draws nothing,
silently (audit finding L10).  All six Vulkan cases parse under glslang with
Vulkan/SPIR-V rules; the check trips on a mutant.

After the remediation all six were rebuilt from `make clean` and COMPILED
rather than merely parsed, with the NDK's own front end:

    for c in <the six>; do
      build/geom-dump --only $c |
      $NDK/shader-tools/linux-x86_64/glslc -fshader-stage=geometry \
          --target-env=vulkan1.0 -o /dev/null -
    done

Six of six clean.  `lines_smooth_zpersp_cylwrap_vk` is the case that carries
`noperspective` and `cylinder_wrap`, so it is the one that shows M2's `float t
= tl;` and H2's `cylWrap()`-adjusted `mix()` in the flat and the smooth arm
alike; `lines_flat_vk` is the one that shows H2 and M1.

## What attempt 3 changed: the pass-1 audit's remediation

`docs/audits/2026-09-19-linecap13-pass1.md` found 2 HIGH, 3 MEDIUM, 3 LOW, and
**all four HIGH/MEDIUM findings sat in the one vertex this change has to
synthesise** -- the cut point where the clip crosses a long edge.  Every one of
them was invisible to this lane's own instruments for the same reason: the
offline model scores ink MASKS, so `--rivals`, `--shader` and `--vs-goldens`
are blind to `gl_Position.z` and to every varying.  A green `--shader` and
green CI said nothing about any of them.

| # | what was wrong | what it now does |
|---|---|---|
| H1 | `line_clip_lerp()` interpolated `z` perspective-correctly | window-space depth is LINEAR in screen space: `z_clip = w * mix(za/wa, zb/wb, t)` |
| H2 | the flat arm pinned `vtxFog`, `vtxT0..T3`, `vtxPointSize` to `i0` | both arms interpolate them; only `vtxD0/D1/B0/B1` follow the shade mode |
| M1 | `vtxFogSpecial` came from the emitted index on one path and `i0` on the other | `emit_vertex_fs()` takes the flat source as its own argument; one value per footprint |
| M2 | the varying mixes always used the perspective-correct parameter | the screen fraction under `state->noperspective`, which is what that qualifier means |

**The lesson to carry, because it is a general one.**  H2 and M2 are the same
mistake: *which varyings interpolate, and by what parameter, is the qualifier
table in `glsl/common.c` -- it is not the shade mode and it is not the
primitive.*  `vtxFog`, `vtxT0..T3` and `vtxPointSize` carry `smooth` (or
`noperspective`) in EVERY shade mode.  Reading "flat shading" as "every
varying is flat" is what pinned six interpolated values to one endpoint, and
the comment that asserted it was written from the shade mode rather than from
the table.  Read the table.

**The depth had no oracle at all, so it got one.**  `line_cap_phase.py
--depth` is new: it transliterates the shipped expression AND the
pre-remediation one, and compares both against the ground truth that the
rasteriser interpolates window-space depth linearly across the parallelogram
the clip replaces.  The mutant stays inside the check on purpose -- the check
reports FAIL *about itself* if the old expression does not trip it, so a check
that discriminates nothing cannot go green.  75 cases; shipped worst |error|
1.1e-16, mutant worst 0.583, and at `wa = 1, wb = 4` it reproduces the audit's
own 0.246 / 0.320 / 0.457 against the true 0.350 / 0.500 / 0.650.

**M3 was an instrument measuring the wrong rule.**  `--controls` unioned
`cap="perp", clip=1.0` -- the centre-sampled band, which was REJECTED -- so
both of its populations described a rule nobody adopted.  It now scores
`pen=1.0, tie="ceil"`:

    pixels the shipped rule removes from the perpendicular footprint  393
      golden-dark (the clip was right)                                393
      golden-lit  (the clip was wrong)                                  0

    5,472 cap boundaries over the same captures
      landing on a whole pixel INDEX  (ceil vs floor1)   1,104 = 617 low
                                                                 + 487 high
      landing on a pixel CENTRE       (the rejected band's question) 1,038

393 closes against `--rivals` (495 - 102), and every removed pixel is one the
goldens agree should be dark -- the clip removes no lit pixel anywhere.  The
audit left open whether any golden edge can distinguish the outward rounding
from `floor + 1`, since every corner in the table above is non-integer; **it
can, on 487 boundaries**, which is what the 102-vs-115 gap is decided on.

That 487 was quoted as 1,104 until the pass-2 audit's N2: `edge_mask()`
computes the LOW bound with `np.floor()` whatever `tie` says, so only the
high side separates `ceil` from `floor + 1`.  The conclusion is the same one
-- 487 is not zero, so the goldens do select the outward rounding -- and the
number is now 2.3x smaller.  `--controls` prints both halves.

Also fixed, from the LOWs: the missing `docs/investigations/line-cap-phase.md`
citation now points at this file (L1); the comment numbers now name their
instrument (L2, above); `vk/instance.c` said 12 where the constant is 18 and
`line_cap_phase.py` called `tie="floor1"` "the measured rule" when the shipped
rule is `tie="ceil"` (L3).

**And a defect the audit did not name, found while checking H2's scenario.**
`cap_clip()` built the cut parameter with `mix(T[i], T[j], f)` on every edge,
including the two SHORT cap edges where `T[i] == T[j]`.  `mix(1, 1, f)` is
`(1 - f) + f` and is not required to be exactly 1, so a `T` of `1 - eps`
missed `emit_line_vertex()`'s endpoint early-out and synthesised a vertex at a
corner that had an endpoint's own values available.  It now takes the exact
value when the two agree.

**The prediction was refused at queue time and is re-registered.**  The arms
job posted `REFUSED` on the PR: `expect` held `C1_coverage_mismatch_px_max`,
which names no golden capture, and `request.sh`'s key gate refuses any
`expect`/`must_not_move` key that binds to nothing.  C1 is not an
`ab_compare` leg at all -- it is read off arm B's captures with
`--vs-goldens` -- so it belongs in the prose, and C2 ("nothing gets worse")
is the leg that belongs in the machine-read field, as
`expect_counts: {"worse": 0}`.  The refusal was correct and the prediction was
inert in exactly the way AGENTS.md's inert-prediction section describes.  Both
refs moved too: `a_ref` is now master's own tip, so arm A and arm B differ by
this lane's commits and nothing else, and `b_ref` names the remediated shader
rather than the pre-audit one.

## Attempt 4: the device FAIL, and the half-pixel deadband (pass-2 audit N1)

The arm ran while attempt 3 was being audited and came back
`VERDICT: FAIL` -- 32 better, **10 worse**, 124 same, against a prediction
whose machine leg is `expect_counts: {"worse": 0}`.  Eight of the ten worse
sat between `w = 4` and `w = 14`, where every instrument in this lane said not
one pixel could change, and `Line_0064.*`/`Line_FFFFFFFF` (the VOID captures
the device draws at 1.0) each moved `1,402 -> 1,401` under a `must_not_move`
glob.

**The offline model was right about pixels and wrong about geometry.**
`E/2 - w/2` being under a pixel does not stop the clip BITING: the bounds are
`floor(m_min - w/2)` and `ceil(m_max + w/2) + 1`, arbitrary reals rounded to
integers, so an overhang of a hundredth of a pixel still crosses one.  The
clip was cutting 3 to 20 of each capture's 57 edges all the way down to
`w = 0.625`, removing slivers far too shallow to contain a pixel centre.  In
double precision that is exactly inert.  On silicon the cut fraction is
`f = da / (da - db)` in float32 over a sliver-sized `da`, every emitted vertex
is then snapped to 1/256 of a pixel, and an exact corner that used to be
emitted verbatim comes back re-quantised.  That is what the eight captures
measured.

**The fix is a deadband in `cap_clip()`, and 0.5 is derived, not tuned.**  A
plane the polygon violates by less than half a pixel is not clipped at all --
the four corners are handed straight back.  The clip planes land on whole
pixel INDICES; this renderer rasterises one sample per pixel at the pixel
CENTRE (every `rasterizationSamples` under `pgraph/vk/` is
`VK_SAMPLE_COUNT_1_BIT`, and nothing in `pgraph/gl/` enables multisampling),
so the nearest sample to any bound is half a pixel away and a shallower cut
provably removes no sample.  The threshold is a property of where the
rasteriser samples, not a number fitted to these captures -- and it explains,
after the fact, why the model's first moving capture is `Line_0024.0`: the
deepest sliver per capture crosses 0.5 px between `w = 16` (0.468) and
`w = 24` (0.704).

> **Corrected in place by audit finding A1 (pass 2b): that paragraph is a
> proof with a missing hypothesis, and the hypothesis is
> `surface_scale_factor == 1`.**  The pixels the deadband is measured in are
> GUEST pixels and the samples are DEVICE pixel centres; they coincide only
> at Rendering Scale 1.  The direction is safe -- 0.5 only ever suppresses
> too much -- but "provably removes no sample" is exact at scale 1 and
> conservative above it.  See *Attempt 5* below for what it costs, and read
> that before quoting anything in this section at a scale above 1.

**`--quantise` is the instrument that can see this, because every other one
here cannot.**  It rasterises the same polygon with each emitted vertex
snapped to the 1/256 grid, and scores three legs against the UNCLIPPED
parallelogram -- master's own geometry, the arm's A side.  Run on this tree:

| | bites (of 57 edges) | exact px moved | quantised px moved |
|---|---:|---:|---:|
| every capture `w < 24`, before the deadband | 3 - 20 | 0 | 4 on 4 captures |
| every capture `w < 24`, after | **0** | 0 | **0** |
| `Line_0063.7` before / after | 32 / 26 | 40 / 40 | 41 / 41 |

    the deadband costs no pixel the exact model scores: PASS
    where the clip cannot move a sample it moves no quantised px: PASS
    the pre-deadband geometry trips that leg: PASS

The mutant lives inside the check, as `--depth`'s does: run with the deadband
at 0 and leg 2 must fail, or the check discriminates nothing.

**Read the 4 px honestly.**  The offline quantiser reproduces the CLASS of the
device's failure and not its size: it flags `Line_0000.5`, `Line_0001.0`,
`Line_0007.0` and `Line_0009.0`, and three of those four are on the device's
own mover list (`Line_0001.0` -1, `Line_0007.0` +2, `Line_0009.0` +1, and
`Line_0000.5` is one of the three captures the arm reported as PIXELS MOVED at
an unchanged score).  It does not model float32 cut arithmetic or the
rasteriser's fill rule, so it under-counts: 4 px offline against 13 captures
moved on the device.  It is a tripwire for "the clip touched geometry it had
no business touching", not a predictor of the device delta.

**What the deadband does NOT fix, stated before the next arm.**  Two of the
ten worse captures were at the wide end -- `Line_0063.0` (+2) and
`Line_0063.1` (+6) -- where the clip legitimately bites and `--quantise`
reports the same numbers with the deadband as without.  Those are the tie-bias
residual this derivation has said from the start it will not chase.  So
`expect_counts: {"worse": 0}` is retired as this prediction's machine leg and
replaced by something sharper where the remediation actually acts: every
capture below `w = 24`, plus the VOID ones the device draws at 1.0, must not
MOVE AT ALL.  Below the deadband `emit_line()` emits master's four corners in
master's order with master's values, so those captures must be byte-identical,
and `runs_per_arm: 2` is now set so `ab_compare` can tell a byte difference
from device nondeterminism -- which also answers the audit's "noise 0 is one
run per arm, not a measured zero".

**One thing the next arm should settle that this lane cannot.**
`Line_width/Fill_0032.0` moved `26,721 -> 26,715` on the failing arm, under a
`must_not_move` glob, and nothing in this lane's diff can reach it: with
`widen_lines` false the generator emits the byte-identical fill shader it
emitted before (`max_vertices = 3`, `emit_vertex()` unrenamed).  With one run
per arm there is no noise estimate to weigh that against.  Two runs per arm
will say whether it is the device or something real; the glob stays in the
prediction either way, because dropping a tripwire that fired is how a gate
stops being one.

## Attempt 5: the deadband's coordinate space (pass-2b audit A1)

Pass 2b closed N1, N2 and N3 and raised one MEDIUM: `0.5` is half a **guest**
pixel, the rasteriser samples **device** pixels, and the derivation above
treats the two as one space.  The audit is right, and it is right for the
reason it gives: `geom_line_params()` (`vk/draw.c`) works in guest pixels and
divides `lineTieBias` by `surface_scale_factor` for exactly that reason, so
`v_vtxPos.xy`, `bound` and `deep` are all guest pixels while the samples sit
`1/scale` guest pixels apart.  At the user's Rendering Scale of 2 the nearest
sample to a bound is a quarter of a guest pixel away, not half.

**Chosen remediation: the audit's option 2 -- keep `0.5`, state the
precondition, and measure the cost rather than describing it.**  Option 1
(push `0.5 / surface_scale_factor` in) is the behavioural fix and it is not
free here: all four components of `lineParams` are live, so it needs a fifth,
and the geometry push-constant range cannot grow 16 -> 20 because the vertex
range that follows holds `vec4 inlineValue[]` and needs 16-byte alignment
(`glsl/vsh.c:994-999`) -- so it is 16 -> 32, on a range `vk/shaders.c`
declares on **every** graphics pipeline layout for descriptor-set
compatibility.  That is a renderer-wide layout change to recover a fraction
of one fix, at a scale no arm in this campaign runs at
(`desktop_channel.sh` pins `surface_scale = 1`), and nothing offline or on
silicon has ever measured this rule above 1x.  Written down as a known,
one-directional limit instead, with the instrument to re-derive it.

**`line_cap_phase.py --scale-cost`** is that instrument.  Same 48 non-void
captures, with the tie bias and the subpixel grid modelled at the scale too
(both are `1 / (2^bits * scale)`), and three columns that are three different
claims:

| scale | suppressed cuts | device samples over-reached | lost |
|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 |
| 2 | 191 | 278 | **112** |
| 3 | 295 | 860 | **298** |
| 4 | 337 | 1666 | **568** |

* **suppressed** is the audit's own column -- cuts whose depth lands in
  `[0.5/scale, 0.5)` -- and 191 / 295 / 337 over 26 / 29 / 30 captures
  reproduces its 191 / 293 / 338 over 26 / 29 / 30.  The two scale-3 and
  scale-4 cells differ by two cuts because this models the tie bias at the
  scale, which the shader pushes and the audit's script held at 1/256.
* **over-reached** is what those suppressed slivers actually cover in device
  samples.  A suppressed cut is shallower than half a guest pixel, so many
  contain no sample at all and cost nothing: 191 cuts are 278 samples.
* **lost** is the one that means anything: the over-reached samples no
  *other* edge's scale-correct footprint covers either.  These captures draw
  57 edges meeting at shared vertices, so a cap sliver is often inside its
  neighbour's band and lights that sample anyway -- 278 over-reached is 112
  lost.

For magnitude: the cap rule removes 393 guest px at scale 1 (`--controls`),
whose device-sample equivalent scales with `scale^2`, so the deadband gives
up on the order of a twelfth of the clip's own work above 1x.  **It gives up
nothing at scale 1, and it can never make anything worse than master at any
scale**, since a suppressed cut emits master's own four corners.

**Which cuts happen is scale-independent, and that is the same fact from the
other side.**  The deadband does not scale, so the bite/no-bite decision is a
property of the geometry alone: measured at scales 1-4, the first capture
with a cut is `Line_0024.0` and 19 captures cut, identically, in all four.
The scale changes what a *suppressed* cut costs, never which are suppressed.

**The check inside the check.**  `--scale-cost`'s scale-1 row is a control
and is trivially zero, so the leg that does the work is the third one: every
sample the span arithmetic counts must be one `covers()` -- the rasteriser's
own inside test, a different code path -- agrees the shipped footprint
lights.  Negative-tested against a mutant of exactly the shape that bites
here, the major-axis sample index taken at `k` instead of `k + 0.5`: the
totals stay plausible (112 -> 103) and the leg reports
`FAIL -- 26 counted samples no emitted polygon covers`.  A shipped-deadband
run of that mutant would have read as a smaller, tidier finding.

**Nothing this remediation touches can move the pending arm.**  `geom.c`'s
change is comment-only and `line_cap_phase.py` runs offline, so the emitted
GLSL is byte-identical to `36e85c96c9`'s -- checked rather than asserted, by
building `geom_dump` twice (`make GLSL=<dir> BUILD=build-head`, so the real
path is never swapped) against this tree and against `4cc0d26dc0`'s
`glsl/geom.c` and diffing all ten emitted cases: `md5 d16bf20f52...` both
sides, 1,295 lines, no differing byte.  That is the whole argument,
which is worth saying because the tempting one is weaker.  "The arm runs at
scale 1" is verified only for the DESKTOP channel, which pins
`surface_scale = 1` (`desktop_channel.sh:454`); the device arms inherit the
app default of 1 (`config_spec.yml`, `SettingsActivity.kt`'s `intDefaults`)
and nothing in `dispatcher.sh` sets it, but a handheld's saved prefs are not
something this lane can read.  It does not matter: the bite/no-bite sets are
identical at scales 1-4, so every leg of the prediction reads the same at any
scale a device happens to be set to.  `--quantise` (3 legs PASS, mutant 4 px
on 4 captures), `--controls` (393/393/0, 1104 = 617 + 487) and `--rivals`
(495 -> 102, `floor + 1` 115, centre band 645) re-run unchanged on this tip.
So the prediction registered at `3beca48079` is **not** re-registered: its
`b_ref 36e85c96c9` is still the last commit that can change a pixel, and
re-registering would restart a ~90-minute arm for a comment.

## What the next lane should not repeat

- **Do not quote the epsilon-tie score as a device prediction.**  It is a
  clean measurement of the geometry alone and it is off by 25x as a
  prediction of the device.  The two differ by 523 px and the difference is
  entirely the tie bias.
- **Do not chase the remaining 544 px by tuning `lineTieBias`.**  It is
  pinned by the extent legs (1,911 of 41,892 band edges land exactly on a
  pixel centre) and by `subPixelPrecisionBits`, and it is not ours to pick.
  If that residual is worth opening, it is a question about the rasteriser's
  vertex quantisation, not about the cap.
- `geom_dump/build/` is generated.  Do not commit it; `make clean && make run`.

## Status

- [x] rule derived offline, no device
- [x] scored over all 48 captures (935 -> 544 at the device tie bias, none worse)
- [x] implemented in `emit_line()` (`7ce57a799b`)
- [x] geom_dump build output untracked, `--vs-goldens` leg committed
- [x] pass-1 audit remediated: H1, H2, M1, M2, M3 fixed, L1-L3 fixed
- [x] `master` merged forward (the PR was CONFLICTING, so no CI had run at all)
- [x] prediction re-registered on live refs, past `request.sh`'s key gate
      (`docs/testing/predictions/line-cap-clip.json`)
- [x] pass-2 audit remediated: N1 (the half-pixel deadband + `--quantise`),
      N2 (`--controls` splits the boundary population), N3 (the PR body no
      longer asserts the two figures its own appendix retires)
- [x] pass-2b audit remediated: A1 (the deadband's coordinate space stated
      where it is derived, in `geom.c` and here, with `--scale-cost` as the
      measurement of what it costs above Rendering Scale 1)
- [x] all six Vulkan cases `geom_dump` emits compile with the NDK's `glslc`
      after the deadband; `--shader` still reads 935 -> 544 at 1/256 and
      414 -> 21 at 1e-9, `--rivals` still 495 -> 102, `--depth` PASS/PASS
- [ ] the re-judged arm: two runs per side, `a_ref` master's tip, `b_ref` the
      deadbanded shader.  The FAIL of 2026-09-19 16:50 is answered by the
      remediation above and by nothing else until that verdict lands.
