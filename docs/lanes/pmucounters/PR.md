State: draft

Lane: pmucounters            Issue: #433
Base: master @ d32c35d3ce
Files: docs/lanes/pmucounters/NOTES.md, docs/lanes/pmucounters/OUTBOX.md, docs/lanes/pmucounters/PR.md, docs/lanes/pmucounters/WAITING, docs/lanes/pmucounters/hakux-pmu.c.inc, docs/lanes/pmucounters/pmuprobe.c, docs/lanes/pmucounters/build_probe.sh, docs/lanes/pmucounters/r0_probe.sh, docs/lanes/pmucounters/pmuread.py, docs/lanes/pmucounters/syntax_check.py
Prediction: none: measurement lane, no arm (no behaviour change; the counting on/off pair is an overhead check read by hand)
Needs device: yes    Needs NDK: yes

Hardware performance counters on the vCPU thread. The question is why the
JIT's code is slow: front-end, back-end/memory, bad speculation, or
instruction count.

So far: the `[pmu433]` instrument (per core-type PMU, three multiplexed groups,
1 s slices with frame times), a standalone NDK build of it for a host-run R0
probe, and the reader with pre-registered control expectations. Waiting on
a grant for the in-process hook, `perf_harden 0` on the handhelds, and the R0
probe run. See OUTBOX.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
