State: draft

Lane: pmucounters            Issue: #433
Base: master @ f2c6b9c5d6
Files: accel/tcg/hakux-pmu.c.inc, accel/tcg/cpu-exec.c, docs/lanes/pmucounters/NOTES.md, docs/lanes/pmucounters/OUTBOX.md, docs/lanes/pmucounters/PR.md, docs/lanes/pmucounters/WAITING, docs/lanes/pmucounters/pmuprobe.c, docs/lanes/pmucounters/build_probe.sh, docs/lanes/pmucounters/r0_probe.sh, docs/lanes/pmucounters/pmuread.py, docs/lanes/pmucounters/syntax_check.py, docs/lanes/pmucounters/elfsyms.py
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

The hook has one copy, at `accel/tcg/`; the lane directory's earlier copy is
gone (it never reached master).

Device runs (Nova, investigative):

| ref | run | id |
|---|---|---|
| 5e4110e016 | A controls (9/11 PASS) | `1-1791584641-pmucounters-283582` |
| 5e4110e016 | B R1 (lines cut at the log limit) | `1-1791584645-pmucounters-283745` |
| b345b5b613 | A2 controls | `1-1791585654-pmucounters-340915` |
| b345b5b613 | B2 R1 | `1-1791585654-pmucounters-341117` |
| b345b5b613 | C R2 sampling | `1-1791585655-pmucounters-341517` |
| b345b5b613 | D counting off | `1-1791585656-pmucounters-341827` |

A and B found three faults in the hook, all fixed in b387f4971a:

- a slice line over Android's 1023-byte log limit was cut, and is now split;
- software switch and migration counts read 0 until the kernel was included;
- a control kernel's setup ran inside its counted window.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
