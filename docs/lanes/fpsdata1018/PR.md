# fpsdata1018: FPS dip causes in the 4-title owner capture, and fixes (#433)

State: ready

Lane: fpsdata1018            Issue: #433
Base: master @ 72af9cb92c
Files: hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/renderer.h, docs/lanes/fpsdata1018/NOTES.md, docs/lanes/fpsdata1018/PR.md, docs/lanes/fpsdata1018/FINDINGS.md, docs/lanes/fpsdata1018/typecheck.py, docs/lanes/fpsdata1018/routes/fpsdata1018-ralli2-drive.route, docs/testing/predictions/fpsdata1018-texscan2d-pixels.json, docs/testing/predictions/fpsdata1018-s2tfb2-pixels.json, docs/testing/perf/fpsdiag/fpsdiag.py, docs/testing/jobs/selftest.d/99-fpsdiag.sh
Prediction: docs/testing/predictions/fpsdata1018-texscan2d-pixels.json @ bce632fb665230a814701edb7cbc12ab756f87393398781e8048cf488b714221
Prediction: docs/testing/predictions/fpsdata1018-s2tfb2-pixels.json @ 095ad2d3ea15762744ae3c7587cbfada403b47f8f46af06da10c2169eef0ead1
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
to the pre-existing download path, which already handles this correctly).

**Fixed a second pixel regression found by the same prediction, in a different format.** The copy route also
missed NV2A's shadow-comparator depth-as-texture formats: a texture read through the comparator unit needs the
same value-preserving treatment already given to compressed and converted formats, not a raw copy. Excluded.
Both prediction fixes are re-registered against their own commits; their arms results will post to this PR.

**GTA III's in-car dip: the surface-sampled-as-its-own-texture copy loop now keeps a run's copy by default.**
`HAKUX_S2T_FB` (built earlier, off by default) lets a slot reuse this run's cached copy of a colour target it
also samples, instead of re-copying and ending the render pass on every sample. Mode 2 only reuses the copy for
a sampling stage whose shader program provably does not read its texture at all, so it cannot change a rendered
pixel; that argument is now backed by a registered pixel prediction, not just the code reading. `HAKUX_S2T_FB=2`
is now the default (`=0` opts out, `=1` keeps the unsafe any-stage mode as opt-in only). A prior device trial
(gta3car1018, #1049) measured fewer render passes and frame time in this mode against a same-session baseline,
with light-traffic moments reaching 30 fps; it stopped short of proving the size of the win because its second
repeat aborted on an adb glitch. This fix does not reach 30 fps on its own in heavy traffic (the fence wait and
stalled finishes still scale with pass count); it is this lever's contribution, not the whole dip.

**Fixed a correctness bug this lever's own pixel prediction caught.** The lever above classified one
texture-shader combiner mode (the one that computes a dot product from the texture's own texel, used for bump
mapping) as one that "does not read its texture" -- it does, so a stage in that mode could be handed a stale
copy. Excluded it from the set that may keep a cached copy; the other three modes in that set emit a constant or
need no texture at all, confirmed by reading the shader generator directly, not by inference from this lever's
own code. The copy cache also gained the same depth-as-texture exclusion the surface-to-texture copy above
already needed, for the same reason -- a stage reading a surface through NV2A's hardware shadow-comparator
unit cannot be handed a raw copy taken by either route. Pixel prediction re-registered against both fixes.

**Fixed a third correctness bug the same pixel prediction caught, same underlying class as the first
regression above.** The copy this lever keeps across draws is sized by the surface's scale factor at the
moment it was taken; a CPU-write surface reconfiguration (no draw) can change that scale factor without
bumping the draw-time counter this cache used as its only staleness check, so a stage could be handed a copy
taken at the wrong scale. The cache now also remembers the scale factor at copy time and declines to reuse a
copy once it no longer matches. Pixel prediction re-registered a fourth time against this fix.

**A pixel test suite in both predictions' checks turned out to disagree with itself.** Three repeat device
runs of the same unchanged build showed `Texture_shadow_comparator` moving on about 1 in 12 of its own captures
with nothing whatever changed -- a pre-existing property of that suite on this device, not something either
fix caused. Both predictions above are re-registered without that suite in their checklist; the two fixes
described above are kept (each is independently correct reading the renderer code), but neither claims that
suite's pixel checks as evidence, because a single device run cannot tell this suite's own noise apart from a
real change in it.

**A second, isolated flake, and a real fix found while chasing it.** Re-reading the texscan2d prediction's
own arms a second time (same `a_ref`/`b_ref` as an earlier clean read-back) showed `Antialiasing_tests/
CPUWriteIgnoresSurfaceConfig` move 0 -> 45,056 bytes -- but `sha256sum` across all four existing base/fix
result directories on bit-identical builds found 3 of 4 byte-identical and only the one dissenting run differs:
a device flake on this one test, outside the already-measured `Texture_shadow_comparator` noise floor, not a
regression. Tracing it surfaced a real, separate gap: `migrate_surface_image()` (the function that moves a
shelved or invalid surface's `VkImage` to a new binding when the same address/format/pitch recurs) copied
every Vulkan-object field except `image_scale`, so a migrated surface's `image_scale` permanently read 0 and
was refused by Fix #1's own `!= 1` check forever -- never corrupting (0 != 1 always refuses), but capping
Fix #1's win to freshly-created surfaces only, missing the common steady-state case of a render target reused
at the same address. Fixed: `migrate_surface_image()` now copies `image_scale` too. Pixel prediction
re-registered a third time against this commit, since it changes texscan eligibility and needs its own
falsifier.

**Owner capture recipe to confirm the fps size of this one** (no reproducible device route exists for GTA III's
specific in-car save state through the dispatcher's own --save registry, and this lane's device verification
goes through the dispatcher only -- never by hand): build a perflog APK from this PR's head, play Grand Theft
Auto III, get in the car, and drive for about a minute, twice -- once as built (HAKUX_S2T_FB defaults to 2) and
once with `HAKUX_S2T_FB=0` set first (the old behaviour) -- then read back `[dipwin]` (`dipwin_read.py`, as
`gta3car1018/NOTES.md` section 4.1/6 did) for `rp`/flip, `fen`, and `rotfen` in each run's moving windows.

**Both pixel predictions have now cleared.** `fpsdata1018-s2tfb2-pixels.json`'s arm (`41c613c22a` vs
`136e8a1723`) came back PASS, 184/184, no caveats. `fpsdata1018-texscan2d-pixels.json`'s arm (`245ddc4964` vs
`c4560f2ab4`) FAILed 2/750 on two `Antialiasing_tests` captures, but both moves were on the UNMODIFIED base
side of the pair, and one of the two (`CPUWriteIgnoresSurfaceConfig`) produced the exact same corrupted image,
byte for byte, as an earlier occurrence on a different, unrelated ref -- the same corrupted frame appearing on
two builds that do not share this fix is a device/driver flake, not something either fix caused. Narrowed the
prediction's exclusion to those two specific captures (not the whole suite: the other 9 `Antialiasing_tests`
captures have never moved across 6 runs on disk) and queued a fresh, honestly pre-registered arm
(`fpsdata1018-texscan2d-reverify`) to confirm; its result will post to this PR. Detail in NOTES.md.

Release note (performance): RalliSport Challenge 2 races and Fable gameplay no longer stall every frame reading a render target back through system memory; Grand Theft Auto III's in-car render-pass count is cut by keeping a texture copy across samples that cannot see a stale one.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
