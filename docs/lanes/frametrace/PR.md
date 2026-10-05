# frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame
State: draft

Lane: frametrace            Issue: #433
Base: master @ d32c35d3ce
Files: docs/lanes/frametrace/PR.md, docs/lanes/frametrace/NOTES.md, docs/lanes/frametrace/OUTBOX.md, docs/lanes/frametrace/capture_simpsons_frametrace.sh, docs/lanes/frametrace/forza-frametrace.route, docs/lanes/frametrace/ft_selftest.c, docs/lanes/frametrace/ftread.py, docs/lanes/frametrace/hooks.diff, docs/lanes/frametrace/scan_runs.py, docs/lanes/frametrace/selftest-fragment.sh, docs/lanes/frametrace/selftest.py, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/profile.h, system/cpus.c
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
| selftest | `selftest.py`: 33 checks on the host, 9 header mutants each caught |
| builder cost on the device | 17-19 us/frame (Thor pilot, 761 frames) |
| hooks outside the row | `hooks.diff` (G1-G8), requested in OUTBOX; not applied |

Status: Thor pilot ran (the Thor's foreground fault ended both arms before
the race; the instrument's record was sound). Nightfire (on, off) and Tron
(on) queued on the Nova; Simpsons host capture requested.

Checks: NDK clang type-check of profile.c and cpus.c (Release line,
re-pointed): clean. `check_android_guards.py`: ok. Desktop build: not run
(this host cannot build desktop; AGENTS.md).

Release note (none): opt-in telemetry, off unless HAKUX_FRAMETRACE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
