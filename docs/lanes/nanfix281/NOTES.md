# lane.nanfix281 -- NaN vertex colours clamp by sign (#281, code half)

Base: master @ 169045feca. Code commit 2bedc113aa. Analysis this builds on:
`docs/lanes/nanattr281/NOTES.md` (#302). It was not re-derived. Only its
predicted residual was re-checked (below).

## Mechanism

Silicon clamps a NaN colour by its sign bit, as it clamps an infinity: -NaN
draws as 0 and +NaN as 1. Attrib_float's MOV passthrough column is the same
ramp for -NaN..+NaN as for 0..1. A MUL whose product is NaN comes out positive
(-NaN x 1.0, x -INF, x -NaN are all white). `NaNToOne` sent every NaN to +1,
which hid the sign on both counts.

## Change

1. `glsl/vsh.c`: new `NaNToSignedOne` (NaN -> -1 if the sign bit is set, else
   +1; the existing clamp then gives 0/1), applied to oD0/oB0/oD1/oB1 in place
   of `NaNToOne`. `NaNToOne` stays, because `_MUL`'s zero test still uses it.
2. `glsl/vsh-prog.c` `_MUL`: after the anything-times-zero forcing, a NaN
   product becomes +NaN (0x7FC00000). After audit pass 1 (MEDIUM-1) this is
   one helper, `_PosNaN`, applied to every op that computes a new value:
   `_MUL`, `_ADD`, `_MAD` after the add, `_DP3/_DPH/_DP4`, DST's product,
   and the ILU ops `RCP/RCC/RSQ/EXP/LOG/LIT`. `_MOV`, `_MIN` and `_MAX`
   return an operand and keep its sign.

Part 1 alone would turn the x1.0/x+-INF/x+-NaNq columns into "whatever sign
the host propagates". Part 2 alone does nothing. The arm tests both together.

## Prediction (`docs/testing/predictions/nanfix281-signbit.json`)

Re-checked against the latest arm on master's binary
(`1790373302-arms-wparamcode223-fix-991557`, apk e300df8476a6) vs the golden,
per column. I simulated the fix by pasting our own `0_1` column 0 over the NaN
captures' column 0:

| capture | today | per column today | predicted |
|---|---:|---|---:|
| `-NaNq_NaNq` | 14,637 | [14637, 0, 0, 0, 0, 0, 0] | **6,223** |
| `-NaNs_NaNs` | 14,697 | [14637, 30, 0, ...] + 30 text | **6,283** |
| `0_1` | 31,115 | [6223, 6223, 0, 0, 6223, 6223, 6223] | 31,115 |
| `-INF_INF` | 24,891 | [6223, 6223, 0, 6222, 6223, 0, 0] | 24,891 |

The brief's "<= 60 / 0 px" cannot be met by this change. What is left is the
+-1 colour floor, and our `0_1` column 0 carries the same 6,223 px today. The
arm must land on exactly these two figures. Any other figure refutes the model.

Legs not registered:
- Exceptional Float: those rows are printed by the CPU vsh emulator
  (`pgraph.c`), which this GLSL change does not reach, and the suite has no
  golden, so a leg keyed on it would be refused at queue time.
- Fixed-function lighting suites: the output map is shared with vsh-ff.c, so a
  -NaN colour from FF lighting now draws 0 where it drew 1. No capture is known
  to produce one, and a single-run guard over those suites would be mostly noise.

## Build

The desktop build cannot run on this host (AGENTS.md, missing libcurl dev).
The C change is string literals only. The GLSL uses only builtins already used
in the same shader (`floatBitsToUint`, `uintBitsToFloat`, `mix(..., bvec4)`,
`isnan`) plus `floatBitsToInt`/`lessThan(ivec4)`, all GLSL 3.30 / ES 3.00. The
arm's device build is the compile check. A compile failure would blank every
capture and break the `-MaxSN_MaxSN`/`-Min_Min` legs, which are 0 today.

## Arm

Queued by the arms job from the committed prediction. **Verdict: PASS, all
12 registered checks hold** (`[job.arms]` on #336, PR label `verified`).
a `1790386145-arms-nanfix281-base-3375997` (169045feca, apk 9c4cdc7460e2)
vs b `1790386145-arms-nanfix281-fix-3376290` (2bedc113aa, apk 13ef43a8159e).

| capture | a | b | predicted |
|---|---:|---:|---:|
| `-NaNq_NaNq` | 14,637 | 6,223 | 6,223 |
| `-NaNs_NaNs` | 14,697 | 6,283 | 6,283 |
| the other 10, `-INF_INF` included | | same | same |

Both must_move figures land exactly on the model. Nothing got worse, and
exact stays 3 -> 3. I read the result dirs: 12 captures per arm, scores1.tsv
`status` is 3 `ok` + 9 `white-content` in both arms, with none `unreadable`,
and no run log says PARTIAL COVERAGE. Each arm ran once, so the byte-level
check calls 2 differing captures "not attributable". Those 2 are the two
must_move captures, and they moved by the predicted 8,414 px each.

The residual (6,223 / 6,283) is the separate +-1 colour floor, not #281. It
is the same 6,223 px that `0_1` column 0 carries.

## Why attempt 1 did not finish

It ended correctly, with a `[lane.nanfix281] waiting:` comment, while the arm
was queued behind the #311/#277 arms and CI was running. It left the PR in
draft, and nothing but the lane can mark a draft ready. Attempt 2 was resumed
by `job.handback` with CI green and the arm `verified`. It read the verdict
and the result dirs, recorded them here, and marked the PR ready.

## Do not repeat

- Do not tune the prediction to the arm's figure. 6,223/6,283 is the model.
- Before calling a leg held, read scores1.tsv `status` for `unreadable` and the
  run log for PARTIAL COVERAGE.

## Remediation of audit pass 1 (a6227fea68)

MEDIUM-1: with only `_MUL` forced positive, a -NaN out of `_ADD`, the add
half of `_MAD`, or `_DP*` reached the sign-reading colour map with the
host's sign. That drew black where master drew white, and nothing had
measured it. Choice: keep the sign reading and make every computing op's
NaN +NaN. For those ops this is exactly master's output (white), and it
agrees with the one measured model (an arithmetic NaN is positive). The
ILU ops get the same treatment for the same reason. Silicon's only ILU NaN
row, `rcp(NaN)=nan` (xbox-vsh-silicon-2026-09-25.md), prints no sign, so
it neither supports this nor contradicts it. The sign is visible nowhere
except the colour clamp: `geom.c` and fog test `isnan`, and comparisons,
`min/max` and `mul` all give the same result for either sign.

This is unmeasured beyond the Attrib float disc. No capture feeds these ops
a NaN, so the prediction was re-registered unchanged on b_ref a6227fea68.
Its job is to catch a GLSL compile failure, which would blank every capture
and fail the 0-px legs. This host has no GLSL validator.

LOW-1 (FF lighting accumulation reads the host's sign) is left as is.
vsh-ff.c does not include the program header, and no capture produces a
NaN FF colour. LOW-2 (the "`_MAD` inherits it" wording) is fixed in the PR
body.
