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

| title | A (=0) | B (=1) | GPU R/flip B/A | verdict |
|---|---|---|---|---|
| Blinx 2 | 1-1792703349-p1zeta1022-1980285, 1-1792704960-p1zeta1022-2079841, 1-1792704963-p1zeta1022-2080106 | 1-1792703350-p1zeta1022-1980392, 1-1792704962-p1zeta1022-2080002 | 0.996 (q1 0.944, q3 1.056), 245 of 245 gameplay windows matched | falsified: not tabled |
| Fable | 1-1792704964-p1zeta1022-2080209, 1-1792704966-p1zeta1022-2080418 | 1-1792704965-p1zeta1022-2080314 | 1.000 (q1 1.000, q3 1.053), 12 A and 101 B windows in the one scene both arms reached | falsified: not tabled |

### Blinx 2

All five runs logged `PurpleVK` and the arm's init line (`0x82, depth stored as float` for =0, `0x81, depth stored
as unorm (HAKUX_ZETA_D24)` for =1). The generated route reaches gameplay in some runs and stays in menus in others,
so the arms are compared in matched `full`/flip windows (`full` >= 800, within 6 pct):

| full/flip | n A | GPU R A (ms) | n B | GPU R B (ms) | B/A |
|---|---|---|---|---|---|
| 800-1200 | 51 | 10.0 | 35 | 8.9 | 0.89 |
| 1200-1600 | 154 | 13.2 | 46 | 15.35 | 1.16 |
| 1600-2400 | 52 | 17.35 | 151 | 17.0 | 0.98 |
| 2400+ | 5 | 26.7 | 13 | 25.6 | 0.96 |

The median of each B window's R over its matched A windows is 0.996. The falsifier (> 0.85) fires: Blinx 2's main
pass does not replay across two tiles under D32S8, so D24 removes nothing there. In menu windows (`full` 200-400)
the phase `GPU X` (passes other than the main one) is 1.9-2.8 ms/flip under =0 and 0.1 under =1, but those windows
run at 60 fps either way. Blinx 2 is not in the table.

### Fable

All three runs logged `PurpleVK` and the arm's init line. The generated route settles in a different place each
run, and each place holds steady for the rest of the run:

| run | arm | settled from | full/flip | rp/flip | GPU R | GPU X | GPU | fps |
|---|---|---|---|---|---|---|---|---|
| 2080209 | A1 (=0) | 300 s | 261 | 82 | 7.2 | 2.9 | 10.1 | 30.0 |
| 2080418 | A2 (=0) | 300 s | 548 | 245 | 6.6 | 8.6 | 15.2 | 27.8 |
| 2080314 | B (=1) | 180 s | 683 | 395 | 1.9 | 16.1 | 18.0 | 23.8 |

The run medians therefore compare places, not arms. A1 passed through B's place between 180 and 240 s, and that is
the only comparison of like with like (`full` 639-721):

| arm | windows | rp/flip | GPU R | GPU X | GPU | Tot | fps |
|---|---|---|---|---|---|---|---|
| A (=0) | 12 | 392 | 1.90 | 16.20 | 18.10 | 31.75 | 23.7 |
| B (=1) | 101 | 395 | 1.90 | 16.10 | 18.00 | 31.60 | 23.8 |

The falsifier (> 0.85 over >= 10 windows) fires at 1.000. In that place almost all the GPU time is outside the
main pass (X 16 ms), which D24 does not change; the two other places were measured under =0 only. Fable is not in
the table.

P4 (`HAKUX_SU_SPLICE`) splices only D24S8/D16 surfaces, so on Fable it needs `HAKUX_ZETA_D24=1`; its A/B runs both
arms under =1. The result above is that =1 costs Fable no GPU time in the place measured (pixels were not
compared). If P4 passes on Fable, P4's branch adds Fable to this table with its own measurement.
