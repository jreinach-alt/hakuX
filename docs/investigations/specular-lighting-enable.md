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
