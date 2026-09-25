# lane.wbufdepth24 -- #266 notes

Base: master @ e48514f980. Instrument: `classify.py` in this directory
(colour miss/extra split plus decoded `_ZB` depth words, against
`/home/justin/goldens/results/W_buffering`).

## What the test does (wbuf_tests.cpp, fold-pins tree)

- Name is `{W,Z}Buf{16,24}{D,F}_<prim>_V<vsh>_ZB<bias>_ZS<slope>`. **V1 is the
  programmable passthrough shader** (screen-space vertices, pushed z up to
  16,809,768 -- *above* 2^24-1 -- at the far edge); **V0 is fixed function**
  (XDK viewport, camera at y=50 looking along a huge floor at y=0).
- ZB1 = polygon offset bias 16. ZS1 = slope factor 65536 (W) or 16 (Z).
- ZCLAMP_EN = CLAMP, CLIP_MIN 0, CLIP_MAX 16777215*16 = 268,435,440, LEQUAL,
  cleared depth = max.
- A trailing `_ZB` is the depth-buffer dump. Its Z24S8 pixel is
  RGBA = (bits 8-15, bits 0-7, stencil, bits 16-23) -- read off the golden's
  own printed labels (`Z=0xFFE9AD` at (159,160) = (0xE9,0xAD,0,0xFF)).
- The colour capture prints the depth word at 15 sample points as text, so a
  depth-word difference at a sample point shows up as `label-differs`.

## Mechanism A: a saturated D24 fragment fails its depth test (the 1.13 M)

Arm `1790321693-arms-wbuf31fix-fix-301236` (Thor, e8218629d757), 24 + 8 quad
captures of the 24-bit formats, classified:

| | px |
|---|---:|
| colour px differing, all Floor/Wall/Roof quads, every format | 1,143,601 |
| ...of which the capture shows the clear colour and the golden does not (quad missing) | 1,129,834 |
| ...of which the golden's depth word there is 0xFFFFFF (saturated) | **1,129,274** (99.95%) |

Every one of those rows is ZBuf24D (all three quads, all variants) or the two
WBuf24D V0 ZS1 "blank" rows. Silicon draws the quad there and writes
0xFFFFFF; we do not draw it and the buffer keeps its clear, which is also
0xFFFFFF -- so the `_ZB` dumps agree and only the colour shows it.

Why: `psh.c`'s D24 branch writes `gl_FragDepth = zfloor / 2^24` after
clamping zfloor only to `clipRange.w` = CLIP_MAX = 268,435,440, not to the
format's 0xFFFFFF. On Vulkan Z24S8 is a **D32_SFLOAT** image
(`vk/surface.c`, `zeta_stored_as_float`), so the fragment carries 1.0 (depth
clamp to the viewport) or up to 16.0 (no clamp), against a cleared
0xFFFFFF/2^24 = 0.99999994: LEQUAL fails and the pixel is dropped. Silicon
saturates the word at 0xFFFFFF, equal to the clear, and LEQUAL passes.

Why only 24D:
- **16-bit rows are the control**: they saturate over far more area (the
  whole of ZBuf16D V1) and draw correctly, because D16 is a unorm target, the
  write clamps to 1.0, and 1.0 *is* the cleared 0xFFFF.
- **F24 rows** already saturate: `zf24 = min(bits >> 7, 0xFFFFFF)`.
- **WBuf24D** only saturates with V0 + ZS1 (slope 65536 on the fixed-function
  floor drives every pixel past 0xFFFFFF -- golden is 0xFFFFFF on all 307,200
  px). Its other rows keep w in 58..325 and never saturate.

Candidate fix (one line, psh.c D24 case): `min(zfloor, 16777215.0)` before
the divide. Predicted: the ~1.13 M missing px go to ~0 on 24 ZBuf24D colour
rows and the 2 WBuf24D V0 ZS1 rows; no `_ZB` row moves (both sides already hold
0xFFFFFF there); 16-bit and F24 rows do not move (different branch).

Kill condition: after the fix, the missing-where-saturated count on those 26
rows stays above 10% of today's, or any 16-bit / F24 row moves.

## Smaller, depth-word only (not A)

From the same classification, words differing in `_ZB` (not affected by A):

| family | shape | px/capture |
|---|---|---:|
| ZBuf24D FloorQuad V0 (fixed function) | ours = gold **+2** over the drawn floor | 90,340 (ZS0) / 138,328 (ZS1) |
| {W,Z}Buf24{D,F} Floor/Roof/Wall V1 ZS1 | +1 (Floor/Wall), -1/-2 (Roof) over the quad | ~124-138 k |
| WBuf24F FloorQuad V0 ZS0 | +1 | ~73-78 k |
| ZBuf24D V1 ZS0 | -1 | ~11 k |

The ZS1 ones are slope-offset rounding (psh.c slope code -- #31's
territory; not touched here). The V0 +2 is a fixed-function z transform
precision question. These are ZB rows where the scorer's "structural" count
is inflated: a +1 or +2 that carries out of the low byte reads as a 254-255
channel step. Count words, not channels.

## Status 2026-09-25 (session 1)

- Nova's logcat on the baseline: `Z24S8 host format 0x82, depth stored as
  float` (D32_SFLOAT_S8_UINT), as mechanism A requires. Thor to be read from
  its baseline.
- Clear path (`pgraph.c` ~5084) stores 0xFFFFFF / 2^24 on a float image, so
  `min(zfloor, 16777215.0) / 2^24` is bit-equal to the clear and LEQUAL passes.
- **Waiting on:** (1) baselines `1790362749-wbufdepth24-3948624` (Thor) and
  `-3948651` (Nova), 2 runs each -- rerun `classify.py RESULT 1` and `... 2` on
  both, and check the two blanks are blank on every run; (2) the board's
  answer to the psh.c grant request on #266. With the grant: one-line fix,
  register `wbufdepth24-d24sat.json` (26 colour rows down, 16-bit / F24 /
  `_ZB` rows must_not_move), arm.
- Do not repeat: the scorer's structural channel count on `_ZB` rows counts a
  carried +1/+2 as a 254 step; decode words.
