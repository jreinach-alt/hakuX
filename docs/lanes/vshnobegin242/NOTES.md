# lane.vshnobegin242 -- #242: run the vertex program for a vertex sent outside Begin/End

Base: master @ 21946df29b. PR #245.

## What changed

`hw/xbox/nv2a/pgraph/pgraph.c`, `SET_VERTEX4F`: when slot 3 arrives with
`primitive_mode == PRIM_TYPE_INVALID`, after the usual
`pgraph_finish_inline_buffer_vertex` it calls
`pgraph_vsh_writeback_constants(pg)` and then `pgraph_reset_inline_buffers(pg)`.

- That is #234's CPU evaluator, unchanged. It runs only in program mode, and
  only when the pre-scan finds a constant write in the bound program. It runs
  the program for "the last vertex". With `inline_buffer_length == 1` that is
  the lone vertex, and every attribute is known from `inline_value`.
- Nothing is rasterised. The reset drops the vertex, which the next Begin
  (or an End with no Begin) would have done anyway. Before this change, lone
  vertices piled up in the inline buffer until the next Begin.
- The inside-Begin/End path is textually unchanged: the new branch is guarded
  on `PRIM_TYPE_INVALID`.

Scope: only `SET_VERTEX4F`, as the brief says. `SET_VERTEX3F` and the
`SET_VERTEX_DATA*_M` attribute-0 setters also finish a vertex and have the same
gap outside Begin/End. Nothing measured exercises them, so they are left
alone. A lane that finds a test sending those outside Begin/End should route
them through the same two calls.

## Do a lone vertex's position/varying outputs go anywhere on silicon?

Unknown, and not settled here. Exceptional Float reads only the constants back
over RDI, and nothing in nxdk_vsh_tests or nxdk_pgraph_tests draws with a lone
vertex and then measures pixels. So this change writes **only the constants**
and rasterises nothing. The evaluator already ignores o-register outputs
except as temporaries.

## Prediction (registered before any build or run)

### vsh, must move (request.sh --program vsh, scored by vsh_score.py; ab_compare refuses vsh results)

`Exceptional_Float/Float.txt` on Thor, b_ref `bd552105ed`, goes from all
`0.000000` (master; #242 cites `1790346001-vsh-2643051`) to the console's
`hardware/runs/2026-09-25-vsh/stage2/console`:

```
Inf, -Inf, NaN, -Nan:            inf, -inf, nan, nan
Max, -Max, Min, -Min:            3.402823e+38, -3.402823e+38, 0.000000, -0.000000
MaxSub, -MaxSub, MinSub, -MinSub: 0.000000, -0.000000, 0.000000, -0.000000
```

i.e. vsh_score IDENTICAL. `MAC_mov` stays IDENTICAL (it draws inside
Begin/End, and that path did not change).

The world in which this fails, and what it would mean:
- **All rows still 0**: the program did not run, or it ran and its write did
  not reach the bank RDI reads. The first could be the mode check (CSV0_D MODE
  != 2 when the lone vertex arrives), the pre-scan, or the evaluator bailing
  out. The second would be a different RDI bank.
- **Finite rows right, NaN/-0 rows different**: arithmetic. `-NaN` printing
  `-nan` where the console prints `nan` would mean the console canonicalises
  NaN on MOV or on RDI, and the emulator keeps the sign bit. Score the finite
  rows separately. A partial fix is a diagnosis, not a revert.

### pgraph, must not move

`docs/testing/predictions/vshnobegin242-must-not-move.json`: a_ref
`21946df29b`, b_ref `bd552105ed`. The legs are Degenerate begin end,
SetVertexData, Attrib setter, 3D primitive, Material color, Overlapping draw
modes, Vertex shader independence/rounding tests, W param and Fog gen. That is
a representative slice of `nv2a_index.py blast pgraph.c`, which names the
whole file. The prediction text says what would move each leg. No `.vsh` on
the pgraph disc writes a constant, so on that disc the only live effect is the
reset of a lone vertex's inline buffer.
