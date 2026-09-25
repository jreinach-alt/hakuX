# lane.nanattr281 -- NaN vertex attributes (#281)

Status: **blocked on files**, analysis complete. The fix needs
`hw/xbox/nv2a/pgraph/glsl/vsh.c` (`[free]`, not yet granted to this lane) and one
function in `hw/xbox/nv2a/pgraph/glsl/vsh-prog.c` (held by lane.vshr12280).
No hw/ file edited, so no arm and no prediction yet.

Base: master @ d709a8d1fa. Reproduce every number below with
`docs/lanes/nanattr281/nan_columns.py <console_dir> <ours_dir>`.

Inputs used:

| role | path | binary / date |
|---|---|---|
| console (K) | `hardware/runs/2026-09-19-calib/full/out/run1` | silicon, 2026-09-19 |
| ours | `dispatch/results/1790359589-xbox-full6743-dry2-2802408/captures1` | 2026-09-25 |
| golden | `~/goldens/results/Attrib_float` | |

The `NaNToOne` lines this names are unchanged on master since before that
run. The 14,637 px figure also matches the five older binaries in
`docs/investigations/attrib-float-is-nantoone-and-the-colour-floor.md`.

## 1. What the test draws (`attribute_float_tests.cpp`)

- The NaN goes in the **diffuse colour**, submitted as raw bits by
  `NV097_SET_DIFFUSE_COLOR4F` (`nv2astate.cpp:643`, `PushF`), per vertex, inside
  Begin/End. It is not in a vertex buffer. Top two vertices get
  `attribute_value[0]` (-NaN), bottom two get `[1]` (+NaN), on r, g and b. Alpha
  is 1.
  - `-NaNq_NaNq`: 0xFFC00000 / 0x7FC00000.
  - `-NaNs_NaNs`: 0xFF800001 / 0x7F800001.
- Seven quads (columns). Column 0 is the passthrough vertex program, a MOV of
  v3 to oD0. Columns 1-6 run `passthrough_mul_color_by_constant`, which MULs the
  diffuse by c[120..123] = 1.0, 0.0, -INF, +INF, -NaNq, +NaNq.

## 2. What silicon does: region, not point

Interior of each quad (2 px in from every edge, 13,348 px per column):

| console region | compared with | px differing |
|---|---|---:|
| `-NaNq_NaNq` col 0 | `0_1` col 0 | **0** |
| `-NaNq_NaNq` col 0 | `-INF_INF` col 0 | **0** |
| `-NaNq_NaNq` col 0 | `-Max_Max` col 0 | **0** |
| `-NaNs_NaNs` col 0 | `-NaNq_NaNq` col 0 | **0** |

| column | console | ours |
|---|---|---|
| passthru (MOV) | 252-colour ramp, 2..253 | **1 colour, 255** |
| x1.0 | 255 | 255 |
| x0.0 | 0 | 0 |
| x-INF / x+INF / x-NaNq / x+NaNq | 255 | 255 |

So on silicon:

- **A NaN that only passes through a MOV is clamped by its sign bit.** -NaN
  becomes 0 and +NaN becomes 1, exactly as -INF/+INF and -Max/+Max do. The
  per-vertex values are then interpolated into the same ramp as `0_1`. It is
  not flushed to 0: the bottom is white. It is not passed as 1 either: the top
  is black. It is not culled: the quad is drawn.
- **A MUL with a NaN operand and a non-zero partner comes out positive.** This
  holds for -NaN x 1.0, -NaN x -INF, and x -NaNq, and each gives a solid-white
  column. `x0.0` gives 0 (the existing anything-times-0 rule). "MUL returns
  +NaN" and "MUL returns something >= 1" draw the same pixels. What the suite
  fixes is only the sign that reaches the colour clamp.

Ours draws column 0 white because `pgraph_glsl_gen_vsh` (`glsl/vsh.c:954-955`,
`:972-973`) applies `NaNToOne` (`vsh.c:513`) to oD0/oB0/oD1/oB1 before the
clamp. Every NaN becomes +1, whatever its sign. The other six columns match
only because silicon's result there really is white.

## 3. Where our path first differs

- **Host attribute fetch and vsh input load: not here.** The value reaches
  oD0 as a NaN on both sides. Silicon's x1.0 column rules out an input that has
  already been turned into a finite value or an infinity. If the input had
  become -INF or -Max, -NaN x 1.0 would come out black at the top, and silicon
  shows white.
- **Rasteriser: not here.** Silicon's column 0 is the ordinary 0-to-1 ramp.
- **vsh output colour conversion: here.** `NaNToOne` in `pgraph_glsl_gen_vsh`.
  This is the GLSL path shared by fixed-function and programmable. PR #245 and
  PR #288 change the **CPU** vsh emulator in `pgraph.c` (a vertex outside
  Begin/End; ILU denormal flushing for constant writeback). This draw uses
  neither, and neither touches `NaNToOne` or `_MUL`. No conflict.

