# #13: the wide-line extent phase is DETERMINED, and the blocker was false

**Derived 2026-09-13, offline from the goldens. No device, no build, no arm.**

Tool: [`docs/testing/line_extent_phase.py`](../testing/line_extent_phase.py).
Prediction: [`docs/testing/predictions/line-extent-phase-exact.json`](../testing/predictions/line-extent-phase-exact.json).

## The claim under test

#13 carried this, and it was the entry's real blocker rather than the ordering one:

> the floor/ceil phase is UNDETERMINED by the available goldens, so a correct
> widening lands in-band without being pixel-exact — meaning even a right fix
> cannot be scored exact, and a leg demanding exactness would FAIL on a correct
> change. […] If the phase really is undetermined, the leg to register is an
> IN-BAND ABSOLUTE, not exactness.

**It is false.** The phase is determined by data that was already on disk, and
the rule that determines it reproduces the goldens' lit runs *exactly* —
100.0000% of both endpoints on 20,946 clean cuts, fit set and held-out set
alike. This is the same shape as #31, which claimed the goldens could not
select the 4-px anchoring regime and was wrong for the same reason: the
instrument in use could not see the discriminating quantity, and nobody had
asked what it could see.

## Why the old reading could not settle it

`line_priority.py --extent` collects, for each clean cut through a wide edge,
the **length** of the lit run, `b - a + 1`, and asks whether that integer is
`floor(E)` or `ceil(E)` for the modelled extent `E`. It reported 100% "in-band"
and no way to choose between the two, which is where "undetermined" came from.

But the length is the *less* informative half of each sample. The goldens also
carry `a` and `b` themselves — **where** the run sits — and the position is what
pins the phase, because the phase is not a free parameter at all. It is a
deterministic function of the band's sub-pixel position against the sample grid:

```
lit(r)  <=>  r + delta  in  the band around the edge centre c
```

Each observed `(a, b)` is a two-sided constraint on that grid, and 20,946 of
them intersect on one answer. The old instrument threw both constraints away
and kept their difference.

## The rule

Three discrete choices, each **selected by the data** (see `--rivals`), and no
fitted constant anywhere:

1. **Vertex screen coordinates TRUNCATE to 1/16 of a pixel** — NV2A's
   fixed-point vertex format. Round-to-nearest, 1/8, 1/32 and no snap at all
   each score worse.
2. **`E = w * (max + min/2) / max`** evaluated on the truncated coordinates,
   with `max`, `min` the larger and smaller of `|dx|`, `|dy|`. This is #13's
   existing alpha-max-plus-beta-min extent; what is new is that it is evaluated
   in fixed point.
3. **A pixel is lit iff its CENTRE lies in the LOW-OPEN band** `(c - E/2,
   c + E/2]`, with `c` the edge centre at that scanline's pixel centre:

   ```
   a = floor(c - E/2 - 1/2) + 1        b = floor(c + E/2 - 1/2)
   ```

   The sample point is the pixel centre on **both** axes. Nothing is offset by
   half a pixel; #13's earlier "the golden's centre is at 160.5" reading was
   this low-open tie-break seen through a closed-band model, which is why the
   `+0.5` viewport arm landed its fitted centre exactly and still scored
   +394,027 px.

## What it measures

Both endpoints of every clean cut, against the goldens:

| population | cuts | exact on `a` AND `b` |
|---|---:|---:|
| widths 6–48 — the set #13's extent rule was fitted on | 8,890 | **100.0000%** |
| widths ≤ 5 — never used in any #13 derivation | 12,056 | **100.0000%** |

The second row is a genuine hold-out: #13's extent sweep was fitted at `w >= 6`
and its order derivation at `w >= 8`, and the registration for those
(`line-edge-priority-order.json`) names widths 3–7 as held out. Nothing in this
rule was tuned on widths ≤ 5, and the low-width set is phase-discriminating in
its own right — 11,451 of its 12,056 cuts have a non-integer `E`, splitting
7,435 ceil / 4,016 floor.

Per block, on the fit set, all at 100.00%: LLoop 319, Poly 2,345, QStrip 2,554,
Quad 1,829, TFan 1,208, Tri 635.

### The rivals, on the same cuts

| variant | widths 6–48 | widths ≤ 5 |
|---|---:|---:|
| **derived** | **100.0000%** | **100.0000%** |
| no sub-pixel truncation | 98.1665% | 98.8056% |
| 1/16 round-to-nearest | 98.7627% | 98.9715% |
| 1/8 truncate | 99.1114% | 98.5319% |
| 1/32 truncate | 99.3251% | 99.4940% |
| `beta = 1`, `w(1+tan)` | 44.4319% | 76.8663% |
| `beta = 0`, `w` (Bresenham) | 40.3262% | 72.0720% |
| perpendicular rectangle `w/cos` | 53.6670% | 88.9350% |
| tie-break closed | 93.8133% | 96.6324% |
| tie-break high-open | 93.4758% | 96.6158% |
| tie-break open | 93.8245% | 96.6324% |

