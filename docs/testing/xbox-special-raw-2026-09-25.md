# #112 item 4 on silicon: zero x inf/NaN, signed zeros and the ILU specials

**Measured 2026-09-25 on the project console (GPU rev 163 / MCP rev 212).**
This was registered beforehand in
[`docs/lanes/xbox/special-raw-prediction.md`](../lanes/xbox/special-raw-prediction.md)
(`a8437a5d5b`). The instrument is `CPU Shader Tests::SPECIAL_RAW`, in
nxdk_vsh_tests `hakux/special-raw` `7006335`
([`special_raw.patch`](../lanes/xbox/special_raw.patch)).

- **Handheld dry run first:** `0-0-x-1790388689-xbox-special-dry-992603`,
  hakuX `84a67b9cf8`. It completed with no crash signal and is the hakuX
  column below.
- **Console run:** 56 s, completion marker present, handed back to the
  dashboard, 44/44 lines.
- **Controls held:** `RCC(±1) = ±1`, and `DP3((-0,0,0),(5,5,5))` gave a zero.
- **Repeatability:** this XBE also carries #339's `SUBNORM_MAC`. Its 32
  silicon results are bit-identical to the first console run.

## What silicon does, and where hakuX stands

| behaviour | silicon | hakuX GLSL helper (the rendering path) | hakuX CPU evaluator (#234, constant writeback) |
|---|---|---|---|
| **MUL/MAD with a zero operand** (0×∞, 0×NaN, −0×5) | **+0**, sign dropped; `MAD(0,∞,1) = 1` | **matches** (`_MUL` forces +0) | NaN / −0: **no forcing** |
| **DP3/DP4 with a zero factor** (0×∞, 0×NaN terms) | **forced to 0 inside the dot**: `(0,1,2)·(∞,1,1) = 3`, `(1,1,1,0)·(1,1,1,NaN) = 3` | **NaN**: `_DP3`/`_DP4` is a plain `dot()` | NaN |
| **RCC signed-zero clamp** | `RCC(±0) = ±2^64`, `RCC(+∞) = +2^-64`, `RCC(−∞) = −2^-64`, `RCC(±1e30) = ±2^-64` | **matches exactly** (`clampAwayZeroInf`) | `RCC(±∞) = 0x9F7FFFFD` (**wrong sign for +∞**), `RCC(±1e30) = ±0x1F7FFFFD` (3 ULP off 2^-64) |
| **RSQ** | `RSQ(−0) = +∞`, `RSQ(−∞) = 0`, `RSQ(−4) = 0.5`, `RSQ(±MaxSub) = +∞` (the subnormal is flushed) | matches, except that as written `RSQ(MaxSub)` would give `0x5F000001` unless the GPU flushes denormals | matches |
| **RCP** | `RCP(±0) = ±∞`, `RCP(±∞) = ±0` | matches | matches |
| **NaN out of the ILU** (RCC/RSQ/RCP of NaN) | **`0x7FFFFFFF` always** (canonical) | passes the input NaN through | passes the input NaN through (`0x7FC00000`/`0xFFC00000`) |

## Defects this names

1. **The rendering path's `_DP3`, `_DP4` and `_DPH` need `_MUL`'s zero-forcing
   on each product.** Silicon forces 0×∞ and 0×NaN terms to 0, and hakuX
   returns NaN. This is the one GLSL-path mismatch measured here. No pixel
   count yet: it needs a vertex program whose dot has such a term.
2. **#234's CPU evaluator** is used only for the constant writeback, and it
   differs from both silicon and hakuX's own GLSL helpers:
   - it forces no zeros in MUL/MAD/DP;
   - it gives `RCC(+∞)` the wrong sign;
   - its RCC clamp is a decimal approximation of 2^±64, not the exact value.

   Aligning it with the GLSL helpers would fix all three.
3. **NaN payload.** Silicon's ILU emits `0x7FFFFFFF`. It rarely shows in pixels,
   but it is a free exact match.

## The rows

The table's middle column is the hakuX CPU evaluator. `(*)` marks a
difference from silicon. The classes name the pre-registered references
silicon's first component matches.

```
MUL a=0x00000000 b=0x7F800000                              silicon=0x00000000 hakuX=0x7FC00000 (*) | GLSL
MUL a=0x80000000 b=0x7F800000                              silicon=0x00000000 hakuX=0x7FC00000 (*) | GLSL
MUL a=0x7F800000 b=0x00000000                              silicon=0x00000000 hakuX=0x7FC00000 (*) | GLSL
MUL a=0x00000000 b=0x7FC00000                              silicon=0x00000000 hakuX=0x7FC00000 (*) | GLSL
MUL a=0x7FC00000 b=0x00000000                              silicon=0x00000000 hakuX=0x7FC00000 (*) | GLSL
MUL a=0x80000000 b=0x40A00000                              silicon=0x00000000 hakuX=0x80000000 (*) | GLSL
MUL a=0x40A00000 b=0x80000000                              silicon=0x00000000 hakuX=0x80000000 (*) | GLSL
MUL a=0x80000000 b=0xC0A00000                              silicon=0x00000000 hakuX=0x00000000     | IEEE,GLSL
MAD a=0x00000000 b=0x7F800000 c=0x3F800000                 silicon=0x3F800000 hakuX=0x7FC00000 (*) | GLSL
MAD a=0x00000000 b=0x7FC00000 c=0x3F800000                 silicon=0x3F800000 hakuX=0x7FC00000 (*) | GLSL
MAD a=0x80000000 b=0x40A00000 c=0x80000000                 silicon=0x00000000 hakuX=0x80000000 (*) | GLSL
MAD a=0x80000000 b=0x40A00000 c=0x00000000                 silicon=0x00000000 hakuX=0x00000000     | IEEE,GLSL
DP3 a=0x00000000,0x3F800000,0x40000000,0x00000000 b=0x7F80 silicon=0x40400000 hakuX=0x7FC00000 (*) | dot-forced
DP3 a=0x80000000,0x00000000,0x00000000,0x00000000 b=0x40A0 silicon=0x00000000 hakuX=0x00000000     | IEEE,GLSL,dot-forced
DP3 a=0x00000000,0x00000000,0x00000000,0x00000000 b=0x7FC0 silicon=0x00000000 hakuX=0x7FC00000 (*) | dot-forced
DP4 a=0x00000000,0x3F800000,0x3F800000,0x3F800000 b=0x7F80 silicon=0x40400000 hakuX=0x7FC00000 (*) | dot-forced
DP4 a=0x3F800000,0x3F800000,0x3F800000,0x00000000 b=0x3F80 silicon=0x40400000 hakuX=0x7FC00000 (*) | dot-forced
RCC a=0x00000000,0x00000000,0x00000000,0x00000000          silicon=0x5F800000 hakuX=0x5F800000     | GLSL
RCC a=0x80000000,0x80000000,0x80000000,0x80000000          silicon=0xDF800000 hakuX=0xDF800000     | GLSL
RCC a=0x7F800000,0x7F800000,0x7F800000,0x7F800000          silicon=0x1F800000 hakuX=0x9F7FFFFD (*) | GLSL
RCC a=0xFF800000,0xFF800000,0xFF800000,0xFF800000          silicon=0x9F800000 hakuX=0x9F7FFFFD (*) | GLSL
RCC a=0x7FC00000,0x7FC00000,0x7FC00000,0x7FC00000          silicon=0x7FFFFFFF hakuX=0x7FC00000 (*) | NONE
RCC a=0xFFC00000,0xFFC00000,0xFFC00000,0xFFC00000          silicon=0x7FFFFFFF hakuX=0xFFC00000 (*) | NONE
RCC a=0x7149F2CA,0x7149F2CA,0x7149F2CA,0x7149F2CA          silicon=0x1F800000 hakuX=0x1F7FFFFD (*) | GLSL
RCC a=0xF149F2CA,0xF149F2CA,0xF149F2CA,0xF149F2CA          silicon=0x9F800000 hakuX=0x9F7FFFFD (*) | GLSL
RCC a=0x0DA24260,0x0DA24260,0x0DA24260,0x0DA24260          silicon=0x5F800000 hakuX=0x5F800000     | GLSL
RCC a=0x8DA24260,0x8DA24260,0x8DA24260,0x8DA24260          silicon=0xDF800000 hakuX=0xDF800000     | GLSL
RCC a=0x007FFFFF,0x007FFFFF,0x007FFFFF,0x007FFFFF          silicon=0x5F800000 hakuX=0x5F800000     | GLSL
RCC a=0x807FFFFF,0x807FFFFF,0x807FFFFF,0x807FFFFF          silicon=0xDF800000 hakuX=0xDF800000     | GLSL
RCC a=0x3F800000,0x3F800000,0x3F800000,0x3F800000          silicon=0x3F800000 hakuX=0x3F800000     | IEEE,GLSL
RCC a=0xBF800000,0xBF800000,0xBF800000,0xBF800000          silicon=0xBF800000 hakuX=0xBF800000     | IEEE,GLSL
RSQ a=0x00000000,0x00000000,0x00000000,0x00000000          silicon=0x7F800000 hakuX=0x7F800000     | IEEE,GLSL
RSQ a=0x80000000,0x80000000,0x80000000,0x80000000          silicon=0x7F800000 hakuX=0x7F800000     | IEEE,GLSL
RSQ a=0x7F800000,0x7F800000,0x7F800000,0x7F800000          silicon=0x00000000 hakuX=0x00000000     | IEEE,GLSL
RSQ a=0xFF800000,0xFF800000,0xFF800000,0xFF800000          silicon=0x00000000 hakuX=0x00000000     | GLSL
RSQ a=0xC0800000,0xC0800000,0xC0800000,0xC0800000          silicon=0x3F000000 hakuX=0x3F000000     | GLSL
RSQ a=0x7FC00000,0x7FC00000,0x7FC00000,0x7FC00000          silicon=0x7FFFFFFF hakuX=0x7FC00000 (*) | NONE
RSQ a=0x007FFFFF,0x007FFFFF,0x007FFFFF,0x007FFFFF          silicon=0x7F800000 hakuX=0x7F800000     | NONE
RSQ a=0x807FFFFF,0x807FFFFF,0x807FFFFF,0x807FFFFF          silicon=0x7F800000 hakuX=0x7F800000     | NONE
RCP a=0x00000000,0x00000000,0x00000000,0x00000000          silicon=0x7F800000 hakuX=0x7F800000     | IEEE,GLSL
RCP a=0x80000000,0x80000000,0x80000000,0x80000000          silicon=0xFF800000 hakuX=0xFF800000     | IEEE,GLSL
RCP a=0x7F800000,0x7F800000,0x7F800000,0x7F800000          silicon=0x00000000 hakuX=0x00000000     | IEEE,GLSL
RCP a=0xFF800000,0xFF800000,0xFF800000,0xFF800000          silicon=0x80000000 hakuX=0x80000000     | IEEE,GLSL
RCP a=0x7FC00000,0x7FC00000,0x7FC00000,0x7FC00000          silicon=0x7FFFFFFF hakuX=0x7FC00000 (*) | NONE
silicon == hakuX (first component) on 22 / 44 lines; (*) marks a difference
```
