# lane.pmucounters OUTBOX

## #433 -- 2026-10-05 08:55 PDT (attempt 1: instrument built, R0 waiting)

pmucounters: the hardware-counter instrument is written and compile-checked;
R0 has not run. Nothing of mine is queued, running or held.

Built (all in `docs/lanes/pmucounters/`): `hakux-pmu.c.inc`, a `[pmu433]`
line per ~1 s slice from the vCPU thread's own counters. It opens one group set
per core-type PMU because a generic hardware event counts on one core type
only and would read zero on the X3. Each slice carries IPC, front- and
back-end stall cycles, branch mispredicts, indirect branches, L1I/iTLB/L1D/
dTLB/L2/L3 refills and TLB walks, plus the frames flipped in the slice and the
longest one. That lets slow windows be read apart from good ones. Off unless
`HAKUX_PMU=1`. `HAKUX_PMU_CTL=1` first runs eight control kernels (known IPC,
known mispredict rate, known L1D/L2/L1I miss rates) through the same
counters. `pmuprobe.c` builds it standalone with the NDK (`-Werror`, clean),
and `pmuread.py` judges the controls and prints the good-vs-slow table. Its
selftest passes, including a control built to fail. The expectations for
every control and the hit/miss rows for R1 are in NOTES.md section 2, written
before any run.

Asks (three, independent):

1. **Grant**: `accel/tcg/hakux-pmu.c.inc` (new file, the hook as above) and
   `accel/tcg/cpu-exec.c` (one `#include` and one `pmu433_tick()` call at the
   existing `[tlb68]` gate, line ~2544). Telemetry only, off by default, no
   behaviour change. With it, R0 and R1 run as ordinary queued soaks
   (`--env HAKUX_PMU=1`), with no holds.
2. **`setprop security.perf_harden 0`** on the Thor and the Nova (it lasts
   until the next reboot; it sets `perf_event_paranoid` 1). Without it every
   `perf_event_open` from the app is refused and the hook only logs the
   refusal. That refusal is itself R0's named negative result. gta482 had this
   leave for its held sessions.
3. **One host-run R0 probe**, about 90 s, no title launched, no pref touched:
   `DEV=thor bash docs/lanes/pmucounters/r0_probe.sh` on an idle Thor inside a
   hold you already hold (the cold-slot runner's gap is fine). Add `HARDEN0=1`
   if ask 2 is granted. It writes to
   `~/hakux-work/perf/<date>-pmucounters/r0-thor/`. It answers the brief's
   R0 (a) and (c) by simpleperf's path, lists which events each core exposes,
   and runs the controls pinned to the X3, an A715 and an A510. The Nova run
   (`DEV=nova`) is the same and can wait for a pathfind gap.

Addendum 09:00 PDT: the hook now also has R2's mode (`HAKUX_PMU=2`, a
sampled raw event attributed in-process to TB / dispatch stub / host
function), so the one grant above covers R1 and R2. It was tested on this
host with software events: 80,669 samples, 0 lost, attributed. It
compile-checks inside `cpu-exec.c` with the Android build's flags (and a
planted error fails that check). The R0 probe now also exercises the sampling
path on the device, so it takes about 2 minutes instead of 90 s.
