# x1port1012-halo: #939 (b) root-caused and fixed behind HAKUX_FIST_ROUND=1 (verified on the Nova, run 13); (a), the layer missing on the ring's dark side, is NOT fixed

State: ready

Lane: x1port1012          Issue: #939 [#938]
Base: master @ 3a44935839
Files: docs/lanes/x1port1012/NOTES.md, docs/lanes/x1port1012/OUTBOX.md, docs/lanes/x1port1012/PR.md, docs/lanes/x1port1012/tools/burstcount.py, docs/lanes/x1port1012/tools/burstdiff.py, docs/lanes/x1port1012/tools/burstseq.py, docs/lanes/x1port1012/tools/burstzoom.py, docs/lanes/x1port1012/tools/fisttrunc-desktop-experiment.md, docs/lanes/x1port1012/tools/gdread.py, docs/lanes/x1port1012/tools/offsetres.py, docs/lanes/x1port1012/tools/ringframes.py, docs/lanes/x1port1012/tools/ringreturn.py, docs/lanes/x1port1012/tools/ringtrack.py, docs/lanes/x1port1012/tools/yclass.py, docs/lanes/x1port1012/tools/ynearest.py, docs/testing/nv2a_index.json, docs/testing/predictions/x1port1012-fistround.json, hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/pgraph/vk/buffer.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/texture.c, tcg/aarch64/tcg-target.c.inc
Prediction: docs/testing/predictions/x1port1012-fistround.json @ fa3a51b4369cdaaa4ff9cbe26b53f108783800174a1c3dc81c6d4276a5733a51
Needs device: yes (Nova)    Needs NDK: yes

Release note (none): default-off `HAKUX_FIST_ROUND=1` makes x87 FIST/FISTP round per the game's rounding mode on arm64 (with it on, Halo's menu ring no longer flickers, #939 (b)); plus default-off #939 diagnostics.

If the owner turns `HAKUX_FIST_ROUND` on by default for 0.5.1, the line becomes
`Release note (rendering): Halo's menu ring no longer jumps back in bursts; float-to-integer stores round as on the Xbox`.

**This is not a #939 fix.** #939 has two symptoms against the real console. (b), the lit side flickering in
bursts, is fixed behind the switch. (a), the surface layer that the console shows over the whole hull and
hakuX does not, is open: run 13's dark side is unchanged.

## (b): cause and remedy

The ring's "rotation" is a u-scroll: the guest writes the hull's texture offset `c[13].w` every frame.
In each burst it writes that value exactly 7/255 low on one frame in three or four, and is back on its line
the next. That is the X/Y alternation. Every other guest word of the hull draw is identical between X and Y
(gd dumps, runs 11 and 12).

The game computes the value with x87 FISTP under round-to-nearest. With `fp_jit` on (the default), inline
FIST/FISTP lower to the TCG `cvt*f_i*` ops:
- **x86_64** emits `CVTSD2SI`, which rounds per MXCSR (loaded from the guest's RC);
- **aarch64** emitted a bare `FCVTZS`, which always truncates.

On ticks whose fraction is 0.5 or more the Nova therefore stores n-1. Desktop proof: a truncating x86_64
build (dg3) writes the same 9 hull glitch frames at exactly 7/255; the rounding build (dg2) writes none.

`HAKUX_FIST_ROUND=1` (5d4b689ed9) emits `FRINTI Vtmp, Vn; FCVTZS Rd, Vtmp` instead. FPCR.RMode already
holds the guest's RC at every FIST (`gen_flcr`; FLDCW ends the TB). Grant: lane.local, `tcg/aarch64/tcg-target.c.inc`,
the cvt lowering and `tcg_target_init` only, default-off.

## Run 13 (`1-1792184446-x1port1012-1339105`, ref 5d4b689ed9), prediction committed first (3710b8bb24)

| leg | measured | verdict |
|---|---|---|
| V | `perfarch fist round=ON`; 32-63 inline FIST sites; 600 dump frames; video +37..+97 s | executed |
| B1 | `offsetres.py`: hull 0 glitch frames, terrain strip 0, other 0 (run 11: 9 and 76) | PASS |
| B2 | `burstcount.py`: 0 bursts on the top crop and 0 on the low crop (run 8: 4 and 5) | PASS |
| B3 | no d1 >= 8 with d2 < d1 at any of the four burst times; the d1 <= 3.5 band clause fails as written (normal motion there is 3.6-5.0, run 11's non-burst rows included) | alternation PASS; band clause FAIL, not re-scored |
| A | +68.2 s frame: the hull is the same dark green-grey as before, without the console's layer | as predicted: (a) not fixed |
| R | no crash; the menu animates through +97 s | PASS |

The switch changes every inline FIST/FISTP in every title: it makes them compute what x86 hardware does.
Default-on wants the device-run gate at fold that lane.local named in the grant. Shipping it on is the owner's call.

## (a): where it stands

Measured so far (NOTES.md, "Lit and dark draws"):
- the cube map's face stride is the hardware's (H1a refuted);
- the eye position, the normals and the skinning are consistent (H1c weighs against);
- the two lights are opposite;
- no later draw adds light to the hull;
- at photo 5's pose, no term computed as hakuX computes it reaches the console's brightness.

The final combiner reads `rgb = r0 + v0.a*(1 - r0)`, with v0.a = v4.z. v4.z is also the floor under both
lights. hakuX supplies v4.z = 0 for this size-2 attribute; a non-zero value would whiten and light the whole
hull, which is the shape of (a). That is hypothesis H5, open, and NOTES.md's "Next" ranks it with the others.

## Also here (default-off diagnostics, from earlier in Phase B)

| switch | commit | what it changes |
|---|---|---|
| `HAKUX_XVSS` | f3acdd0912 | `noskip` runs every transform-program launch; `audit` logs when the v0-hash skip would differ. Ruled out for Halo (it never launches one) |
| `HAKUX_S2TSHELF` | 18fb351588 | `0` turns off the shelved-surface lookup; `audit` logs hits. Ruled out for Halo (zero hits) |
| (log only) | 223f216d7c | one line per per-frame staging buffer at init: HOST_COHERENT or not |
| `XEMU_FRAME_DUMP=...,gd` | 7a1889054a | frame-dump schema 9: per-draw guest state deltas, host pipeline identity, per-stage texture hashes; read with `tools/gdread.py` |

Phase C (#938, speech level), Phase D (Fable, fp_jit) and Phase E (`HAKUX_PATTFENCE`, owner's go only) have not started.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
