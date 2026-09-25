# Audit pass 1 — PR #234, `lane/vshconst`: emulate vertex-program writes to constant registers (#233)

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #234, branch `lane/vshconst`, tip **`a73eb00a7f`**. CI at audit
time: `build` pass (x2), `check` pass.
**Date** 2026-09-25. **Record** `2026-09-25-vshconst-pass1.md`.

**0 HIGH. 2 MEDIUM. 3 LOW.** Verdict: `needs-remediation`.

The code change is in five files: the GLSL translator (`glsl/vsh-prog.c`,
`vsh-prog.h`, `vsh.c`), the new CPU writeback in `pgraph.c`, and the RDI bound
in `rdi.c`. `nv2a_index.json` is a mechanical regeneration, and the rest is
the two predictions and `NOTES.md`. I read the upstream `nv2a_vsh_cpu`
emulator and parser at the pinned revision `1115255708` against the writeback's
guards.

## What I checked and found correct, so pass 2 does not re-derive it

* **The writeback's bounds guards match the emulator's arrays and asserts.**
  `fetch_value` maps a temporary read of index 12 to `output_regs` and indexes
  `temp_regs` for everything else, so the guard sending R13..R15 to index 0 is
  the only one it needs. `apply_operation` asserts `OUTPUT < 13`,
  `TEMPORARY < 12` and `CONTEXT < 192`. `vsh_apply_outputs_known` removes each
  of those before `nv2a_vsh_emu_apply` runs, and remaps a write to R12 to `o0`.
  The relative-read guard computes `index + (int)a0[0]`, which is the same
  expression the emulator uses (`offset += (int)state->address_reg[0]`), so the
  guard and the read agree on every A0.
* **The known-mask is consistent with the parser.** ILU scalar ops read
  component 0 after the parser has broadcast `swizzle[0]`, which is why
  `in_known[0][0]` is right for RCP/RCC/RSQ/EXP/LOG. The parser gives ADD its
  second operand from input C, and the known pass runs `vsh_input_known` on
  `step.mac.inputs[]` after the parser has placed them, so the pass and the
  emulator see the same operands. LIT, DST, the dot products and ARL are
  treated as known only when every input component is known. That is
  conservative, never wrong.
* **The translator and `pgraph_glsl_vsh_token_constant_write` agree on which
  tokens write a constant.** `decode_opcode` emits the o/c write only for the
  unit whose opcode is not NOP, when `FLD_OUT_MUX` selects that unit and
  `O_MASK != 0`. The helper applies the same three conditions, and both scans
  stop at `FLD_FINAL`. No program can emit `c_rw` without declaring it.
  `convert_c_register` is the identity on the 8-bit field (0..255), so c[192]
  and above go to `_c_rw_oob` on the GPU and to `NV2ART_NONE` on the CPU.
* **Parse failure is no less safe than before.** `nv2a_vsh_parse_program`
  frees its steps on failure, `pgraph_vsh_cpu_program` returns NULL without
  marking the slot valid, and `LAUNCH_TRANSFORM_PROGRAM` still asserts exactly
  as it did.
* **RDI past c[191] returns 0.** `r` is initialised to 0 before the switch.
* **The fog readback change is keyed on program data**, which is part of the
  shader state, so `VSH_FOG_WRITE_CONST` → `COMPUTED` cannot go stale.
* **The Vulkan default path sees the writeback.** With merge and reorder off
  (the default), the Vulkan draw path uploads uniforms synchronously in
  `draw_end`, before the writeback runs. The next draw sees
  `vsh_constants_any_dirty`, and the render-thread snapshot is debug-only.

## MEDIUM

### M1. A paired ILU reads the constant its MAC partner just wrote (GLSL only)

`vsh-prog.c` `decode_token` / `decode_opcode`. In a paired instruction
(MAC and ILU both not NOP) with the output mux on the MAC, the MAC's o/c write
goes straight to the destination. `use_temp_var` defers only the MAC's
*temporary* write through `_temp_vec`. The ILU statement is appended after the
MAC's, and its input C is the expression `c_rw[n]`, evaluated at that point.
One instruction has one `FLD_CONST`, so the MAC's inputs and the ILU's input C
all read the same `c[n]`, and `FLD_OUT_ADDRESS` can name that register too.

Before this PR a constant write aborted the translator, so this read-after-write
could not happen. With `c_rw` writable, it can.

**Failure scenario.** A program with the paired instruction
`mad c[5], v0, c[5], c[5]` + `rcp r1.x, c[5].x` (output mux = MAC,
`FLD_CONST` = `FLD_OUT_ADDRESS` = 5) gives these results:

