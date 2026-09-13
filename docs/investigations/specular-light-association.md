# #53's per-vertex light association: established, and not derivable from this corpus

Derived offline from the goldens plus the `z-after-057/058` captures
(`2501f35211`, APK `553cfffc73d3`), which is the tip after both of #53's
landed fixes -- the lighting mux `63be3ebf75` and the back-specular
`oB1 = v8` `7a650a98a9`. No build, no device.

Reproduce with `python3 docs/testing/specular_light_assignment.py
[RESULTDIR ...]`.

## The instrument, and why it needs no model

#53's residue lives in `Specular`/`Specular_back`'s `ControlFlags_VS`. Those
tests draw sixteen screen-space quads in four rows of four over a 0x00/0x20
checkerboard. Rows 1 and 3 put the DIFFUSE channel on screen, so they carry
the light loop's diffuse term: **eight lit quads**, which matches the
"8 lit quads" already recorded on the issue.

Two facts make the light term recoverable exactly:

* `ControlFlagsNoLight_*` is the same scene with `LIGHT_ENABLE_MASK = 0`.
  Subtracting it cancels the checkerboard **and** the constant term, whatever
  they are -- no model of either is needed.
* The blend weights are exactly 0.75/0.25, pinned twice over: the no-light
  quad reads 6 over background 0 and 14 over background 32, from a source of 8
  (`kSceneAmbientColor` = 0.031373 = 8/255). `6/8` gives the source weight and
  `(14-6)/32` the destination weight, independently, and both give the same
  answer. Note it is **not** the framebuffer alpha, which reads 207.

So `light = (lit - unlit) / 0.75`, and a quad's field is piecewise linear on
the two triangles the quad is split into. Plane-fitting each triangle recovers
the four per-vertex values **without assuming which vertex feeds which
corner**, which is the question at issue.

Three things fall out before any hypothesis:

**The quad is split on the UL-LR diagonal**, i.e. `(v0,v1,v2)+(v0,v2,v3)`.
Pooled worst residual 1.10 bytes against 5.94 for the other diagonal on
`Specular`, and 1.14 against 20.20 on `Specular_back`. 1.1 is the
quantisation floor (one byte, divided by 0.75).

**The field is continuous across that diagonal.** The two triangles disagree
at the shared corners by at most 0.42 (front) and 0.41 (back) L-units. This
matters: it kills the whole family of models in which each triangle gets its
own permutation of its three vertices' values, because such a model can only
produce two distinct quad patterns once continuity is imposed, and six are
observed.

**The level set is the fixed-function level set.** Every one of the 32 fitted
corner values per suite lands on one of the two levels the `_FF` capture
produces, worst distance **0.38** (front, levels 56.72/68.95) and **0.61**
(back, levels 168.73/210.79). No parameter was fitted to make that happen --
the levels come from a different capture. The two levels are the two values
`N·L` can take: the four normals differ only in the sign of `nx` (and, in the
back test, `ny`), the light has no eye-space `y` component, so `N·L` takes
exactly two values and the fixed-function capture shows exactly the
left/right split that implies.

## The claim on the issue survives, with one correction

> in 4 of 8 lit quads, silicon's per-vertex light assignment is not a
> permutation of the vertex stream

**Established, and it is 3 of 8, in each suite** -- six of sixteen lit quads,
not four of eight. Codes over the corners in submission order (UL, UR, LR,
LL), H the high level:

| quad | `SET_LIGHT_CONTROL` | `Specular` FF | `Specular` VS | `Specular_back` FF | `Specular_back` VS |
|---|---|---|---|---|---|
| q10 | SEP_SPEC\|ALPHA_FROM_MAT | HLLH | **LLHL** | LHHL | HLHL |
| q11 | SEP_SPEC | HLLH | HHLL | LHHL | LHHL |
| q12 | ALPHA_FROM_MAT | HLLH | **HLHH** | LHHL | HLLH |
| q13 | 0 | HLLH | **LLHL** | LHHL | HLHL |
| q30 | SEP_SPEC\|ALPHA_FROM_MAT | HLLH | LHLH | LHHL | **LHLL** |
| q31 | SEP_SPEC | HLLH | HLLH | LHHL | **HHLH** |
| q32 | ALPHA_FROM_MAT | HLLH | LHHL | LHHL | LLHH |
| q33 | 0 | HLLH | LHLH | LHHL | **LHLL** |

Bold are the odd-weight codes: three highs and one low, or one and three.
Four normals can supply only two of each, so no reordering of the vertex
stream produces them -- per quad, and, by the continuity result above, per
triangle as well. A value is *duplicated*, not moved.

**Fixed function is uniform**: the same code on all eight quads, in both
suites. So this is specific to the programmable path, and the
fixed-function capture is a clean control rather than a second unknown.

## The decisive pixels: q31 front, q11 back

Our own captures, decomposed the same way, emit the **fixed-function** code on
all eight quads in both suites (worst distance from a level 0.11 and 0.13). So
the arithmetic, the geometry, the blend and the interpolation in our
programmable path are all already right, and the whole residue is the
association. The per-quad residual against the golden says so to the pixel:

| `Specular/ControlFlags_VS` | px | max |
|---|---:|---:|
| q31 -- the one quad whose golden code **is** the fixed-function code | **327** | **1** |
| q10 | 8,277 | 20 |
| q11 | 8,191 | 20 |
| q12 | 7,959 | 20 |
| q13 | 8,269 | 20 |
| q30 | 7,483 | 9 |
| q32 | 8,476 | 20 |
| q33 | 8,147 | 20 |
| whole capture | 75,691 | 20 |

