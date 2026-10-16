# fps1015: measured causes for the owner's FPS defects (MKSM, Top Spin, Batman Begins, Prince of Persia, Halo 2); HAKUX_S2T_CVT

State: ready

Lane: fps1015            Issue: #433 #986 #992 #995 #993 #994
Base: master @ 0e5fab6bef
Files: docs/lanes/fps1015/PR.md, docs/lanes/fps1015/NOTES.md, docs/lanes/fps1015/winsplit.py, docs/lanes/fps1015/s2tscan.py, docs/lanes/fps1015/dlrate.py, docs/lanes/fps1015/irqrate.py, docs/lanes/fps1015/dumpstat.py, docs/lanes/fps1015/stallscan.py, docs/lanes/fps1015/cvtcensus.py, docs/lanes/fps1015/s2tread.py, docs/lanes/fps1015/tsread.py, docs/lanes/fps1015/routes/fps1015-mksm.route, docs/lanes/fps1015/routes/fps1015-topspin.route, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c, docs/testing/predictions/fps1015-pixels.json, docs/testing/predictions/fps1015-mksm.json, docs/testing/predictions/fps1015-topspin.json
Prediction: docs/testing/predictions/fps1015-pixels.json @ 50e23fcbb68a87f6d82b8e8d5600d22672ffd52240ba693290e425fede4fd8f4, docs/testing/predictions/fps1015-mksm.json @ df1ac10a2d8de1ff54be6c2a1e16614310a21867b66c72222813356933be3004, docs/testing/predictions/fps1015-topspin.json @ aa107cd4c3174da4d7b96ba46a6c2a5675c91f07f2e4774e86fc7c691ec72ee1
Needs device: yes    Needs NDK: yes

Release note (none): HAKUX_S2T_CVT, off by default, decodes 16-bit render targets that a title samples as textures on the GPU instead of downloading them.

Per-issue split of the slow frames into vCPU, GPU and wait time from the saved owner-play telemetry, and one
default-off lever for the cause four of the five titles share. Details and every number are in
`docs/lanes/fps1015/NOTES.md`.

| issue | title | slow frames | cause | status |
|---|---|---|---|---|
| #986 | Mortal Kombat: Shaolin Monks | cutscene 14-23 fps, G 41-64 ms | 3 16-bit render-to-texture downloads a frame (`cvt`), each a finish and a fence wait; median G 43.2 ms with `Fin` 18.5 ms | cause found; with `HAKUX_S2T_CVT=1` the cutscene's first 1800 frames run at 54.2-54.4 fps instead of 27.5-29.0 (two runs per arm) |
| #992 | Top Spin | match play 26-31 ms frames | the same downloads, 30 a frame in match play; bound 11-15 ms of the frame | cause found; with `HAKUX_S2T_CVT=1` match play runs at 59 fps instead of 38 (median G 16.7 against 26.1 ms, one run per arm). Replays still drop to 14-18 fps, bound by the PFIFO thread at three times live play's draws |
| #992 | Brian Lara Cricket 2005 | ball in play | a different shape | unexplained; needs one perflog run |
| #995 | Batman Begins | fire/explosion cutscenes 14-23 fps | GPU work outgrows the 30-fps cap; one download a frame stops it overlapping the PFIFO thread | partly explained |
| #993 | Prince of Persia | fog room 19 fps | PFIFO-thread frame 33-36 ms against the 33.4 ms two-vblank budget; nine shadow-map downloads a frame inside it | reduced to a bound; the A/B needs a save at the fog room, 17 minutes into a new game |
| #994 | Halo 2 | fps to 0, 2.1-5.2 s frames | first-time pipeline compiles on the draw thread | explained; the lever is #569's |

## HAKUX_S2T_CVT

#59 expands X1R5G5B5, A1R5G5B5 and R5G6B5 textures to RGBA8 on the CPU, so
`check_surface_to_texture_compatiblity()` refuses a 16-bit colour surface sampled as one of those textures, and
`create_texture()` downloads the surface: a finish and a fence wait per texture, which serialize the PFIFO thread
and the GPU. With `HAKUX_S2T_CVT=1` the check accepts them and `pgraph_vk_s2t_cvt_copy()` records, inline in the
frame's command buffer, a copy of the surface's 16-bit words to a scratch buffer, a compute pass that writes one
RGBA8 texel per word with #59's replication and alpha rule, and a copy of the texels into the texture. The decode
matches the CPU rule on all 65536 words of each format on the host.

Cost: off, one `getenv` at first use. On, per refused texture, one 2-byte buffer copy, one compute dispatch over
the texels and one 4-byte buffer copy, all on the GPU, plus a scratch buffer of at least 4 MB held until shutdown.
In MKSM's gameplay the GPU's time outside render passes is 4.2 ms a frame with it against 0.3 ms without. The
downloads it replaces may run outside that timer, so the decode's own cost is 0-4 ms a frame; `HAKUX_GPUXFR=1`
measures it per site.

## The A/B

One build, two arms differing only by env (`a_ref` = `b_ref` = f5a67ba52c):

- Pixel leg (`fps1015-pixels.json`): 33 texture and surface suites; every capture the same or inside the band,
  worse = 0, and `[s2tcvt] first` in the switch-on arm's logcat.
