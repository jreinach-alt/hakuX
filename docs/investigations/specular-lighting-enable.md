# Both specular suites are four captures, and it is `LIGHTING_ENABLE`

`Specular` and `Specular_back` carry 546,438 and 511,257 structural channels on
the board. Measured per capture with the one-step share and the worst error
(`score_um_light1`, `iso_light.iso`, eleven lighting suites):

| capture | channels | one-step | max |
|---|---:|---:|---:|
| `Specular ControlFlags_VS` | 341,984 | 5.2% | 253 |
| `Specular_back ControlFlagsNoLight_VS` | 329,049 | 6.6% | 253 |
| `Specular_back ControlFlags_VS` | 328,449 | 7.0% | 253 |
| `Specular ControlFlagsNoLight_VS` | 325,340 | 5.5% | 253 |
| `Specular ControlFlagsLightDisable_VS` | 68,184 | **95.0%** | **3** |
| `Specular_back ControlFlagsLightDisable_VS` | 65,873 | **97.8%** | **3** |
| every `_FF` capture | 501 - 65,090 | 92% - 100% | 32 - 112 |

**Four captures hold 1,244,148 of the two suites' 1,330,629 structural
channels, 93.5% of it.** Everything else in both suites, the whole
`SpecParams` set and every fixed function capture, is a precision floor.

The three `_VS` captures differ only in two register writes:

| capture | `LIGHTING_ENABLE` | light enabled | result |
|---|---|---|---|
| `ControlFlagsLightDisable_VS` | false | no | **97.8% one-step, max 3** |
| `ControlFlagsNoLight_VS` | **true** | no | 5.5% one-step, max 253 |
| `ControlFlags_VS` | **true** | **yes** | 5.2% one-step, max 253 |

## We do not react to either write

Comparing renders against each other rather than against the goldens:

| | ours | golden |
|---|---:|---:|
| `LightDisable_VS` vs `NoLight_VS` | **722 px** | 85,922 px |
| `NoLight_VS` vs `ControlFlags_VS` | **656 px** | 85,856 px |

656 and 722 pixels is the printed test name. **We render all three the same
image**; silicon renders three different ones. And ours is the *lighting-off*
one in every case -- our `NoLight_VS` is closer to the `LightDisable_VS`
golden (54,331 px) than to its own (94,893 px), and the same for
`ControlFlags_VS`.

So under a vertex program, `NV097_SET_LIGHTING_ENABLE` and the light state
both change silicon's output substantially, and change ours by the label
only. Whatever the fixed function stage does with those registers, some of it
survives a programmable vertex shader.

## The obvious mechanism, measured and dead

`vsh-ff.c` folds the specular into the diffuse when lighting is on and the
specular is not kept separate:

```c
if (lighting && (!specular_enable || !separate_specular)) {
    oD0.xyz += oD1.xyz;
    oB0.xyz += oB1.xyz;
}
```

The programmable path does not, which is exactly the shape of a defect that
appears only when lighting is enabled. Applying the same fold there, with
`lighting` captured for both paths:

| | channels | structural |
|---|---:|---:|
| before | 5,907,445 | 1,839,724 |
| with the fold | 5,906,277 | 1,836,937 |
| delta | **-1,168** | **-2,787** |

Four captures moved and one of them got worse. Against a target of 1.24M
channels this is nothing: the fold reaches a few hundred pixels and is not
what separates the three renders. Reverted.

Measured over all eleven lighting suites, 195 captures, so the negative also
says the fold changes nothing anywhere else -- which is its own small result,
since it means the difference between the two vertex paths on that line is
not observable in this corpus.

## What the goldens say it is

Checkable without a build, which is where this should have started. Over the
85,922 pixels where the two goldens differ:

| golden | mean RGB | distinct colours there |
|---|---|---:|
| `ControlFlagsLightDisable_VS` | `[21.6, 22.3, 137.7]` | many |
| `ControlFlagsNoLight_VS` | `[9.3, 9.3, 9.3]` | **30, every one of them grey** |
| `ControlFlags_VS` (one light) | `[46.1, 14.4, 27.8]` | many |

**With lighting enabled and no lights, silicon's output in that region is
greyscale** -- 30 distinct values, all of the form `[n,n,n]`: `[14,14,14]`,
`[6,6,6]`, `[0,0,0]`, `[32,32,32]`. It is darker than the lighting-off image
on 85,746 of 85,922 pixels. Turn a light on and colour comes back, tinted by
the light.

The blue the lighting-off image carries there is the vertex colour the program
wrote. Enabling the unit with no lights does not dim it or add to it: it
**replaces** it with a grey that has no dependence on the vertex colour at all.
That is the material path taking over -- the emissive and ambient terms, with
no diffuse or specular contribution to add because no light is enabled -- and
it happens under a vertex program, where our implementation assumes the
program owns the colour outputs outright.

So the mechanism is not "lighting adds something the programmable path
misses". It is that `LIGHTING_ENABLE` gates *which source* feeds the colour
outputs, and that gate survives a programmable vertex shader. The colour
material source registers (`CSV0_C` EMISSION / AMBIENT / DIFFUSE / SPECULAR)
are the obvious place that selection lives, and `Material_color_source` is a
suite with 72,300 structural channels of its own that would be worth reading
alongside.

1,244,148 structural channels in four captures, two registers that provably
do nothing in our programmable path and provably do something on silicon, and
a signature -- grey where the vertex colour should be -- specific enough to
check any candidate against before building it.

## Landed

`f0829404`. The colour material selectors and light enables move out of the
fixed function union into the shared vertex state, the constant term comes out
of `append_lighting` into a helper both paths call, and the programmable path
emits it when `LIGHTING_ENABLE` is set.

