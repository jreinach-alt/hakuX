# #38 mechanism 2: the blocker is FALSE — three of the five captures are already on disk

**Measured 2026-09-13, offline from the goldens. No device, no build, no arm.**

Instruments, all runnable with no arguments:

* [`docs/testing/pair_fill_blocks_38.py`](../testing/pair_fill_blocks_38.py) — the main result
* [`docs/testing/pair_y_group_38.py`](../testing/pair_y_group_38.py) — the 2×1 result
* [`docs/testing/pair_census_38.py`](../testing/pair_census_38.py) — the widened corpus census

## The claim under test

`nv2a_issues.toml`, `[issue.38]`:

> mechanism 2 needs five new captures (one property varied at a time off the
> `Alpha_func` band) that do not exist upstream — behind the test-suite fork

The five, from [`issue57-is-issue38-mech2.md`](issue57-is-issue38-mech2.md) §3:

| # | vary | separates | verdict here |
|---|---|---|---|
| 1 | `PRIMITIVE_TRIANGLES` instead of `QUADS` | primitive type from immediate mode | **exists** |
| 2 | 128 px wide instead of 512 | "one large primitive" from immediate mode | **exists, confounded with 3** |
| 3 | `SET_VERTEX3F` instead of `SET_VERTEX4F` | the register from immediate mode | **exists, confounded with 2** |
| 4 | the ramp running in y instead of x | whether the group is 2×1 or 2×2 | **answered: 2×1** |
| 5 | a second y-gradient | the period-3 breakdown | still needed |

**The claim is FALSE.** Three of the five are answered by data already on disk.
**Two** new captures are needed, not five: one that separates width from the
submission register, and one for the period-3 breakdown.

The tie the blocker rests on was four-way. It is now **two-way**, and the
surviving pair is exactly confounded — which is the one thing a new capture
still has to fix.

## 1. Why the corpus looked empty: two instruments, two blind spots

The blocker's force comes from "the class has exactly two members, so the
positive cell cannot be subdivided". Membership needs, per draw:

* **A** screen space, no perspective divide — a `PassthroughVertexShader`
* **B** immediate-mode vertices — `SetVertex` inside `Begin`/`End`
* **C** a per-vertex diffuse *gradient*

Both instruments that decide this are blind in a way that maps onto the tie:

**`pair_rule_candidates.py` decides C by counting distinct *textual*
`SetDiffuse` arguments** inside a block of at most 4,000 characters. A palette
walked in a loop is one string, so every such draw reads as `colours = 1`.
Re-scanning all 100 sources with a loop-aware detector finds **14 candidate
sources against the old script's 7**.

**`interpolator_phase.py` judges a row only when ≥ 50 qualifying positions
exist at each parity, among pixels whose neighbours differ by ≤ 4 per
channel.** That is a **width floor of roughly 200 px** — which is *exactly the
"one large primitive" conjunct* — and a ban on steep gradients, which small
draws necessarily have. A 60-px draw cannot be reported as paired by it even if
it is.

This is the #13 shape. `line_priority.py --extent` recorded a run's length
while the goldens also carried its position; here the census records a rate over
a population it selects with the conjunct under test.

## 2. `Line_width/Fill_*` — narrow, triangle and `SET_VERTEX3F` class members

`line_width_tests.cpp`'s constructor runs its whole shape set three times with
**`fill = true`**:

```cpp
for (auto line_width : {0, 1 << 3, 32 << 3}) {
  tests_[MakeTestName(true, line_width)] = ... Test(test_name, true, line_width);
}
...
static void SetFill(bool enabled) {
  uint32_t fill_mode = enabled ? NV097_SET_FRONT_POLYGON_MODE_V_FILL
                               : NV097_SET_FRONT_POLYGON_MODE_V_LINE;
```

giving the goldens `Fill_0000.0`, `Fill_0001.0`, `Fill_0032.0`. Those are
**filled** polygons, not the wireframe the other 58 captures in the suite draw,
and each carries five filled blocks that are all class members —
`PassthroughVertexShader` from `Initialize`, `SetDiffuse(kPalette[i])` per
vertex inside one `Begin`/`End`, `SetVertex(x, y, 1.0f)`:

