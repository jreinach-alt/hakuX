# #255 on silicon: what the MAC unit does with subnormal operands

**Measured 2026-09-25 on the project console (GPU rev 163 / MCP rev 212).**
This was registered beforehand in
[`docs/lanes/xbox/subnorm-mac-prediction.md`](../lanes/xbox/subnorm-mac-prediction.md)
(`404437a160`). The instrument is `CPU Shader Tests::SUBNORM_MAC`, added in
nxdk_vsh_tests `hakux/subnorm-mac` `330e4a8`
([`subnorm_mac.patch`](../lanes/xbox/subnorm_mac.patch)).

- **Emulator dry run:** `0-0-x-1790379884-xbox-subnorm-dry2-1443343`, hakuX
  `84a67b9cf8` on a handheld. It completed with no crash signal, and it is the
  hakuX column below.
- **Console run:** 50 s, completion marker present, handed back to the
  dashboard, 32/32 lines.

## What silicon does

1. **MOV keeps subnormals bit-exact.** All six subnormal constants, positive
   and negative, came back unchanged through `mov r0, c[96]; mov c[188], r0`.
   Nothing is flushed on a move.
2. **MUL, ADD and MAD flush a subnormal *operand* to +0, and the sign is
   dropped.** `-MaxSub x 2^24` gives `+0`, and so does `-MinSub x 2^100`.
   Under IEEE these are normal numbers; the sign-keeping flush-to-zero model
   predicted `-0`.
3. **A result that underflows into the subnormal range is flushed to a zero
   that *keeps* its sign.** `-2^-70 x 2^-70` gives `-0`.
4. **ADD does not follow IEEE's signed-zero rule.** `-0 + -0` gives `+0`, and
   so does `-MinSub + -MinSub` (both operands flushed to +0).
5. **MAD flushes the subnormal product before the add.** `2^-70 x 2^-70 + MinNormal`
   gives `0x00800000`, where IEEE, or keeping the intermediate, gives
   `0x00800200`. `MinNormal x -0.5 + 0` gives `+0`.

## The rows

```
op   a        b        c        | silicon  hakuX    | IEEE     FTZ-io   FTZ-o    | silicon class
MOV  007FFFFF                   | 007FFFFF 00000000*| 007FFFFF 00000000 00000000 | IEEE
MOV  807FFFFF                   | 807FFFFF 80000000*| 807FFFFF 80000000 80000000 | IEEE
MOV  00000001                   | 00000001 00000000*| 00000001 00000000 00000000 | IEEE
MOV  80000001                   | 80000001 80000000*| 80000001 80000000 80000000 | IEEE
MOV  00400000                   | 00400000 00000000*| 00400000 00000000 00000000 | IEEE
MOV  80400000                   | 80400000 80000000*| 80400000 80000000 80000000 | IEEE
MOV  00800000                   | 00800000 00800000 | 00800000 00800000 00800000 | IEEE,FTZ-io,FTZ-o
MOV  80000000                   | 80000000 80000000 | 80000000 80000000 80000000 | IEEE,FTZ-io,FTZ-o
MUL  007FFFFF 4B800000          | 00000000 00000000 | 0C7FFFFE 00000000 0C7FFFFE | FTZ-io
MUL  807FFFFF 4B800000          | 00000000 80000000*| 8C7FFFFE 80000000 8C7FFFFE | NONE
MUL  00000001 71800000          | 00000000 00000000 | 27000000 00000000 27000000 | FTZ-io
MUL  80000001 71800000          | 00000000 80000000*| A7000000 80000000 A7000000 | NONE
MUL  1C800000 1C800000          | 00000000 00000000 | 00000200 00000000 00000000 | FTZ-io,FTZ-o
MUL  9C800000 1C800000          | 80000000 80000000 | 80000200 80000000 80000000 | FTZ-io,FTZ-o
MUL  1F800000 1F800000          | 00000000 00000000 | 00200000 00000000 00000000 | FTZ-io,FTZ-o
MUL  21800000 21800000          | 03800000 03800000 | 03800000 03800000 03800000 | IEEE,FTZ-io,FTZ-o
ADD  007FFFFF 00000000          | 00000000 00000000 | 007FFFFF 00000000 00000000 | FTZ-io,FTZ-o
ADD  007FFFFF 007FFFFF          | 00000000 00000000 | 00FFFFFE 00000000 00FFFFFE | FTZ-io
ADD  807FFFFF 00000000          | 00000000 00000000 | 807FFFFF 00000000 80000000 | FTZ-io
ADD  00800000 807FFFFF          | 00800000 00800000 | 00000001 00800000 00000000 | FTZ-io
ADD  00800000 007FFFFF          | 00800000 00800000 | 00FFFFFF 00800000 00FFFFFF | FTZ-io
ADD  3F800000 00000001          | 3F800000 3F800000 | 3F800000 3F800000 3F800000 | IEEE,FTZ-io,FTZ-o
ADD  80000000 80000000          | 00000000 80000000*| 80000000 80000000 80000000 | NONE
ADD  80000001 80000001          | 00000000 80000000*| 80000002 80000000 80000000 | NONE
MAD  007FFFFF 4B800000 00000000 | 00000000 00000000 | 0C7FFFFE 00000000 0C7FFFFE | FTZ-io
MAD  1C800000 1C800000 00000000 | 00000000 00000000 | 00000200 00000000 00000000 | FTZ-io,FTZ-o
MAD  1C800000 1C800000 00800000 | 00800000 00800200*| 00800200 00800000 00800000 | FTZ-io,FTZ-o
MAD  807FFFFF 3F800000 00000000 | 00000000 00000000 | 807FFFFF 00000000 00000000 | FTZ-io,FTZ-o
MAD  3F800000 3F800000 007FFFFF | 3F800000 3F800000 | 3F800000 3F800000 3F800000 | IEEE,FTZ-io,FTZ-o
MAD  00800000 3F000000 00000000 | 00000000 00000000 | 00400000 00000000 00000000 | FTZ-io,FTZ-o
MAD  00800000 BF000000 00000000 | 00000000 80000000*| 80400000 00000000 00000000 | FTZ-io,FTZ-o
MAD  00000000 00000000 007FFFFF | 00000000 00000000 | 007FFFFF 00000000 00000000 | FTZ-io,FTZ-o
silicon == hakuX on 20 / 32 rows (* marks a difference)
control MUL 21800000: silicon 03800000 (expected 03800000) OK
control ADD 3F800000: silicon 3F800000 (expected 3F800000) OK
control ADD 80000000: silicon 00000000 (expected 80000000) IMPOSSIBLE
control MAD 3F800000: silicon 3F800000 (expected 3F800000) OK
```

