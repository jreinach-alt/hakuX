# `Attrib_float` is `NaNToOne` plus the colour floor — and `gl/vertex.c` is not involved

I picked `Attrib_float` (50,893 channels per capture, n=12) because it resolved
to **`gl/vertex.c`, the one in-lane file with zero unmerged peer commits**.
That criterion is about whose tree is current, not about where the bug is, and
here the two came apart: `gl/vertex.c` is not implicated at all.

Reproduced by
`docs/testing/attrib_float_columns.py <pgraph_run_root> <goldens_root>`.

## Deterministic, five times over, at zero cost

| binary | total | byte-exact |
|---|---:|---:|
| `0.3.3-j1-102-g0b0e037` | 610,719 | 3 / 12 |
| `0.3.3-j1-103-gc7a7878` | 610,719 | 3 / 12 |
| `0.3.3-j1-104-gc43f5f8` | 610,719 | 3 / 12 |
| `0.3.3-j1-306-gf659312a` | 610,719 | 3 / 12 |
| `0.4.0-j1-331-gd7dfe146` | 610,719 | 3 / 12 |

Identical **to the channel** across five binaries spanning 0.3.3-j1-102 to
0.4.0-j1-331 — runs already on disk, no emulator run spent.

Worth recording against the test's own source: `attribute_float_tests.cpp:55`
carries a TODO saying *"the handling of the signaling NaN is nondeterministic.
Sometimes it is converted to quiet NaN."* On this host it is **not** — 
`-NaNs_NaNs` sits at exactly 44,091 in all five runs.

## The structure is per-column, and binary

The suite draws **seven columns**, one quad each: a plain passthrough, then six
where a vertex shader multiplies the diffuse colour by **1.0, 0.0, −INF, +INF,
−NaNq, +NaNq** (`attribute_float_tests.cpp:139-140`). **So even the mundane
"0 to 1" capture carries infinities and NaNs — through the multiplier, not the
attribute.** That is why `0_1` and `0_8` are the *worst* captures at 93,345
each, which reads as a paradox until you read the test.

Differing pixels per column:

| capture | passthru | ×1.0 | ×0.0 | ×−INF | ×+INF | ×−NaNq | ×+NaNq |
|---|---:|---:|---:|---:|---:|---:|---:|
| `0_1` | 6,223 | 6,223 | 0 | 0 | 6,223 | 6,223 | 6,223 |
| `0_8` | 6,223 | 6,223 | 0 | 0 | 6,223 | 6,223 | 6,223 |
| `-1_1` | 6,223 | 6,223 | 0 | 6,222 | 6,223 | 0 | 0 |
| `-8_1` | 6,223 | 6,223 | 0 | 6,222 | 6,223 | 0 | 0 |
| `-INF_INF` | 6,223 | 6,223 | 0 | 6,222 | 6,223 | 0 | 0 |
| `-Max_Max` | 6,223 | 6,223 | 0 | 6,222 | 6,223 | 0 | 0 |
| `-MinN_MinN` | 0 | 0 | 0 | 6,222 | 6,223 | 0 | 0 |
| `-NaNq_NaNq` | **14,637** | 0 | 0 | 0 | 0 | 0 | 0 |
| `-NaNs_NaNs` | **14,637** | 30 | 0 | 0 | 0 | 0 | 0 |
| `-MaxSN_MaxSN` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `-Min_Min` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Every non-zero cell is 6,222/6,223 or 14,637 — a column is either exactly wrong
or exactly right, never partly. **×0.0 is correct in every capture**, including
where the attribute is INF or NaN. Both subnormal captures are byte-exact
everywhere.

## Two populations, and they are different defects

Measuring how far each column moves from its own column 0, **on our side and
hardware's separately**:

| capture | column | ours moves | hardware moves |
|---|---|---:|---:|
| `0_1` | ×0.0 | 43,911 | 43,911 |
| `0_1` | ×−INF | 43,911 | 43,911 |
| `-MinN_MinN` | ×−NaNq | 44,064 | 44,064 |
| **`-NaNq_NaNq`** | **×1.0** | **0** | **43,911** |
| **`-NaNq_NaNq`** | **×−INF** | **0** | **43,911** |
| **`-NaNq_NaNq`** | **×+NaNq** | **0** | **43,911** |

For ordinary attributes our pipeline responds to the multiplier exactly as
hardware does. **When the attribute is NaN, hardware still responds to every
multiplier and we respond to none** — because our column is already saturated.

**Population 1 — the NaN attribute.** `-NaNq_NaNq` column 0 is **one colour,
`[255, 255, 255]`, across all 14,637 differing pixels**, where hardware draws a
255-value gradient. The cause is named in the shader generator:

```c
/* hw/xbox/nv2a/pgraph/glsl/vsh.c:239 */
"vec4 NaNToOne(vec4 src) {\n"
"  return mix(src, vec4(1.0), isnan(src));\n"
"}\n"
...
"  vtxD0 = colorPrecision(clamp(NaNToOne(oD0), 0.0, 1.0));\n"   /* :510 */
```

A NaN diffuse component is turned into **1.0** before the clamp, so the whole
quad saturates to white and every later multiply is a no-op on it. Hardware
does something else, and whatever it is, it still varies with the multiplier.

**Population 2 — everything else.** `0_1` column 0: 6,223 pixels, 248 distinct
colours on our side against 226 on hardware's, and the signed delta is bounded
by **[−1, +1]** with **100% at |d| ≤ 2**. That is the same ±1 colour floor
already characterised in `Attrib_carryover` — and `colorPrecision`, the
truncation added by `5c2b26db`, sits on the same line.

## Where the fix would live — not here

Both populations resolve to **`glsl/vsh.c`**: `NaNToOne` at `:239`, applied at
`:510`, `:511`, `:528`, `:529`, and `colorPrecision` alongside it. That file is
`[free]`, not this lane, and it is the `psh.c`/`vsh.c` grant already wanted by
seven other leads. **Eight now.**

`gl/vertex.c` binds the attribute (`glVertexAttrib4fv` at `:110`) and does not
touch NaN. Choosing the suite on that file's cleanliness was choosing on the
wrong property.

**The rule: a file being uncontaminated says whose tree is current, not where
the bug is.** I had a good reason to avoid the peer-touched files and mistook it
for a reason to expect the defect in the one that was left. The two questions
are independent and both need answering before a suite is worth opening.

A second, smaller note for whoever holds `vsh.c`: the fix is not simply deleting
`NaNToOne`. Hardware's NaN column is a *gradient that responds to the
multiplier*, so the replacement has to be a defined conversion, not
pass-through — and `0.0 × NaN` must keep matching, since the ×0.0 column is
byte-exact today in every capture including the NaN ones.
