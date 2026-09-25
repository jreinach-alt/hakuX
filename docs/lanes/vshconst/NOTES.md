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

## Attempt 1 stopped here (superseded by attempt 2, below)

Attempt 1 did not finish because the rest of the job was in files the lane
did not hold. It ended in a deliberate waiting+blocked state: the
translator fix pushed, the arm registered, and a board request for rdi.c and
the writeback. Wave 157 granted `rdi.c` and `pgraph.c` (not `gl/draw.c` or
`vk/draw.c`, which went to lane.shadeflat224). What attempt 1 wrote about the
gap, kept for the record:

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

Desktop build of 47ee3f65e9, built in this worktree's gitignored
`build-linux/` against `$WORK/desktop/deps/prefix`, so the shared desktop
tree was never touched. Disc: `~/hakux-work/vsh-build/nxdk_vsh_tests-c3dde45-shutdown.iso`
with `vsh_tests.cnf` = `ILU RCP Tests` only (toolsmith's `make_test_iso.py
--program vsh`, from PR #229's branch). Renderer: OpenGL on llvmpipe.

| run | result |
|---|---|
| master (toolsmith, 09-19 binary, #112) | abort `vsh-prog.c:383` TODO assert |
| 47ee3f65e9, GL | **translator assert gone**, no GL compile error in the log; aborts later at `rdi.c:31` `pgraph_rdi_read` when the test reads c[192] back, RUN_EXIT=134 |
| 47ee3f65e9 + a LOCAL, UNCOMMITTED rdi.c patch (reads past c[191] return 0; reverted afterwards, tree clean) | run completes, RUN_EXIT=0; `vsh_score.py` DIFFERS: rows [4]..[31] match silicon's zeros; rows [0]..[3] print 0.000000 where silicon prints the RCP results |

So on desktop the crash is fixed, and the printed-value match is **blocked**
on two things outside this lane's files (below). Rows [0]..[3] read 0 because
the value written in the GLSL never reaches `pg->vsh_constants`, and that
array is what RDI reads.

Not verified here: Vulkan. This host has no Xvfb (`xvfb-run: command not
found`), and the tree builds no standalone glslang. The Vulkan dialect of
`vec4 c_rw[192] = c;` (`c` is a member of an anonymous uniform block there)
is exercised first on the handheld. The handheld run of `request.sh --program
vsh` after #229 folds should show IluRcpTests completing (no abort) and
DIFFERS on rows [0]..[3] until the writeback lands.

Arm: `docs/testing/predictions/vshconst-must-not-move.json`, a_ref a6bb4a13d4,
b_ref 47ee3f65e9, all must-not-move over the three Vertex shader suites,
W param and Fog coord vec4. The prediction text names what would move each
leg.

## State at end of attempt 1 (2026-09-25, superseded)

- Waited on the `[job.arms]` verdict for `vshconst-must-not-move.json` and on
  CI. Blocked on rdi.c and the writeback, both then outside this lane's files.

## Attempt 2 (2026-09-25): the writeback and the RDI bound

### What changed

1. `pgraph/rdi.c` `pgraph_rdi_read`: a vertex-constant read past c[191]
   returns 0 instead of asserting. That matches silicon (rows [4]..[31]).
2. `pgraph/pgraph.c` `pgraph_vsh_writeback_constants`, called in
   `SET_BEGIN_END` right after `renderer->ops.draw_end` and before
   `pgraph_reset_inline_buffers`, so GL and Vulkan both get it from one
   place. In program mode (CSV0_D MODE == 2), if
   `pgraph_glsl_vsh_token_constant_write` fires on any token of the bound
   program, the program runs on the CPU for the draw's last vertex. The
   components it writes to c[0..191] go into `pg->vsh_constants`, marked
   dirty like a `SET_TRANSFORM_CONSTANT` would mark them. RDI then reads
   them, and the next draw uploads them. That is the cross-draw persistence
   silicon shows.
3. **The CPU evaluator is the upstream `nv2a_vsh_cpu` emulator, not a new
   one.** `LAUNCH_TRANSFORM_PROGRAM` already uses it. It is compiled on
   Android (CMakeLists.txt:670-673; `nv2a_vsh_emulator_stub.c` is in no
   source list). Its parsed-program cache moved into a helper,
   `pgraph_vsh_cpu_program`, that both callers share. For LAUNCH the parse,
   the cache and the v0 hash behave exactly as before. It still asserts on a
   parse failure, and the draw path skips instead.
4. It steps the program one instruction at a time (`nv2a_vsh_emu_apply`)
   instead of calling `nv2a_vsh_emu_execute`, because the emulator does not
   bounds-check and asserts are live on Android:
   - an A0-relative read past c[191], or through an unknown A0, and a read of
     R13..R15, are repointed at a safe register and marked unknown;
   - a constant write past c[191] is dropped (no register there);
   - an o-register index >= 13 is dropped;
   - a write to R12 goes to o0, which is what R12 is.
5. Silicon's float rules: denormals are flushed to a zero of the same sign
   on the way in (constants, inputs) and after every step (written
   registers). That is what makes RCP(+-MaxSub/MinSub) = +-inf and
   RCP(+-FLT_MAX) = +-0. The emulator's own RCP would give -8.5e37 for
   -MaxSub, and silicon prints -inf.

### Where the evaluation cannot know the value (the brief's "say so")

A per-component "known" mask runs alongside the emulator. Only components
that are known are written back. The rest keep their old value and are
counted in an `NV2A_DPRINTF`. A component is unknown when it depends on:

- **an input read from a vertex array** (DRAW_ARRAYS, inline elements,
  inline array): the last vertex's value is in guest memory, and this path
  does not fetch it. Attributes with `count == 0` are constant for the draw
  (`inline_value`) and are known. In an inline-buffer draw every
  attribute's `inline_value` is the last vertex's, so all are known.
- **a temporary, o0/R12 or A0 read before the program writes it.** The GLSL
  path starts them at 0. Silicon starts them with whatever the previous
  vertex left, which nothing here can know.
- **a relative read through an unknown A0**, or past c[191].

The op model is conservative. Component-wise ops (MOV MUL ADD MAD MIN MAX
SLT SGE, ILU MOV) are tracked per component, and the scalar ILU ops
(RCP RCC RSQ EXP LOG) on the one component they read. DP3/DPH/DP4/DST/LIT/ARL
are known only if every component of every input is. That can leave a known
value unwritten, but it never writes a guessed one.

What the evaluation ASSUMES and has not measured:

- **The last vertex's write is the one that survives.** The brief's shape.
  It is irrelevant when every vertex writes the same value (ILU RCP Tests,
  and any write that depends only on constants). For a write that depends on
  inline-buffer inputs it is a real assumption. A console run whose vertices
  write different values, then read back, would settle it.
- **No vertex sees another vertex's write inside one draw.** The GLSL copy
  `c_rw` starts from the draw's constants for every vertex, and the CPU pass
  does the same. On silicon vertex N may read vertex N-1's write. Nothing
  here has measured that.
- The pass reads both units' inputs before either writes, as the emulator
  and silicon do. The GLSL translation emits the MAC write before the ILU
  op, so a paired instruction whose ILU reads the constant its MAC writes
  differs between the in-draw GLSL and the written-back value. No known
  program does that.
- Emulator op semantics (e.g. ARL truncation, MUL zero rule) are
  nv2a_vsh_cpu's and not the GLSL's. Where they differ, the written-back
  value follows nv2a_vsh_cpu, which its author tested against hardware.

### Measurements (attempt 2)

Same desktop recipe as attempt 1: OpenGL on llvmpipe, disc
`nxdk_vsh_tests-c3dde45-shutdown.iso` with `vsh_tests.cnf` = ILU RCP Tests
only, a fresh copy of `x1box/hdd.img`, and `vsh_score.py` against
`hardware/runs/2026-09-25-vsh/stage1b/console`. The base `hdd.img` has no
`nxdk_vsh_tests` directory (extract_results: "not found"), so the file cannot
be left over from an older run. The runner was scratch (`/tmp/vshconst-run/run.sh`,
mirroring `desktop_channel.sh cmd_run`).

| build | RUN_EXIT | ILU_RCP_Tests/IluRcpTests |
|---|---|---|
| d9c0ed0b8e (lane on a6bb4a13d4) | 0 | **IDENTICAL**, all rows [0]..[31] |
| 9ff7f6d67a (merged with master f2e8ef8ba8) | 0 | **IDENTICAL**, all rows [0]..[31] |

The guest log reads `Completed IluRcpTests 417ms / Testing completed
normally`. Attempt 1's run of the GLSL-only fix plus an rdi.c-only patch
printed 0.000000 for rows [0]..[3], so the writeback is what moves those
rows. That run is the falsifier. The PNG differs (123498 px), which is the
known desktop-GL-vs-console font/raster gap; the verdict is on the text.

Vulkan is not run: this host cannot run it (see Do not repeat). The
writeback is renderer-independent (CPU, in pgraph.c), so the handheld
checks the Vulkan GLSL of `c_rw` and the whole path on Adreno.

### Arm 2

`docs/testing/predictions/vshconst-writeback-must-not-move.json`: a_ref
f2e8ef8ba8 (master), b_ref 9ff7f6d67a (master + the lane). All
must-not-move over Vertex shader independence/rounding/swizzle, W param, Fog
coord vec4, Fog vsh, Fog gen (FF and VS captures) and SetVertexData. The
prediction names the change that would move each leg. The pgraph.c blast
names 87 suites. The writeback returns at the mode check for
fixed-function draws, so the live legs are the vertex-program suites. Fog gen
FF and SetVertexData check that the call order at draw end disturbs nothing.
Arm 1 (`vshconst-must-not-move.json`, GLSL only) stands as registered.

### Still owed, and the state at the end of attempt 2

- The handheld: `request.sh --program vsh ... --suites "ILU RCP Tests"`,
  once #229 folds. It is the run that counts.
- The two arms' `[job.arms]` verdicts.
- WAITING, not blocked. Definition-of-done items 1-4 hold: preflight passes,
  `Files:` matches the diff, NOTES are here, and both arms are registered and
  committed. The PR stays in draft until arm 2's verdict is clean and CI is
  green on the head, because the brief's "done when" needs the arm verdict on
  #233. Then mark it ready. A move on an arm-2 leg means the pre-scan
  misfired or the draw-end call order is wrong. Read the prediction's leg
  text before touching the leg.

## Attempt 3 (2026-09-25): why attempt 2 did not finish, and the re-run

Attempt 2 ended waiting on arm 2's `[job.arms]` verdict. That verdict came
back **ARM ERROR**, and the cause was the host, not the patch. The base half
(`1790327181-arms-vshconst-base-821044`) completed. The fix half
(`1790327181-arms-vshconst-fix-821066`) ran 130 s, then its pull failed
after three WSL `UtilAcceptVsock ... accept4 failed 110` errors. `adb` here
is Windows `adb.exe` over WSL interop. Its logcat is a normal run with no
signal and no assert. Arm 1 was lost the same way. The arms job does not
re-queue a half-run pair, so attempt 3 re-ran the whole pair itself with
`ab_run.sh --fix 9ff7f6d67a --parent f2e8ef8ba8 --expect
docs/testing/predictions/vshconst-writeback-must-not-move.json`. Both APKs
were cached. Rerunning both halves keeps the pair on the same device session.
Attempt 3 also merged origin/master (0940056bf6, models.env only). It did not
rebase, so b_ref 9ff7f6d67a is still an ancestor of the head.

WAITING at the end of attempt 3. Preflight passes on the merged head, and
`Files:` matches the diff. The re-run was queued as `1790328976-vshconst-base-1459825`
and `1790328976-vshconst-fix-1460107`. It was self-queued, so no `[job.arms]`
comment will announce it. The next attempt picks it up with
`bash docs/testing/ab_run.sh --resume
1790328976-vshconst-base-1459825,1790328976-vshconst-fix-1460107 --expect
docs/testing/predictions/vshconst-writeback-must-not-move.json`, posts the
verdict on #234 and #233, and then runs `gh pr ready 234` if it is clean.
If the fix half is lost to adb interop again, that is still a host fault
(toolsmith's dispatch defect 3), not a result.

## Attempt 4 (2026-09-25): arm 2 judged PASS, PR marked ready

Attempt 3 did not finish because it was waiting on the self-queued re-run. It
could not sleep, so it stopped. The re-run pair came back DONE, with no
interop errors. `ab_run.sh --resume ... --expect
vshconst-writeback-must-not-move.json` gives **VERDICT: PASS, all 306
registered checks hold**. The prediction was PRE-REGISTERED (bound sha256
02a801ea...c8f4a5).

| | A f2e8ef8ba8 (apk b4db00b5e5c2) | B 9ff7f6d67a (apk 236e448d37fa) |
|---|---|---|
| captures | 306 | 306 |
| exact | 129 | 129 |
| status `ok` / `white-content` / `unreadable` | 299 / 7 / 0 | 299 / 7 / 0 |
| differing total | 6,454,403 | 6,454,403 |

Arm B has no movers, and all 306 shared captures are byte-identical between
the arms. The status column is the same on every (suite, test) row. The
seven `white-content` rows are in Vertex shader independence tests and W
param, in both arms. No status turned `unreadable`, so this is not the
unreadable-scores-as-exact trap from #224's arm.

Attempt 4 merged origin/master with `git merge`, not a rebase, so b_ref stays
an ancestor. It then marked #234 ready. Still owed after it folds: the
handheld ILU RCP Tests run through `request.sh --program vsh` once #229 folds.

## Remediation of pass 1 (2026-09-25, job.cloud)

Pass 1 (`docs/audits/2026-09-25-vshconst-pass1.md`) found 0 HIGH and 2 MEDIUM.
Both are fixed here. The LOWs are left as recorded.

- **M1, a paired ILU read its MAC partner's constant write (GLSL).** In
  `decode_opcode`, when the MAC is paired with an ILU and muxed to a constant
  register, the MAC now writes `_c_rw_tmp`. The suffix, which `decode_token`
  appends after the ILU statement, copies the masked components into
  `c_rw[n]`. `mad c[5], v0, c[5], c[5]` + `rcp r1.x, c[5].x` now emits
  `MAD(_c_rw_tmp,xyzw, ...)`, `RCP(R1,x, c_rw[5])` and
  `c_rw[5].xyzw = _c_rw_tmp.xyzw;`, in that order, so the RCP reads the old
  c[5], as the emulator and silicon do. `_c_rw_tmp` is declared with the
  `c_rw` copy, so the GLSL of a program that writes no constant is unchanged.
  An out-of-range address still goes straight to `_c_rw_oob`, which nothing
  reads.
- **M2, merged Vulkan draws missed the writeback.**
  `pgraph_vsh_writeback_constants` now bumps `any_reg_gen` when it changes any
  constant. `try_enqueue_draw_arrays` and its indexed variant then upload
  fresh uniforms for the next merged draw, instead of reusing the previous
  entry's UBO offsets.

Neither change can move the arm 2 captures. M1 only changes programs that
write a constant from a paired MAC, and no `.vsh` on the pgraph disc writes a
constant at all (see "Do not repeat"). M2 does nothing unless the writeback
changed a constant. Both files pass `-fsyntax-only` with the desktop build's
flags. The arm has not been re-run on this ref.

## Do not repeat

- `nv2a_index.py blast` on `vsh-prog.c` or `vsh.c` answers "No indexed suite
  exercises symbols in those files". The coupling is through the program
  tokens, not a hardware symbol. The arm's suite list comes from the brief and
  the goldens directory, not from blast.
- No `.vsh` under `~/nxdk_pgraph_tests/src` writes a constant register, so on
  the pgraph disc this change can only move a capture through a compile
  failure or a pre-scan misfire.
- Desktop Vulkan cannot run on this host: no `xvfb-run`/Xvfb, and SDL's
  offscreen driver cannot create a Vulkan surface ("Failed to create main
  window"). Use GL on llvmpipe, or the handheld.
- Do not write a second CPU vertex-program emulator. `nv2a_vsh_cpu` is
  built on both desktop and Android. It does NOT bounds-check relative
  reads, and it asserts on out-of-range writes, so guard each step as
  `pgraph_vsh_writeback_constants` does. Do not call
  `nv2a_vsh_emu_execute` on guest data.
- `nv2a_vsh_cpu_rcp` gives a finite result for a denormal input. Silicon
  gives +-inf. Flush denormals before and after each step.
- `desktop_channel.sh build` checks out a ref in the SHARED `$WORK/desktop/tree`.
  Build in your own worktree's gitignored `build-linux/` instead, pointing
  PKG_CONFIG_PATH/LD_LIBRARY_PATH at `$WORK/desktop/deps/prefix` (about 25 min
  cold).
