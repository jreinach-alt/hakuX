# lane.cloud-34: where #34 stands (2026-09-26)

Analysis only, no code. Every finding #34 filed or picked up since is fixed
and folded, on lavapipe and on the Adreno 740 system driver. Recommend close.

## The findings, one row each

| # | finding | fixed by | desktop (lavapipe, layer 1.3.275) | Adreno 740 system driver (layer 1.4.341.0) |
|---|---|---|---|---|
| 1 | descriptor set updated while bound | e7998e7 | 0, Clear (control `2337519c`: 22,613) | not reported, Clear |
| 2 | push template vs incompatible layout (`07993`) | 83a4718 | 0, Clear/Image blit/Surface clip | not reported, Clear |
| 3 | set 0 not bound (`08600`) | 83a4718 | 0 | not reported, Clear |
| 4 | RAW on `LOAD_OP_LOAD` | 0a428d5 | 0 (control: 17) | not reported, Clear |
| 5 | Z16 through a colour aspect (`09105`) | 8f49518 | 0 | not reported, Clear |
| 6 | zero-extent framebuffer (Surface clip) | 9e39ca4 | 0 | not measured |
| 7 | sampled read after attachment write (`SYNC-HAZARD-READ-AFTER-WRITE` at draw) | 4b425324 plus later work | 0 (issue comment 2026-09-13, with a control) | not reported, Clear |
| 8 | retired image view pushed again (layer segfault) | 136b15a | Surface clip completes under the layer | not measured |
| 9 | `VUID-VkShaderModuleCreateInfo-pCode-08740` GeometryPointSize | PR #371 (folded f6ead6e172) | cannot occur: lavapipe has the feature | 1 -> 0, controls PASS (`docs/lanes/vkpointsize34/NOTES.md`, requests 1790317606-vklayer34-4071708 and 1790408065-vkpointsize34-3720485) |

"Not reported" on Adreno means the Clear run under the layer, with synchronisation
validation chained in (`vk/instance.c` sets `create_info.pNext =
&validationFeatures` whenever validation is enabled, Android included) and all five
positive-control lines present, emitted exactly one message, and that was row 9.
After #371 it emits none.

## What these zeros do not cover

- **The fleet driver.** 857 of 1152 device runs load `vulkan.purple.so` through
  adrenotools, which enters via `volkInitializeCustom` and bypasses the loader and
  every layer (`docs/testing/vk_validation_android.md`, block 2). Every Adreno row
  above is about the system Qualcomm driver. This is a limit of the instrument, not
  an open finding; nothing in #34 was ever measured on the custom driver.
- **Adreno on Image blit and Surface clip.** Only Clear has been surveyed on device.
  The issue's own table says Image blit has Clear's shape, and the desktop zeros hold
  on all three discs. If the board wants it, the run that settles it is ref
  `386af38184` (the vklayer34 instrumentation on the #371 fix) queued as a suites
  request with `--no-expect` for `Image blit` and `Surface clip` on thor, counted
  with `python3 docs/lanes/vklayer34/count_vuids.py <result dir>`; a pass is every
  control line present and 0 messages. It is not a scored pixel arm, so there is no
  prediction to register for it.

## Instrument follow-up, not #34's

`vk_validation_android.md` blocks 1 and 3 are still in place on master @ 6c25a829ef:

- `docs/testing/dispatcher.sh:1379` LOGCAT_SPEC ends `*:S` and does not name
  `xemu-vk-validation`, so an ordinary run never shows even the
  `validation_layers config = 0` line. The app's own logger
  (`HakuXApplication.kt:26`) already lists the tag at `:V`.
- No request field sets the `validation_layers` pref or forces the system driver,
  so every survey above needed a throwaway code ref.

`dispatcher.sh` is in no territory row right now (blinx372b released it at wave
245; the toolsmith row's note says it returns there) and it is an instrument, so
this lane did not edit it. It belongs with lane.toolsmith.
