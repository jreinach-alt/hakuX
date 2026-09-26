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
   product becomes +NaN (0x7FC00000). `_MAD` inherits it. `_ADD`, `_DP*`,
   `_MIN/_MAX` are unchanged and unmeasured, because no capture feeds them a NaN.

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

Queued by the arms job from the committed prediction. The verdict will be
posted on the PR as `[job.arms]`.

## Do not repeat

- Do not tune the prediction to the arm's figure. 6,223/6,283 is the model.
- Before calling a leg held, read scores1.tsv `status` for `unreadable` and the
  run log for PARTIAL COVERAGE.
