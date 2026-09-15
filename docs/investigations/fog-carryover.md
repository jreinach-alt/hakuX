# `Fog_carryover` is one defect, and it is not the fog gen mode

Every failing pixel in this suite is the draw that omits the fog coordinate.
Nothing else in it fails at all.

Measured on `score_rad1` (all eight fog suites, `iso_fog.iso`):

| test | px differing | where |
|---|---:|---|
| `CarryoverTris`, `CarryoverPoints`, `CarryoverPoly`, `CarryoverQuads`, `CarryoverQuadStrip`, `CarryoverTriFan`, `CarryoverTriStrip` | **16,384 each** | rows 64-439, cols 448-511 |
| `CarryoverLines` / `LineStrip` / `LineLoop` | 16,464 / 16,952 / 17,456 | the same block, plus line pixels |
| `FogCarryover` | 12,096 | rows 62-353, cols 299-393 |

16,384 is exactly the 64x256 right-hand quad -- the one the test draws
*without* specifying a fog coordinate. And the colours say which way it
fails, uniformly over all 16,384:

| | ours | golden |
|---|---|---|
| `CarryoverTris` | `(0,0,255)` — diffuse, no fog | `(255,0,0)` — fog colour, full fog |

The left columns, which do write a fog coordinate, are exact. So fog is
correct when the guest specifies it and wrong when the guest relies on the
last value persisting.

## The obvious explanation is wrong, and the measurement says so

The suite sets `NV097_SET_FOG_GEN_MODE_V_SPEC_ALPHA`, and its shader
(`passthrough_just_position_and_color.vsh`) writes `oPos`, `oDiffuse`,
`oSpecular`, `oBackDiffuse`, `oBackSpecular` -- and never `oFog`. Meanwhile
`glsl/vsh.c` takes the programmable path's fog coordinate from `oFog.x`
unconditionally, under a FIXME asking whether foggen ought to do something
there. Fog from the specular alpha, a program that sets specular and not fog,
and an emulator reading the register the program never wrote: that reads like
the whole answer.

It is not. Honouring `FOGGEN_SPEC_ALPHA` in the programmable path, exactly as
the fixed function stage does (`clamp(oD1.a, 0.0, 1.0)`), and leaving every
other mode on `oFog.x`, costs **7,449,481 channels** across the fog suites:

| suite | before | after | delta |
|---|---:|---:|---:|
| `Fog_coord_vec4` | 92,070 | 2,415,162 | **+2,323,092** |
| `Fog_exceptional_value` | 5,435,524 | 8,130,347 | +2,694,823 |
| `Fog_gen` | 4,666,628 | 6,436,978 | +1,770,350 |
| `Fog_carryover` | 357,032 | 1,018,248 | +661,216 |
| `Fog`, `Fog_param`, `Fog_vsh`, `Fog_inf_coord` | | | 0 |

`Fog_coord_vec4` is the one that settles it. Those captures were at **nine**
differing pixels -- as exact as anything in the corpus -- and the change took
them to 61,143 apiece. They set the fog coordinate and expect it used, with
the gen mode set to something else entirely.

**Under a vertex program the nv2a ignores `FOG_GEN_MODE` and uses `oFog`.**
The FIXME's note that RollerCoaster Tycoon sets `FOGGEN_PLANAR`, writes
`oFog.xyzw = v0.z` and expects `oFog.x` was the right read of the hardware all
along, and it generalises: it is not a quirk of one game, it is the rule.
Reverted; the tree is as it was.

## What is actually left

Register persistence. On hardware the vertex engine's output registers keep
their contents; a program that never writes `oFog` leaves whatever the last
one put there, which is precisely what "carryover" names. `glsl/vsh.c:213`
starts every invocation at `vec4(0.0,0.0,0.0,1.0)` instead.

That is consistent with every measurement here, including the ones that
killed the foggen hypothesis:

| | program writes `oFog`? | result |
|---|---|---|
| `Fog_coord_vec4` | yes | exact, 9 px |
| RollerCoaster Tycoon | yes | works today |
| `Fog_carryover` | **no** | we give the initialiser, hardware gives the carried value |

And "does this program write `oFog`" is decidable from the program text, so
the condition is free. What is not free is the value: it is whatever the
previous draw's last vertex produced, which lives on the GPU. Emulating it
needs either the last value tracked on the CPU for the cases where it is
derivable from an attribute, or a readback. That is a design decision about
cross-draw state rather than a line of shader, so it is written down here
rather than attempted.

357,032 channels, and the cause is now named rather than guessed at.
