# Audit pass 1 — PR #245, `lane/vshnobegin242`: run the vertex program for a vertex sent outside Begin/End (#242)

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #245, branch `lane/vshnobegin242`, tip **`a79eee3f11`**. CI at
audit time: `build` pass (x2), `check` pass. Arms label: `verified`
(`vshnobegin242-must-not-move-runs3.json`, 403/403, 3 runs per arm).
**Date** 2026-09-25. **Record** `2026-09-25-vshnobegin242-pass1.md`.

**0 HIGH. 0 MEDIUM. 2 LOW.** Verdict: `fold-ready`. Neither LOW is a defect
the diff introduces, so pass 2 has nothing to verify.

The code change is 16 lines in `hw/xbox/nv2a/pgraph/pgraph.c`: a forward
declaration and a branch in `SET_VERTEX4F`. When slot 3 arrives with
`primitive_mode == PRIM_TYPE_INVALID`, the branch calls
`pgraph_vsh_writeback_constants()` and then `pgraph_reset_inline_buffers()`.
The rest of the diff is `NOTES.md`, two predictions and a regenerated
`nv2a_index.json`.

## What I checked and found correct, so pass 2 does not re-derive it

* **The inside-Begin/End path cannot reach the branch.** `SET_BEGIN_END`
  sets `primitive_mode` to a valid type on Begin and back to
  `PRIM_TYPE_INVALID` only after End's `draw_end`, writeback and reset. A
  vertex sent inside a primitive is untouched. "Begin without End" returns
  before it changes `primitive_mode`, so a stray second Begin does not open
  the branch either.
- **The writeback's preconditions hold for a lone vertex.**
  `pgraph_finish_inline_buffer_vertex` has already run, so
  `inline_buffer_length >= 1` and the early "nothing to draw" return does not
  fire. For the same reason `known.input[i]` is true for every attribute, and
  the inputs are the `inline_value`s. The End path uses exactly those inputs
  for an inline-buffer draw, so the lone vertex is evaluated with the End
  path's rules rather than new ones. Fixed-function mode (`CSV0_D` mode ≠ 2)
  and programs that write no constant still return at the pre-scan, as the
  prediction's leg (3) says.
* **The writeback needs no renderer state.** It reads `program_data`,
  `vsh_constants` and the attribute `inline_value`s, and writes
  `vsh_constants`, the dirty flags and `any_reg_gen`. None of these depends on
  `draw_begin`, and a `SET_TRANSFORM_CONSTANT` outside Begin already writes
  them from method context all the time. The `any_reg_gen++` on change stops
  a Vulkan merged draw from reusing stale uniforms, which is the same guard
  the End path relies on.
* **The early reset does not change any other draw.** `pgraph_reset_inline_buffers`
  zeroes the inline buffer, `inline_array`, `inline_elements` and the
  draw-arrays state. Outside Begin, the only things that read those are the
  next Begin (which resets them first), End-without-Begin (which also resets)
  and the writeback. So dropping them at the lone vertex instead of at the
  next Begin cannot change a draw. It also bounds the inline buffer, which
  before this change grew by one entry per lone vertex until the next Begin.
* **The index regeneration is mechanical.** Every changed `loc` in
  `nv2a_index.json` is a `pgraph.c` line. The 267 entries after the
  insertion move by +16, the 2 between the forward declaration and
  `SET_VERTEX4F` (3666 and 3668) move by +2, and nothing else in the file
  changes except `emulator_commit`. This matches the 2 + 14 inserted lines.
* **The superseded FAIL is accounted for.** `arms.sh` recomputes the
  `verified`/`regressed` label from every verdict with the supersede rule, and
  the PR is `verified`. The runs3 prediction's refs are the lane's merged
  refs. The PR body reports every prediction ref as an ancestor of HEAD, and
  CI is green on `a79eee3f11`.

## LOW

### L1. Only `SET_VERTEX4F` gets the lone-vertex behaviour

Six other methods finish an inline vertex through
`pgraph_finish_inline_buffer_vertex`: `SET_VERTEX3F`, `SET_VERTEX_DATA2F_M`
and `SET_VERTEX_DATA4F_M` (attribute 0), `SET_VERTEX_DATA2S`, `SET_VERTEX_DATA4UB`
and `SET_VERTEX_DATA4S_M`. None of them gets the branch.

**Scenario.** A program-mode title (or an nxdk test) sends its lone vertex
with `SET_VERTEX_DATA4F_M` on attribute 0, or with `SET_VERTEX3F`. It then
reads back over RDI the constants the program wrote. It still reads the old
values: #242's defect persists on every submission method except one.

**Why LOW.** Those paths are textually unchanged and behave as they did on
master. The PR does not introduce the gap. It fixes the one method the
exercised test uses, and the NOTES do not claim more. **Recommended
follow-up** (separate issue, not a condition of this fold): move the branch
into `pgraph_finish_inline_buffer_vertex` itself, after the increment, so
every submission method shares it. Then register a must-move leg that sends
the lone vertex through a second method. Nothing on either disc exercises
those methods outside Begin today, so the move would need its own falsifier.

### L2. The forward declaration sits mid-file

`static void pgraph_vsh_writeback_constants(PGRAPHState *pg);` is declared
just above `SET_VERTEX4F` instead of with the file's other prototypes.
Quality only. It also shifts `nv2a_index.json` by 2 lines more than a
top-of-file prototype would. There is no failure scenario.

## Out of scope, noted

The MaxSub row's negative subnormals come back as `+0` where silicon keeps
`-0`. That is arithmetic in the evaluator (#255), and the PR correctly
leaves it out.
