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
      landing on a whole pixel INDEX  (ceil vs floor1)               1,104
      landing on a pixel CENTRE       (the rejected band's question) 1,038

393 closes against `--rivals` (495 - 102), and every removed pixel is one the
goldens agree should be dark -- the clip removes no lit pixel anywhere.  The
audit left open whether any golden edge can distinguish the outward rounding
from `floor + 1`, since every corner in the table above is non-integer; **it
can, on 1,104 boundaries**, which is what the 102-vs-115 gap is decided on.

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