| block | primitive | width | E | O | **E − O** |
|---|---|---:|---:|---:|---:|
| `TRIANGLES` | triangle | ~78 px | 0.0769 | 0.0809 | **−0.0040** |
| `QUAD_STRIP` | quad | 105 px | 0.0172 | 0.0165 | **+0.0007** |
| `TRIANGLE_FAN` | triangle | ~94 px | 0.0404 | 0.0372 | **+0.0032** |
| `POLYGON` | polygon | ~99 px | 0.0297 | 0.0274 | **+0.0023** |
| `QUADS` | quad | 60 px | 0.0247 | 0.0527 | **−0.0280** |

949–3,836 qualifying even positions per block, identical on all three captures
(`LINE_WIDTH` does not affect a filled polygon, so the three are a built-in
replicate). **Every one is unpaired.**

### Why a steep gradient is a good probe, not a bad one

These ramps run at about 4.3 bytes/px — above the old census's ≤ 4 bound, which
is why it never judged them. Raw from `Fill_0032.0`, y = 95:

```
R : 120 125 129 133 138 142 146 150 155 159 163 167 171 175 179 184 188 192
```

Every pixel differs. **A pair-constant field gives E = 1 at any steepness**,
because within a pair the two pixels are equal by construction — so `E ≈ 0` here
is a hard negative, not an unmeasured row. That is the same argument the prior
lane used to accept `High_vertex_count`.

### The controls, which the script re-runs every time

| | E − O |
|---|---:|
| positive — `Alpha_func` band | **+0.9766** |
| positive — `Context_switch/GRZero` | **+0.7890** |
| negative — `High_vertex_count` | **+0.0000** |
| the fifteen Fill readings | max \|E − O\| = **0.0280** |

The instrument separates a paired draw from an unpaired one by 0.79–0.98 and
puts every Fill block with the negative control. `pair_fill_blocks_38.py`
withholds its verdict if either positive control drops below 0.5.

### A second statistic, sharing nothing but the image

E/O asks how often adjacent pixels are equal. The **x-step parity** — of the
positions where the byte changes, what parity do they sit at — is a different
question on the same pixels, and it is the statistic §3 uses. A 2-px group puts
every change at one parity.

| | even | odd | skew |
|---|---:|---:|---:|
| `Alpha_func` band (paired) | 0 | 8,249 | **1.000** |
| `GRZero` polygon (paired) | 12,597 | 69,955 | **0.847** |
| `High_vertex_count` (unpaired) | 103,545 | 71,716 | 0.591 |
| Fill `TRIANGLES` | 2,571 | 2,575 | **0.500** |
| Fill `QUAD_STRIP` | 12,077 | 11,973 | **0.502** |
| Fill `TRIANGLE_FAN` | 8,542 | 8,543 | **0.500** |
| Fill `POLYGON` | 9,986 | 10,020 | **0.501** |
| Fill `QUADS` | 4,870 | 4,643 | **0.512** |

The Fill blocks are **flatter than the known-unpaired control**, which itself
sits at 0.591 because its 6×6 quad grid has an alignment of its own. Two
statistics, one conclusion. This matters more than usual here because the E/O
qualifier was wrong twice (§4), so the second statistic is a check on the
instrument and not only on the draw.

### What that does to the tie

| candidate selector | predicts Fill blocks… | observed | |
|---|---|---|---|
| `immediate ∧ w=1` | pair | unpaired | **REFUTED** |
| `… ∧ QUADS or POLYGON` | pair (the QUADS and POLYGON blocks satisfy it) | unpaired | **REFUTED** |
| `… ∧ width ≥ 512` | no pair | unpaired | survives |
| `… ∧ SET_VERTEX4F` | no pair | unpaired | survives |

**Two of four eliminated, with no new geometry** — which is the outcome
`issue57-is-issue38-mech2.md` named as the thing that would void its own
section:

> if a reader finds a suite that satisfies A ∧ B ∧ C and the census calls it
> unpaired **on its own draw's pixels rather than on a background**, the
> conjunction is refuted.

It does, and it is. Note the direction: the prior lane looked for a narrow or
triangle draw that *pairs*. These are narrow and triangle draws that *do not*,
which eliminates the two candidates predicting they would.

The two survivors are **exactly confounded** in this evidence: every Fill block
is both narrow and 3F. That confound is what still needs a capture.

## 3. The group is 2×1 — capture 4, answered

