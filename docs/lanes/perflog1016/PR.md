# perflog1016: a pause-menu switch for the perflog telemetry tier, and a "Mark this moment" button (#433)

State: ready

Lane: perflog1016            Issue: #433 (motivating defect #998)
Base: master @ 7e00c7cf73 (merged in 10-18; branched from 15a72e10dc)
Files: accel/tcg/cputlb.c, accel/tcg/translate-all.c, android/app/src/main/java/com/rfandango/haku_x/PauseMenuOverlay.kt, hw/xbox/nv2a/debug.h, hw/xbox/nv2a/pfifo.c, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/vk/renderer.c, docs/testing/predictions/perflog1016-defaultpath.json, docs/testing/predictions/perflog1016-postlend.json, docs/lanes/perflog1016/PR.md, docs/lanes/perflog1016/NOTES.md, docs/lanes/perflog1016/OUTBOX.md, docs/lanes/perflog1016/WAITING, docs/lanes/perflog1016/abread.py, docs/lanes/perflog1016/lend_check.py, docs/lanes/perflog1016/ndk_check.py, docs/lanes/perflog1016/rt_selftest.c, docs/lanes/perflog1016/scan_soaks.py, docs/lanes/perflog1016/selftest.py, docs/lanes/perflog1016/site_context.py, docs/lanes/perflog1016/write_prediction.py, docs/lanes/perflog1016/write_prediction_p2.py, docs/lanes/perflog1016/pfifo.c.patch, docs/lanes/perflog1016/profile.c.patch, docs/lanes/perflog1016/renderer.c.patch, docs/lanes/perflog1016/surface.c.patch
Prediction: docs/testing/predictions/perflog1016-postlend.json @ 2c3c417926c3fc07f67e2bf50a4cd5a67ce5180622dc9030525f75bd62984bed (P2, hand-read: the full PR's default path A/B plus the ON leg; judged by abread.py --judge --on. P1, perflog1016-defaultpath.json @ c09fb430..., was read 10-18: CLEARED)
Needs device: yes    Needs NDK: yes

Release note (none): an opt-in debug switch, off at every launch; the pause menu's debug section gains Perflog, Mark this moment and Frame dump buttons.

The owner asked for the perflog telemetry from the pause menu, mid-run, so a defect like #998's flicker can be captured without a rebuild and replay.

**What it is.** The switch is a marker file, `perflog.on`, in the app's external files dir (where `frame_dump.on` lives).
- The emulator polls it at the flip, at most once a second (`vk/renderer.c`, inside the frame dump's existing limit).
- One line on every flip: `hakuX-perf: [perflog] runtime tier ON (frame N, by marker)`, or `by env`.
- The pause menu's debug section toggles it. The label reads `Perflog: OFF` / `Perflog: ON`, or `ON (perflog build)` / `ON (XEMU_PERFLOG_RT)` when it is pinned.
- `XEMU_PERFLOG_RT=1` (`request.sh --env`) pins it on for a queued soak.
- The marker is deleted at every launch.
- No JNI is needed, so `MainActivity.kt` and `strings.xml` are untouched.

**How the hooks are switched.**
- debug.h's phase-timer macros and counters run under the switch in a plain build. That covers ~155 call sites, among them draw.c's ~101, with no edit at the call site.
- Off, a phase costs one relaxed load and a not-taken branch, with no clock read.
- `profile.c` compiles set/poll and prints its every-60-frames block (hakuX-phase, hakuX-cpu, xemu-*) only while the switch is on.
- `pfifo.c`'s puller/pusher/lock timers follow the switch: one relaxed load per method command, one per pusher pass.
- The TCG `[tcg787]` hooks follow the same switch.
- **Mark this moment** writes `hakuX-route: mark owner-N`, the route driver's shape.

**Not switchable.** These still need `-Pperflog=true`: per-draw, per-bind and per-upload attribution; GPU timestamps; the method histogram; the callback-latency split; `[tpc787]`; and, in this PR, `vk/surface.c`'s timers (the file is lane.gta3instr1018's, so `xemu-surf` prints 0 ms under the switch). NOTES.md has the full inventory with classes A/B/C, and a per-defect-class statement of what the switch does and does not give. It names no cause for #998.

| | state |
|---|---|
| inventory (NOTES.md) | done; pfifo row corrected to class A (per method command) |
| switch: debug.h + profile.c + renderer.c + pfifo.c + TCG + pause menu | done. The three granted files were applied at ce91b11b74 on master 7e00c7cf73. `selftest.py`: SELFTEST OK (16+4+2 passes; header mutants 11/11; KT mutants 14/14; wiring checks on the three files, WIRE mutants 11/11; 10 reader fixtures). NDK compile check: 0 new errors |
| `vk/surface.c` coverage | dropped (held by lane.gta3instr1018); `surface.c.patch` kept for its next holder |
| P1 default-path A/B, before the patches (10-16; Nova, GTA VC, A B B A) | **CLEARED**. tcpu B-A -7.1 ms/s against a band of 56.0; gfps 29 in all four runs; Ri B-A -0.67 ms against a band of 1.65. B2 started warm, and B1-B2 = 55.9 > 14, so no tight bound is claimed; cold runs only, B-A tcpu is +20.9. Same-build cold noise is ~29 ms/s. Tables in NOTES.md |
| P2 default-path A/B on the full PR + the ON leg | **pending, device**: queued 10-18 behind the owner's Nova hold, ON A1 B1 A2 B2 A3: `1-1792344816-perflog1016-1365941`, `1-1792344821-perflog1016-1366376`, `1-1792344826-perflog1016-1366882`, `1-1792344832-perflog1016-1368963`, `1-1792344837-perflog1016-1369630`, `1-1792344843-perflog1016-1370194`. Registered before queueing; the rules are in NOTES.md "P2" |
| ON-path proof (perflog lines in logcat) | **pending, device**: the ON run above (env pin). The button path (`by marker`) has host coverage only and is the first check in an owner session after the fold |
| owner-play capture keeps the ON lines | no: lane.local's `ownerplay.py` filter drops the seven ON-block tags (it keeps the flip line, marks and `[tcg787]`); NEED in OUTBOX.md, lane.local's call |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