Over all eleven lighting suites, 195 captures:

| | before | after | |
|---|---:|---:|---:|
| `Specular` | 1,098,410 | 949,436 | |
| `Specular_back` | 816,777 | 471,283 | |
| nine other suites | | unchanged to the channel | |
| **total channels** | 5,907,445 | 5,412,977 | **-494,468** |
| **total structural** | 1,839,724 | 1,410,402 | **-429,322** |

Per capture:

| capture | before | after | one-step now | max |
|---|---:|---:|---:|---:|
| `Specular_back ControlFlagsNoLight_VS` | 329,049 | **83,597** | 3.9% | 254 |
| `Specular_back ControlFlags_VS` | 328,449 | 228,407 | 1.4% | 254 |
| `Specular ControlFlagsNoLight_VS` | 325,340 | 242,449 | 1.8% | 254 |
| `Specular ControlFlags_VS` | 341,984 | 275,901 | 1.7% | 254 |
| `ControlFlagsLightDisable_VS` (both) | 68,184 / 65,873 | **unchanged** | 95% / 98% | 3 |

The lighting-off captures not moving at all is the check that the new code
fires only where the register is set, and the nine untouched suites -- every
fixed function capture among them -- is the check that the refactor left that
path's shader text alone.

## The constant term was reading zeros

`f0829404` emitted the constant term and it evaluated to zero.
`set_vsh_uniform_values` gates `ltctxa`, `ltctxb`, `ltc1` and the light vectors
on `is_fixed_function` alone, so the registers the new code depends on were
never uploaded for a vertex program.

The goldens pinned it without a build. On `ControlFlagsNoLight_VS` the golden
was exactly **six higher than us on both tones** of the quad region, and six
falls out of the blend: silicon composites a source grey of 8 at the alpha we
were already producing, giving 6 over the background's 0 and 14 over its 32,
while we composited a source of 0 and got 0 and 8. Not a blend difference and
not a selector difference -- the constant itself was zero because the register
never arrived. `fb9cf8c7`:

| capture | before | after |
|---|---:|---:|
| `Specular ControlFlagsNoLight_VS` | 242,449 | **37,969** |
| `Specular ControlFlags_VS` | 275,901 | 258,861 |
| everything else in the sweep | | unchanged |
| **total channels** | 5,412,977 | 5,191,457 |
| **total structural** | 1,410,402 | **1,188,882** |

Every channel removed was structural.

## Where the two suites stand

| | structural, start of day | now |
|---|---:|---:|
| `Specular` + `Specular_back` | 1,330,629 | **679,787** |

## What the residue is, corrected

`f0829404`'s commit message said what remains "is the lights". That is wrong
for the front and right for the back, and the two are different defects:

| | unlit capture | lit capture | attributable to the light |
|---|---:|---:|---:|
| `Specular` | 37,969 | 258,861 | **220,892** |
| `Specular_back` | 83,597 | 228,407 | 144,810 |

Now that the front's constant term is arriving, the light *is* the dominant
front residue -- but it was not when I wrote that, and the back still carries
83,597 with no light enabled at all. `Specular_back` did not move for the
uniform fix either, so its constant term was already arriving and its unlit
residue is something else again.

The light contribution needs an eye-space normal. The fixed function stage
builds it from the `normal` attribute and `invModelViewMat`, both of which a
vertex program's shader can reach -- `v2` is declared like any other attribute
and the matrix registers are uploaded now. What it also needs is the rest of
the lighting header: the per-light colour defines, `specularFactor`, `ltMul`,
`FLOAT_MAX`. That is a refactor of `vsh-ff.c`'s header emission into something
both paths call rather than a few lines, which is why it stops here.

## The light loop, measured and held back

Built the rest of it: `vsh-ff.c`'s lighting header factored into a function
both paths call, `local_eye` and `normalization` moved to the shared state
beside `lighting`, and the programmable path emitting the full
`append_lighting` -- constant term, light loop and all -- with the eye-space
inputs the fixed function stage uses when skinning is off:

```
vec4 tPosition = position * modelViewMat0;
vec3 tNormal = (vec4(normal, 0.0) * invModelViewMat0).xyz;
```

The reasoning is the same one that made the constant term work: the lighting
unit does not read the program's outputs, it reads the vertex, so it should
reach the position and normal attributes through the transform registers.

Over all eleven lighting suites, 195 captures:

| capture | before | after |
|---|---:|---:|
| `Specular ControlFlags_VS` | 258,861 | 229,197 |
| `Specular_back ControlFlags_VS` | 228,407 | 203,041 |
| everything else | | unchanged |
| **total** | 5,191,457 | 5,136,427 |

**−55,030 channels, no regressions, and only the two lit captures move** --
which is the right shape. But it is 12% of the ~365,000 the lights are
supposed to account for, and 12% is the wrong number for a model that is
actually right.

The test says why. `TestControlFlags` calls
`SetXDKDefaultViewportAndFixedFunctionMatrices()` once, and then drives the
**program's** model matrix per draw -- `shader->GetModelMatrix()`,
`MatrixRotate`, `MatrixTranslate`. So the geometry rotates through constants
the vertex program owns while `modelViewMat0` sits at the XDK default.
Hardware's lighting follows the rotation; a normal built from the fixed
function register cannot. Whatever the unit reads, it is not that.

So this is held back rather than landed. It changes colour output for every
vertex-program draw with lighting and a light enabled, and 12% on two
captures is not enough to ship a model the test's own setup argues against.
Reverted; the measurement is the result.

What it does establish: the remaining lit residue is not the *presence* of a
light term, which is now emitted, but where its geometry comes from. That is
a question about what the lighting unit sees when a vertex program owns the
transform, and it wants hardware evidence rather than another candidate.