Settled on `Context_switch/GRZero`, which both prior lanes accept as paired, is
512 px wide, and carries a genuine **2-D** gradient.

**Stated before the number:** if the group were 2×2, silicon would hold the
colour constant across the even-aligned row pair `{2n, 2n+1}`, so every y step
would land at one parity and the skew would be 1.000. If it is 2×1, y steps fall
wherever the ramp crosses a byte boundary and the skew sits at 0.500.

| | population | skew |
|---|---:|---:|
| **control** — x steps, `Alpha_func` ×4 | 50,662 | **1.000** (0 even / 50,662 odd) |
| **measurement** — y steps, `GRZero`, R/G/B | 129,299 | **0.501 – 0.511** |
| corroboration — y steps, `Attrib_float` ×9 | 388,835 | **0.503** |

The control is exact and its *sense* is a second confirmation: all 50,662 x
steps fall between an odd x and the next even x, i.e. precisely on the boundary
between pair `{2m, 2m+1}` and pair `{2m+2, 2m+3}`. `GRZero`'s own x steps skew
0.793–0.886 in the same run.

So the instrument resolves a 2-pixel group to 1.000 when one is present and
reads 0.501–0.511 in y **on a draw that is unambiguously paired in x**. **The
group is 2×1.**

### `Attrib_float` is the class's missing third member

`attribute_float_tests.cpp` lines 114–178: `PassthroughVertexShader`, explicit
`w = 1` (`{x, y, 1, 1}`), `PRIMITIVE_QUADS`, immediate mode, four vertex colours
— **A ∧ B ∧ C**. It was missed because its colour is set in a loop
(`SetDiffuse(vb[v+4], ...)`, one textual call, four colours).
`issue57-is-issue38-mech2.md` §5 had its y number and discounted it as "an RGB
ramp on an **unpaired draw**". It is not outside the class; it is in it.

It is corroboration rather than the argument, because it carries a confound the
`GRZero` reading does not: its quad is 51 px wide, so under a selector with a
width conjunct it would not be selected and its y null would say nothing.

## 4. The widened whole-corpus census FAILED, and is reported as failed

The plan was to re-run all 5,608 goldens with the width floor and the 4-byte
ceiling lifted, and read off whether any new capture pairs. **That instrument
does not work at whole-frame scope and its totals are not quoted anywhere in
this document.** It is recorded because three successive versions of one filter
were wrong and every one of them printed a clean-looking total.

**Version 1 — a false positive class of 1,673 captures.** Every `Blend_tests`
capture read as paired. Dumping the qualifying positions of `1-dstRGB_MIN_1`
put them at x = 14,15,16 / 58,59,60 / 118,119,120 — the background-to-swatch
transitions `(32,32,32) -> (4,48,4)`. **A lone hard edge is monotone, and a step
of 28 is inside the bound, so it qualified as a ramp.** At an edge two of three
window positions are "same" and one is not, and because swatch grids sit on a
regular even-aligned pitch, *every* edge in the frame shares a parity —
manufacturing E ≫ O out of geometry containing no interpolant at all.

**Version 2 — a false negative that broke the positive control.** Requiring two
non-zero deltas among `(prev, d, nxt)` fixes the edges and also excludes every
**between-pair** position of a *perfectly* pair-constant field, where the deltas
alternate `0, ≠0, 0`. `Alpha_func` dropped to zero measurable captures — and the
census still printed a perfectly plausible `0 paired`. Only the explicit control
line caught it.

**Version 3 — widening the neighbourhood to ±3 restores the control and breaks
the impossible row.** `Alpha_func` returns at E − O = 0.984 and
`High_vertex_count` at 0.003, but **1,309 captures now report E == O == 1.000**:
the neighbourhood a paired field needs also admits flat background sitting next
to a gradient, once the window is a whole frame rather than a draw. Per
"a measurement that disagrees with the arithmetic is the instrument until proven
otherwise", that voids the run. The script now refuses its own summary when the
impossible-row count exceeds 2% and says to use the region probe instead.

**What survives is `qualifying()` applied to a rectangle that IS the draw.**
That is how §2 uses it: the population is the primitive's own pixels, the
impossible row does not fire, and the controls separate by 0.79–0.98. The
`Line_width/Fill_*` discovery came from **reading the sources**, not from the
census, so nothing in this document rests on the failed instrument.