## 4. NaNs vs NaNq: one mechanism

Silicon's column 0 is identical for the two (0 of 13,348 px), and so is ours
(both 14,637 px from the console, all in column 0). The console-vs-golden 60 px
on `-NaNs_NaNs` all sits in rows 75-86, which is the printed
`0x%08x to 0x%08x` line: the golden's build printed a different sNaN pattern.
That fits the test's own TODO (`:55-57`) about sNaN being quieted on the
submission path. It is text, not rendering, and it is 0 px on the console we
compare to.

## 5. The fix (for whoever holds the files)

Two parts. **Both are needed:**

1. `glsl/vsh.c`, `pgraph_glsl_gen_vsh` colour outputs: replace
   `NaNToOne(oX)` with a sign-directed map, applied before the clamp.

   ```glsl
   vec4 NaNToSignedOne(vec4 src) {
     bvec4 neg = notEqual(floatBitsToUint(src) & 0x80000000u, uvec4(0u));
     return mix(src, mix(vec4(1.0), vec4(0.0), neg), isnan(src));
   }
   ```

   `NaNToOne` stays as it is for `_MUL`'s zero test in vsh-prog.c.
2. `glsl/vsh-prog.c`, `_MUL` (the `vsh_header` string, `:611-624`): make a NaN
   product positive, e.g.
   `ret = mix(ret, vec4(uintBitsToFloat(0x7FC00000u)), isnan(ret));` after
   the zero-forcing.

   Without this, part 1 turns the x1.0, x+-INF and x+-NaNq columns into
   "whatever sign the host GPU propagates" for -NaN x k. IEEE only recommends
   propagating an input NaN's payload, and sign-propagating hosts would draw
   those columns as a ramp, a 13k px regression per column. Today `NaNToOne`
   hides the host's sign. `_MAD` goes through `_MUL`, so it inherits the fix.

   `_ADD`, `_DP3/4/H`, `_MIN/_MAX`: this suite does not exercise them with a
   NaN, so this lane leaves them unmeasured and unchanged.

Part 1 alone is the **failing world** for the x1.0 column. Part 2 alone is
inert, because `NaNToOne` still maps every NaN to 1.

## 6. The arm (not registered: no refs exist yet)

Register after the grant, after the last merge from master, on concrete refs.
Scored against the golden:

| leg | capture | today | predicted | the patch change that would move it |
|---|---|---:|---:|---|
| must_move | `Attrib_float/-NaNq_NaNq` | 14,637 | ~6,223 | part 1: column 0 becomes our own `0_1` column 0 |
| must_move | `Attrib_float/-NaNs_NaNs` | 14,697 | ~6,283 | same, plus 60 px of golden text |
| must_not_move | `Attrib_float/-INF_INF` (Inf leg) | 24,891 | 24,891 | a map that took isinf as well as isnan and sent it to 1 |
| must_not_move | `Attrib_float/Colors` | 0 | 0 | part 2 using the wrong sign (-NaN x NaN constant -> 0) |
| must_not_move | `Attrib_float/0_1`, `0_8`, `-1_1`, `-8_1`, `-Max_Max`, `-MinN_MinN` | as today | as today | part 2 missing: their x+-NaNq columns are MUL by a NaN |
| must_not_move | `Attrib_float/-MaxSN_MaxSN`, `-Min_Min` | 0 | 0 | neither part: no NaN reaches a colour; they check the edit is local |

**The residual is not zero, and it is not this defect.** After the fix, our
NaN column 0 is our `0_1` column 0. That one is 6,223 px from silicon by the
known +-1 colour floor (`colorPrecision`, same file, same line; see the
investigation doc's Population 2). Exact against the golden needs that separate
fix too.

The Exceptional Float rows lane.vshsubneg255 works are **not** a leg. They are
printed from the CPU vsh emulator in `pgraph.c`, which this GLSL change does not
reach. Register one only if the fix grows into `pgraph.c`.

When the arm runs, check scores1.tsv `status` for `unreadable` and the run log
for PARTIAL COVERAGE before reading any leg as moved.

## What the next lane should not repeat

- Do not delete `NaNToOne` from the outputs and pass the NaN through. The GLSL
  clamp of a NaN is undefined, and silicon's answer depends on the sign.
- Do not fix the output without `_MUL`. The x1.0 column is the only thing in
  the suite that pins MUL's NaN sign, and it passes today only because
  `NaNToOne` hides the sign.
- Silicon's column 0 is a ramp that goes up to 253. One mid-quad pixel would
  read as "silicon flushes NaN to some grey". Compare regions.
