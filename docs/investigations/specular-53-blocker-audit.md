# #53: the blocker is TRUE, and the capture it needs is a one-constant change

**Audited 2026-09-13, offline from the goldens and the test sources. No device,
no build, no arm.**

Instrument: [`docs/testing/specular53_four_value_probe.py`](../testing/specular53_four_value_probe.py).

## The claim under test

> the corpus supplies only two distinct N.L values per lit quad, so no 3-1 code
> can name its source vertex; the three settling observations all need captures
> we cannot produce

Two campaign precedents said a blocker of this shape was false with the
answering data already on disk — #31's 4-px anchoring regime and #13's wide-line
extent phase. **This one is true**, and the useful part of saying so is that the
audit converts it from an assertion into four measurements and names the capture
that lifts it — which turns out to be far cheaper than "a new nxdk_pgraph_tests
case".

## 1. The premise, measured rather than inherited

The light term is recovered model-free as
`(ControlFlags_VS - ControlFlagsNoLight_VS) / 0.75`, which cancels the
checkerboard and the constant term whatever they are, then plane-fitted per
triangle so the four per-vertex values come out **without assuming which vertex
feeds which corner**.

| | distinct levels, pooled over the 32 corner values of the 8 lit quads | max within any one quad | worst plane residual |
|---|---:|---:|---:|
| `Specular` | **2** (56.79, 69.16) | **2** | 1.10 |
| `Specular_back` | **2** (169.25, 211.07) | **2** | 1.14 |

A residual of ~1.1 byte is the quantisation floor (one byte, divided by 0.75).
So the premise holds: two levels, both suites, every quad.

## 2. The ambiguity is 16-fold, not merely "hard"

With two source values over four vertices — submission order `[A,B,B,A]` — the
`4^4 = 256` vertex→corner source maps produce only **16 distinct images**, and
**every observed image is produced by exactly 16 different source maps**. An
observed 3-1 code says a value was duplicated and cannot say from where. That is
the blocker's second clause, and it is arithmetic rather than a difficulty.

## 3. The discriminating class is empty across the whole corpus

`TestSuite` pushes `SET_LIGHTING_ENABLE false` before every test, so a test that
does not turn it on cannot be in the class — which makes the enumeration
complete rather than a sample. Of 200 test sources, **14** ever push
`SET_LIGHTING_ENABLE`. Of those 14, exactly **two** draw with a vertex program
while the hardware lighting unit is on:

* `Specular::ControlFlags_VS`
* `Specular back::ControlFlags_VS`

Both draw the same sixteen flat quads with four normals differing only in the
signs of `nx` and `ny`, under `kDirectionalLightDir{1, 0, 1}` — **y exactly
zero**, so `N·L` collapses onto `nx` and takes two values.

Rich-normal geometry under hardware lighting *does* exist in the corpus and is
**always fixed-function**:

| where | geometry | path |
|---|---|---|
| `Lighting_control` | cone, cylinder, sphere, Suzanne, torus | FF only — the VS variants push `SET_LIGHTING_ENABLE false` and print "(Lighting disabled)", lighting in the shader instead |
| `Specular::NonUnitNormal_*` | 65-vertex spherical triangle fan | `SetVertexShaderProgram(nullptr)` |
| `Specular::SpecParams_FF_*` | the same five models | name says FF; `nullptr` at line 598 |

So the corpus separates the two things it would need to combine.

## 4. The escape route exists, is readable, and is closed

The blocker is about the **light** term. The same draw also carries per-vertex
**diffuse** colour, whose four components are distinct by construction —
0.25/0.50/0.75/1.00, blue in `Specular`, red in `Specular_back`. That is a
four-valued probe of the vertex→corner association, and the class is non-empty.
So it was read.

**With the lighting unit off** (`ControlFlagsLightDisable_VS`, `LIGHTING_ENABLE = 0`)
it is recovered at all four corners **in submission order**:

| suite | quads matching submission order | max error vs the submitted constants | residual |
|---|---:|---:|---:|
| `Specular` | **8 of 8** | 0.95 byte | ≤0.95 |
| `Specular_back` | **8 of 8** | 0.37 byte | ≤0.93 |

So the vertex stream reaches the corners correctly under a vertex program, and
the #53 anomaly is created *inside* the lighting unit.

**With the lighting unit on** — the only condition under which the anomaly
exists — the lighting unit replaces the per-vertex diffuse with its own output.
Searched over every channel of every lit quad of both lighting-enabled captures
in both suites: **0 of 128 (quad × channel) slots carry the four submitted
values**, the closest being off by 77.5 bytes.

**The four-valued probe and the defect cannot coexist in this corpus.** That is
the sharpest statement of the blocker and it is a measurement, not an argument.

## 5. Settling observation 1 is partly answerable from disk

