# lane.dpforce345: #345 half 1, DP3/DPH/DP4 zero-force each product

Base: master @ 2dc2b5c49a. PR #383.

## The mechanism

Silicon forces each 0 x inf and 0 x NaN term inside a DP3 or DP4 to 0
(`docs/testing/xbox-special-raw-2026-09-25.md`, PR #344). For example,
`(0,1,2).(inf,1,1) = 3`. `_MUL` already applies this rule. The GLSL
`_DP3`/`_DPH`/`_DP4` helpers were a plain `dot()`, which gives NaN.

The change is in `hw/xbox/nv2a/pgraph/glsl/vsh-prog.c`. Each helper still
computes `d = dot(...)`. The new `_DotZeroForced(d, a, b)` returns `d`
unless `d` is NaN. When `d` is NaN, it returns the sum of `_MUL(a, b)`'s
products:

- `DP3` pads w with 0 on both sides.
- `DPH` passes `(a.xyz, 1)`. Its w term is `_MUL(1, b.w)`, which is never
  forced because 1 is not a zero.

**Why the NaN gate.** A zero factor can change a dot's value only through a
0 x inf or 0 x NaN term, and every such term makes `dot()` NaN. So every
dot whose plain result is not NaN keeps `dot()`'s value bit for bit. There
is no FMA or reordering difference on any finite lit path, and the
must-not-move legs are inert by construction rather than by luck.

When the NaN comes from `inf + -inf` with no zero factor, the forced sum is
NaN too, and `_PosNaN` makes it +NaN exactly as before. The #281 sign rule
is untouched.

`dp_model.py` is the helper in float32. It reproduces all 5 silicon DP rows:
3 move from NaN to silicon's value and 2 stay unchanged. The run is
offline, with no GLSL compiler on this host.

## The brief's falsifier cannot see this hunk

The brief said to score `vsh_score.py` against the console text. **That
instrument does not run this GLSL:**

- nxdk_vsh_tests `CPU Shader Tests` values come from
  `NV097_LAUNCH_TRANSFORM_PROGRAM` and the constant writeback
  (`pgraph.c`: `pgraph_vsh_cpu_program`, `pgraph_vsh_writeback_constants`).
  Both execute on the nv2a_vsh_cpu evaluator.
- `special-raw-prediction.md` says so ("hakuX's nxdk_vsh_tests values come
  from #234's CPU evaluator").
- #281's prediction says the same about Exceptional Float.

A vsh_score run of this branch would print the same rows as master. That
result would be an instrument that cannot see the change, not a measurement.
The DP rows there are #345 half 2.

## The arm

`docs/testing/predictions/dpforce345-inert-finite.json` (a_ref 2dc2b5c49a,
b_ref 74a238a614) has no must_move leg. No golden I can name feeds a DP a
0 x inf/NaN term. Every leg is must_not_move, over these suites:

- the 6 `Lighting_*` suites;
- the 3 `Vertex_shader_*` suites;
- `Attrib_float`;
- `Fog_vsh`, `Fog_exceptional_value` and `Fog_inf_coord`.

What would move each leg:

- **Every capture:** a compile failure of the new helper blanks it.
- **Any other capture:** only a DP that is NaN today, meaning an inf/NaN
  input meets a zero. A move toward the golden there would be this defect
  showing. Report it as unpredicted and do not claim it.

`W_param` is left out. Its `prog_` captures run `passthrough.vsh` (mov only)
and `rcc_clamp_test.vsh` (mul, rcc), neither of which has a DP
(`docs/lanes/wparam223/NOTES.md`).

`register.py` re-registers the prediction on new refs.

## Half 2 (not built)

The nv2a_vsh_cpu evaluator (third-party, `subprojects/nv2a_vsh_cpu.wrap`,
also fetched by `android/app/src/main/cpp/CMakeLists.txt` at a pinned
revision) misses the zero-forcing in MUL/MAD/DP. It also gets `RCC(+inf)`'s
sign wrong and uses a decimal 2^-64. Fixing it means one of these:

- patching the library, which needs a fork or a wrap `diff_files` plus a
  matching CMake patch step, both kept in sync;
- post-correcting in `pgraph.c`, which cannot, because the evaluator's
  intermediate products are gone by writeback.

Neither is a small call-site fix. It is a follow-up for the board.

## Do not repeat

- Do not use nxdk_vsh_tests text to judge a `glsl/` change: it reads the CPU
  evaluator.
- Do not replace `dot()` with an unconditional sum of products. It changes
  rounding (FMA and order) on every finite lit vertex for no gain.

## Status (2026-09-26)

Waiting on two things:

- the `[job.arms]` verdict for `dpforce345-inert-finite.json` (a_ref
  2dc2b5c49a, b_ref 74a238a614);
- CI on the PR head.

When both land, cite the verdict in the PR and mark it ready. If any
must_not_move leg gets worse, the claim that the hunk is inert on finite dots
is refuted.
