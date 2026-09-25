# lane.vshconst -- #233: vertex-program writes to constant registers

Base: master @ a6bb4a13d4. PR #234.

## What was wrong

`vsh-prog.c` `decode_opcode`, on `FLD_OUT_ORB == OUTPUT_C`, ran
`assert(!"TODO: Emulate writeable const registers")`. Android release builds
pass `-UNDEBUG`, so the assert is live on the handhelds. Past the assert the
code emitted `cN` (no brackets), which is not a GLSL identifier that exists, so
even with NDEBUG the shader would have failed to compile.

## Every path that reads a program's output select (brief step 1)

`grep -rn "FLD_OUT_ORB\|FLD_OUT_ADDRESS\|vsh_get_field"` under `hw/` finds
only two files that decode program tokens:

| where | what it does with the output select | state before |
|---|---|---|
| `glsl/vsh-prog.c` `decode_opcode` | emits the destination | the TODO assert (the crash) |
| `glsl/vsh.c` `vsh_token_writes_fog` | asks "does this land in oFog" | correct: requires `OUTPUT_O` |
| `glsl/vsh.c` `vsh_classify_fog_write` | calls `mov oFog, c[n]` CPU-readable from `vsh_constants` | **silently wrong** if the program writes c[n]: the CPU copy no longer holds what the register holds |

No other translator exists (GL and Vulkan share `glsl/`).

## Silicon: do constant writes persist? (the brief's open question)

**Yes, they persist after the draw ends. The source is the test itself, not a
new console run.**
`~/nxdk_vsh_tests/src/test_host.cpp` `TestHost::Compute` draws two quads with
the program, waits for idle, then `fetch_results` reads c[188..219] back
through `NV_PGRAPH_RDI_INDEX = 0x170000 + index*16` / `NV_PGRAPH_RDI_DATA`,
which is the vertex-program constant RAM (`RDI_INDEX_VTX_CONSTANTS0 = 0x17`,
the same RAM `SET_TRANSFORM_CONSTANT` loads). `ilu_rcp.vsh` does nothing but
`RCP c[188..191].<comp>, c[96..99].<comp>`. The console's `IluRcpTests.txt`
prints the RCP results in rows [0]..[3], so the written values were still in
constant RAM after the draw. (`TestHost::ClearState` loads zeros into
c[188..191], `test_host.cpp:1003-1006`, and the RCP program's own upload
touches only c[96..99], so the printed values cannot be left over from any
upload.)

What this does and does not show:

- It shows the write reaches the constant RAM and outlives the draw. The next
  draw's program reads that same RAM, so a later draw sees the written value
  unless the CPU reloads it. That is cross-draw persistence, from the RAM's
  identity rather than from a second draw that reads it back. A console run
  with draw 1 writing c[n] and draw 2 copying c[n] to an output would measure
  it directly. It isn't needed to act, and I have not asked for one.
- It cannot show which vertex's write survives, or whether vertex N reads
  vertex N-1's write. Every vertex in this test writes the same values.
- Rows [4]..[31] (c[192..219], past the 192-entry file) read 0 over RDI.

## What this PR does

1. `vsh-prog.c`: a program that writes any constant register declares
   `vec4 c_rw[192] = c;` at the top of `main`, reads every constant through
   `c_rw` (the A0-relative form included), and writes into `c_rw[n]`. A write
   past register 191 goes to a scratch `_c_rw_oob` that nothing reads. So a
   write is visible to later instructions of the same run. **A program that
   writes no constant emits byte-identical GLSL**, so every existing pgraph
   capture should be unaffected. The pre-scan is
   `pgraph_glsl_vsh_token_constant_write`, which uses the same unit/mux/mask
   condition under which `decode_opcode` emits the write.
2. `vsh.c` `pgraph_glsl_vsh_fog_write`: `mov oFog, c[n]` is now COMPUTED, not
   CONST, when the program writes c[n] anywhere.

## What it does NOT do: carry the write out of the draw

Silicon persists the write (above), and xemu still doesn't: the value lives
in a GLSL local and is gone when the invocation ends. `pg->vsh_constants`
(what RDI reads and what the next draw uploads) still holds the CPU's upload.
Fixing that needs code outside this lane's files:

- `pgraph/rdi.c` `pgraph_rdi_read`: `assert((address / 4) <
  NV2A_VERTEXSHADER_CONSTANTS)` aborts on c[192..], which ILU RCP Tests reads
  (rows [4]..[31]). Silicon returns 0 there.
- A writeback: after a draw whose program writes constants, put the last
  vertex's written values into `pg->vsh_constants` and mark them dirty. A GPU
  readback is heavy (SSBO/transform feedback and a sync). The cheaper route is
  a CPU evaluation of the program for the draw's last vertex from
  `vsh_constants` + `inline_value`, the pattern #41/#42 already use for fog.
  It is exact for programs whose writes depend only on constants (ILU RCP
  Tests is one) and needs silicon's float rules (RCP of a denormal is ±inf,
  RCP of FLT_MAX is 0, per the golden).

Both are in the board request and on #233.

## Measurements

(filled in below as they land)

## Do not repeat

- `nv2a_index.py blast` on `vsh-prog.c` or `vsh.c` answers "No indexed suite
  exercises symbols in those files". The coupling is through the program
  tokens, not a hardware symbol. The arm's suite list comes from the brief and
  the goldens directory, not from blast.
- No `.vsh` under `~/nxdk_pgraph_tests/src` writes a constant register, so on
  the pgraph disc this change can only move a capture through a compile
  failure or a pre-scan misfire.