Observation 1 asks for `ControlFlags_VS` run twice on silicon, to decide whether
the association is deterministic at all. No second silicon capture exists: the
goldens repo carries **one commit** and one file per test.

What the corpus does carry is a **within-capture replicate**. q10/q13 and
q30/q33 are separate draws of identical geometry differing only in
`SET_LIGHT_CONTROL` — which does not enter the diffuse light term — and in x
position. Their light fields agree to:

    Specular       q10 vs q13   0.0000 L-units
    Specular       q30 vs q33   0.0000 L-units
    Specular_back  q10 vs q13   0.0000 L-units
    Specular_back  q30 vs q33   0.0000 L-units

Four pairs of four, both suites, exactly zero. With the cross-suite
deviation-set agreement already on the issue (5 of 6 patterns identical), the
association is deterministic **within a frame**.

**This does not close observation 1.** It cannot see a resolution that is fixed
per run and stable within it, which is exactly what two silicon runs would
test. Observation 1 is weakened, not answered.

## 6. The oB1 sub-claim: right in substance, loose in wording

> no capture writes anything but the vertex specular to oB1

Two shaders in the tree **do** write something else:

* `src/shaders/fixed_function_approximation_shader.vsh:86` — `mov oBackSpecular, #invalid_color`, and `invalid_color` is `{1,0,1,1}`, magenta;
* `src/shaders/passthrough_mul_color_by_constant.vsh:18` — `mul oBackSpecular, iBackSpecular, #back_specular_multiplier`.

Neither is **observable**:

* all 32 `Lighting_control` goldens contain **0 magenta pixels**, so the
  `invalid_color` write never reaches the framebuffer;
* the only suite rendering back faces under a vertex program is
  `Specular_back`, whose program is
  `projection_vertex_shader_no_lighting.vsh:24  mov oBackSpecular, iBackSpecular`
  — a pure passthrough, so `oB1 ≡ v8` there by construction.

The conclusion stands. The wording should be *"no capture in which oB1 is
observable writes anything but the vertex specular to it"*, because a lane
grepping the sources will find those two writes and conclude the note is wrong.

## What a discriminating capture must look like

A draw that is **all** of:

1. under a vertex program (`SetVertexShaderProgram(shader)`, not `nullptr`);
2. with `NV097_SET_LIGHTING_ENABLE = 1` and at least one light enabled;
3. whose primitive's vertices carry **four distinct `N·L`** values;
4. with the lit term reaching the framebuffer separably — the existing combiner
   setup in `TestControlFlags` already does this.

## And it is a one-constant change, not a new test case

`TestControlFlags` already submits four normals differing in the signs of
**both** `nx` and `ny`. Only the light kills the fourth degree of freedom, by
having `y = 0`. Changing `kDirectionalLightDir` from `{1, 0, 1}` to `{1, 0.5, 1}`
in `specular_tests.cpp:41` and `specular_back_tests.cpp:44` gives:

| | distinct `N·L` | spacing |
|---|---:|---|
| `{1, 0, 1}` — today | 2 | −0.7702, −0.6301 |
| `{1, 0.5, 1}` | **4** | −0.7591, −0.6931, −0.6271, −0.5611, even steps of 0.0660 |

Calibrated on the measurement in §1 — a 0.1400 `N·L` gap renders as 12.37 byte,
so **88.3 byte per unit `N·L`** — the four levels would be separated by
**5.83 byte** against a measured quantisation floor of ~1.1 byte, a **5.3×
margin**. Each corner's value then names its source vertex uniquely and the
association is *read* rather than fitted.

No new geometry, no new draw, no new test case: two constants. That is a much
cheaper request than the blocker implies, and it is the one to make.

## The leg to register, once that capture exists

Not registrable today — there is nothing to bind a prediction to without the
capture. When it exists, the leg is **exact and golden-constrained**: the
recovered per-corner source map for all eight lit quads, read directly off the
four distinct levels, compared against silicon. A fix that widens or reorders
plausibly but gets the association wrong cannot land all eight.

## What this does NOT establish

* **The mechanism.** Nothing here says what the lighting unit does differently
  under a vertex program. The audit bounds what the corpus can decide; it
  proposes no rule.
* **Observation 1.** See §5 — the within-capture replicate cannot see a
  per-run resolution.
* **Observation 3** (the sub-pixel x phase hypothesis) is untouched. It remains
  six cells against six data points, as `specular-light-association.md` records.
* **Anything about our own captures.** This audit reads goldens and test
  sources only. No emulator capture was scored.
* **Whether `{1, 0.5, 1}` is the best choice.** It is *a* sufficient one, chosen
  because it is minimal and its separation is calculable from data already
  measured. A larger `y` separates further and changes more of the scene.
* **The sign convention** mapping `N·L` to the rendered byte. Only |slope| is
  used, and separability does not depend on it.