- Soak leg, #986 (`fps1015-mksm.json`, route `docs/lanes/fps1015/routes/fps1015-mksm.route`, judge
  `docs/lanes/fps1015/s2tread.py`): in the Goro's Lair cutscene, downloads gone (sd 0.1 a frame or less), median G
  down 6-22 ms (point -10: 43 to ~33 ms), median fps up 5 or more (point +8: 22 to ~30); gameplay fps no more
  than 3 below off.
- Soak leg, #992 (`fps1015-topspin.json`, route `docs/lanes/fps1015/routes/fps1015-topspin.route` on Top Spin's
  first golden, judge `docs/lanes/fps1015/tsread.py`): in match play, downloads gone (sd 1 a frame or less),
  median G down 4-13 ms (point -8: 27.5 to ~19.5 ms), median fps up 6 or more (point +14: 36 to ~50); in the
  stadium fly-over, median G down 10 ms or more (point -20: 46 to ~26).

### Results

**Soak, pilot pair (on1 1792163888-fps1015-716638, off1 1792163893-fps1015-717142): PASS on every leg.**

| leg | registered | measured |
|---|---|---|
| R | on sd <= 0.1 a frame, cvt 0; off sd >= 2.5 | on 0.00, cvt 0; off 3.00 |
| P | median G on - off in [-22, -6] ms | -7.7 (16.7 against 24.4) |
| F | median gfps on - off >= +5 | +20.0 (59 against 39) |
| N | gameplay gfps on >= off - 3 | 59 against 51 |

The cutscene is frame-locked, so a fast run leaves it before the span's last shot and the span takes in gameplay.
Over the same 1800 guest frames from its first shot (reported, not judged):

| run | wall s | fps | median G ms | Fin ms | GPU ms |
|---|---|---|---|---|---|
| on1 | 33.1 | 54.4 | 16.7 | 2.7 | 14.4 |
| on2 | 33.2 | 54.2 | 16.9 | 2.8 | 14.2 |
| off1 | 62.1 | 29.0 | 34.3 | 20.5 | 15.2 |
| off2 | 65.5 | 27.5 | 34.3 | 20.0 | 15.3 |

The PFIFO thread's finish wait goes and the GPU's work does not grow.

**Soak, all four (on2 1792168743-fps1015-1960988, off2 1792168748-fps1015-1962522 added): PASS on every leg,
over on1, off1 and off2.** R: on sd 0.00 a frame, cvt 0; off 3.00. P: -13.6 ms (16.7 against 30.3). F: +28 (59
against 31). N: 59 against 51. on2 is void by the V rule as registered: its logcat has `[s2tcvt] on` and no
`[s2tcvt] first`. The decode logs that line on its first call, unconditionally, and on2's counters show the decode
in 72 of its 80 cutscene windows (s2tc 540 a window, cvt 0, sd 0.00), so the line was lost from the log. Its
numbers are in the table above as reported, not judged.

**Pixel leg (A 1792163881-fps1015-716411, B 1792163875-fps1015-716177): FAIL as registered (10 worse, predicted
0).** 816 of 881 captures are byte-identical, Blend_surface included, where the switch's decode ran. The 65 that
move are 64 in Texture_shadow_comparator and the unstable Texture_border/2D_BorderTex_SZ. Texture_shadow_comparator
samples depth formats only, which the switch does not decode. It is wrong in both arms: all 288 captures differ
from every saved run between 09-12 and 10-10 (e654516849), and with the switch off this branch runs no new code.
The marker triangles keep a colour set for an earlier marker. This is a regression on master between e654516849
and 0e5fab6bef, in vk/draw.c's super-fast pre-draw path by reading (an inline attribute value that reaches no
uniform push, the hole #274 closed in create_pipeline only). Details and the candidate commits are in NOTES.md,
"The A/B, results". The switch stays off by default; this suite cannot clear it until the regression is fixed.

**Soak, #992 Top Spin (on1 1792170178-fps1015-2310292, off1 1792170186-fps1015-2314810): R, P and F pass; I is
refuted as registered.**

| leg | registered | measured | |
|---|---|---|---|
| R | on sd <= 1 a frame, cvt 0; off sd >= 15 | on 0.00, cvt 0; off 24.15 (30.0 a guest frame) | PASS |
| P | match-play median G on - off in [-13, -4] ms | -9.4 (16.7 against 26.1) | PASS |
| F | match-play median gfps on - off >= +6 | +21.0 (59 against 38) | PASS |
| I | stadium fly-over median G on - off <= -10 ms | -9.4 | FAIL |

On this golden the route reaches match play at the fifteenth step in both arms, before the fly-over span begins.
The span therefore read match play, where the switch-on arm is already at the vblank. Neither run's match play is
a clean route window, because the arms were also played by hand. The arms agree through the menus and split at
the same step: 30 downloads and a 12.7 ms finish wait a frame without the switch, none with it.

Replay playback with the switch runs at 14-18 fps. Its frames carry 2.9-3.4 times live play's texture binds and
2.4-3.2 times its render passes. The PFIFO thread is busy for about 46 ms of a 52-59 ms frame. The GPU takes
22.5 ms and the finish wait 0.5 ms.

The judge counts a stall block as 60 guest frames. A block is 60 present plus flip finishes, which is `flip` guest
frames; the judge's docstring now says so. No leg moves.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