`Specular_back/ControlFlags_VS`: q11 is **2,081** px at max 1; the other seven
lit quads are 8,051-8,480 at max 31-45; the capture is 86,567.

That is the calibration the method needs. On the single quad where silicon's
association agrees with ours, we are within one byte over 8,480 pixels --
which proves the instrument and proves that nothing else is left. `max 20`
elsewhere is exactly the blue channel's level gap (26.9 L-units x 0.75 =
20.2), so no differing pixel is wrong by more than one level swap. The
residual is the association and only the association.

Also worth recording, because it is free: q22 and q23 carry 5,226 and 4,089 px
**identically in the lit and the unlit capture**, so 11,224 px of
`ControlFlags_VS`'s total is a pre-existing residual that has nothing to do
with the light. #53's own share of that capture is about 64,200 px.

## Every uniform rival is excluded by the same measurement

A shader with no rule can only emit a uniform assignment, so all sixteen were
scored against the golden -- synthesising the Gouraud field for each candidate
over the measured diagonal and counting red-channel pixels beyond
quantisation:

| `Specular` | px | quads reproduced |
|---|---:|---:|
| LLHL | 35,435 | 2 |
| LHLH | 37,538 | 2 |
| LHHL | 38,428 | 1 |
| fixed function HLLH | 44,984 (rank 9 of 16) | 1 |

| `Specular_back` | px | quads reproduced |
|---|---:|---:|
| HLHL | 47,162 | 2 |
| LHLL | 48,411 | 2 |
| fixed function LHHL | 54,167 (rank 5 of 16) | 1 |

**No uniform assignment reproduces the golden.** The best is right on two of
eight quads. Switching to it would take about 21% off the red residual and is
a pure curve fit: it has no mechanism, it disagrees with the fixed-function
path that is separately verified correct, and it would have to be gated on
"programmable" for no stated reason. Not done.

## What the corpus can and cannot decide

Two exclusions are real, and both are measurements rather than arguments:

* **`SET_LIGHT_CONTROL` alone does not select the association.** q10 and q13
  differ in it (SEP_SPEC|ALPHA_FROM_MAT against 0) and share a code; q31 and
  q11 share it and do not share a code between rows. So it is not a function
  of that register.
* **Position alone does not select it either.** The two suites draw the
  sixteen quads at the same positions and get different codes at the same
  quad, beyond the front/back level swap.

What is left is a joint dependence, and here the corpus runs out. Within one
suite the eight codes are consistent with being a function of *(the quad's
sub-pixel x phase, the row)*: the four columns sit at fractional x offsets
2/3, 1/3, 0, 2/3, and it is exactly the two columns sharing a phase -- q10/q13
and q30/q33 -- that share a code, in both suites, four pairs out of four. But
three phases by two rows is six cells and six distinct codes are observed, so
**that hypothesis has as many free parameters as it has data and cannot be
tested here.** Recording it as the shape to attack, not as a finding.

One structural fact does survive, and it argues the association is
deterministic rather than a race between the pushbuffer and the vertex
pipeline. Take each code's deviation from its own suite's fixed-function code:

```
Specular      {0000, 0011, 0101, 1011, 1101, 1111}
Specular_back {0000, 0011, 0101, 1011, 1100, 1111}
```

Five of six deviation patterns are **identical** between the two suites, and
the sixth differs in one bit -- while the quad each is attached to is
permuted. A race would not reproduce five of six patterns across two captures.

## The blocker, as the measurement that would refute it

Every lit quad in the corpus submits the **same four normals in the same
order**, and those four normals supply only **two** distinct `N·L` values. So
an observed 3-1 code says a value was duplicated but cannot say *which*
vertex it was duplicated from: with only two distinct values available, many
source maps predict the same colour at every pixel. That is why this is not
derivable here, and it is a property of the test rather than of the analysis.

Three captures would settle it, in this order, and all three are
nxdk_pgraph_tests changes rather than emulator changes:

1. **Run `Specular::ControlFlags_VS` twice on silicon and compare the eight
   codes.** If they differ, the association is not a function of anything and
   every question below is moot. This needs no new test -- just two captures.
   The deviation-set result above predicts they will agree; that prediction is
   what the run tests.
2. **A quad whose four vertices carry four distinct light terms** -- four
   normals with four distinct `N·L`, under a vertex program with
   `LIGHTING_ENABLE` and a light. Then each corner's value names its source
   vertex uniquely and the association is *read*, not fitted. This is the one
   that turns the question from underdetermined into arithmetic.
3. **The same quad, same state, at several sub-pixel x offsets in one
   capture** (left edge at k, k+1/4, k+1/3, k+1/2, k+2/3). If the code tracks
   the phase, the sub-pixel hypothesis is established with one capture; if it
   does not, it dies with one capture. Five extra draws in an existing test.

Until then #53's remaining residue -- about 64,200 px on
`Specular/ControlFlags_VS` and about 69,000 on `Specular_back` -- is
**correctly valued and correctly parked**: the light loop is arithmetically
exact, every differing pixel is one level swap and no more, and the priority
the issue already carries (low; a vertex program with `LIGHTING_ENABLE` is not
a state D3D titles program) is the right one.
