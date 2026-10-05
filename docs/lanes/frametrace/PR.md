# frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame
State: draft

Lane: frametrace            Issue: #433
Base: master @ d32c35d3ce
Files: docs/lanes/frametrace/PR.md, docs/lanes/frametrace/NOTES.md, docs/lanes/frametrace/OUTBOX.md, docs/lanes/frametrace/WAITING, docs/lanes/frametrace/archive.py, docs/lanes/frametrace/capture_simpsons_frametrace.sh, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/frames.csv.gz, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/ft.log.gz, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/meta.md, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/frames.csv.gz, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/ft.log.gz, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/meta.md, docs/lanes/frametrace/csvinfo.py, docs/lanes/frametrace/forza-frametrace.route, docs/lanes/frametrace/forza-nova-frametrace.route, docs/lanes/frametrace/ft_selftest.c, docs/lanes/frametrace/ftread.py, docs/lanes/frametrace/hooks.diff, docs/lanes/frametrace/overhead.py, docs/lanes/frametrace/scan_runs.py, docs/lanes/frametrace/selftest-fragment.sh, docs/lanes/frametrace/selftest.py, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/profile.h, system/cpus.c
Prediction: none: telemetry, off by default; judged by the overhead pair (NOTES section 2) and the selftest
Needs device: yes (Nova captures queued; Simpsons is a host capture)    Needs NDK: yes

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
| selftest | `selftest.py`: 36 checks on the host, 12 header mutants each caught |
| in-process cost on the device | 71 us/frame on the Nova (builder 25 + writer 46); 17-19 us builder on the Thor |
| overhead on the pace | one-run test `HAKUX_FRAMETRACE_DUTY` (instrument off/on every s seconds); judged by NOTES section 5 |
| hooks outside the row | `hooks.diff` (G1-G8) and G9 (MMIO split), requested in OUTBOX; not applied |
| raw data | `captures/<result id>/` (`archive.py`; `ftread.py` reads it) |

First reads (NOTES section 4), Nightfire and Tron on the Nova, both 60 Hz:

| | Nightfire | Tron 2.0 |
|---|---|---|
| late frames | 50.4% | 23.6% |
| late frames whose pacemaker is the vCPU running guest code | 99.8% | 88.9% |
| vCPU on-CPU per late frame (deadline 16.7 ms) | 27.4 ms | 29.6 ms |
| PFIFO thread waiting for work, per late frame | 9.1 ms | 18.8 ms |
| GPU busy, median frame; frames with GPU >= 90% | 34%; 0 | 22%; 0 |

Status: Forza (Nova) and the one-run overhead test (Nightfire) queued;
Simpsons waits on a host capture; the Thor's Forza runs die on a launcher
focus fault.

Checks: NDK clang type-check of profile.c and cpus.c (Release line,
re-pointed): clean. `check_android_guards.py`: ok. Desktop build: not run
(this host cannot build desktop; AGENTS.md).

Release note (none): opt-in telemetry, off unless HAKUX_FRAMETRACE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
