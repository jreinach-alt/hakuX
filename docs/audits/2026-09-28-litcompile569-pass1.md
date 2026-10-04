# Audit pass 1: PR #580, lane/litcompile569

On the Vulkan path, #569 B1 rewrites the lighting unit's bit-exact helpers in
`vsh-ff.c` as straight-line code.
Head audited: `3e24ed0fe9`. Auditor: job.cloud, 2026-09-28.

**Verdict: no HIGH, no MEDIUM, two LOW.** The PR goes to `needs-audit-2`.

## What was checked

- **The diff:** 14 files. The only one that ships is `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`
  (+171/-2). The rest is lane tooling under `docs/lanes/litcompile569/` and
  two prediction files.
- **Which shaders see the new block.** `pgraph_glsl_append_version()`
  (`glsl/common.c:102-133`) emits `#version 450` for Vulkan only, `#version 300+ es`
  for GLES and `#version 400` for desktop GL. `#if __VERSION__ >= 450` therefore
  selects the new forms on Vulkan alone. GLES and GL keep the old text byte for
  byte: the `#else` branch is master's block, with only a closing `#endif` added.
- **GLSL 4.50 legality.** The new code uses `mix(genUType/genIType/genBType, …,
  genBType)`, which is 4.50 core. It also uses `findMSB` on `uint`/`uvec3`,
  `bvec3(uvec3)` and `uint(bool)` constructors, and uvec3 shifts by a uvec3.
  These are all legal at 450. None of them reaches the ES/400 branch.
- **Callers of the helpers that exist only in the old branch.** `ltA`, `ltMk`,
  `ltMulCore`, `ltShr`, `ltIsNan`, `ltIsInf` and `ltMsb` are not defined under
  450. A grep over `hw/xbox/nv2a/` finds every call to them inside the `#else`
  branch itself. The lighting emitters call only `lt`, `ltM`, `ltsM`, `ltVM`,
  `ltVA`, `ltA3`, `ltDp`, `ltsA` and `ltR`, and all of these are defined in
  both branches. So no Vulkan shader references an undefined function today.
- **Case order, helper by helper, new against old** (read by hand, not
  through the lane's transcription):
  - **`ltMulV`:** priority is NaN > either-zero (+0) > either-inf >
    signedInf-and-`e>=255` > `ec<=0` (signed zero) > `ec>=255` (saturate to
    `0x7F7FFC00`). This matches `ltMulCore`'s early returns. `c = m>>14` is 0
    or 1 because `m <= (0x3FFF^2)>>13`.
  - **`ltA3` / `ltVA`:** NaN > both infinities > either infinity > `r==0` >
    `ltMkU`. The `er` start of 0 in the old form is dominated by `e+2 >= 2`.
    `sh >= -5` because `er >= e+2`, so the `clamp(-sh,0,31)` never
    truncates. `ltVA` is `ltA3(a,b,0)` because a zero third lane contributes
    `f=0` and exponent 0.
  - **`ltsA`:** the shift `er-e-1 >= 0` always. `min(…,31)` of a 14-bit
    mantissa gives the same 0 as `ltShr`'s `>=32`. `|r| <= 0x7FFE`, so
    `14 - findMSB >= 0`.
  - **`ltR`:** NaN > `ex==0` (+inf) > inf (0) > `er<=0`. This matches the old
    returns.
  - **`ltMkU`:** zero beats saturate, as in `ltMk`.
  - **Throwaway lanes:** computed garbage in a lane that a later `mix` discards
    (a negative `ec` cast to uint, `findMSB(0) = -1` giving a shift of 21 or
    15) is always overridden. None of these shifts reaches 32.
- **The C transcription against the GLSL.** I read `lt_check.c`'s `n_*`
  functions line against line with the new GLSL and found them faithful. The
  vector `==`/`!=` reductions in `ltA3` are spelled "any lane", as GLSL defines
  them.
- **The harness, run on this host:**
  `OUT=/tmp/ltchk580 run_lt_check.sh 5` exits 0.
  - Every helper shows 0 mismatches, and `ltR` was run over all 2^32 inputs.
  - Mutants 1-10 are each caught, each by the helper it targets.
- **Device evidence on the PR:** the `[job.arms]` verdict is PASS, with all
  489 registered lighting-set captures byte-identical, full sweep, a=`503b901ee4`
  b=`fb80d7e793`. This covers the one risk the C check cannot: Turnip/ir3
  lowering a construct differently from C.
- **Lane tooling:**
  - `doa_soak_judge.py` imports `fbwin` from `docs/lanes/shaderfb569/`, which
    is on master.
  - `bound()` refuses to judge when its constants drift from the registered
    legs.
  - `run_lt_check.sh` writes to `$OUT`, or to `.scratch/` by default.

## Findings

### LOW 1: the 450 block has no `ltA`

`vsh-ff.c:181-332`: the `#else` branch defines `float ltA(float, float)`, but
the Vulkan branch does not.

- **Failure scenario:** a later change to the lighting emitters calls
  `ltA(x, y)`, for example a scalar add in a new light term. It compiles and
  renders on GLES and GL 4.00. On Vulkan, every lit vertex shader then fails
  glslang with "no matching overloaded function". Every lit fixed-function
  draw on Android would lose its pipeline.
- **Why it is LOW:** nothing calls `ltA` today, so this is a trap for the next
  editor, not a defect in this diff.
- **Fix:** add `float ltA(float a, float b) { return ltA3(a, b, 0.0); }` to the
  450 block. Or state in the block comment which names the two branches must
  both define.

### LOW 2: `doa_soak_judge.py` prints PASS/FAIL on a void pair

`doa_soak_judge.py:115-140`. The judge sets `void` and prints one `VOID`
line, then still prints `L1 … -> PASS`/`FAIL` and `L2`–`L4` verdicts
underneath.

- **Failure scenario:** a warm or thermally paused pair shows `L1 … PASS`.
  Someone who quotes that line alone reads a void leg as confirmed.
- **Second failure scenario:** an arm with no `[shd413]` creates
  (`dpn == 0`) raises `ZeroDivisionError` at line 114, before any verdict is
  printed.
- **Why it is LOW:** this is lane tooling that is not shipped, and the VOID
  line is printed first. It does not affect the change under audit.

## What pass 2 should verify

- **LOW 1:** either `ltA` is defined under 450, or the block comment says that
  both branches must define the same names. Without either, the scenario above
  is still live.
- **LOW 2:** no fix is required to fold. If the lane changes the judge, check
  that a void pair prints no bare PASS.
- **The shipping change:** nothing in it needs re-verifying unless the head
  moves past `3e24ed0fe9` in `vsh-ff.c`. If it does, re-run
  `run_lt_check.sh` and re-diff the transcription.
