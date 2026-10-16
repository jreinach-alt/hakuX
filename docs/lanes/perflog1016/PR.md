# perflog1016: a pause-menu switch for the perflog telemetry tier, and a "Mark this moment" button (#433)

State: draft

Lane: perflog1016            Issue: #433 (motivating defect #998)
Base: master @ 15a72e10dc (origin/master 4bf47129b1 merged in, 10-16)
Files: accel/tcg/cputlb.c, accel/tcg/translate-all.c, android/app/src/main/java/com/rfandango/haku_x/PauseMenuOverlay.kt, hw/xbox/nv2a/debug.h, docs/testing/predictions/perflog1016-defaultpath.json, docs/lanes/perflog1016/PR.md, docs/lanes/perflog1016/NOTES.md, docs/lanes/perflog1016/OUTBOX.md, docs/lanes/perflog1016/WAITING, docs/lanes/perflog1016/abread.py, docs/lanes/perflog1016/lend_check.py, docs/lanes/perflog1016/ndk_check.py, docs/lanes/perflog1016/rt_selftest.c, docs/lanes/perflog1016/scan_soaks.py, docs/lanes/perflog1016/selftest.py, docs/lanes/perflog1016/site_context.py, docs/lanes/perflog1016/write_prediction.py, docs/lanes/perflog1016/pfifo.c.patch, docs/lanes/perflog1016/profile.c.patch, docs/lanes/perflog1016/renderer.c.patch, docs/lanes/perflog1016/surface.c.patch
Prediction: docs/testing/predictions/perflog1016-defaultpath.json (hand-read soak pair, default path with the switch OFF; judged by abread.py --judge)
Needs device: yes    Needs NDK: yes

Release note (none): an opt-in debug switch, off at every launch; the pause menu's debug section gains Perflog, Mark this moment and Frame dump buttons.

The owner asked for the perflog telemetry from the pause menu, mid-run, so a defect like #998's flicker can be captured without a rebuild and replay.

**What it is.** The switch is a marker file, `perflog.on`, in the app's external files dir (where `frame_dump.on` lives).
- The emulator polls it at the flip, at most once a second.
- One line on every flip: `hakuX-perf: [perflog] runtime tier ON (frame N, by marker)`.
- The pause menu's debug section toggles it. The label reads `Perflog: OFF` / `Perflog: ON`, or `ON (perflog build)` / `ON (XEMU_PERFLOG_RT)` when it is pinned.
- `XEMU_PERFLOG_RT=1` pins it on for a queued soak.
- The marker is deleted at every launch.
- No JNI is needed, so `MainActivity.kt` and `strings.xml` are untouched.

**How the hooks are switched.**
- debug.h's phase-timer macros and counters run under the switch in a plain build. That covers ~155 call sites, among them draw.c's ~101, with no edit at the call site.
- Off, a phase costs one relaxed load and a not-taken branch, with no clock read.
- The TCG `[tcg787]` hooks follow the same switch.
- **Mark this moment** writes `hakuX-route: mark owner-N`, the route driver's shape.

**Not switchable.** Per-draw, per-bind and per-upload attribution, GPU timestamps, the method histogram and `[tpc787]` still need `-Pperflog=true`. NOTES.md has the full inventory, classes A/B/C, and the per-defect-class statement of what the switch does and does not give. It names no cause for #998.

| | state |
|---|---|
| inventory (NOTES.md) | done |
| switch in debug.h + TCG + pause menu | done; host selftest 16+4+2 passes, 11/11 mutants caught; NDK compile check |
| `profile.c` + `vk/renderer.c` (the implementation and the poll) | **pending a lend from lane.fps1015**: `profile.c.patch`, `renderer.c.patch`, NEED: in OUTBOX.md. Without them the switch cannot turn on |
| `pfifo.c` + `vk/surface.c` coverage | pending the same lend: `pfifo.c.patch`, `surface.c.patch` |
| default-path A/B (Nova, GTA VC, A B B A, switch OFF) | queued; ids in NOTES.md |
| ON-path proof (perflog lines in logcat) | pending the lend |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
