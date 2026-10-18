# bootstatic1017: black while the guest has the screen off, no static or green at title start (#1045)

State: draft

Lane: bootstatic1017            Issue: #1045
Base: master @ 9abd80e90c
Files: docs/lanes/bootstatic1017/NOTES.md, docs/lanes/bootstatic1017/PR.md, docs/lanes/bootstatic1017/d1_flash.png, docs/lanes/bootstatic1017/d2_ram.png, docs/lanes/bootstatic1017/forge_search.out, docs/lanes/bootstatic1017/nova_green.png, docs/lanes/bootstatic1017/nova_ids.tsv, docs/lanes/bootstatic1017/pre_7441.png, docs/lanes/bootstatic1017/step0_search.out, docs/lanes/bootstatic1017/tools/desk_ab.py, docs/lanes/bootstatic1017/tools/desk_judge.py, docs/lanes/bootstatic1017/tools/deskboot.py, docs/lanes/bootstatic1017/tools/forge_search.py, docs/lanes/bootstatic1017/tools/judge_boot.py, docs/lanes/bootstatic1017/tools/judge_boot_selftest.py, docs/lanes/bootstatic1017/tools/judge_nova.py, docs/lanes/bootstatic1017/tools/judge_video.py, docs/lanes/bootstatic1017/tools/judge_video_selftest.py, docs/lanes/bootstatic1017/tools/logpeek.py, docs/lanes/bootstatic1017/tools/nova_table.py, docs/lanes/bootstatic1017/tools/novatitles.py, docs/lanes/bootstatic1017/tools/nspans.py, docs/lanes/bootstatic1017/tools/preframes.py, docs/lanes/bootstatic1017/tools/queue_nova.sh, docs/lanes/bootstatic1017/tools/ramsheet.py, docs/lanes/bootstatic1017/tools/rowlit.py, docs/lanes/bootstatic1017/tools/setup_desk.py, docs/lanes/bootstatic1017/tools/sheet.py, docs/lanes/bootstatic1017/tools/stale_logo.py, docs/lanes/bootstatic1017/tools/step0_search.sh, docs/lanes/bootstatic1017/tools/strip.py, docs/lanes/bootstatic1017/tools/tracker_search.py, docs/lanes/bootstatic1017/tools/tspan.py, docs/lanes/bootstatic1017/tools/video_table.py, docs/lanes/bootstatic1017/tools/vidruns.py, docs/lanes/bootstatic1017/tools/wait_nova.sh, docs/lanes/bootstatic1017/tools/withdraw_mine.py, docs/lanes/bootstatic1017/video_table.out, hw/xbox/nv2a/pgraph/vk/renderer.c, ui/xemu.c
Prediction: none: no arm. The change is in the present path only (`sdl2_gl_refresh`), which no pgraph golden passes through (the suites' captures are written by the guest to E:); measured instead by the launch probe, before and after, desktop and Nova
Needs device: yes    Needs NDK: no
Selftest: none -- no selftest.d fragment reads ui/xemu.c or docs/lanes/bootstatic1017/ (selftest.d searched for xemu.c, docs/lanes/bootstatic1017, boot1045, BOOTPROBE: no hits). The emulator change is covered by its desktop and Android builds and by the before/after launch-probe runs; the lane's judges have their own self-tests (tools/judge_boot_selftest.py, tools/judge_video_selftest.py).

Release note (rendering): the brief whole-screen static before the Xbox logo, and the green streaks between the logo and the game, no longer show when a title starts; the screen stays black there, as on a real Xbox.

## What it was

Both looks have one cause: **QEMU's VGA view of guest RAM was shown while the guest had the VGA screen off (SR01
bit 5)**. On a real Xbox that window is black.
- **Static**: the kernel sets 640x480x32 with the scan-out at address 0 and the screen off. The view is its low
  memory: 0.2 s on the Nova, every title. On the desktop it matched guest RAM at address 0 with r = 0.976.
- **Green streaks**: while the title loads, the kernel has the screen off and the scan-out at the title's future
  framebuffer, which holds leftover green logo data. That is 3.4 s for Halo CE on the Nova. The RAM dump at that
  address, drawn as BGRX, is the frame (`nova_green.png`).
- Android's `android_blit_frame` never read SR01. The desktop did (upstream `129c48dd6e`), but it drew a VGA image
  one refresh old, so one present of either look leaked at the screen-on edge.

## The change (`ui/xemu.c`)

- **R1 (Android)**: draw black while `nv2a_get_screen_off()` holds, or held when this refresh read the VGA view.
- **R2 (both)**: read the VGA view before the upload, not after the present; still one update per refresh.

Nothing changes while the guest has the screen on.

## Measured: every present from launch to the title's first picture

`tools/judge_nova.py` (M1: screen-off presents whose window is not black, by hash; M2/M3: noise, static or streaks
with the screen on) and `tools/desk_judge.py`. Before = `7ea8b80e71`, after = `446e9abbed`.

| platform | title (engine) | before | after |
|---|---|---|---|
| desktop | THPS4 (Neversoft) | FLASH (static, 1 present) | CLEAN |
| desktop | Halo CE (Blam) | FLASH (green, 1 present) | CLEAN |
| desktop | Burnout 3 (RenderWare) | FLASH (static, 1 present) | CLEAN |
| Nova, Turnip | Halo CE | FLASH: M1 225 (static 12, logo 8, green 205) | queued |
| Nova, Turnip | Top Spin (PAM) | queued | queued |
| Nova, Turnip | GTA III (RenderWare) | queued | queued |

`NOTES.md` has the Already-tried table, the hypotheses with their final P, the instruments' blind spots, and the
remedies ranked.

`ui/xemu.c` also carries the `[boot1045]` present probe (`HAKUX_BOOTPROBE`, off by default; one `getenv` when unset).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
