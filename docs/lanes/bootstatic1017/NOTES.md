# lane.bootstatic1017: the brief static or green flash at every title start (#1045)

Issue: **#1045** on the forge ("A brief flash of static or green distortion shows every time a game starts", filed
2026-10-17 14:37 PDT by `jobs`, body "Not investigated yet"). The brief said #433 until an addendum gave the real
number. The forge search below found #1045, word for word the owner's report, so commits use #1045 from here on.

## The report and what has been confirmed

- Owner, 10-17 ~14:35 PDT: "Can we do something about the brief static or green distortion that displays every time
  a new title starts? They all have that. ... it's always been present."
- Owner via lane.xbox, 10-17 ~14:50 PDT: "Yes, the flash/static is before the Xbox logo appears. Just confirmed."
  So it shows **before the boot animation's first picture**, before any title code runs. That rules out everything a
  title does (its mode set, its PVIDEO use, its first draws) and points at app start, the first presents, and the
  BIOS/kernel's first video-mode and PCRTC setup.
- Owner via lane.xbox, 10-17 ~15:00 PDT (answering Question 1): "Whole screen static, displays on most, almost all,
  games. NSFW is one example, Top Spin is another." NSFW is NFS: Most Wanted (4541007B, render_mode sysmem in the
  per-title table); Top Spin is 4D530035 (render_mode auto). Both ran on Turnip today. So:
  - **whole screen**, which fits a view that scales one guest image to the window (H1's VGA view does), and does not
    fit a band, a tile, or an overlay window;
  - **static**; green is not mentioned this time, so the green look is unconfirmed, not dropped;
  - **most, not all, titles**: a title that skips it is a discriminator. Before the logo no title code has run, so
    whatever differs is in the launch: the app's per-title settings (render_mode differs between the two examples, so
    it is not that), whether a save state is auto-loaded instead of booting (`savestate_auto_load`, default off,
    `xemu_android.cpp:1127`), or the timing between the first refreshes and the kernel's first GPU frame. Asked below.
- Owner via lane.xbox, 10-17 ~15:05 PDT (answering Question 3): "I thought I saw a title today that did not. But I
  can't find one. Halo 1, NFS:MW, THPS4, MP2, GTA3, all have it." With Top Spin, every title checked shows it: Halo CE,
  NFS: Most Wanted, THPS4, Max Payne 2, GTA III, Top Spin, all on the 0.5.2-rc1 release app on Turnip. **No
  discriminating title: treated as universal.** So the save-state and timing discriminators above have nothing to
  explain, and H7's bump is taken back (0.05 -> 0.03).
- Still unknown: how many frames it lasts.

## Step 0: Already tried

Searched before any code, as the brief requires. Scripts and their raw output are committed next to this file:
`tools/step0_search.sh` -> `step0_search.out` (33 `--grep -i` terms over all refs, 27 pickaxe `-S` terms over
`hw/xbox ui android`), `tools/tracker_search.py` (origin/board `nv2a_issues.toml`, 400 issues; output reproduced in
the row below), `tools/forge_search.py` -> `forge_search.out` (22 terms over all forge issues, read-only GETs).

