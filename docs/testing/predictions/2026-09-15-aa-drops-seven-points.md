# Prediction: why the AA arm drops 7 of 12 points

Registered 2026-09-15 on `59cbecac`, before testing the mechanism.

## What is characterised

`3D_primitive`'s `Points` captures are **byte-exact** without the AA surface and
differ in exactly **7 pixels** with it -- the same 7 for `-ls`, `-ps` and
`-ls-ps`. Every one of those 7 is a **completely isolated single pixel**, nothing
within +/-5 columns or +/-3 rows in either image, where **we render background
(48,48,48) and the hardware renders a point.**

`Test()` dispatches `PRIMITIVE_POINTS` to `CreateLines()`, so the points are the
12 line vertices. Matching by diffuse colour:

| vertex | position | z | screen | AA arm |
|---|---|---|---|---|
| v0 | `kLeft, kTop` | ZFront | (121, 113) | **dropped** |
| v1 | `kRight, kTop` | ZFront | — (white, shared with text) | present |
| v2 | `-2, 1` | ZFront | (175, 168) | present |
| v3 | `2, 0` | ZBack | (417, 240) | **dropped** |
| v4 | `1.5, 0.5` | ZBack | (392, 216) | present |
| v5 | `-1.5, 0.75` | ZBack | (248, 204) | **dropped** |
| v6 | `kRight, 0.25` | ZFront | — (white, shared with text) | present |
| v7 | `1.75, 1.25` | ZFront | (447, 149) | **dropped** |
| v8 | `kLeft, 1.0` | ZFront | (121, 168) | **dropped** |
| v9 | `kLeft, -1.0` | ZFront | (121, 312) | **dropped** |
| v10 | `kLeft, kBottom` | ZBack | (187, 324) | present |
| v11 | `kRight, kBottom` | ZBack | (453, 324) | **dropped** |

**Depth alone does not explain it**: v4 and v5 are both at ZBack and only v5 is
dropped; v2 and v3 are the red pair at different depths and only v3 is dropped.

## The confound that must be stated

The AA block at `three_d_primitive_tests.cpp:936` changes **three** things at
once, not one:

1. `AA_CENTER_CORNER_2` multisampling,
2. depth format **`SZF_Z16`** (the non-AA arm uses the suite default),
3. rendering into **texture memory at double pitch**, resolved by a later
   textured draw.

Calling this arm "AA" is shorthand. Any mechanism proposed here has to say which
of the three it blames, and the measurement has to be able to tell them apart.

## Candidates

| # | mechanism | already weakened by |
|---|---|---|
| A | depth test rejects them -- Z16 quantises where Z24 did not | v4/v5 both ZBack, only v5 dropped |
| B | alpha test rejects them | -- |
| C | clipped in the doubled-width space (guard band or scissor) | -- |
| D | point centre rounds to a sample the resolve discards | -- |
| E | scissor doubled in the wrong space (`gl/draw.c:193,428`) | -- |

## Prediction

**P1 -- the control that splits the candidate space.** `Lines`, `LineStrip` and
`LineLoop` are built from **the same 12 vertices**. If the drop happens at
vertex, transform or clip level (C, E), those primitives must lose the segments
touching v0, v3, v5, v7, v8, v9 and v11 in the AA arm. If they do not, the drop
is specific to **point rasterisation** (D) and C/E are out.

**P2.** If P1 says point-specific, then the same 7 are dropped at every draw
mode (`default`, `inlinearrays`, `inlineelements`, `inlinebuf`) -- already
implied by the submission-path pivot being flat, so a difference there would
contradict data in hand.

**P3.** If P1 says vertex-level, the dropped set is a function of position
alone, and the three `kLeft` vertices (v0, v8, v9) being dropped while `kLeft`
at ZBack (v10) survives points at a projected-x threshold rather than a depth
one.

## Controls

**C1.** The non-AA arm must stay byte-exact for `Points` throughout. It is the
baseline that makes "dropped" meaningful; if any measurement here shows a
non-AA difference, the comparison is contaminated.

**C2.** No EXTRA pixels in ours anywhere in the AA `Points` capture. Already
measured: 7 missing, **0 extra**. If a later run shows extras, the framing
"we drop points" is wrong and it is a displacement instead.

## What kills it

P1 returning "lines lose nothing" AND P2 failing would mean the drop depends on
the submission path, contradicting the flat 25.0%-each pivot and meaning one of
those two measurements is wrong.

## Scope, stated up front

`pgraph.h:521`, `glsl/vsh.c:643` and `glsl/psh.c` are **not this lane's**.
`gl/draw.c` and `gl/surface.c` are. Depending on which candidate survives, the
fix may be entirely outside this lane -- in which case this is a handover, not
a repair.

---

## Outcome: P1 says POINT-SPECIFIC. Candidates A, C and E are disfavoured.

The discriminator is not whether the 7 coordinates differ in the line captures --
those coordinates lie **along** lines there, so "both painted" says nothing. It
is whether the line captures show a **gold-only excess** (content the hardware
draws and we do not, which is what dropping a vertex would produce) or a
**balanced** count (displacement).

