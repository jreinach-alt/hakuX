# lane.yuv10 -- #10 SET_CONTROL0 colour-space conversion

## Dry run (2026-09-26)

`docs/lanes/xbox/csc_measured_model.py` at `origin/lane/xbox-csc10`
(`1e6c45dfbd`) against master's goldens: BumpMap_YUY2_L, BumpMap_UYVY_L,
BumpEnvLum_YUY2_L and BumpEnvLum_UYVY_L each 1,688 wrong of 111,496 quad px
(98.49% exact). Reproduces the brief's figure before any C edit.