* **Silicon and the CPU emulator** read both units' inputs before either
  writes (`prepare_inputs`, and the PR's own comment "Both units read before
  either writes, as the emulator does"). The RCP sees the **old** c[5].
* **The GLSL** runs `MAD(c_rw[5], ...)` and then `RCP(R1.x, c_rw[5].x)`, so
  the RCP sees the **new** c[5].

Anything derived from `r1` in that run is wrong on the GPU: the position,
colours, texcoords and fog. The CPU writeback in the same PR computes the
silicon value, so the GPU and RDI also disagree with each other. ILU RCP Tests
does not use this shape, so the golden cannot see it.

**Fix direction.** When the MAC is muxed to a constant and the ILU is present,
write the MAC's o/c result through a temporary and assign it after the ILU,
as the suffix mechanism already does for R1. The alternative is to latch input
C into a local before the MAC statement.

### M2. With draw merge on, the third and later merged draws miss the writeback (Vulkan)

`pgraph.c` `pgraph_vsh_writeback_constants` sets `vsh_constants[][]`,
`vsh_constants_dirty[]` and `vsh_constants_any_dirty`, but it does not bump
`any_reg_gen`. `vk/draw.c` `try_enqueue_draw_arrays` and the indexed variant
decide whether to upload fresh uniforms for a merged draw from
`pg->any_reg_gen != q->any_reg_gen` alone.

**Failure scenario.** Set `g_xemu_draw_merge` on. It is off by default, but it
is a user pref the Android JNI layer sets (`xemu_android.cpp`). Then draw with
`DrawArrays` three times in a row with a constant-writing program and no
register change between the draws:

1. Draw 1 goes through `pgraph_vk_flush_draw` with fresh uniforms.
2. Draw 2 enqueues at `q->count == 0` and uploads fresh uniforms, so it sees
   draw 1's writeback.
3. Draw 3 reuses draw 2's UBO offsets, because `any_reg_gen` has not moved, so
   it renders with constants that do not include draw 2's writeback.

RDI returns the right values meanwhile, so the GPU and the CPU disagree. The PR
body says the writeback is "from one place for both renderers" and "the next
draw uploads them. That is silicon's persistence". Under this pref that claim
does not hold for Vulkan. This is the same latent class that
`nv2a_issues.toml` records for `SET_TEXTURE_MATRIX` ("never bumps
any_reg_gen"), and the PR adds a new member to it.

**Fix direction.** Bump `any_reg_gen` (or flush the draw queue) in the
writeback whenever a constant actually changed. The change is one line inside
the existing `bits != pg->vsh_constants[r][c]` branch.

## LOW

### L1. A paired MAC write to R1 differs between the CPU emulator and the translator

The translator drops a paired MAC's write to R1 (`mask = 0` in
`decode_opcode`). The upstream parser keeps it, and the ILU's R1 write then
overlaps it only on the ILU's mask. Take `mul r1.xy, ...` + `rcp r1.z, ...`
followed by `mov c[9].x, r1.x`:

* The CPU writeback stores the product.
* The GLSL, and silicon if the translator's rule is right, leave r1.x holding
  its old value.

The known-mask treats r1.x as known, so the writeback stores a value the GPU
never computed. This is rare, and it comes from the upstream emulator's fidelity
rather than from this diff. The cheap guard is to mark R1 unknown after a
paired MAC write to it.

### L2. The parse covers all of program memory, not just the program

`nv2a_vsh_parse_program` is given `NV2A_MAX_TRANSFORM_PROGRAM_LENGTH -
program_start` slots and parses every one of them. It does not stop at FINAL.
Suppose a stale token past FINAL has MAC opcode 14/15, or is an ARL with a
temporary mask. The parse then fails, and the writeback skips the draw, with
only a `NV2A_DPRINTF` saying so. The slot is never marked valid, so the parse
also runs again, with a malloc and a free, on every draw that uses that
program. The GLSL path is unaffected because it stops at FINAL.
`LAUNCH_TRANSFORM_PROGRAM` had the same parse before this PR, but it asserted
on a failure rather than skipping in silence.

### L3. Every program-mode draw now scans its program's tokens

The `writes_constant` loop at the top of `pgraph_vsh_writeback_constants` runs
on every draw in program mode, including draws whose program writes no
constant. That is up to 136 tokens and three field extractions each, per draw.
It is small, but it is new work on the hot path of every vertex-program title,
and the answer changes only when `vsh_program_data_gen` or `program_start`
does. Caching it on those two values removes the scan.

## Not findings, recorded so pass 2 knows they were considered

* **Vulkan and GLSL-ES have never compiled the `c_rw` copy.** No
  must-not-move leg in arm 2 exercises a constant-writing program. The
  handheld ILU RCP run the PR says it still owes is the evidence that closes
  this. It is not a defect until it fails.
* **The two assumptions the PR names are unmeasured**: the last vertex's write
  survives, and vertices do not see each other's writes. `NOTES.md` states
  both, with the run that would settle them. The code does what it says.
* **`(int)` of a NaN A0 is undefined behaviour in C**, but the guard and the
  emulator use the same conversion, so they cannot disagree. This is not
  something this PR introduced.
