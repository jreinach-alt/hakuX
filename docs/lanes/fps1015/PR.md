# fps1015: measured causes for the owner's FPS defects (MKSM, Top Spin, Batman Begins, Prince of Persia, Halo 2); HAKUX_S2T_CVT

State: draft

Lane: fps1015            Issue: #433 #986 #992 #995 #993 #994
Base: master @ 0e5fab6bef
Files: docs/lanes/fps1015/PR.md, docs/lanes/fps1015/NOTES.md, docs/lanes/fps1015/winsplit.py, docs/lanes/fps1015/s2tscan.py, docs/lanes/fps1015/dlrate.py, docs/lanes/fps1015/irqrate.py, docs/lanes/fps1015/dumpstat.py, docs/lanes/fps1015/stallscan.py, docs/lanes/fps1015/cvtcensus.py, docs/lanes/fps1015/s2tread.py, docs/lanes/fps1015/routes/fps1015-mksm.route, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c, docs/testing/predictions/fps1015-pixels.json, docs/testing/predictions/fps1015-mksm.json
Prediction: docs/testing/predictions/fps1015-pixels.json @ 50e23fcbb68a87f6d82b8e8d5600d22672ffd52240ba693290e425fede4fd8f4, docs/testing/predictions/fps1015-mksm.json @ df1ac10a2d8de1ff54be6c2a1e16614310a21867b66c72222813356933be3004
Needs device: yes    Needs NDK: yes

Release note (none): HAKUX_S2T_CVT, off by default, decodes 16-bit render targets that a title samples as textures on the GPU instead of downloading them.

Per-issue split of the slow frames into vCPU, GPU and wait time from the saved owner-play telemetry, and one
default-off lever for the cause four of the five titles share. Details and every number are in
`docs/lanes/fps1015/NOTES.md`.

| issue | title | slow frames | cause | status |
|---|---|---|---|---|
| #986 | Mortal Kombat: Shaolin Monks | cutscene 14-23 fps, G 41-64 ms | 3 16-bit render-to-texture downloads a frame (`cvt`), each a finish and a fence wait; median G 43.2 ms with `Fin` 18.5 ms | cause found; A/B registered |
| #992 | Top Spin | match play 26-31 ms frames | the same downloads, 24-32 a frame (59 in the arena intro); bound 11-15 ms of the frame | cause found; A/B needs a route the profile gate admits |
| #992 | Brian Lara Cricket 2005 | ball in play | a different shape | unexplained; needs one perflog run |
| #995 | Batman Begins | fire/explosion cutscenes 14-23 fps | GPU work outgrows the 30-fps cap; one download a frame stops it overlapping the PFIFO thread | partly explained |
| #993 | Prince of Persia | fog room 19 fps | PFIFO-thread frame 33-36 ms against the 33.4 ms two-vblank budget; nine shadow-map downloads a frame inside it | reduced to a bound |
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
The GPU time is not measured yet; the soak's `GPU` column reports it.

## The A/B

One build, two arms differing only by env (`a_ref` = `b_ref` = f5a67ba52c):

- Pixel leg (`fps1015-pixels.json`): 33 texture and surface suites; every capture the same or inside the band,
  worse = 0, and `[s2tcvt] first` in the switch-on arm's logcat.
- Soak leg, #986 (`fps1015-mksm.json`, route `docs/lanes/fps1015/routes/fps1015-mksm.route`, judge
  `docs/lanes/fps1015/s2tread.py`): in the Goro's Lair cutscene, downloads gone (sd 0.1 a frame or less), median G
  down 6-22 ms (point -10: 43 to ~33 ms), median fps up 5 or more (point +8: 22 to ~30); gameplay fps no more
  than 3 below off.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