## Against hakuX (`84a67b9cf8`): 20 of 32 rows agree, and 12 differ

| rows | silicon | hakuX |
|---|---|---|
| MOV of a subnormal (6) | kept bit-exact | flushed to a signed zero |
| MUL with a negative subnormal operand (2) | `+0` | `-0` |
| ADD `-0 + -0`, `-MinSub + -MinSub` (2) | `+0` | `-0` |
| MAD `2^-70 x 2^-70 + MinNormal` | `0x00800000` (product flushed) | `0x00800200` (product kept) |
| MAD `MinNormal x -0.5 + 0` | `+0` | `-0` |

hakuX's printed values come from #234's CPU evaluator. It flushes "in and
out, to a zero of the same sign" (`vsh_flush_denormal`), and it keeps a MAD's
product unflushed. Silicon differs on the move, on the sign of an operand
flush, on ADD's zero sign, and on MAD's intermediate.

## A registered control that missed, and why it is my registration's error, not the instrument's

I registered `ADD -0 + -0 = 0x80000000` as hypothesis-independent, with "a miss
there means the instrument is broken". It missed: silicon gives `0x00000000`.
The instrument is not broken:

- The MOV rows carry `-0`, every negative subnormal and MinNormal through the
  same constant-load and RDI path unchanged.
- The other three controls held exactly: `2^-60 x 2^-60`, `1 + MinSub`, and
  `1 x 1 + MaxSub`.

The error is the premise. I assumed IEEE's `-0 + -0 = -0`, and silicon's adder
returns `+0` for a zero sum. That is a finding, recorded here as a
registration mistake rather than silently re-labelled.

## Bearing on #255 / #288

#288's verification is `Exceptional_Float/Float` text "IDENTICAL 0,-0,0,-0".
That text is `%f`, which prints both `-0` and a negative subnormal as
`-0.000000`, so it cannot tell whether silicon produced `-0` or kept
`-MaxSub`.

These rows measure constants, not the vertex-attribute path Exceptional Float
uses. On the constant path, silicon's MOV keeps a negative subnormal
bit-exact rather than flushing it to `-0`. Whether the attribute path flushes
is not measured here. A raw-bits variant of Exceptional Float would settle it.