| capture | differing px | ours-only | gold-only |
|---|---:|---:|---:|
| `Points` | **0** | 0 | 0 |
| `Points-ls` | 7 | **0** | **7** |
| `Lines` | 361 | 3 | 3 |
| `Lines-ls` | 2,151 | 146 | 153 |
| `LineStrip` | 760 | 1 | 4 |
| `LineStrip-ls` | 4,064 | 240 | 223 |
| `LineLoop` | 834 | 1 | 4 |
| `LineLoop-ls` | 4,780 | 297 | 279 |

**`Points-ls` is a pure drop: 0 ours-only against 7 gold-only.** Every line
capture in the AA arm is **balanced** -- 146/153, 240/223, 297/279 -- which is
displacement, not loss.

Dropping a vertex would delete the two segments touching it and produce a large
one-sided gold-only excess. Nothing of the sort appears. So:

- **A (depth test)** -- disfavoured. A depth rejection applies to line fragments
  too, and would show the same one-sided excess.
- **C (clipped in doubled-width space)** and **E (scissor doubled wrongly)** --
  disfavoured for the same reason, and they were the two that most needed ruling
  out because they are the ones that live in this lane's files.
- **D (point rasterisation / resolve sampling)** -- survives.

**C1 held**: `Points` is byte-exact throughout. **C2 held**: 0 extra pixels.

**P2 and P3 not reached.** P3 was conditional on P1 saying vertex-level, and it
did not.

## A candidate for D, registered rather than claimed

The AA surface is **double width**, and the guest resolves it by drawing a
textured quad from it back to a single-width target. If that resolve effectively
samples one of the two columns per output pixel, then a one-pixel point survives
or vanishes according to **which column it lands in** -- while a line, covering
many columns, survives either way and only shifts at its edges. That is the
shape of what is measured: points lost outright, lines displaced.

It also predicts roughly half the points should vanish, and **7 of 12 did**.

**This is a story that fits, not a result.** It was formed after seeing the
numbers, the "roughly half" agreement is one draw from a small sample, and final
screen-x parity of the dropped set is not clean (six odd, one even against a
mixed surviving set) -- though screen x is the wrong space to test it in, which
is itself a reason the test has to be built rather than eyeballed. Registering
it here so the next measurement has something to falsify.

## Follow-up: final-screen-x parity is NOT the discriminator, but position IS

All twelve points isolated by a 5x5 neighbourhood test, with coordinate parity:

| coord | x%2 | y%2 | vertex | AA arm |
|---|---:|---:|---|---|
| (121, 113) | 1 | 1 | v0 `kLeft` ZFront | **dropped** |
| (519, 113) | 1 | 1 | v1 `kRight` ZFront | survived |
| (447, 149) | 1 | 1 | v7 `1.75,1.25` ZFront | **dropped** |
| (121, 168) | 1 | 0 | v8 `kLeft` ZFront | **dropped** |
| (175, 168) | 1 | 0 | v2 `-2,1` ZFront | survived |
| (248, 204) | **0** | 0 | v5 `-1.5,0.75` ZBack | **dropped** |
| (392, 216) | **0** | 0 | v4 `1.5,0.5` ZBack | survived |
| (519, 222) | 1 | 0 | v6 `kRight` ZFront | survived |
| (417, 240) | 1 | 0 | v3 `2,0` ZBack | **dropped** |
| (121, 312) | 1 | 0 | v9 `kLeft` ZFront | **dropped** |
| (187, 324) | 1 | 0 | v10 `kLeft` ZBack | survived |
| (453, 324) | 1 | 0 | v11 `kRight` ZBack | **dropped** |

**Both sets contain odd and even x**, so the parity of the final screen x is not
the rule. That was the wrong space to test in, as this file already said it
would be -- the composited screen x is downstream of the resolve.

**But the outcome is a deterministic function of the projected x**, and that is
new:

- The three vertices at `kLeft` with `ZFront` -- v0, v8, v9 -- share one
  projected x (121) and **all three drop**.
- The two at `kRight` with `ZFront` -- v1, v6 -- share x=519 and **both
  survive**.
- At y=113 one drops (x=121) and one survives (x=519); at y=168, x=121 drops and
  x=175 survives; at y=324, x=453 drops and x=187 survives. **So y is not it,
  and within a row x decides.**

Same x, same outcome, every time. Whatever rejects these points reads the
horizontal position and nothing else that varies here -- not depth (v4 and v5
are both ZBack and split), not colour, not row.

**This is consistent with the column candidate and does not establish it.** A
rule keyed on the AA-column index would look exactly like this, but so would
several others, and the AA-column index cannot be computed from the composited
image because the sub-pixel positions are not recoverable from it. Testing it
properly needs the projected coordinates, which means instrumenting the
transform -- and the transform is `glsl/vsh.c:643`, which is **not this lane's**.

Recorded as the state of the evidence: the discriminator is horizontal position,
the mechanism is not established, and the next step lies outside this lane.
