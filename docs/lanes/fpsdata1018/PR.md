# fpsdata1018: FPS dip causes in the 4-title owner capture, and fixes (#433)

State: draft

Lane: fpsdata1018            Issue: #433
Base: master @ 72af9cb92c
Files: hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/renderer.h, docs/lanes/fpsdata1018/NOTES.md, docs/lanes/fpsdata1018/PR.md, docs/lanes/fpsdata1018/typecheck.py, docs/lanes/fpsdata1018/routes/fpsdata1018-ralli2-drive.route, docs/testing/predictions/fpsdata1018-texscan2d-pixels.json, docs/testing/perf/fpsdiag/fpsdiag.py, docs/testing/jobs/selftest.d/99-fpsdiag.sh
Prediction: docs/testing/predictions/fpsdata1018-texscan2d-pixels.json @ 2aed2cea325ead44a673f008d5155ac193891f2fa6fa1d773cb485608818437e
Needs device: yes    Needs NDK: yes

Reads the owner's 2026-10-18 capture of RalliSport 2, GTA III, Fable and Blinx 2 (master perflog 72af9cb92c) for
the wait each title's dip windows add, per phase, and lands fixes for those waits.

**Texture reads of a render target that is not the texture's shape no longer go through guest memory.** In
RalliSport 2's race, every frame binds a 640x480 linear texture over a 260x260 surface the game draws at its first
row. The surface-to-texture route needs equal extents, so the surface was downloaded with a full GPU sync (17-26 ms
a frame, the whole Fin swing) and the texture re-uploaded. Fable's gameplay does the same for two 3-level swizzled
textures whose every mip level is a surface of its own (six downloads and their syncs a frame).

The GPU-side route that already copied a cube map's drawn faces (texscan) now plans a 2D texture as well:
- a swizzled surface that is exactly one mip level is copied into that level;
- a linear surface at the texture's pitch is copied into its rectangle.

Each copy passes the surface-to-texture compatibility test for its own shape, so the texels match the round trip.
A 2D texture with no drawn surface over it is untouched. `HAKUX_TEXSCAN2D=0` restores the cube-only route.

| Title | Counter in the capture | Predicted |
|---|---|---|
| RalliSport 2 race | `fin=sdown` 60/window, 17-26 ms/frame, 18-27 fps | `sdown` 0, Fin < 2 ms, 35-50 fps |
| Fable gameplay | 420 downloads/window, `tobuf` 27.5 ms/frame, 11-24 fps | `tobuf` 0; +3 to +8 fps (a zeta-upload sync may take part of the wait) |
| GTA III, Blinx 2 | no texture download in gameplay | unchanged |

`fpsdiag.py` gains two candidates: `c2b_fin_sub_renderthread_wait` (the Fin swing is the finish's own submit wait,
not the frame-slot fence) and `c9_surf_download_wait` (the Surf swing).

**Fixed a texture-corruption regression in the above.** The arms job's pixel prediction on the first cut FAILed:
a render target created while the antialiasing/supersampling scale factor was not 1 could stay eligible for this
GPU-side copy after the scale factor changed back to 1, and the copy read a crop of its oversized backing image
instead of a resolved one. `SurfaceBinding` now remembers the scale factor its image was actually created under,
and the copy route declines a render target whose image does not match the current, unscaled grid (falling back
to the pre-existing download path, which already handles this correctly). Pixel prediction re-registered against
this fix; its arms result will post to this PR.

Release note (performance): RalliSport Challenge 2 races and Fable gameplay no longer stall every frame reading a render target back through system memory.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
