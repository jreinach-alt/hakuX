# #31: the corpus blocker is TRUE, and here is what it would take to lift it

**Measured 2026-09-13, offline from the goldens and the test sources. No
device, no build, no arm.**

Tool: [`docs/testing/wbuf31_blocker_audit.py`](../testing/wbuf31_blocker_audit.py),
which sits on top of [`wbuf_anchor_recover.py`](../testing/wbuf_anchor_recover.py).
Background: [`wbuffer-slope-offset.md`](wbuffer-slope-offset.md).

## The claim under test

`nv2a_issues.toml`, `[issue.31].blocked_on`:

> The remaining 566,549 px need geometry the corpus does not contain — a
> triangle translated in y across the 4-grid phase at fixed clip, or a quad at
> `clip_top>0` with both triangles top-truncated. That is a new
> nxdk_pgraph_tests case, not an arm. TriV's 105,600 is a third mechanism with
> no candidate rule and its recorded column refuted.

Two limbs: `ClipF` 460,949 px (the regime selector) and `TriV` 105,600 px (a
third mechanism). Both were tested. **Both hold.** This is not the #13 or the
earlier #31 result — the discriminating data is genuinely not on disk — and the
value of the audit is that it says *exactly* which capture is missing, and makes
the request an order of magnitude cheaper than the sentence above asks for.

## Before anything else: is the class non-empty?

`NV097_SET_POLYGON_OFFSET_SCALE_FACTOR` is pushed with a non-zero value in
**exactly one file** of `nxdk_pgraph_tests` — `wbuf_tests.cpp:464`.
`depth_clamp_tests.cpp` pushes `POLYGON_OFFSET_BIAS` only, which is a constant
and which no anchor rule can move. So the class of captures that can carry an
anchor at all is the `W buffering` suite and nothing else, and the 100-suite
corpus contributes no second site.

Within the suite, the populations and what each can resolve:

| population | distinct depths over the ink (5 prims) | can it bound an anchor? |
|---|---:|---|
| `WBuf24D` | 137–208 | **yes** — integer depth, so the quantisation is 1 unit of `w` and the offset interval comes out ~0.002 wide on a value of 1e5 |
| `WBuf24F` | 200–493 | weakly — 24-bit *float*, so at 4e5 the quantisation is ~6 units, not 1 |
| `WBuf16D` | **7–10** | no — a 16-bit integer depth over this `w` range resolves ten levels |
| `WBuf16F` | 188–289 | no |

(The distinct-depth counts are small everywhere because `w` only spans 58–326;
what separates the rows is the *quantisation step*, and only `WBuf24D` has one
of 1 unit at the offsets involved.)

And the clip variants exist only at `depthf == 6`, i.e. `WBuf24D`
(`wbuf_tests.cpp:330`, `:368`), so none of the 16-bit captures carries a
`ClipF` or `ClipW` at all. They duplicate five primitives already measured.

**One sub-claim in the existing write-up is false.** It records "the
fixed-function `_V0_` ZS1 captures are empty (nothing drawn) on hardware; not
investigated". Measured: empty on `WBuf24D` and both 16-bit formats, and **not**
empty on `WBuf24F` — 137,170 and 142,560 non-clear px. It changes no verdict,
because every `_V0_` capture draws the same `FloorQuad` geometry and so fills no
cell of the table below. It is recorded because "empty" was asserted of a class
that is not uniformly empty, which is the failure this project keeps paying for
in the other direction.

## Limb 1 — `ClipF`: TRUE, and the missing capture is one integer

### What the table actually contains

| clip_top | tri | px | recovered anchor row | first covered | 4-grid+2 | ct+2 |
|---:|---|---:|---:|---:|---:|---:|
| 0 | t0 | 29,780 | **0.000** | 0 | 2 | 2 |
| 0 | t1 | 192,190 | **0.000** | 0 | 2 | 2 |
| 32 | t0 | 16,801 | **32.001** | 32 | 34 | 34 |
| 32 | t1 | 189,489 | **34.000** | 32 | 34 | 34 |
| 128 | t0 | — | *cell empty* | | | |
| 128 | t1 | 159,250 | **130.001** | 128 | 130 | 130 |
| 224 | t0 | — | *cell empty* | | | |
| 224 | t1 | 112,210 | **226.001** | 224 | 226 | 226 |

`FloorQuad` t1 and `ClipF` t1 are the same triangle — both draws push the
identical four vertices `(53.1875,-34.3125) (586.75,-34.3125) (1808.6875,453)
(-1168.6875,453)`, confirmed from source rather than inferred — differing only
in `clip_top`. That is the existing write-up's Pair B and it stands.

### Two degeneracies, and the first is new

**DEGENERACY 1 — every clip_top the suite can generate is a multiple of 32.**
`clip_top = kVertSampleCoords[3 + 6*i]` (`wbuf_tests.cpp:335`), and
`kVertSampleCoords` is `0, 32, 64, … 448`. So no `clip_top` anywhere in this
suite is anything but `0 (mod 4)`, and **"anchor = clip_top + 2" and "anchor =
the absolute 4-grid at phase 2" are the same prediction on every capture that
exists.** The write-up records `ClipF` t1's rule as `clip_top+2`; it is one of
two rules that fit, and the other is the rule `TriH` already obeys at all four
phases. Nothing on disk separates them.

