# #10 YUV class: what SET_CONTROL0's colour-space field does to texture samples

**Status: PRE-REGISTERED.** This file, [`csc_score.py`](csc_score.py),
[`csc_synth.py`](csc_synth.py) and the tests patch [`csc10.patch`](csc10.patch)
were committed and pushed before the emulator dry run and before the console
run. The branch was cut fresh from `origin/master` (`7b20fd2f66`).

**Amended before any silicon run** (see the section at the end). The first
dry run showed the bump tests' matrix was degenerate. BumpS and BumpT now use
one matrix word each, and the build changed. Every leg and prediction is
unchanged.

## Why

#10's YUV class is `BumpMap_YUY2_L`, `_UYVY_L`, `BumpEnvLum_YUY2_L` and
`_UYVY_L`, 111,496 px each. Its tracker row is `blocked_on` a console
measurement (board, 2026-09-26 11:58Z).

The goldens already name its cause (#10, comment 5848712719):
- The harness sets `SET_CONTROL0`'s `COLOR_SPACE_CONVERT` field
  (`CRYCB_TO_RGB`, bits 28-31) whenever stage 0 holds a YUV texture.
- Silicon then converts stage 1's A8R8G8B8 checker texel too. Both
  `BumpMap_YUY2_L` colours are exact under hakuX's `convert_ycbcr_to_rgb()`
  (`util.h`), with Y from R and the red term's rounding constant at 128.
- hakuX drops the field (`pgraph.c:2590`).

The goldens do not settle five things a fix needs:
1. whether the field converts every stage, or only through the dependent read;
2. which of G and B is Cb;
3. whether the bump offsets come from raw or converted stage-0 bytes;
4. the luminance source, and the order of the multiply against the conversion;
5. what a YUV texture reads as with the field off.

## What runs

- **The XBE.** nxdk_pgraph_tests `6743b6a` plus [`csc10.patch`](csc10.patch)
  (tests branch `hakux/csc-yuv10` `89a9040`). The patch adds a
  `Color space conversion` suite, registered after `AlphaFuncTests`.
  - XBE sha256 `f95e6bac16de…`, ISO `87a9a3ec4b7a…`.
- **The field is forced.** After `PrepareDraw`, every test pushes
  `SET_CONTROL0` with `SetupControl0`'s own value and only the colour-space
  field set or clear. The next test's `PrepareDraw` restores the harness value.
  - Blending, culling and the alpha test are off.
  - Every stage samples nearest.
  - The quads are drawn in screen space through the passthrough vertex program.
  - It uses pushbuffer methods only. There are no MMIO writes.
- **The session.** `Alpha func::AlphaFuncAlways_Disabled` runs first
  (PR #348), then the 16 tests, then `Bump map::BumpMap_YUY2_L` and
  `Bump env lum::BumpEnvLum_YUY2_L` as silicon controls. Shutdown on
  completion is off, networking is off, and the progress log is on.
- **The order.** A Thor dry run goes through the dispatcher first. Then the
  console runs through `tools/xbox/pgraph_run.py`.

| test | stages | what it reads |
|---|---|---|
| `CSC_Palette_Off` / `_On` | 1 | 256 designed A8R8G8B8 cells, R from 16 columns, (G, B) from 16 rows, four alphas |
| `CSC_Stages_Tex0_On` / `Tex1_On` / `Tex3_On` / `Tex1_Off` | 4 | each stage a mirrored copy of the palette, variants 0-3; the final combiner selects TEX0, TEX1 or TEX3 |
| `CSC_YUY2_Off` / `_On`, `CSC_UYVY_Off` / `_On` | 1 | 32 raw YUV cells `{Y0, U, Y1, V}`, read at an even and an odd texel |
| `CSC_BumpS_Off` / `_On`, `CSC_BumpT_Off` / `_On` | 2 | stage 0 uniform raw (R, G, B) = (128, 64, 192); stage 1 a ramp (R = x or y, G = B = 128); the left quad is the ramp at one pixel per texel (the colour table), the right quad the middle half displaced by `BUMPENVMAP` with one matrix word, w0 = 0.125 (BumpS, dS along s) or w2 = 0.125 (BumpT, dT along t) |
| `CSC_Lum_Off` / `_On` | 2 | stage 0 uniform raw (160, 96, 224); `BUMPENVMAP_LUMINANCE` over the palette, zero matrix, scale 1, offset 0 |

## Legs

The judge is [`csc_score.py`](csc_score.py), fixed before any data. Its
models:
- `csc()` is `util.h`'s converter with the red rounding constant at 128.
- The raw bump read is psh.c's unflagged one: dS from B, dT from G, two's
  complement over 128.

**Instrument legs.** If any fails, the run says nothing about the field.
- **K1:** every `Palette_Off` cell is its texel, RGBA, exactly.
- **K2:** every `Stages_Tex1_Off` cell is palette variant 1 exactly. This shows
  four stages each sample their own texture.
- **K3:** `BumpMap_YUY2_L` and `BumpEnvLum_YUY2_L` are pixel-identical to
  PR #340's console captures, which equal the goldens.
- **K4:** `BumpS_Off` and `BumpT_Off` displace by the raw prediction, -16 and
  +16 texels, within 1. This checks the offset readout. It uses the bump-matrix
  word order the G8B8 goldens support (see the amendment).

**Predictions.**
- **A1:** in `Palette_On`, exactly one Cb/Cr assignment reproduces every
  in-range cell exactly, with alpha unchanged. In-range means Y 42..209 and
  Cb, Cr 17..238: 36 cells, in the range `util.h` was fitted on. Cell
  (254, 0, 0) must read (72, 255, 18), the #10 golden's value.
- **B1:** `Stages_Tex0_On`, `Tex1_On` and `Tex3_On` are each their own stage's
  palette, converted with A1's assignment, exact on the in-range cells.

**Reported, with no prediction.**
- Every out-of-range cell, against kr 127 and 128.
- The raw channel slot of each byte in `YUY2_Off` and `UYVY_Off`.
- Whether `_Off` equals `_On` for YUV.
- `YUY2_On` and `UYVY_On` against hakuX's decode.
- The `_On` displacement against three rivals: raw -16/+16, converted Cb=G
  +0.25/+26.25, converted Cb=B -0.25/-24.25.
- The best luminance model with the field off and on. The candidates are
  L from each raw or converted channel, /255 or /256, truncate or round, and
  converting before, after or not at all.

**Void, not refuted.** If `Palette_On` equals `Palette_Off` and `YUY2_Off`
equals `YUY2_On`, the forced field never took effect. That makes the run void.
It does not refute A1 or B1.

**Mutation tests of the judge**, run on eight synthetic worlds from
[`csc_synth.py`](csc_synth.py) before this commit:

| world | outcome |
|---|---|
| the planted good world | all legs hold |
| palette off by one cell | K1 fails |
| hakuX's behaviour (no conversion, YUV always decoded) | A1 and B1 fail |
| stage 1 unconverted | B1 fails on Tex1 only |
| a wrong `_Off` displacement | K4 fails |
| red constant 127 | A1 fails on the (254, 0, 0) cell |
| Cb and Cr swapped | A1 holds under the other assignment |
| a missing capture | exit 2, void |

The reported readouts recovered each planted model exactly (slots, luminance
order and source, displacement rival, rounding constant).

**hakuX's expected row, from the dry run.** hakuX ignores the field:
- A1 and B1 fail on the dry run, and that failure is the defect.
- K1, K2 and K4 must hold on hakuX too. If they do not, the dry run has found an
  instrument problem before any silicon time.

## What each outcome means for a fix

- **A1 and B1 hold.** The field converts every stage's sample. The fix stores
  bits 28-31 of `SET_CONTROL0` and applies the converter to every stage's texel
  when the field is set: Y from R, with A1's Cb/Cr order. The YUV slots with the
  field off then say what hakuX must upload for YUV formats instead of
  decoding unconditionally.
- **B1 fails on Tex1 and Tex3 but holds on Tex0.** The field converts stage 0
  only. The goldens' converted TEX1 then comes through the dependent read, and
  the fix is local to the bump path.
- **A1 fails under both assignments.** The converter for RGB data is not
  `util.h`'s. `Palette_On` is then the measured table.
- **The `_On` displacement.** A raw reading means the texture shader takes
  offsets from unconverted bytes, so a YUV bump source feeds the slots measured
  in `YUY2_Off`. A converted reading means hakuX's upload-time decode is right
  for the offsets.

## Amended 2026-09-26, before any silicon run

The first Thor dry run was `0-0-x-1790447894-xbox-csc10-dry-704756`, at ref
`84a67b9cf8`. It completed all 19 tests normally. K1 and K2 held. K4 failed:
both bumped quads displaced by 0.00 texels, where -16 and +16 were registered.

**The cause was the design, not the instrument.**
- `SET_TEXTURE_SET_BUMP_ENV_MAT`'s four words land as
  s += w0·dS + w3·dT and t += w1·dS + w2·dT. That is the swizzle in
  `pgraph.c`'s method handler.
- The registered matrix was (0.125, 0, 0, 0.125). With this source's
  dS = -0.5 and dT = +0.5, it cancels exactly on both axes.
- The registration assumed the D3D reading instead (s += w0·dS + w2·dT), taken
  from `docs/testing/bump_oracle.py` without checking it against hakuX.

**The G8B8 goldens favour hakuX's word order.** This is `bump_oracle.py`'s own
geometry, scored both ways (percent of 111,496 quad px):

| golden | matrix | D3D order | hakuX's order |
|---|---|---:|---:|
| `BumpMap_G8B8` | (0.3, 0, 0, 0.5) | 80.4 | 90.3 |
| `BumpMap_G8B8_B` | (0.3, 0, 0, 0.5) | 52.0 | 82.5 |
| `BumpMap_G8B8_R90` | (0, -0.1, 0.3, 0) | 53.6 | 85.2 |
| `BumpMap_G8B8_B_R90` | (0, -0.1, 0.3, 0) | 67.5 | 85.6 |

**The change.**
- BumpS now uses w0 alone (dS along s) and BumpT uses w2 alone (dT along t),
  so each ramp reads one offset.
- K4's predictions (-16 and +16) and every other leg are unchanged.
- The new build is tests `89a9040`, XBE `f95e6bac16de…` and ISO
  `87a9a3ec4b7a…`.
- A second dry run is queued before any console time.

