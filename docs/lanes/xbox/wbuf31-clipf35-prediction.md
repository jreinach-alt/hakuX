# #31 on silicon: `ClipF` at `clip_top = 35` -- prediction, registered before the run

**Status: PRE-REGISTERED.** This file is committed and pushed before the disc
boots on the console. Nothing below was chosen after a capture existed. The
verdict table is not new: it was registered on 2026-09-19 in
[`docs/investigations/wbuffer-31-clipf-phase.md`](../../investigations/wbuffer-31-clipf-phase.md)
and is printed by `docs/testing/wbuf_clip_phase_choice.py`. What is new is
where the capture comes from, and the controls that must hold for it to count.

## Why this capture decides #31's remaining residual

`ClipF`'s second triangle anchors its slope-scaled polygon offset 2 rows below
`clip_top` on every capture that exists (34, 130, 226 at `clip_top` 32, 128,
224), and the shipped code anchors it at the first covered row snapped to the
2x2 quad (32, 128, 224). That is the part of #31 not yet modelled. Every
`clip_top` the suite can generate is a multiple of 32, so **63** candidate
rules fit all three captures and no existing capture separates any two of
them. At `clip_top = 35` they split seven ways.

The investigation that picked 35 said "do not queue it" because this
project's devices run the emulator under test, so a capture from them would
recover the emulator's own rule. The console is NV2A silicon: GPU rev 163 /
MCP rev 212 (V1.1), [`xbox-console-provenance.md`](../../testing/xbox-console-provenance.md).

## V0 -- this console anchors exactly like the golden hardware (already measured)

The published goldens come from 1.0 silicon; this console is a 1.1. So before
a capture from it can stand in for the goldens, the console must reproduce the
golden anchors. It does, from data already on disk:
`wbuf_anchor_recover.py` over the console's own 530 `W_buffering` captures
from the 2026-09-19 calibration run
(`~/hakux-work/hardware/runs/2026-09-19-calib/full/out/run1`, viewed in the
goldens layout) prints output **byte-identical** to the same tool over the
goldens: all 66 anchors, the exact offset intervals, and the `floor(w)`
control (FloorQuad, RoofQuad, WallQuad, TriH 0 mismatches; TriV 144/26,400).
`ClipF` t1: **34.000, 130.001, 226.001**, as on the goldens.

## What runs

| | |
|---|---|
| tests tree | `abaire/nxdk_pgraph_tests` `6743b6a` + `docs/testing/wbuf31_clipf_phase.patch`, unchanged: branch `hakux/wbuf31-clipf35` @ `a39bc60fc2` in `~/nxdk_pgraph_tests-wbuf31` |
| XBE | `default.xbe`, sha256 `d740024a1e6e7133dda5ca93ef0cce658f97b1d55312a86d8ddfdcfc7d17973e` |
| ISO | `nxdk_pgraph_tests_xiso.iso`, 5,832,704 bytes, sha256 `1b6bcc21b7fd8462f486495477350447a97f3d0e310052faf18eec202980abc8` |
| console install | `E:\Apps\PgraphWbuf31\` (new directory; `PgraphCalib` and `PgraphPerTest` untouched) |
| suite | `W buffering` only |
| tests | `WBuf24D_FloorQuad_V1_ZB0_ZS0`, `WBuf24D_FloorQuad_V1_ZB0_ZS1`, `WBuf24D_ClipF-150-032_V1_ZB0_ZS1`, `WBuf24D_ClipF-150-128_V1_ZB0_ZS1`, `WBuf24D_ClipF-150-224_V1_ZB0_ZS1`, `WBuf24D_ClipF-150-035_V1_ZB0_ZS1` |

Each test writes a colour capture and a `_ZB` depth capture. The unclipped
`FloorQuad` `ZS0` capture is the plane `ClipF` is read against (identical
geometry; `floor(w)` does not see the clip).

## Controls, each of which voids the run if it fails

- **C1 -- the run reproduces the known anchors.** `ClipF-150-032`, `-128`,
  `-224` t1 recover 34, 130, 226 again (within the tool's 0.01 px), and
  `ClipF-150-032` t0 recovers 32. A run that cannot reproduce three anchors
  it has already produced once is not read for the fourth.
- **C2 -- the new variant is the geometry it was designed to be.**
  `ClipF-150-035`: t0 covers **15,773 px** and t1 **189,047 px**. These are
  computed from geometry alone by `wbuf_clip_phase_choice.py`, the same routine
  that reproduces the measured 16,801 and 189,489 px at `clip_top = 32`.
- **C3 -- the plane is sound on this run.** `FloorQuad` `floor(w)` versus
  the run's own `ZS0` capture: 0 mismatches, as in V0.

## The verdict -- the recovered anchor of `ClipF-150-035` t1

| recovered anchor | rule | reading |
|---:|---|---|
| **34** | `4*floor(ct/4)+2` | the absolute 4-grid at phase 2, the rule `TriH` pins on all 24 of its triangles |
| **36** | `2*floor(ct/2)+2` | the 2x2-quad snap, plus 2 |
| **37** | `ct+2` | the rule recorded as measured on #31 |
| **38** | `2*floor((ct+1)/2)+2`, or a 4-grid at another phase | phase variants |
| **42 / 50 / 66** | grids of 8 / 16 / 32 | coarse grids |
| anything else | -- | the whole 63-rule family is refuted |

What the emulator does today at 35 (the shipped quad snap, no +2) is 34 as
well, but the shipped rule is already refuted at 32, 128 and 224 (it gives the
`clip_top` itself), so a 34 would not vindicate it.

## Safeguards (no remote power cycle until the owner's networked switch arrives)

- The XBE runs on the desktop emulator first, through the dispatcher's desktop
  channel, and must finish its tests there without a crash or a hang.
- `enable_shutdown_on_completion` is **false**: the console must stay up with
  its log readable.
- No register writes of any kind. This XBE is the stock test program plus one
  test variant.
- Every FTP poll has a timeout. If the console stops answering, the run stops
  and the owner gets one plain-text line.

## Scoring, exactly

Captures are fetched over FTP into a directory in the goldens layout
(`<root>/W_buffering/<name>.png`), and then

    python3 docs/testing/wbuf_anchor_recover.py --goldens <root>

prints C3 (its CONTROL block), C1 and the verdict (its `ClipF-150-*` rows).
C2's pixel counts are the `n` column of the same rows. Captures and logs stay
on the host under `~/hakux-work/hardware/runs/`; only the scored result is
committed, in the manner of `xbox-calibration-2026-09-20.md`.