The same applies on the other axis: `ClipW`'s `clip_left` is
`kHorizSampleCoords[6*i]` = 159, 261, 363, from an array stepping by 34, so
`clip_left mod 4` alternates 3, 1 and is **never 0 or 2**.

**DEGENERACY 2 — the `(t0, clip_top > 0)` cell has exactly one observation.**
t0 has no covered pixel at `clip_top` 128 or 224; its left edge has left the
framebuffer by then. This was *checked*, not inferred from the instrument's
silence — the existing tool simply prints no row for those two and the absence
reads identically to a dropped case.

So the interaction that decides the regime rests on **one** t0 observation at
`clip_top > 0` and **three** t1 observations at a single clip phase. Every
discriminator the existing write-up lists is still dead on Pair A / Pair B, and
three more tried here die the same way: first covered pixel in 4×4 tile-scan
order (predicts row 32 for `ClipF` t1, measured 34); the tile's own centre pixel
(predicts row 2 for `FloorQuad` t1, measured 0); and whether the *clip's* top
edge rather than the framebuffer edge cut the primitive (true for t0 at
`clip_top`=32 as well, so it cannot split them).

### The cheaper refuting capture

The blocker asks for "a triangle translated in y across the 4-grid phase at
fixed clip, or a quad at `clip_top>0` with both triangles top-truncated". The
first half is already satisfied by `TriH`, which sweeps `y_top` through all four
phases and pins the absolute 4-grid at phase 2 on all 24 triangles. What is
actually missing is narrower and cheaper:

* **(a) one `ClipF` variant at a `clip_top` that is not `0 (mod 4)`** — 33, 34
  or 35. That is one integer in `kVertSampleCoords`, not a new test case, and it
  separates `clip_top+2` from the absolute 4-grid in a single capture.
* **(b) a `clip_top` between 1 and ~127**, so that the `(t0, clipped)` cell gets
  a second observation instead of resting on `clip_top`=32 alone.
* **(c) a `TriH`/`TriV` variant stepping the CROSS axis by a non-multiple of 4**
  — see limb 2.

## Limb 2 — `TriV`: TRUE, and it is a *refuted model family*, not an unfitted one

### What the existing instrument could not see

`wbuf_anchor_recover.py` recovers the anchor correctly — that is not in
question, and this audit reuses its recovery. What it does with the number is
compare it against one rule's predicted anchor at a **0.01 px tolerance**
(`abs(r[6] - r[8]) < 0.01`), and report a miss as "not an integer pixel under
any rule". Two things follow. The tolerance is **30× wider than the data
supports** — the interval pins the sample position to 2.7e-4 px. And the verdict
is per-rule: "no rule I tried fits" is what it can say, which reads as a fit
nobody has found yet.

The goldens carry more. Each offset is bounded to an *exact interval*, and
inverting that interval gives the sample position the golden requires. Scored
against the interval, and then fitted as a **family** with a held-out residue,
`TriV` is not unfitted — it is **refuted**, and so is every rule of its shape.

### New structural fact: the offsets are exactly 4-periodic

`TriH` and `TriV` are each 24 translates of one shape. `TriH` steps x by 20 and
`y_top` by 1; `TriV` steps `y_top` by 20 and `x_left` by 1. If the offset
depended on the triangle's position along the **non-gradient** axis, triangles
`s` and `s+4` would differ — they are 80 px apart on that axis, and the
instrument would show six distinct intervals per residue.

Measured: **six triangles per residue, identical intervals to six decimals, on
both suites.**

```
TriV residue 0: 6 triangles, [403283.155152, 403283.156622]  IDENTICAL
TriV residue 1: 6 triangles, [421475.655920, 421475.668907]  IDENTICAL
TriV residue 2: 6 triangles, [440927.273243, 440927.287849]  IDENTICAL
TriV residue 3: 6 triangles, [461755.622424, 461755.625510]  IDENTICAL
```

So each suite's offset is a function of its shift `mod 4` alone. `TriV` t0 and
t20 are 400 rows apart and agree to the last digit of a 0.0014-wide interval.
**That kills the whole family of "the plane solve's rounding accumulates across
the screen" explanations**, which is where the natural next guess would have
gone, and it is a direct consequence of the per-triangle plane-solve term the
existing write-up measures on `FloorQuad`.

### The inversion, with `TriH` as the control

| | s=0 | s=1 | s=2 | s=3 |
|---|---:|---:|---:|---:|
| `TriH` sample row | **2.5000** | **2.5000** | **2.5000** | **2.5000** |
| `TriV` sample col | 164.5072 | 164.4634 | 164.4195 | 164.3758 |

`TriH` sits on the pixel centre of row 2 at every residue — the published rule,
confirmed against the interval rather than against a rounded integer.

