# #112 item 4 on silicon: zero x inf/NaN, signed zeros, and the ILU specials, registered before the run

**Status: PRE-REGISTERED.** This was committed and pushed, and posted on #112,
before the XBE ran anywhere.

## What is measured

The "inherited" vertex-program behaviours in hakuX's GLSL helpers
(`glsl/vsh-prog.c`, `glsl/vsh.c`):

- `_MUL` forces **+0** when either operand is ±0, with NaN counting as 1 (so
  0×∞ and 0×NaN both give +0). `_MAD` is `_MUL + c`.
- `_DP3` and `_DP4` are a plain `dot()`, with **no** zero-forcing.
- `_RCC` is `clampAwayZeroInf(1/x)`. That clamps into [2^-64, 2^64], and sends
  −0 and NaN to the negative side.
- `_RSQ` gives +∞ for ±0 and 0 for ±∞, and takes `abs(x)` for the rest.

## The instrument

`CPU Shader Tests::SPECIAL_RAW`, nxdk_vsh_tests `hakux/special-raw`
(`7006335`, on #339's `hakux/subnorm-mac`). It records the raw bits of 44
results across 35 computations (the table below) and compares nothing.

- ILU ops read one scalar, so each ILU case is its own run with all four
  input components equal. All four outputs are recorded.
- DP results are replicated, and all four components are recorded.

hakuX's nxdk_vsh_tests values come from #234's CPU evaluator, not from these
GLSL helpers. The silicon column is the answer. The hakuX dry run shows the
evaluator; the GLSL column below is computed from the helpers as written.

## References, computed before the run

IEEE float32; hakuX's GLSL helpers; and, for DP, zero-forcing inside the dot
(`_MUL`'s rule applied to each product).

```
op   inputs                   | IEEE       hakuX-GLSL dot-forced
MUL  00000000 x 7F800000      | 0xFFC00000 0x00000000
MUL  80000000 x 7F800000      | 0xFFC00000 0x00000000
MUL  7F800000 x 00000000      | 0xFFC00000 0x00000000
MUL  00000000 x 7FC00000      | 0x7FC00000 0x00000000
MUL  7FC00000 x 00000000      | 0x7FC00000 0x00000000
MUL  80000000 x 40A00000      | 0x80000000 0x00000000
MUL  40A00000 x 80000000      | 0x80000000 0x00000000
MUL  80000000 x C0A00000      | 0x00000000 0x00000000
MAD  00000000 7F800000 3F800000 | 0xFFC00000 0x3F800000
MAD  00000000 7FC00000 3F800000 | 0x7FC00000 0x3F800000
MAD  80000000 40A00000 80000000 | 0x80000000 0x00000000
MAD  80000000 40A00000 00000000 | 0x00000000 0x00000000
DP3  a=00000000,3F800000,40000000 b=7F800000,3F800000,3F800000 | 0xFFC00000 0xFFC00000 0x40400000
DP3  a=80000000,00000000,00000000 b=40A00000,40A00000,40A00000 | 0x00000000 0x00000000 0x00000000
DP3  a=00000000,00000000,00000000 b=7FC00000,3F800000,3F800000 | 0x7FC00000 0x7FC00000 0x00000000
DP4  a=00000000,3F800000,3F800000,3F800000 b=7F800000,3F800000,3F800000,3F800000 | 0xFFC00000 0xFFC00000 0x40400000
DP4  a=3F800000,3F800000,3F800000,00000000 b=3F800000,3F800000,3F800000,7FC00000 | 0x7FC00000 0x7FC00000 0x40400000
RCC  00000000                 | 0x7F800000 0x5F800000
RCC  80000000                 | 0xFF800000 0xDF800000
RCC  7F800000                 | 0x00000000 0x1F800000
RCC  FF800000                 | 0x80000000 0x9F800000
RCC  7FC00000                 | 0x7FC00000 0x7FC00000
RCC  FFC00000                 | 0xFFC00000 0xFFC00000
RCC  7149F2CA                 | 0x0DA24260 0x1F800000
RCC  F149F2CA                 | 0x8DA24260 0x9F800000
RCC  0DA24260                 | 0x7149F2CA 0x5F800000
RCC  8DA24260                 | 0xF149F2CA 0xDF800000
RCC  007FFFFF                 | 0x7E800001 0x5F800000
RCC  807FFFFF                 | 0xFE800001 0xDF800000
RCC  3F800000                 | 0x3F800000 0x3F800000
RCC  BF800000                 | 0xBF800000 0xBF800000
RSQ  00000000                 | 0x7F800000 0x7F800000
RSQ  80000000                 | 0x7F800000 0x7F800000
RSQ  7F800000                 | 0x00000000 0x00000000
RSQ  FF800000                 | 0x7FC00000 0x00000000
RSQ  C0800000                 | 0x7FC00000 0x3F000000
RSQ  7FC00000                 | 0x7FC00000 0x7FC00000
RSQ  007FFFFF                 | 0x5F000001 0x5F000001
RSQ  807FFFFF                 | 0x7FC00000 0x5F000001
RCP  00000000                 | 0x7F800000 0x7F800000
RCP  80000000                 | 0xFF800000 0xFF800000
RCP  7F800000                 | 0x00000000 0x00000000
RCP  FF800000                 | 0x80000000 0x80000000
RCP  7FC00000                 | 0x7FC00000 0x7FC00000
```

Two corrections to the table:

- IEEE `RSQ(-0)` is `-inf` (`0xFF800000`), not `+inf`. hakuX's `src == 0.0`
  test also catches −0 and gives `+inf`.
- GLSL's `clamp()` on NaN is implementation-defined, so hakuX's `RCC(NaN)`
  cell is not a firm prediction.

## Legs

- **Controls, which no hypothesis moves:**
  - `RCC(1.0) = 0x3F800000` and `RCC(-1.0) = 0xBF800000`. rcp(1) = 1 was
    already measured on silicon (#225's ILU RCP rows).
  - `DP3((-0,0,0),(5,5,5))` is a zero of **either** sign.
  - This time the sign of zero is deliberately left out of the controls.
    #339 showed silicon does not follow IEEE there.
- **The answer:** each row is classified as IEEE, hakuX-GLSL, dot-forced, or
  none, and reported per op.
- **Completion:** "Testing completed normally", the console hands back to the
  dashboard, and `SPECIAL_raw.txt` has 44 lines.
