# lane.vshsubneg255 -- #255: a negative subnormal through a MAC MOV

Base: master @ d92ae5d7f3 (PR #245 folded). PR #288.

## The stage where it went wrong: the premise was inverted

The brief said the sign bit of a negative subnormal dies somewhere between
SET_VERTEX4F and the constant RDI reads. It does not. Reading the source
chain end to end:

| stage | code | -MaxSub (0x807FFFFF) |
|---|---|---|
| SET_VERTEX4F | `inline_value[slot] = *(float*)&parameter` | 0x807FFFFF |
| input flush | `vsh_flush_denormal` (pgraph.c, #233) | **0x80000000 (-0.0)** |
| MAC MOV | `nv2a_vsh_cpu_mov` is a `memcpy`; `set_register` multiplies by +1.0f | 0x80000000 |
| output flush | `vsh_flush_outputs` | 0x80000000 |
| writeback | `memcpy` into `pg->vsh_constants[188]` | 0x80000000 |
| RDI read | `rdi.c`: raw bits | 0x80000000 |

So hakuX hands the guest **-0.0**, with the sign intact. The guest prints it
with `third_party/printf/printf.c` `_ftoa`, which writes a `-` only
`if (value < 0)`. -0.0 is not below zero, so it prints `0.000000`.

So the console's `-0.000000` does not mean -0. It means the value the console
returned was **below zero**: a negative number too small for `%f`. Silicon did
not flush the subnormal on this path. The stage that goes wrong is the
**input flush**, and the output flush would do the same thing again: #233
applied both to every unit. The sign was never lost; the magnitude was.

The same printf rule, applied to the console's ILU RCP Tests text
(`hardware/runs/2026-09-25-vsh/stage1b/console/ILU_RCP_Tests/IluRcpTests.txt`),
gives the other half:

- `rcp(-MaxSub) = -inf`, `rcp(MinSub) = inf`: the ILU's input **is** flushed.
  Unflushed, `1/-MaxSub` is -8.5e37.
- `rcp(-Max)` prints `0.000000`, not `-0.000000`. The true result is a negative
  subnormal (-2.9e-39), which would print `-0.000000` if kept. So the ILU's
  output **is** flushed.

One rule fits every console row with no per-op exception: **the ILU flushes
denormals in and out; the MAC passes them through.** The brief's candidates
(an evaluator op turning -0 into +0, the writeback copy, the known/mask
handling) are all clean. None of them touches the sign.

What is NOT measured: MAC arithmetic (MUL, ADD, MAD, DP*) on a subnormal. The
only MAC evidence is MOV. Under this change the MAC does host IEEE arithmetic
on subnormals. If silicon's MAC flushes inside arithmetic but not in MOV, this
is wrong for those ops, and nothing on disc can tell. CPU Shader Tests with
`USE_EXCEPTIONAL_VALUES` defined (cpu_shader_tests.cpp:21) would settle it on
the console.

A scratch harness (evaluator + test program + flush, desktop) was written
under `.scratch/` but this session could not run a compiler, so the table
above is from reading source, not from execution. Every step in it is a
`memcpy`, a `* 1.0f`, or `vsh_flush_denormal`.

## The change

`pgraph.c`, `pgraph_vsh_writeback_constants`: no flush of the constants or
inputs on the way in, and no flush of MAC writes. A step with an ILU op runs
the MAC on the live registers and the ILU on a copy with every denormal
flushed. The ILU's written components are copied back flushed. Both units
still read before either writes, and the ILU still writes last.
`nv2a_vsh_emu_initialize_full_execution_state` memsets its struct, so the
copy is taken after it.

Only programs that write a constant reach this code. No `.vsh` on the pgraph
disc does, so no pgraph golden can move. `nv2a_index.json` is regenerated over
fold-pins nxdk_pgraph_tests @ 6743b6a and pbkitplusplus @ e91d509 (line moves
only).

## Prediction (written before any build or run)

Scored by `vsh_score.py` against the 2026-09-25 console text. ab_compare
refuses vsh results, so this is the prediction of record. Base = master
`d92ae5d7f3`, fix = `6a183e3061`, Thor, `--program vsh`, disc
`nxdk_vsh_tests-c3dde45-shutdown.iso`. The suites are every one with a console
text: Exceptional Float, ILU RCP Tests, MAC mov, MAC Add Tests, Paired ILU
Tests, AmericasArmyShader, SpyVsSpy, Vertex Data Array Format Tests.

### Must move (Exceptional Float line 7), four legs

| leg | console | base (#245 measured) | fix predicted |
|---|---|---|---|
| MaxSub | 0.000000 | 0.000000 | 0.000000 (not discriminating: prints the same flushed or not) |
| -MaxSub | -0.000000 | 0.000000 | **-0.000000** |
| MinSub | 0.000000 | 0.000000 | 0.000000 (not discriminating) |
| -MinSub | -0.000000 | 0.000000 | **-0.000000** |

So Exceptional_Float/Float goes DIFFERS to IDENTICAL. Lines 3 and 5 (Inf/NaN,
Max/Min) stay as the console prints them in both arms.

Failing worlds:
- **Both negatives still `0.000000`**: the value is still not below zero when
  the guest compares it. Either something outside this function still
  flushes (read the writeback's `known` path for v0 first), or the guest's
  own float->double conversion or compare flushes under TCG, e.g. a guest
  MXCSR DAZ honoured by QEMU but not by the P3. The second would mean the
  console's output depends on the P3's FPU, and the fix belongs in neither
  pgraph nor the evaluator. Diagnose it; do not revert.
- **One negative moves, the other does not**: both take the same
  memcpy path, so a split would be magnitude-dependent (MinSub is 2^-149,
  MaxSub just under 2^-126). That points at a flush-to-zero in the guest's
  printf (the `value < 0` compare or the float->double), not at pgraph.

### Must not move (same `vsh_score` status and the same diff lines in both arms)

| suite | what would move it |
|---|---|
| ILU RCP Tests (IDENTICAL on master, #233) | the ILU copy or its flush being wrong: a zeroed copy gives rcp(0)=inf in every column; a missing output flush turns `rcp(-Max)` into `-0.000000` |
| Paired ILU Tests | the MAC/ILU split: a wrong write order, or the ILU's copy-back missing a paired write (R1 vs R10) |
| MAC mov, MAC Add Tests | only a denormal input, and neither feeds one (grep of tests/); a control for the MAC-only path, which is `nv2a_vsh_emu_apply` unchanged |
| AmericasArmyShader, SpyVsSpy | a game shader with an ILU op in a constant-writing program; normal values, so only the split can move them |
| Vertex Data Array Format Tests | nothing: array-sourced inputs are unknown to the writeback and are not written back in either arm |

For the base arm's statuses on the suites nobody has run under hakuX yet,
the prediction is only "equal in both arms", not "IDENTICAL to the console".

## Verdict (attempt 2, 2026-09-25): HOLDS, every leg

Attempt 1 did not finish because it was waiting. The two vsh runs and CI were
both pending when the session ended, and that is a finished state. The mistake
was ending with the PR still in draft and no reader-visible marker beyond the
PR comment. The handback job resumed this lane with CI GREEN on `806d24916c`.

Runs (both `DONE`, "Testing completed normally", 10/10 captures, 0 MISSING,
0 STALE, no `UtilAcceptVsock`, no PARTIAL). **Device: Nova (ee317437), not
Thor.** The dispatcher placed them there. Thor and Nova agree per capture (0
disagree in 3,040), so this does not change the verdict, but it is a Nova
result.

| arm | id | ref | apk | EF/Float | counts |
|---|---|---|---|---|---|
| fix | `1790365377-vshsubneg255-441388` | 6a183e3061 | 36d1981d723a | **IDENTICAL** | 3 IDENTICAL / 7 DIFFERS |
| base | `1790365379-vshsubneg255-441528` | d92ae5d7f3 | 824d399f0280 | DIFFERS line 7 `0,0,0,0` | 2 / 8 |

- Must move: -MaxSub and -MinSub both print `-0.000000` under the fix, so
  Exceptional_Float/Float is IDENTICAL to the console. Neither failing world
  (both stay, or one moves) occurred.
- Must not move: a diff of the two `vsh1.txt` reports shows only the
  staleness timestamp and the Exceptional Float block changed. Every other
  suite has the same status and the same diff lines in both arms: ILU RCP
  (IDENTICAL), MAC mov (IDENTICAL), MAC Add, Paired ILU, AmericasArmyShader,
  SpyVsSpy and the three Vertex Data Array rows (DIFFERS, unchanged). Those
  DIFFERS rows are pre-existing defects that this change does not touch.
- Still not measured: MAC arithmetic on a subnormal (see above).

Merged origin/master at the end (a merge, not a rebase, so both arm refs stay
ancestors). The only conflict was `nv2a_index.json`, which was rebuilt over
fold-pins nxdk_pgraph_tests @ 6743b6a with `--support` pbkitplusplus.
