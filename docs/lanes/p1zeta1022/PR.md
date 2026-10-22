# p1zeta1022: Z24S8 stored as D24_UNORM_S8_UINT for the titles where it halves the GMEM tiles (#433)

State: draft

Lane: p1zeta1022              Issue: #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p1zeta1022/PR.md, android/app/src/main/cpp/xemu_android.cpp,
hw/xbox/nv2a/pgraph/vk/draw.c
Prediction: GPU R ms/flip (phase line) on a tabled title falls to 0.57-0.64 of the D32S8 arm. Falsified per title
  when GPU R/flip B/A > 0.85 over >= 10 play windows with `[dipwin] full` within 6 pct of the other arm
Needs device: yes (env A/B on master first, then one confirming run on the fold)
Needs NDK: yes

fps30 PLAN.md item P1.

## Mechanism

Z24S8 is stored as D32_SFLOAT_S8_UINT unless `HAKUX_ZETA_D24=1` (surface.c, read once at init). On Turnip the
D32S8 stencil is a separate GMEM plane, which doubles the tile width alignment: a 640x480 pass with 4-byte colour
no longer fits one tile, takes two, and with no binning pass the whole draw stream is replayed in each. D24S8 packs
depth and stencil into one 4-byte plane and the pass fits one tile.

The depth readback paths already handle both formats: `copy_zeta_surface_to_texture` (texture.c) samples through a
depth view, and `pgraph_vk_pack_depth_stencil_direct` (surface-compute.c) packs D24 and D32S8. The cost is the
one the surface.c comment names: a gl_FragDepth float through the unorm quantiser can store a guest depth word one
unit off (Adreno keeps 0x800008 where hardware has 0x800007), so a title that reads its depth back exactly can show
it. That is why this is a per-title table and not a new default.

## Change

- `xemu_android.cpp`: `kTitleZetaD24[]` and `ApplyZetaFormat(title_id)`, called in SyncSetupFiles right after
  `ApplyRenderMode`. A tabled title gets `HAKUX_ZETA_D24=1` before the renderer starts. An `HAKUX_ZETA_D24`
  already in the environment (the env_vars pref) wins, so `0` turns it off for an A/B. A value the table set is
  unset on the next launch in the same process. One logcat line per launch:
  `zeta_d24: <value> (<env|table|default>) title=<id> (#433)`.
- `draw.c`: the `[dipwin]` header gains `zfmt=f32|d24` from `pg->zeta_stored_as_float`, so every window states
  which arm it measured.

The table carries only the titles whose A/B passed (see below).

## A/B

Env A/B on master b944110629 (no new code needed to measure), `--perflog`, Nova, A-B-A per title, A last so the
env_vars pref is left on the shipped setting:

| title | A1 (=0) | B (=1) | A2 (=0) | GPU R/flip B/A | verdict |
|---|---|---|---|---|---|
| Blinx 2 | 1-1792703349-p1zeta1022-1980285 | 1-1792703350-p1zeta1022-1980392 | | | |
| Fable | | | | | |