Each of the three choices is therefore a measurement. The truncation grid and
mode are separated by 60–177 cuts out of 8,890 — a small class, which is why
`--rivals` prints the wrong-count and not only the percentage — and the
tie-break by 550–580, which are the cuts whose band lands exactly on a sample
point (580 of 8,890; every one of them is an odd width on an axis-aligned rail).

### Whole-capture coverage

Over all 48 non-void `Line_*` captures (the nine void ones are excluded: the
width register holds nine bits of eighths, 64.0 does not fit, and hardware drew
`Line_0064.*` at 1.0), reconstructing the full ink mask edge by edge with butt
caps:

| footprint | mismatched px | of 1,967,133 golden ink px |
|---|---:|---:|
| derived rule | **495** | **0.0252%** |
| perpendicular rectangle — what we draw today | 59,605 | 3.0300% |

**14 of the 48 captures are pixel-exact in coverage.** Of the 495 residual
pixels, **493 are ours-only** (we would light ink silicon does not) and
**98.8% sit within `w/2 + 2` of a vertex**. What is left is therefore the
**cap and join phase**, which this measurement does not settle — see below.

## The control that matters most

Run the same instrument on **our own** captures
(`z-6762a54c82-044-Line_width`, apk `03ca859f9457`) and the ranking inverts:

| | goldens | our captures |
|---|---:|---:|
| derived rule | **100.0000%** | 46.7863% |
| perpendicular rectangle | 53.6670% | **93.5945%** |

The instrument is not agreeing with whatever it is shown. It identifies silicon
as drawing the hypot-approximation footprint with a low-open band on a 1/16
fixed-point grid, and identifies us as drawing a perpendicular rectangle — which
is exactly what `vk/draw.c` asks Vulkan for.

## Establishing what the instrument cannot see

Before any of the above was allowed to change a decision:

* **The discriminating class is non-empty.** 7,514 of the 8,890 fit-set cuts
  have `frac(E) != 0` and can separate floor from ceil at all, splitting 3,099
  ceil / 4,415 floor. Had that count been zero the corpus really would have been
  unable to select a phase, and the blocker would have stood.
* **The integer-`E` cuts are a control with a required answer.** All 1,376 of
  them light exactly `E` pixels — `length - E` takes the single value 0.0. A
  closed band would light `E + 1` whenever the ends fall on sample points, so
  those cuts are what refutes the closed tie-break rather than a preference.
* **No impossible row.** Zero cuts have a run length outside
  `[floor(E), ceil(E)]`, so the extent model is not being rescued by a filter.
* **The cut filter is golden-blind.** Cleanliness is decided from the geometry
  and the *perpendicular* footprint, never from the derived one, so the
  selection cannot favour the model being tested.

## What this does NOT establish

* **The cap and join phase.** 493 ours-only pixels, 98.8% within `w/2 + 2` of a
  vertex, concentrated at the widest captures (43 px at `w = 63.875`). The
  reconstruction above uses a perpendicular butt cap because it beats a vertical
  one by 234x (495 px against 115,917 px), but 495 is not zero and no rule here
  selects the cap's own floor/ceil.
* **Anything about our captures post-#67.** Every available `Line width` capture
  set predates `bc4bebcee0`; the newest is `6762a54c82` / apk `03ca859f9457`.
  The `Line width` vertices are float literals rather than anything computed
  through the guest's `floorf`, so #67 is expected to be inert here — but that
  is an expectation, not a measurement, and the 46.79% / 93.59% figures above
  are quoted as pre-#67.
* **Colour at an overlap.** This is a coverage measurement. Which of several
  overlapping wide edges is on top is #13's separate priority rule, already
  derived, and 76.3% of the issue's residual.
* **Any other suite.** `Line width` is the only suite with a full geometric
  model behind it. `2D Lines`, `Swath width`, `Point size`, `Point params`,
  `Smoothing control` and `Stipple tests` are untouched by this, and the 2D
  engine is a different path entirely.
* **That a fix will land the numbers.** Nothing has been built. The extent rule
  still needs generated line geometry, which needs `gl/shaders.c` — lane.remote's
  file — so this lane wrote no renderer code.

## Consequence for #13

The leg to register is **not** an in-band absolute. It is an **exact** leg, and
the reason a right fix can now be scored exact is that the phase is a function
of quantities the fix itself computes: truncate the vertices to 1/16, widen by
`w * (max + min/2) / max`, and light the pixel centres in the low-open band.
The registered prediction states it in golden-constrained terms — agreement with
the *goldens'* runs, not with the model — so that it is not a tautology of the
patch.
