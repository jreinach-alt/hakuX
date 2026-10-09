State: draft

Lane: pmucounters            Issue: #433
Base: master @ f2c6b9c5d6
Files: accel/tcg/hakux-pmu.c.inc, accel/tcg/cpu-exec.c, docs/lanes/pmucounters/NOTES.md, docs/lanes/pmucounters/OUTBOX.md, docs/lanes/pmucounters/PR.md, docs/lanes/pmucounters/WAITING, docs/lanes/pmucounters/hakux-pmu.c.inc, docs/lanes/pmucounters/pmuprobe.c, docs/lanes/pmucounters/build_probe.sh, docs/lanes/pmucounters/r0_probe.sh, docs/lanes/pmucounters/pmuread.py, docs/lanes/pmucounters/syntax_check.py, docs/lanes/pmucounters/elfsyms.py
Prediction: none: measurement lane, no arm (no behaviour change; the counting on/off pair is an overhead check read by hand)
Needs device: yes    Needs NDK: yes

Release note (none): opt-in instrumentation (`HAKUX_PMU`), off by default.

Hardware performance counters on the vCPU thread. The question is why the
JIT's code is slow: front-end, back-end/memory, bad speculation, or
instruction count.

`accel/tcg/hakux-pmu.c.inc` (granted 10-09, board 82379753c2) is called from
`cpu-exec.c` at the existing `[tlb68]` gate. Unset, it costs one load and a
branch there. With `HAKUX_PMU=1` it prints one `[pmu433]` line per ~1 s
slice:

- the counts come from the CPU's own counters, in groups of 5 events (cycles,
  instructions and 3 more), five groups, multiplexed;
- each group is opened once per CPU, so every number belongs to one core
  type;
- the line also carries frames flipped and the longest frame, so slow slices
  can be read apart from good ones.

`HAKUX_PMU_CTL=1` first runs eight control kernels through the same counters.
`HAKUX_PMU=2` samples up to four events instead, each attributed in-process to
a TB, the dispatch stub or a host library offset.

R0 (10-09, Nova): the PMU schedules at most 5 events per group. The 10-05
hook's 7-event groups never ran, which is why it read zero. Results for R1,
R2 and R3 are in OUTBOX.md as they land.

`docs/lanes/pmucounters/hakux-pmu.c.inc` is on the Files line because this
PR deletes it: the hook now has one copy, at `accel/tcg/`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
