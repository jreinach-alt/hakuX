# bootstatic1017: black while the guest has the screen off, no static or green at title start (#1045)

State: ready

Lane: bootstatic1017            Issue: #1045
Base: master @ 9abd80e90c
Files: docs/lanes/bootstatic1017/NOTES.md, docs/lanes/bootstatic1017/PR.md, docs/lanes/bootstatic1017/d1_flash.png, docs/lanes/bootstatic1017/d2_ram.png, docs/lanes/bootstatic1017/forge_search.out, docs/lanes/bootstatic1017/nova_green.png, docs/lanes/bootstatic1017/nova_ids.tsv, docs/lanes/bootstatic1017/pre_1609.png, docs/lanes/bootstatic1017/pre_7441.png, docs/lanes/bootstatic1017/step0_search.out, docs/lanes/bootstatic1017/tools/desk_ab.py, docs/lanes/bootstatic1017/tools/desk_judge.py, docs/lanes/bootstatic1017/tools/deskboot.py, docs/lanes/bootstatic1017/tools/forge_search.py, docs/lanes/bootstatic1017/tools/judge_boot.py, docs/lanes/bootstatic1017/tools/judge_boot_selftest.py, docs/lanes/bootstatic1017/tools/judge_nova.py, docs/lanes/bootstatic1017/tools/judge_video.py, docs/lanes/bootstatic1017/tools/judge_video_selftest.py, docs/lanes/bootstatic1017/tools/logpeek.py, docs/lanes/bootstatic1017/tools/nova_table.py, docs/lanes/bootstatic1017/tools/novatitles.py, docs/lanes/bootstatic1017/tools/nspans.py, docs/lanes/bootstatic1017/tools/preframes.py, docs/lanes/bootstatic1017/tools/queue_nova.sh, docs/lanes/bootstatic1017/tools/ramsheet.py, docs/lanes/bootstatic1017/tools/rowlit.py, docs/lanes/bootstatic1017/tools/setup_desk.py, docs/lanes/bootstatic1017/tools/sheet.py, docs/lanes/bootstatic1017/tools/stale_logo.py, docs/lanes/bootstatic1017/tools/step0_search.sh, docs/lanes/bootstatic1017/tools/strip.py, docs/lanes/bootstatic1017/tools/tracker_search.py, docs/lanes/bootstatic1017/tools/tspan.py, docs/lanes/bootstatic1017/tools/video_table.py, docs/lanes/bootstatic1017/tools/vidruns.py, docs/lanes/bootstatic1017/tools/wait_nova.sh, docs/lanes/bootstatic1017/tools/withdraw_mine.py, docs/lanes/bootstatic1017/video_table.out, hw/xbox/nv2a/pgraph/vk/renderer.c, ui/xemu.c
Prediction: none: no arm. The change is in the present path only (`sdl2_gl_refresh` and the display image `pgraph_vk_get_framebuffer_surface` hands it), which no pgraph golden passes through (the suites' captures are written by the guest to E:); measured instead by the launch probe and screen video, before and after, desktop and Nova
Needs device: yes    Needs NDK: no
Selftest: none -- no selftest.d fragment reads ui/xemu.c, hw/xbox/nv2a/pgraph/vk/renderer.c or docs/lanes/bootstatic1017/ (searched for xemu.c, renderer.c, get_framebuffer_surface, sdl2_gl_refresh, boot1045, BOOTPROBE: no hits). The fragments that name docs/lanes/ (86-nightly-notes, 87-ops-tick) read PR.md files in fixture lanes they build themselves, and this PR's Release note line is the standard one-line form. The emulator change is covered by its desktop and Android builds and by the before/after launch-probe runs; the lane's judges have their own self-tests (tools/judge_boot_selftest.py, tools/judge_video_selftest.py).

Release note (rendering): the brief whole-screen static before the Xbox logo, and the green streaks between the logo and the game, no longer show when a title starts; the screen stays black there, as on a real Xbox.

## What it was

Both looks have one cause: **QEMU's VGA view of guest RAM was shown while the guest had the VGA screen off (SR01
bit 5)**. On a real Xbox that window is black.
- **Static**: the kernel sets 640x480x32 with the scan-out at address 0 and the screen off. The view is its low
  memory: 0.2 s on the Nova, every title. On the desktop it matched guest RAM at address 0 with r = 0.976.
