# Specular: the programmable path is structurally wrong, the fixed one is not

Taken from the corpus re-ranked on non-one-step residue, where `Specular` and
`Specular_back` together carry 1,057,695 structural channels over 39 captures
and had not been looked at. This is a first characterisation, not a diagnosis.

| suite | px | captures | exact |
|---|---:|---:|---:|
| `Specular` | 444,161 | 22 | **0** |
| `Specular_back` | 307,266 | 17 | **0** |

## The split is along the shader path, not the feature

| capture | px | of which \|d\|=1 | max \|d\| |
|---|---:|---:|---:|
| `Specular::ControlFlags_VS` | 94,819 | 8,830 | **253** |
| `Specular::ControlFlagsNoLight_VS` | 94,819 | 8,830 | **253** |
| `Specular::ControlFlagsLightDisable_VS` | 53,452 | 50,135 | 3 |
| `Specular::ControlFlagsLightDisable_FF` | 51,701 | 48,685 | 32 |
| `Specular::ControlFlags_FF` | 41,101 | 40,283 | 32 |
| `Specular_back::ControlFlags_VS` | 95,592 | 9,783 | **253** |

The two `ControlFlags*_VS` captures are the whole of the top: ~86,000 px each
above one step, against fixed-function variants that are 95%+ one-step with a
maximum of 32. **The programmable vertex shader path is structurally wrong
where the fixed-function path is within precision.**

Their pixel counts are equal to the pixel — 94,819 twice in `Specular`, 95,592
twice in `Specular_back` — but the images are not identical, and neither are
their goldens. Equal counts, different content.

## What the wrong region looks like

On `Specular::ControlFlags_VS`, 94,819 px over rows 190-459 and cols 107-577,
about a third of the frame:

| | most common colours where wrong |
|---|---|
| ours | `(0,0,191)`, `(0,0,192)`, `(0,0,190)` — pure blue, red and green at zero |
| gold | `(66,26,48)`, `(58,18,40)`, `(59,19,33)` — red and green present, blue far dimmer |

We emit blue alone across a large object; hardware emits a mix with red and
green and much less blue. That is not a shading gradient being slightly off, it
is a different colour being produced.

`CreateGeometry` sets the per-vertex diffuse to `{0, 0, 0, 0.75}` and notes
that `SET_COLOR_MATERIAL` makes the per-vertex diffuse be ignored entirely,
while the alpha from the specular value is added to the material alpha — so
where our blue comes from is itself a question worth asking first.

## Why this is worth someone's time

It is the largest structural block on the re-ranked board that nobody has
opened, it is concentrated in four captures rather than spread thin, the
fixed-function control is nearby and nearly correct, and the failure is a gross
colour difference rather than a rounding rule. There is also a known structural
hazard in this area: `foggen` lives in `FixedFunctionVshState` and is unioned
with `ProgrammableVshState`, so the programmable path cannot see it (standing
FIXME at `glsl/vsh.c:374`). Whether specular state has the same problem is the
first thing to check.

## Measured: our fixed-function output is closer to the VS golden than our VS is

Two comparisons, both pointing the same way. Rather than guess what the
programmable path does wrong, ask whether it lands anywhere near hardware's
answer for the same test:

| test | our VS vs gold VS | **our FF vs gold VS** |
|---|---:|---:|
| `ControlFlagsNoLight` | 94,819 px | **23,591 px** |
| `ControlFlags` | 94,819 px | **92,793 px** |

On `ControlFlagsNoLight` our **fixed-function** render is four times closer to
the **programmable** golden than our own programmable render is. The colours in
the disputed region say the same thing plainly:

| | most common colours |
|---|---|
| our VS | `(0,0,191)`, `(0,0,192)`, `(0,0,190)` |
| our FF | `(60,14,24)`, `(52,6,16)`, `(55,6,16)` |
| **gold VS** | `(66,26,48)`, `(58,18,40)`, `(59,19,33)` |

Our fixed-function output and hardware's programmable output are the same family
of colours. Our programmable output is pure blue with red and green at zero.

Two things follow, and both are measured rather than inferred:

- **We do run the shader.** Our VS and FF outputs differ by 106,574 px, so the
  programmable path is not being silently ignored.
- **Hardware's two paths agree far more than ours do.** On
  `ControlFlagsNoLight`, gold's VS and FF differ by 23,478 px where ours differ
  by 106,517. Hardware's programmable result stays close to its fixed-function
  result; ours diverges into a different colour entirely.

So the defect is in what our programmable path produces, and its signature is
the loss of red and green with blue left high. That is as far as the
measurements reach. **No mechanism is offered here** -- four were offered and
killed across this corpus tonight, and the next claim about this suite should
arrive with a measurement that survives being looked at twice.