**A false positive class of 1,673 captures.** Every `Blend_tests` capture read
as paired. Dumping the qualifying positions of `1-dstRGB_MIN_1` put them at
x = 14,15,16 / 58,59,60 / 118,119,120 — the background-to-swatch transitions
`(32,32,32) -> (4,48,4)`. **A lone hard edge is monotone, and a step of 28 is
inside the bound, so it qualified as a ramp.** At an edge two of three window
positions are "same" and one is not, and because swatch grids sit on a regular
even-aligned pitch, *every* edge in the frame shares a parity — manufacturing
E ≫ O out of geometry containing no interpolant at all.

**Then a false negative that broke the positive control.** Requiring two
non-zero deltas among `(prev, d, nxt)` fixes the edges and also excludes every
**between-pair** position of a *perfectly* pair-constant field, where the deltas
alternate `0, ≠0, 0`. `Alpha_func` dropped to zero measurable captures — and the
census still printed a perfectly plausible `0 paired`. Widening the
neighbourhood to ±3 restores it.

The second failure is the more instructive: **the run reported a clean total
while the instrument had gone blind to the one capture it was calibrated on.**
Only the explicit control line caught it.

## 5. Consequence for #38

`blocked_on` should become:

> mechanism 2's selection rule is narrowed to a two-way tie — `immediate ∧ w=1`
> conjoined with EITHER `width ≥ 512` OR `SET_VERTEX4F`. Two new captures
> remain: (a) the `Alpha_func` band at its full 512 px submitted through
> `SET_VERTEX3F`, or equivalently the same band narrowed to 128 px on
> `SET_VERTEX4F` — either separates the two survivors alone; and (b) a base
> quad with a second y-gradient, for the period-3 breakdown on `GRZero`'s second
> fan triangle. The bare conjunction and the primitive-type reading are
> REFUTED on `Line_width/Fill_*`; the group is 2×1, measured.

## What this does NOT establish

* **Which of width or register is the selector.** They are perfectly confounded
  in the corpus: every narrow class member is 3F and every 4F class member with
  an x gradient is ≥ 512 px. One capture decides it; none here does.
* **The period-3 breakdown** on `GRZero`'s second fan triangle. Capture 5
  stands. Measuring y-step *parity* is a different question from pair-exactness
  varying with `y mod 3`, and nothing here touches it.
* **That a wide 3F draw would pair.** The inference "the register is the
  selector" is not supported by anything here — only "the register has not been
  eliminated".
* **That `Attrib_float`'s pointer overload emits `SET_VERTEX4F`.**
  `TestHost::SetVertex(const float *)` lives in an external dependency not
  vendored in this checkout. The block is immediate mode by the same structural
  criterion used for both accepted positives, and the vertex carries four
  components, but the register is inferred rather than read. Nothing in §2 or §3
  depends on it.
* **Anything about our own captures.** Every number here is from the goldens.
  No capture directory was scored, so `bc4bebcee0` (guest `floorf` was `rint`)
  is irrelevant to all of it.
* **That there is no fourth class member.** I intended the widened census to
  answer this and it failed (§4), so the enumeration rests on the loop-aware
  source scan alone — 14 candidate sources across all 100 files, of which three
  are measurable members. That scan is still regex-based, and it decides **A**
  at file scope rather than per `Begin`/`End` block. A fourth member is
  possible; `Line_width/Fill_*` shows the cost of assuming otherwise.

## Falsifiers

`python3 docs/testing/pair_fill_blocks_38.py` must print positive controls above
+0.5, a negative control near 0, and `largest |E - O| < 0.1` over the fifteen
Fill readings. If a Fill block starts pairing, §2 inverts and the bare
conjunction is back.

`python3 docs/testing/pair_y_group_38.py` must print skew **1.000** on the
`Alpha_func` x control and **0.503** on `Attrib_float` y. If the x control falls
below 0.9 the instrument is blind and the script refuses its verdict.

`python3 docs/testing/pair_census_38.py` currently prints
`THE CENSUS IS VOID AT THIS SCOPE` and that is the expected output — it is kept
for `qualifying()` and as the record of §4, not as a source of numbers. If
someone makes its impossible-row count fall below 2% of measurable captures
without breaking the `Alpha_func` control, the whole-corpus question is open
again and worth re-asking.
