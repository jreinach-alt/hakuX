# bootstatic1017: the brief static or green flash at every title start (#1045)

State: draft

Lane: bootstatic1017            Issue: #1045
Base: master @ 9abd80e90c
Files: docs/lanes/bootstatic1017/PR.md, docs/lanes/bootstatic1017/NOTES.md, docs/lanes/bootstatic1017/step0_search.out, docs/lanes/bootstatic1017/forge_search.out, docs/lanes/bootstatic1017/tools/step0_search.sh, docs/lanes/bootstatic1017/tools/tracker_search.py, docs/lanes/bootstatic1017/tools/forge_search.py, docs/lanes/bootstatic1017/tools/setup_desk.py, docs/lanes/bootstatic1017/tools/judge_boot.py, docs/lanes/bootstatic1017/tools/judge_boot_selftest.py, docs/lanes/bootstatic1017/tools/deskboot.py, ui/xemu.c
Prediction: none: analysis-only (so far; registered if a remedy moves pixels)
Needs device: yes    Needs NDK: no

Deep dive into the brief static or green flash the owner sees at the start of every title, before the Xbox logo.
`NOTES.md` has the Step 0 Already-tried table and the hypotheses.

The lead so far: until the kernel's first GPU frame is bound at the scan-out address, the UI shows QEMU's VGA view of
raw guest RAM (`ui/xemu.c:2302`). The existing frame dumper cannot see those frames, because it runs only on a guest
flip, so a probe at the present comes first.

The owner says it is whole-screen static, on every title checked (Halo CE, NFS: Most Wanted, THPS4, Max Payne 2,
GTA III, Top Spin).

`ui/xemu.c` carries the `[boot1045]` present probe, armed by `HAKUX_BOOTPROBE` and off by default. Its judge is
`tools/judge_boot.py`, with a synthetic self-test in `tools/judge_boot_selftest.py`.

Release note (none): an opt-in launch probe, off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