| approach | where (commit, lane, NOTES line) | verdict | what it means here |
|---|---|---|---|
| Commit-message search for garbage/static/green/flash near boot/launch/first frame | lane.xbox (brief, Step 0 item 2) | nothing relevant | Extended below; still nothing. |
| `--grep` garbage, static, green, flash, noise, uninitiali, corrupt, flicker, stale frame | `step0_search.out` | Only in-game defects: #303/#719 FMV green blocks (fmv303 `1c67ab0d91`, greensize303 `9d1155f919`, fmv303c `976c5f60ab`), haloship1017 EARLY flash (`4a645e26c4`, REPORT_EARLY draws 12 rear flares for one frame, #1039), flicker801 detector (`4db9642680`), VRAM eviction fixes (`344a87bdd1`, `1d10f6cb2a`) | No one has looked at a launch flash. The one measured green (#303) keeps luma and loses Cr in blocks inside an FMV, which is a different shape from a full flash before the logo. |
| `--grep` first frame, first present, black screen, splash, title start, launch, startup, boot | `step0_search.out` | `36dcc8dbac` (desktop presents a Vulkan frame **through GL**, `-display xemu`); `7592336667` and `390d35807f` (black screens: swapchain format; MCPX overlay at reset); the rest are routes, release docs, hangs (#672, #751, #835) | The desktop and Android both present through GL with the same fallback (below), so a desktop yes/no splits core from Android presentation as the brief expects. No first-present clear was ever written. |
| `--grep` swapchain, present, eglSwap, SDLSurface, surfaceCreated, surfaceChanged | `step0_search.out`; `ed84d90a00`, `67fe8d7b2e`, `7592336667`; `c9a66088b9` (60 Hz surface request, #526) | An Android direct-present Vulkan swapchain existed (07-28 to 08-22). `grep swapchain hw/xbox/nv2a/pgraph/vk` today: **0 hits**, it is gone. SDLSurface was touched once, for frame rate. | The present path today is display image (AHB on Android) -> GL texture -> `android_blit_frame` -> `SDL_GL_SwapWindow`. No swapchain first image to blame. |
| `--grep` boot anim, skip.*boot; `-S` skip_boot_anim, boot_anim | `d94f73c88a` (03-04), `08c0c8db3d` (04-01): toggle, **on by default** -> `short-animation=on` (`system/vl.c:3036`) | in tree, unexamined for this | Every Android launch takes the short animation. A lever for an A/B (off = full animation) on whether the flash sits before or inside the kernel's animation, but not a suspect by itself, because "always" includes builds before 03-04. |
| `--grep` pcrtc, start address, video mode; `-S` NV_PCRTC_START, pcrtc_start, NV_PRAMDAC_GENERAL_CONTROL, vga_framebuffer | `3d33d8101b`/`584dbda1d6`/`3f557e6d45` (2018 upstream), `52a922da2b`/`2dd619ab2a` (Chihiro), `2dc570561e` (2019 upstream, VGA get_bpp X1R5G5B5) | nothing in this fork | PCRTC start handling is upstream's, untouched: `pcrtc.c:65` stores the address and nothing else. Blanking is not modelled in the nv2a path (H5). |
| `--grep` pvideo, overlay, yuv; `-S` pvideo, NV_PVIDEO | `d054b366f8`, `48c1720da8`, `9fd957d950` (SIZE_IN sentinel), cloud-110 (#110 open, #117), `de1c93d244`/`4fe77d5830` (#303 probe); #10 yuv10/csc10 (texture CSC) | only in-game | All-zero YUV converts to about RGB (0, 135, 0), a dark green, so a zeroed overlay would read green. But the flash comes before the logo, and nothing in the kernel's boot path is known to enable PVIDEO. Kept as H3, low. |
| `--grep` display texture, clear.*display; `-S` vkCmdClearColorImage, glClear, display.image, display.draw_time, render_display, pgraph_vk_render_display, VK_IMAGE_LAYOUT_UNDEFINED | `77c3b0e2c0` (only ClearColorImage: fps unlock), `8428a60c16` (only glClear), `c2cd7f64e8` (double buffer), `70aef9f9d3`, `448b51a9b4` | no clear of the display image was ever added | The display image is transitioned from UNDEFINED, and its render pass does not load it (`display.c` render pass and `render_display`). The draw covers it fully with one triangle, so this matters only if a not-yet-drawn image is ever shown (H2). |
| Tracker search: titles naming boot/launch/first frame/black screen/static/green/flash/garbage/noise/splash/startup/logo/swapchain/pcrtc/video mode/pvideo/overlay/yuv/blank/flicker/corrupt | `tools/tracker_search.py` over origin/board `nv2a_issues.toml` (400 issues) | 56 hits, none a launch flash: #110 PVIDEO stubs (open), #64/#65 VBLANK, #303/#719 FMV green, #672/#751/#835 boot hangs, #982 first-level freeze, flicker issues #801/#897/#939/#983/#994/#998 | No tracker row covers this. #1045 has no row yet (lane.local files it). |
| Forge issue search, same terms plus distortion | `tools/forge_search.py` -> `forge_search.out` | **#1045** (this issue) and nothing else on a launch flash | Confirms the issue number. |
| Footage: a green-share detector over dispatcher stills | greensize303 NOTES lines 25-38 | 177 flagged frames: green only in Star Wars III and Spikeout FMVs/logos; boot stills of every other title are clean at the 0.3% threshold | Stills are seconds apart, and the brief warns that dispatcher captures often start after the launch, so they could not see a flash of a few frames before the logo. This is a blind spot, not evidence of absence (memory: what the instrument cannot see). |
| Launch-time switches: `MainActivity.kt:38` FASTPATHS_VARS (REPORT_ASYNC, TEXSCAN, DRAWREC, UNI_BULK, UNI_UBERCACHE, UNI_FOGCACHE, POSTED_PUT, LOCKFREE_WAKE), HAKUX_SURFGPU (`surface.c:533`, download batching of rebound shelved surfaces), HAKUX_GPL ubershader; 0.5.2 defaults S2T_CVT, REPORT_EARLY, FLDCW_CHAIN (`c3660fdd86`) | `MainActivity.kt:184-255` | none touches PCRTC, the display image, the UI fallback or the present | Not suspects. "Every build so far" predates all of them. No A/B on them. |
| The existing frame dumper (`XEMU_FRAME_DUMP`, `renderer.c:2437`; dir `renderer.c:2020`) | `fdump_end_frame` `renderer.c:3740`, called from the flip at `renderer.c:4101` | **cannot see the suspect frames** | It runs only on a guest flip, and writes `dump_surface_ppm` of the SurfaceBinding at `pcrtc.start + line_offset`, and only if one exists. A refresh with no binding there (H1), and the host image actually presented (H2/H4), are both outside it. An instrument at the present is needed. |

Code read for the account (no edits):
- `hw/xbox/nv2a/pgraph/vk/display.c:1940-1990`: `pgraph_vk_render_display` returns without drawing when no surface is
  bound at `pcrtc.start + line_offset`, or the surface has no colour, width or height.
- `hw/xbox/nv2a/pgraph/vk/renderer.c:4131-4190`: `pgraph_vk_get_framebuffer_surface` returns 0 in that case, and when
  no display image is `valid` yet.
- `ui/xemu.c:2302-2322`: **when the tex is 0, the UI shows QEMU's VGA view of guest RAM**: `graphic_hw_update` ->
  `nv2a_vga_gfx_update` -> `vga_update_display` (`hw/display/vga.c:1785`), then `xb_surface_gl_create_texture` of the
  console surface. The comment at `ui/xemu.c:2141-2150` calls this the fallback "when the guest code isn't using HW
  accelerated rendering". The VGA view reads guest RAM at `pcrtc.start` (`nv2a.c:224`) at the CRTC's size, with the
  depth from CR28 (`nv2a.c:183`: 0 -> bpp 0, which QEMU draws as **4-bit planar**; 2 -> 15/16; 3 -> 32), or in text
  mode if GR06 says so, or blank only if AR index bit 5 is clear (`vga.c:1797`).
- `ui/xemu.c:2340`: every refresh clears the GL window to black before the blit, so a refresh that shows black is
  the window, and a refresh that shows anything else got it from `tex`.

## Hypotheses

P is per look, re-ranked on the owner's "before the Xbox logo". Each names its Already-tried row, or the search that
found nothing.

Re-rank on "whole screen static, almost all games" (10-17 ~15:00): H1 static 0.55 -> **0.65**, since a whole-screen
image of raw RAM is what the VGA view draws; H2 static 0.20 -> 0.15 (a SurfaceBinding at the scan-out address is the
kernel's full framebuffer, so it is whole-screen too, which keeps it second); H4 0.10 -> 0.08; H6 0.10 -> 0.07; H7
0.03 -> 0.05 (a launch-path difference is now needed to explain the titles that skip it). Green P are unchanged and
unconfirmed. The table's figures below are the earlier ones.

| # | hypothesis | static P | green P | Already tried | instrument | hit | miss |
|---|---|---|---|---|---|---|---|
| H1 | **The VGA fallback shows raw guest RAM.** Between the first refreshes and the first SurfaceBinding at the kernel's PCRTC address, the tex is 0 and `ui/xemu.c:2302` shows QEMU's VGA view of whatever is in RAM at `pcrtc.start`, in whatever mode the VGA registers say (reset state, 4-bit planar, text, or the kernel's mode before its first clear). (lane.xbox's B1) | **0.55** (was 0.35) | 0.30 | new for the fallback: searched `-S vga_framebuffer`, `nv2a_get_framebuffer_surface`, `--grep display texture`, nothing. Frame-dumper row: blind to it | present probe (below): per refresh, `src=fallback|nv2a`, `pcrtc.start`, CR28 depth, GR06/AR-index mode, plus a dump of the presented image | the flash frames are `src=fallback`, and their pixels match guest RAM at `pcrtc.start` decoded at the logged mode | the flash frames are `src=nv2a`, or the fallback frames are black |
| H2 | **A display or surface image is shown before anything wrote it.** A SurfaceBinding exists at the PCRTC address, but its VkImage (pooled, UNDEFINED, on Adreno possibly UBWC-compressed) is presented before the kernel's first clear or draw, or before its upload from RAM. Uninitialised Adreno memory often reads as green or blocky garbage. (B2, the surface half) | 0.20 | 0.30 | display-texture row (no clear ever added); `-S VK_IMAGE_LAYOUT_UNDEFINED` (surface pool `99842a38bd`, `4f8d079d29`) | the probe adds, for `src=nv2a`, the binding's draw count since creation, `upload_pending`, `draw_dirty`, and pooled or not | flash frames come from a binding with no draw and no upload | every `src=nv2a` frame has at least one draw or upload behind it |
| H3 | **PVIDEO over a zeroed or unwritten YUV buffer** (zeros -> about (0,135,0)) | 0.02 | 0.10 (was "B3, YUV read as RGB") | pvideo/overlay/yuv row | the probe logs `pvideo enabled`, its buffer offset and format | flash frames have PVIDEO enabled | PVIDEO off throughout the flash |
| H4 | **The host window shows a buffer GL never drew**: the SDL/EGL window's first buffers, or the SurfaceView's previous content, before the first `SDL_GL_SwapWindow` lands. (B2, the host half, and B4's "SDL surface's previous buffer") | 0.10 | 0.15 | swapchain/eglSwap/SDLSurface row | `adb shell screenrecord` from before the tap, set against the probe's first-refresh timestamp | the flash comes before refresh #1, or with no matching probe frame | the flash frames line up with probe frames |
| H5 | **The guest blanks the screen and we ignore it.** On silicon the kernel can blank the encoder or the CRTC while it sets the mode (AV blank, VGA SR01 screen-off, PRAMDAC), which hides whatever is in RAM. Our nv2a path models no blanking (pcrtc row). This decides the remedy, not the source of the pixels: it is true together with H1 or H2. | n/a | n/a | pcrtc/start-address row: nothing | the probe logs SR01, AR index, and the AV/encoder register writes the kernel makes | the flash frames fall inside a window the guest has blanked | the guest never blanks, so silicon would show the same thing, and the remedy is ours to choose (black until the first valid frame) |
| H6 | **Mode or format change mid-boot**: for a frame the display reads the kernel's buffer at the wrong pitch, size or bpp (16 vs 32), as the display images are recreated on a size change. (B3) | 0.10 (was 0.25) | 0.10 | pcrtc/video mode row | the probe logs width, height, pitch, bpp, and display-image recreation per refresh | the flash frames sit on a logged mode change and decode cleanly at the old or new geometry | no mode change near them |
| H7 | **Other**: a previous session's state, or the short-animation path itself. (B4) | 0.03 | 0.05 | boot-anim row | A/B with skip_boot_anim off | the flash changes with the toggle | it does not |

The two looks may be one cause seen through two decodes: the VGA view of the same RAM in 4-bit planar or text mode
reads as coloured noise, and the same bytes at 32 bpp read differently. H1 can produce both looks, so it is chased
first, with H2 alongside because the same probe separates them.

## Plan (after this table is pushed)

1. **Desktop first, no device time.** Run the desktop build (`docs/testing/desktop-runs.md`), C: checked first. A probe
   at the present (`ui/xemu.c` refresh plus `display.c`/`renderer.c` state, env-gated, off by default) records every
   refresh from the first: source, mode, PCRTC, binding state, PVIDEO, blanking registers, and writes every presented
   frame to disk for the first ~10 s. Judge per region with a numeric judge (share of noise, share of green), frames
   matched by refresh number, not wall time.
2. **The Nova on Turnip**, queued through the dispatcher (lane.local holds it): `screenrecord` from before the tap,
   with the same probe on, `GPU: PurpleVK` checked in the log.
3. Remedies ranked by P x win once the account covers both looks. The candidates the code already suggests: show black
   (not the VGA view) until the first valid nv2a frame, with the VGA view kept for guests that never use the GPU;
   model the guest's blank; clear a new display binding's image.

## The instrument: a present probe in `ui/xemu.c` (off by default)

`HAKUX_BOOTPROBE=1` (or `=<absolute dir>`) arms it at the first present; unset, it costs one `getenv`. In
`sdl2_gl_refresh`, after the frame is drawn into the window's back buffer and before `SDL_GL_SwapWindow`, it records
every present for `HAKUX_BOOTPROBE_SECS` (default 20) to `boot1045_log.txt`:
- `src`: which texture was drawn: `n` the nv2a display image, `v` the VGA fallback, `c` the CPU readback;
- the scan-out registers: `pcrtc.start`, line offset, the VGA view's size and bpp, CR28, GR06, AR index, SR01, CR17,
  PRAMDAC general control, `NV_PVIDEO_BUFFER`;
- guest RAM at the scan-out address (64 KB): non-zero share, a neighbour-difference figure, and a hash;
- the window, read back with `glReadPixels` from the default framebuffer: mean colour, and over the centre half the
  mean neighbour difference `nb` (noise is high, a picture or a flat fill is low), the lit share and the green share.
Each new window image (by hash) is written as `boot1045_f<n>.ppm` (≤320 wide), up to 600; after 30 nv2a presents in
a row, only every 10th is written. While the fallback is drawn, each new image of guest RAM at the scan-out (by hash, up
to 20) is written as `boot1045_r<n>.bin`, one screen at the logged line offset.

The readback stalls the GL pipeline once per present, so frame times measured with the probe on are not frame times.
It runs only while measuring a launch.

The judge, `tools/judge_boot.py`, was committed before any data, and its rules are in its docstring:
- **coverage**: n starts at 0 with no gaps, a GPU picture is reached, and at least 120 presents follow it;
- **classes**: black, green, noise or picture. The noise bar is set from the run's own clean spread: 2x the largest
  `nb` among lit presents in the last quarter of the log, floor 20;
- **episodes**, and each hypothesis's hit and miss;
- **RAM match**: the fallback frame's luma is Pearson-correlated with the RAM dump decoded at the logged bpp. The null
  is the same decode shifted by (37, 23); a match needs r ≥ 0.3 and ≥ 3x |null|.

`tools/judge_boot_selftest.py` passes on synthetic data (H1 shape: MATCH r = 1.00, null -0.01; the mutant, a frame
unrelated to the RAM: no match; noise from `src=n`: H1 MISS, H2 HIT), FAILS=0.

The desktop build is `tools/setup_desk.py`, then `build-linux/cfg.py` (bindpose1017's recipe).

## Desktop run d1: the static reproduces, for one present

`tools/deskboot.py d1 120 90`: THPS4, the goldens HDD, lavapipe, SDL's offscreen video driver (a GL window; SDL 2.30's
offscreen driver cannot make a Vulkan window, so `ui/xemu.c` now asks for a GL window under that driver only; nothing
on the desktop ever made a Vulkan surface of it). The judge said **not covered**. C1 held (n from 0, no gaps), but C2
asks for a `src=n` picture and the desktop has none (below). The title's picture is there by eye at present 1354,
with 3,200 presents after it. The judge now carries a declared desktop rule for C2 (the first lit picture at a start
address other than the kernel's logo), committed before d2. Evidence: `d1_flash.png` (presents 0, 61, 62, 221, by
`tools/sheet.py`).

| presents | t (ms) | VGA state (probe) | window |
|---|---|---|---|
| 0-34 | 0-940 | reset: 8x1, CR28 0 (bpp 0), SR01 0x00, start 0 | black |
| 35-60 | ~960-1288 | the kernel's mode: 640x480, CR28 0x83 (32 bpp), pitch 2560, **SR01 0x21 (screen off)**, start **0** | black |
| **61** | **1516** | start **0x032a4000**, **SR01 0x01 (screen on)**; guest RAM there is all zero | **whole-screen coloured static**, nb 46.4, lit 0.52, green share 0.11 |
| 62-220 | 1529-5391 | same; RAM there still zero | black |
| 221-223 | 5870-6058 | same | the Xbox logo |
| 224-1353 | 6150-26911 | SR01 0x21 again (screen off while the title loads) | black |
| 1354- | 26971- | start 0x018e8000, screen on | the title |

Every present on the desktop is `src=v`: the desktop's Vulkan has no `VK_KHR_external_semaphore_fd` on lavapipe, so
it presents by download (`instance.c:559-571`), `pgraph_vk_get_framebuffer_surface` returns 0, and the window always
shows the VGA view of guest RAM. So on the desktop, `src` cannot separate H1 from H2. On Android, external memory is
always on (`instance.c:555-558`), so the Nova's probe can.

What the static is. During presents 35-60 the VGA view is set to 640x480 at 32 bpp with start 0: it reads
`0x0-0x12c000` of guest RAM, which is the kernel's low memory (the first 64 KB went from 8% to 48% non-zero over those
presents, with a neighbour difference of 44 by the end, the same figure as the static's 46). RAM at the new start
is all zero at present 61 and shows black one present later, so the static is not RAM at the new start. The leading
reading is the VGA view of RAM at address 0, drawn one refresh earlier (below). `tools/rowlit.py` puts the static's
dark bands at guest rows 194-267 (`0x79400-0xa7800` at pitch 2560, if the image fills the window) and a few thin
ones. That is a layout of mostly empty memory, but it is not yet matched to RAM: d1's RAM dumps were all spent on the
reset state. d2 dumps RAM at start 0 in the kernel's mode, and the judge's correlation decides.

Why it shows for exactly one present on the desktop:
- **The desktop blanks while the guest says screen off.** Upstream added this in `129c48dd6e` (2023, "ui: Blank
  screen when VGA SCREEN_OFF is set"). `RenderFramebuffer` (`ui/xui/gl-helpers.cc:923`) skips the draw while SR01
  bit 5 is set. That is why 35-60 and 224-1353 are black although guest RAM is not.
- **The desktop's VGA image is one refresh old.** On the desktop, `graphic_hw_update` runs at the end of a refresh
  (`ui/xemu.c:2714`), after the present. So the texture drawn at present 61 was rendered at the end of present 60,
  from start 0. The kernel turned the screen on and moved the start between those two points. One present of the old
  image gets through before the next update redraws from the new start.

**The Android present has no screen-off check.** `android_blit_frame` (`ui/xemu.c:342`) draws whatever `tex` is, and
nothing on Android reads SR01. `nv2a_get_screen_off` has one caller in the tree, the desktop's `RenderFramebuffer`.
On Android, `graphic_hw_update` runs before the draw (`ui/xemu.c:2615`). So every Android refresh during the kernel's
screen-off window (presents 35-60 here, about 330 ms on this host) should show the VGA view of kernel memory: whole
screen, static, before the logo. That is the owner's report, at about 20 frames rather than one. The window after
the logo (224-1353 here) would show whatever the scan-out holds while the title loads, on hardware black. That is
the next thing to see on the Nova.

So H1 (the pixels) and H5 (the blank we ignore) are one account, with the screen-off check missing on Android.
Re-rank, static: H1+H5 together 0.80 (desktop reproduction plus a code reading that names the missing check on
Android); H2 0.08; H4 0.05; H6 0.05 (the static sits on a start-address change, but it decodes as the old start at
the same geometry, not as a wrong pitch or bpp); H7 0.02. The green look is still unseen. The static frame's green
share is 0.11, not a green flash. Green P unchanged until the Nova shows it.

### Instrument changes after d1, committed before d2

- Probe: RAM dumps only in a real mode (bpp > 0, at least 320x200), each new image at least 4 presents apart (up to
  24). On every change of start or SR01 (an edge) it also dumps the present before it, which the desktop draws one
  refresh late (up to 16). For VGA fallback presents, `tnb/tlit/tgrn` are the window's numbers taken over the console
  surface the texture was made from, before any screen-off blank. That is what a present path with no screen-off
  check draws, so the desktop can measure what the Nova should show.
- Judge: the desktop C2 rule above. RAM match pairs each dump with the window at the same present ("same", Android's
  order) and at the next one ("next", the desktop's). The "unblanked view" reports episodes of noise or green in the
  texture numbers, with their screen-off count. Each window episode says whether the present before it was blanked.
- Self-test: cases D (the d1 shape, with a "next" RAM match) and E (its mutant: the leak frame unrelated to the RAM,
  so no match). FAILS=0.

## Waiting / blocked

Nothing outstanding. Next: d2 on the desktop, judged. Then queue the Nova.

## Questions (for lane.xbox / the owner; work continues meanwhile)

1. Does the static or green cover the whole screen, or a band or a box? **Answered** 10-17 ~15:00: whole screen,
   static, almost all games (NFS: Most Wanted, Top Spin).
2. Is it static on some launches and green on others, or both in one launch? (Green was not mentioned in the answer.)
3. Which titles do not show it? One name is enough: it is the discriminator. **Answered** 10-17 ~15:05: none found
   (Halo CE, NFS:MW, THPS4, MP2, GTA III all have it).
