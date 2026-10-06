# frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame
State: ready

Lane: frametrace            Issue: #433
Base: master @ d32c35d3ce (merged to current master at 02b01b7b44; current at 7e47dde38c)
Files: docs/lanes/frametrace/NOTES.md, docs/lanes/frametrace/OUTBOX.md, docs/lanes/frametrace/PR.md, docs/lanes/frametrace/archive.py, docs/lanes/frametrace/capture_simpsons_frametrace.sh, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/frames.csv.gz, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/ft.log.gz, docs/lanes/frametrace/captures/1-1791216614-lane.frametrace-2373212/meta.md, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/frames.csv.gz, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/ft.log.gz, docs/lanes/frametrace/captures/1-1791216620-lane.frametrace-2374008/meta.md, docs/lanes/frametrace/captures/1-1791225231-lane.frametrace-2914369/frames.csv.gz, docs/lanes/frametrace/captures/1-1791225231-lane.frametrace-2914369/ft.log.gz, docs/lanes/frametrace/captures/1-1791225231-lane.frametrace-2914369/meta.md, docs/lanes/frametrace/captures/1-1791225335-lane.frametrace-2925645/frames.csv.gz, docs/lanes/frametrace/captures/1-1791225335-lane.frametrace-2925645/ft.log.gz, docs/lanes/frametrace/captures/1-1791225335-lane.frametrace-2925645/meta.md, docs/lanes/frametrace/captures/1-1791245535-lane.frametrace-680559/frames.csv.gz, docs/lanes/frametrace/captures/1-1791245535-lane.frametrace-680559/ft.log.gz, docs/lanes/frametrace/captures/1-1791245535-lane.frametrace-680559/meta.md, docs/lanes/frametrace/chain-session4.md, docs/lanes/frametrace/chain.py, docs/lanes/frametrace/csvinfo.py, docs/lanes/frametrace/forza-frametrace.route, docs/lanes/frametrace/forza-nova-frametrace.route, docs/lanes/frametrace/ft_selftest.c, docs/lanes/frametrace/ftread.py, docs/lanes/frametrace/hooks-g9.diff, docs/lanes/frametrace/hooks.diff, docs/lanes/frametrace/idlejoin.py, docs/lanes/frametrace/make_hooks_g9.py, docs/lanes/frametrace/overhead.py, docs/lanes/frametrace/scan_runs.py, docs/lanes/frametrace/selftest-fragment.sh, docs/lanes/frametrace/selftest.py, docs/lanes/frametrace/simpsons-frametrace.route, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/profile.h, system/cpus.c
Prediction: none: telemetry, off by default; judged by the overhead pair (NOTES section 2) and the selftest
Needs device: no (four captures done; the next one follows the grant)    Needs NDK: yes


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
| reader | `ftread.py` (gameplay window from the route's mark; VOID without one); `chain.py` (re-reads pre-session-4 captures with the corrected rule; closes the vCPU chain); `idlejoin.py` (guest idle from [rr425w]) |
| selftest | `selftest.py`: 39 checks on the host, 16 header mutants each caught |
| in-process cost on the device | 71-89 us/frame on the Nova (builder + writer); 17-19 us builder on the Thor |
| overhead on the pace | one-run test `HAKUX_FRAMETRACE_DUTY` (off/on every 15 s): PASS, no 3% move in fps or vCPU run share (NOTES section 5) |
| hooks outside the row | `hooks.diff` (G1-G8) and G9 (MMIO split), requested in OUTBOX; not applied |
| raw data | `captures/<result id>/` (`archive.py`; `ftread.py` reads it) |

Reads (NOTES section 8), Nova, 615 MHz throughout; late = P over the
guest's deadline (the rule was corrected in session 4: the VBLANK deferral
had hidden most late frames from a VBLANK count):

| | Simpsons (60) | Forza (30) | Nightfire (60) | Tron 2.0 (60) |
|---|---|---|---|---|
| fps | 44.7 | 26.9 | 38.8 | 44.8 |
| late frames | 97% | 67% | 99% | 48% |
| late on guest work alone | 10% | 34% | 27% | 70% |
| otherwise the vCPU waits in | DMA_PUT pfifo.lock, 6.3 ms/frame | its idle loop, 12.5 ms | its idle loop, 8.2 ms | DMA_PUT pfifo.lock, 2.3 ms |
| PFIFO thread blocked in no hooked wait, ms/frame | 7.4 | 14.6 | 6.6 | 2.5 |
| GPU main-CB execution, busy share of the frame | 23% | 48% | 34% | 22% |

Three of four titles are mostly waiting, not running guest code. The wait
is between the PFIFO thread and GPU completion, and the GPU's measured
execution is under half of every frame. Simpsons answers vcpusleep's open
question: the GPU executes 5.1 ms of its 22.4 ms frame. Next (NOTES section
9): the G1/G3/G4 hooks plus a per-submit GPU timeline (G10), requested in
OUTBOX.

Checks: NDK clang type-check of profile.c and cpus.c (Release line,
re-pointed): clean. `check_android_guards.py`: ok. Desktop build: not run
(this host cannot build desktop; AGENTS.md).

Release note (none): opt-in telemetry, off unless HAKUX_FRAMETRACE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