- **Green streaks**: while the title loads, the kernel has the screen off and the scan-out at the title's future
  framebuffer, which holds leftover green logo data. That is 3.3 s for Halo CE on the Nova video. The RAM dump at that
  address, drawn as BGRX, is the frame (`nova_green.png`).
- Android's `android_blit_frame` never read SR01. The desktop did (upstream `129c48dd6e`), but it drew a VGA image
  one refresh old, so one present of either look leaked at the screen-on edge.

## The change

- **R1 (`ui/xemu.c`, Android)**: draw black while `nv2a_get_screen_off()` holds, or held when this refresh read the
  VGA view.
- **R2 (`ui/xemu.c`, both)**: read the VGA view before the upload, not after the present; still one update per
  refresh.
- **R5 (`renderer.c`, one hunk)**: the first present after a screen-off interval waits for a render of the current
  scan-out. With external memory (the Nova), `pgraph_vk_get_framebuffer_surface` returns the image of the previous
  sync and kicks the next without waiting, which is one refresh of latency in play. Across a screen-off interval
  that previous image is the kernel's logo, so once R1 made the interval black, the logo blinked for one present
  at the title's first picture. R5 takes the existing waiting path once per screen-on edge (once or twice per launch);
  play never turns the screen off, so it adds no wait there, and the guest is never blocked by it.

Nothing changes while the guest has the screen on.

## Measured: every present from launch to the title's first picture

`tools/judge_nova.py` (M1: screen-off presents whose window is not black, by hash; M2/M3: noise, static or streaks
with the screen on), `tools/stale_logo.py` (M4: the kernel's logo shown at the title's first scan-out),
`tools/desk_judge.py`. Every judge was committed before its data. Before = `7ea8b80e71` (probe only); after =
`446e9abbed` (R1+R2) and `2a012b14fc` (R5). Nova runs are Turnip in all twelve (0 stock-driver lines).

| platform | title (engine) | before | after R1+R2 | after R5 |
|---|---|---|---|---|
| desktop | THPS4 (Neversoft) | FLASH (static, 1 present) | CLEAN | (R5 not on the desktop's path: no external memory) |
| desktop | Halo CE (Blam) | FLASH (green, 1 present) | CLEAN | as left |
| desktop | Burnout 3 (RenderWare) | FLASH (static, 1 present) | CLEAN | as left |
| Nova, Turnip | Halo CE (Blam) | FLASH: M1 249 (and 225 in a first run), M4 1 | CLEAN: M1 0, M4 1 | CLEAN: M1 0, M4 0 (vacuous: the logo never reached the screen) |
| Nova, Turnip | Top Spin (PAM) | FLASH: M1 193, M4 1 | CLEAN: M1 0, M4 1 | CLEAN: M1 0, **M4 0** (twice) |
| Nova, Turnip | GTA III (RenderWare) | FLASH: M1 95, M4 1 | CLEAN: M1 0, M4 1 | CLEAN: M1 0, **M4 0** (twice) |

**The screen video** (`tools/judge_video.py`, `video_table.out`), where it starts at least 2 s before the first
present:
- Halo CE before: static, then the logo, then 3.3 s of green streaks, then static, then Halo.
- Halo CE after (R5): black from the hakuX splash's fade to Halo's first picture (7.1 s).
- Top Spin after (R5): black, the kernel's own logo for 1 frame, black, then Top Spin.

GTA III's R5 video starts 1.95 s before the first present (bar 2.0 s, so VOID; the bar was not moved). It shows the
launcher, black, the kernel's logo for 0.47 s, black, then GTA III. The only "green" any video classes before a launch
is the launcher's Android robot (`pre_7441.png`, `pre_1609.png`).

`NOTES.md` has the Already-tried table, the hypotheses with their final P, the instruments' blind spots, the remedies
ranked by P x win, and what the next lane should not repeat.

`ui/xemu.c` also carries the `[boot1045]` present probe (`HAKUX_BOOTPROBE`, off by default; one `getenv` when unset).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