`TriV` does not sit on any pixel centre, and it **drifts by −0.0438 px for every
pixel the triangle translates**. An anchor on any fixed grid is constant within
a residue group by construction, so no such rule can produce a drift, whatever
its phase or step.

The uncertainty matters here, so it is bounded two ways rather than assumed.
The golden's own depth quantisation contributes ~3e-8 px. The model side is
bounded by the interval being **non-empty over ~1,100 px of each triangle**: our
w agrees with hardware's interpolated w to better than 0.002 *everywhere* on the
triangle, which is 2.7e-4 px of sample position. The drift is 160× that.

### The rival sweep

Every model is `offset = FACTOR · C · |d| / (i(A)·i(B))`, scored inside the
golden's interval on all four residues.

| | `TriH` | `TriV` |
|---|---:|---:|
| rules tried | 5 | 32 |
| residues inside the interval | 1/4 at row 2 | **0/4, every rule** |
| worst relative error, best rule | **1.1e-7** | **5.6e-3** |
| in offset units | 0.05 | ~2,500 |

The **separation** is the finding. `TriH`'s residual of 1.1e-7 is the
per-triangle plane-solve rounding this issue already measures as a separate
floor. `TriV`'s best is four orders of magnitude larger, so `TriV` is *not* that
floor and the two must not be pooled.

Rules tried and beaten, all 0/4: the absolute 4-px column grid at every phase
0–8, sampled at pixel centres and at pixel corners; 2-px and 4-px steps divided
by their length at phases 0, 2, 4; the first covered column at offsets 0–4; and
the 2×2-quad snap of the first covered column at offsets 0–2.

### And the family, not just the rules

Within one residue group any fixed-grid rule is a fixed absolute pair, so
`P(s) = C·(A−s)·(B−s)` is a quadratic in `s` with three free parameters. Fitted
through residues 0, 1, 2 and asked to predict residue 3:

```
predicted P(3) = 1998.984915
golden   P(3) in [1998.990493, 1998.990507]
miss = 418 x the interval width,  at a fitted step count C = 1.090
```

Three free parameters calibrated on three of the four points, and the fourth is
still out by hundreds of interval widths at a step count that is not an integer.
**So `TriV` refutes the model family — "an anchor pixel plus a finite difference
along the gradient axis" — and not merely one phase of it.** Any rule for `TriV`
must change the *form* of the offset computation, and there is nothing in the
corpus that constrains a new form: the 24 triangles supply exactly four distinct
numbers.

### The corpus gap that follows, and it is new

`TriH`'s x is `160 + 20s`, so `x mod 4` is 0 for all 24. `TriV`'s `y_top` is
`20s + 0.5`, so `y_top mod 4` is 0.5 for all 24. **Each family sweeps its
gradient axis through all four phases and holds the cross axis at one phase.**
If the anchor is a two-dimensional quantity — which the `ClipF` t0/t1 split is
evidence for, since those two triangles differ in nothing the gradient axis can
see — then the corpus holds a single cross-axis phase and is structurally blind
to that dependence. Nobody had recorded this, and it is a second, independent
reason the blocker holds.

## What this does NOT establish

* **A mechanism for `TriV`.** The refutation is negative. `TriV` remains a third
  mechanism; what is new is that it is refuted rather than unfitted, that it has
  no cross-axis dependence, and that its anchor is pinned to ±0.0003 px.
* **That no rule exists.** The sweep covers anchor-plus-finite-difference models
  on the gradient axis. A model that reads the vertex `w` values directly, or
  that computes in a fixed-point format with its own rounding, is untouched by
  it — and with four distinct numbers to fit, such a model would be a curve fit
  from this corpus whatever it scored.
* **Anything about the 941,308-px off-by-one floor**, which the existing
  write-up attributes to silicon's per-triangle plane solve. `TriH`'s 1.1e-7 is
  consistent with it and is offered as one more data point, not as a model.
* **Anything from our own captures.** This is goldens and test sources only. No
  emulator capture was scored, so nothing here is affected by `bc4bebcee0`.
* **`WBuf24F` as a second oracle.** It is the only unused population with usable
  resolution, its `_V0_` ZS1 captures are non-empty, and it was not decoded —
  24-bit float at 4e5 quantises to ~6 units, six orders coarser than the
  interval this work relies on, and it draws no geometry `WBuf24D` does not.

## Consequence for #31

The `blocked_on` sentence is sound and should stay, with three corrections:

1. The first half of its prescribed capture — "a triangle translated in y across
   the 4-grid phase at fixed clip" — is **already in the corpus** as `TriH`, and
   already pins the absolute 4-grid at phase 2 on 24 of 24. What is missing is a
   `clip_top` that is not a multiple of 4, which is one integer in
   `kVertSampleCoords` rather than a new test case.
2. `TriV` should be recorded as a **refuted model family**, not as "no candidate
   rule". The distinction decides what the next person does: not "fit harder",
   but "the offset for this shape is not an anchored finite difference".
3. A third missing capture should be named: a `TriH`/`TriV` variant that steps
   the cross axis by a non-multiple of 4. The corpus holds one cross-axis phase
   and cannot see a 2-D anchor at all.
