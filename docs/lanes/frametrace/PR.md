# frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame
State: draft

Lane: frametrace            Issue: #433
Base: master @ d32c35d3ce (merged to current master at 02b01b7b44)
Files: docs/lanes/frametrace/NOTES.md, docs/lanes/frametrace/OUTBOX.md, docs/lanes/frametrace/PR.md, docs/lanes/frametrace/WAITING, docs/lanes/frametrace/archive.py, docs/lanes/frametrace/capture_simpsons_frametrace.sh, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/frames.csv.gz, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/ft.log.gz, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/meta.md, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/frames.csv.gz, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/ft.log.gz, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/meta.md, docs/lanes/frametrace/captures/1-1791225231-lane.frametrace-2914369/frames.csv.gz, docs/lanes/frametrace/captures/1-1791225231-lane.frametrace-2914369/ft.log.gz, docs/lanes/frametrace/captures/1-1791225231-lane.frametrace-2914369/meta.md, docs/lanes/frametrace/captures/1-1791225335-lane.frametrace-2925645/frames.csv.gz, docs/lanes/frametrace/captures/1-1791225335-lane.frametrace-2925645/ft.log.gz, docs/lanes/frametrace/captures/1-1791225335-lane.frametrace-2925645/meta.md, docs/lanes/frametrace/csvinfo.py, docs/lanes/frametrace/forza-frametrace.route, docs/lanes/frametrace/forza-nova-frametrace.route, docs/lanes/frametrace/ft_selftest.c, docs/lanes/frametrace/ftread.py, docs/lanes/frametrace/hooks-g9.diff, docs/lanes/frametrace/hooks.diff, docs/lanes/frametrace/idlejoin.py, docs/lanes/frametrace/make_hooks_g9.py, docs/lanes/frametrace/overhead.py, docs/lanes/frametrace/scan_runs.py, docs/lanes/frametrace/selftest-fragment.sh, docs/lanes/frametrace/selftest.py, docs/lanes/frametrace/simpsons-frametrace.route, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/profile.h, system/cpus.c
Prediction: none: telemetry, off by default; judged by the overhead pair (NOTES section 2) and the selftest
Needs device: yes (Simpsons queued on the Nova)    Needs NDK: yes

An instrument, not a fix: with `HAKUX_FRAMETRACE=1` the emulator records one
row per guest flip saying where the frame's time went on the vCPU, the PFIFO
thread and the main loop (on-CPU, run queue, blocked, and blocked by reason),
what the holder of each vCPU lock wait was doing (and which thread it was),
the GPU's execution time and clock, the VBLANKs the guest asked for and got,
and which of eight classes set the pace. Unset, every hook is a load and a
branch.

| | |
|---|---|
| attribution rule | `hakux_ft_attribute()` in `profile.h`; written out in NOTES section 1 |
| output | `[hakuX-ft1]` 1 Hz summary and `[hakuX-ft]` hitch blocks on `hakuX-lane`; `frametrace_<date>.csv` per frame (`--pull 'frametrace_*'`) |
| reader | `docs/lanes/frametrace/ftread.py` (gameplay window from the route's mark; VOID without one) |
| selftest | `selftest.py`: 38 checks on the host, 15 header mutants each caught |
| in-process cost on the device | 71-89 us/frame on the Nova (builder + writer); 17-19 us builder on the Thor |
| overhead on the pace | one-run test `HAKUX_FRAMETRACE_DUTY` (off/on every 15 s): PASS, no 3% move in fps or vCPU run share (NOTES section 5) |
| hooks outside the row | `hooks.diff` (G1-G8) and G9 (MMIO split), requested in OUTBOX; not applied |
| raw data | `captures/<result id>/` (`archive.py`; `ftread.py` reads it) |

Reads so far (NOTES sections 4 and 6), Nova, 615 MHz throughout:

| | Nightfire (60 Hz) | Tron 2.0 (60 Hz) | Forza (30 Hz) |
|---|---|---|---|
| late frames | 50.4% | 23.6% | 46.1% |
| guest idle loop, ms/frame (in-row `run` books it as vCPU work until G1) | 8.2 | 1.0 | 12.5 |
| late frames over the deadline on guest work alone | 34-99.8% (two regimes) | 88-89% | 41-44% |
| PFIFO thread blocked in no hooked wait, ms/frame | 6.6 | - | 15.0 |
| GPU busy, median frame; frames with GPU >= 90% | 34%; 0 | 22%; 0 | 48%; 0 |

Tron is vCPU-bound. Forza is not: its guest works 22-25 ms of a 33.4 ms
deadline and waits, while the PFIFO thread is blocked ~15 ms a frame and
the GPU is half idle; G1 + G3 (requested, patch ready) decide what that
wait is. Nightfire is vCPU-bound in a quarter of its windows and waits in
the rest.

Status: Simpsons queued on the Nova (blind route from pathfind's hold).

Checks: NDK clang type-check of profile.c and cpus.c (Release line,
re-pointed): clean. `check_android_guards.py`: ok. Desktop build: not run
(this host cannot build desktop; AGENTS.md).

Release note (none): opt-in telemetry, off unless HAKUX_FRAMETRACE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
