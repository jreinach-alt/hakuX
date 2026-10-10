State: ready

Lane: pmucounters            Issue: #433
Base: master @ 2b9846b729
Files: accel/tcg/hakux-pmu.c.inc, accel/tcg/cpu-exec.c, docs/lanes/pmucounters/NOTES.md, docs/lanes/pmucounters/OUTBOX.md, docs/lanes/pmucounters/PR.md, docs/lanes/pmucounters/pmuprobe.c, docs/lanes/pmucounters/build_probe.sh, docs/lanes/pmucounters/r0_probe.sh, docs/lanes/pmucounters/pmuread.py, docs/lanes/pmucounters/syntax_check.py, docs/lanes/pmucounters/elfsyms.py, docs/lanes/pmucounters/overhead.py, docs/lanes/pmucounters/waits.py, docs/lanes/pmucounters/spinfps.py, docs/lanes/pmucounters/tbbins.py, docs/lanes/pmucounters/tbper.py, docs/lanes/pmucounters/objcheck433.py, docs/lanes/pmucounters/pairread.py, docs/lanes/pmucounters/workbin.py
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

## Results (Amped 2, Nova)

- **The counters are an instrument.** 10 of 11 control kernels read as
  predicted on the X3: IPC, indirect mispredicts, L1I and L1D refills, and
  both stall classes. L2 refills read 16% high, because of page-walk traffic.
- **Slow frames are waits, not slower code.** No counter differs between
  good and slow 1 s slices by more than one good-slice sd. The vCPU thread
  is off-CPU 8 points more in slow slices.
- **The JIT's code runs at high IPC.** With the title's pacing spin out, it
  is about 3.1-3.3 on the X3. Front-end stall is 12% of cycles. Mispredicts
  are at most 0.028 per indirect branch, about 2% of cycles. Back-end stall
  is 28%. On the code side the lever is instruction count, not a stall
  class.
- **Where the cycles go (sampled).**
  - JIT code is 56% of cycles; the pacing spin TB alone is 24%.
  - Dispatch (`helper_lookup_tb_ptr`, `tb_lookup`, `qht`) is 17%.
  - softmmu `mmu_lookup1` is 7%.
  - With the spin removed, no other TB reaches 1%.
- **The frame.** From a 30 fps window to a < 24 fps one, the frame grows
  11 ms:
  - about 9 ms is more guest work;
  - about 11 ms is more off-CPU time, mostly the vCPU's DMA_PUT waiting on
    pfifo.lock while the PFIFO thread waits on GPU fences in report
    processing;
  - the pacing spin shrinks by 9 ms, which offsets part of that growth.
- **Ranked candidates** (P x win):
  1. the report-processing fence waits under pfifo.lock, ~5% of frame time
     overall;
  2. dispatch, ~1%;
  3. `mmu_lookup1`, ~0.4%.

  Two pre-registered pairs (`HAKUX_OCCL_WAIT=0` vs the shipped wait) were
  meant to decide #1 directly. In both, the shipped-wait arm (W, then W2)
  went void: the route's fixed-timing script, with the wait's extra pacing
  change, lands its button presses on a different screen than it does
  without the wait (parked against a tree in the first pair, stuck
  cycling menus in the second) -- a finding in its own right about this
  route, independent of #1. The registered fallback secondary (pool the
  two valid no-wait runs, N and N2, against the three valid shipped-wait
  runs from R1/R2/overhead, B2/C/D, at matched vCPU work per frame) reads
  a **hit**: off-CPU time is 2.5-4.5 ms/frame lower for no-wait across
  every work bin >= 21 ms/frame, frames-weighted gap 4.39 ms/frame, well
  past the registered 1.5 ms/frame threshold, and it replicates
  independently between N and N2. **#1's P is 0.8, final.**
- **Counting cost** is below the route's run-to-run noise (on/off pair).

NOTES.md 3e-3h has the tables and the evidence.

Device runs (Nova, investigative):

| ref | run | id |
|---|---|---|
| 5e4110e016 | A controls (9/11 PASS) | `1-1791584641-pmucounters-283582` |
| 5e4110e016 | B R1 (lines cut at the log limit) | `1-1791584645-pmucounters-283745` |
| b345b5b613 | A2 controls (10/11 PASS) | `1-1791585654-pmucounters-340915` |
| b345b5b613 | B2 R1 counting | `1-1791585654-pmucounters-341117` |
| b345b5b613 | C R2 sampling | `1-1791585655-pmucounters-341517` |
| b345b5b613 | D counting off | `1-1791585656-pmucounters-341827` |
| b345b5b613 | N report wait skipped (valid) | `1-1791588183-pmucounters-521453` |
| b345b5b613 | W shipped wait (void: stuck rider) | `1-1791588184-pmucounters-521720` |
| b345b5b613 | N2 report wait skipped (valid) | `1-1791592304-pmucounters-321962` |
| b345b5b613 | W2 shipped wait (void: stuck in menus) | `1-1791592309-pmucounters-323321` |

A and B found three faults in the hook, all fixed in b387f4971a:

- a slice line over Android's 1023-byte log limit was cut, and is now split;
- software switch and migration counts read 0 until the kernel was included;
- a control kernel's setup ran inside its counted window.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
