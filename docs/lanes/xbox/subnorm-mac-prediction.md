# #255 on silicon: what the MAC unit does with subnormal operands, registered before the run

**Status: PRE-REGISTERED.** This was committed and pushed before the XBE ran
anywhere. The host routed it on the #112 thread, item 3.

lane.vshsubneg255 (#255/#288) left MUL, ADD and MAD on subnormal operands
unmeasured on silicon. `CPU Shader Tests` cannot measure them as it stands:

- `almost_equal()` passes any hardware ±0 whose CPU value is within
  FLT_EPSILON, and it never checks the sign of zero, so a flushed subnormal
  passes silently.
- It prints only FAILs, and it saves nothing.

## The instrument

This adds one test, `CPU Shader Tests::SUBNORM_MAC`, in `~/nxdk_vsh_tests`,
branch `hakux/subnorm-mac` (`330e4a8`, on `c3dde45`).

- It runs the suite's own `mac_{mov,mul,add,mad}_passthrough` programs:
  operands arrive in `c[96..]`, pass through `mov` into a temporary, and the
  result goes to `c[188]`, which is read back over RDI.
- The operands are chosen to separate the questions (see below).
- It writes every case's raw result bits to `SUBNORM_MAC_raw.txt` and
  compares nothing.

There are two builds of the same source. The console variant reboots to the
dashboard at the end (XBE sha256 `43ba4a4ed34c…`). The shutdown variant ends
the emulator run (ISO `28cc037f2742…`). The emulator runs first, then the
console, under the standing safeguards.

## What each hypothesis predicts (IEEE float32 references, computed before the run)

"FTZ in+out" flushes every subnormal operand and result to a zero of the same
sign. "FTZ out" flushes results only. MAD is modelled as a rounded product,
then the add.

```
op   a          b          c          | IEEE       FTZ in+out FTZ out   
MOV  0x007FFFFF                       | 0x007FFFFF 0x00000000 0x00000000
MOV  0x807FFFFF                       | 0x807FFFFF 0x80000000 0x80000000
MOV  0x00000001                       | 0x00000001 0x00000000 0x00000000
MOV  0x80000001                       | 0x80000001 0x80000000 0x80000000
MOV  0x00400000                       | 0x00400000 0x00000000 0x00000000
MOV  0x80400000                       | 0x80400000 0x80000000 0x80000000
MOV  0x00800000                       | 0x00800000 0x00800000 0x00800000
MOV  0x80000000                       | 0x80000000 0x80000000 0x80000000
MUL  0x007FFFFF 0x4B800000            | 0x0C7FFFFE 0x00000000 0x0C7FFFFE
MUL  0x807FFFFF 0x4B800000            | 0x8C7FFFFE 0x80000000 0x8C7FFFFE
MUL  0x00000001 0x71800000            | 0x27000000 0x00000000 0x27000000
MUL  0x80000001 0x71800000            | 0xA7000000 0x80000000 0xA7000000
MUL  0x1C800000 0x1C800000            | 0x00000200 0x00000000 0x00000000
MUL  0x9C800000 0x1C800000            | 0x80000200 0x80000000 0x80000000
MUL  0x1F800000 0x1F800000            | 0x00200000 0x00000000 0x00000000
MUL  0x21800000 0x21800000            | 0x03800000 0x03800000 0x03800000
ADD  0x007FFFFF 0x00000000            | 0x007FFFFF 0x00000000 0x00000000
ADD  0x007FFFFF 0x007FFFFF            | 0x00FFFFFE 0x00000000 0x00FFFFFE
ADD  0x807FFFFF 0x00000000            | 0x807FFFFF 0x00000000 0x80000000
ADD  0x00800000 0x807FFFFF            | 0x00000001 0x00800000 0x00000000
ADD  0x00800000 0x007FFFFF            | 0x00FFFFFF 0x00800000 0x00FFFFFF
ADD  0x3F800000 0x00000001            | 0x3F800000 0x3F800000 0x3F800000
ADD  0x80000000 0x80000000            | 0x80000000 0x80000000 0x80000000
ADD  0x80000001 0x80000001            | 0x80000002 0x80000000 0x80000000
MAD  0x007FFFFF 0x4B800000 0x00000000 | 0x0C7FFFFE 0x00000000 0x0C7FFFFE
MAD  0x1C800000 0x1C800000 0x00000000 | 0x00000200 0x00000000 0x00000000
MAD  0x1C800000 0x1C800000 0x00800000 | 0x00800200 0x00800000 0x00800000
MAD  0x807FFFFF 0x3F800000 0x00000000 | 0x807FFFFF 0x00000000 0x00000000
MAD  0x3F800000 0x3F800000 0x007FFFFF | 0x3F800000 0x3F800000 0x3F800000
MAD  0x00800000 0x3F000000 0x00000000 | 0x00400000 0x00000000 0x00000000
MAD  0x00800000 0xBF000000 0x00000000 | 0x80400000 0x00000000 0x00000000
MAD  0x00000000 0x00000000 0x007FFFFF | 0x007FFFFF 0x00000000 0x00000000
```

## Legs

- **Classification.** Each of the 32 hardware results is classified as
  matching IEEE, FTZ in+out, FTZ out, or none of them. The per-op pattern is
  the answer: whether operands are flushed, whether results are flushed, and
  the sign a flushed zero keeps.
- **Impossible row: `MUL 0x21800000 x 0x21800000` must be `0x03800000`.** That
  is a normal times a normal with a normal result, the same under every
  hypothesis. So must `ADD 1.0 + MinSub` (`0x3F800000`), `ADD -0 + -0`
  (`0x80000000`) and `MAD 1 x 1 + MaxSub` (`0x3F800000`). A miss there means
  the instrument is broken, not silicon.
- **Completion.** "Testing completed normally", the console hands back to the
  dashboard, and `SUBNORM_MAC_raw.txt` has 32 lines.

The result goes on #255.
