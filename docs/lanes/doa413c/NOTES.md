# lane.doa413c -- #413: DOA Ultimate stage-transition stall (0-2 fps, up to 76 s)

Base master f82e7e87fe. Disc `54430006-Dead_or_Alive_1_Ultimate.xiso.iso`, Nova.
Source runs: `0-0-y-1790433159-titleplay-p1-doa1u` (the 76 s gap) and the perflog soak
`1790450181-doa413-1721403` (two 13-14 s gaps with the same counters, PR #417).

## 0. What was already known (PR #417, docs/lanes/doa413/NOTES.md, section 1(b) and 3(b))

In every gap: the vCPU thread is on-CPU 83-99% of the wall clock, the emulated VBLANK is on
time (59.94 Hz, 0.1 ms late), the pusher gets 0-60 kicks per 2 s, and the renderer is idle.
doa413 read this as "the guest runs flat out", with two open readings: (i) a guest waiting on
something the emulator delivers slowly (disc, a device), or (ii) guest work made slow by TCG.

What that reading did not have: #525 (lane.retreason425) found the Xbox kernel's idle loop
(`sti; nop; nop; cli; test; jz` at `0x8001b02e`) never executes `hlt`. **A vCPU thread at
90-99% is therefore what an idle guest looks like too.** The counters cannot separate (i) from
(ii). The guest pc can.

Offline, from the two runs on disk: the only guest pcs in the logs are `hakuX-tier1` promote
lines (one per 10,000 promotes). The `cpu_io_recompile` TBs (cflags `0xff031001`, an MMIO access
mid-TB) at `0x34dae6` and `0x34e013` appear in the stalls *and* in the fights (soak 12:56:14,
12:58:01), so they do not mark the stall.

## 1. Pre-registration (committed before the device session)

**Instrument.** One held Nova session (`capture_stall.sh`, adapted from
`docs/lanes/gta482/capture_gta.sh` and `docs/lanes/slowdown462/capture_profile.sh`), apk
`a593d8eb85` (the build slowdown462 profiled DOA with, and the layout `gta482/tbmap.py` was
validated on), route `titles/routes/survey.route` (the source run's route). The script watches
the live logcat. When a stall starts -- no `fifoskew` and no `gfps=` line for 4 s while the
last `[tlb68]` `cpu=` is at least 1500 of 2000 -- it records 10 s of `simpleperf record
-e cpu-clock --call-graph dwarf` over the app, then dumps the TCG code buffer and guest RAM
through `/proc/<pid>/mem`. From launch to exit it samples `/proc/<pid>/task/*/io` and `stat`
once a second (per-thread read bytes, read syscalls and CPU time).

**Readings, named before the data exists:**

- **R1, idle share.** Of the vCPU thread's JIT samples that map to a TB (`tbmap.py`), the
  share whose TB pc is in the kernel idle loop (`0x8001b000-0x8001b0ff`).
- **R2, disc read rate.** Bytes and read syscalls per second on the emulator process during
  the stall window, per thread, from `/proc/<pid>/task/*/io` (`rchar`, `syscr`), against the
  menus and the fight.
- **R3, host split of the vCPU thread.** Share of its samples in JIT code, in the softmmu /
  MMIO helpers (`io_readx`, `memory_region_dispatch_*`, `cpu_io_recompile`), and in the
  translator (`tb_gen_code`, `tb_invalidate_*`).

**Prediction (mechanism M1, a guest waiting on the disc).** The guest is idle, not computing:
**R1 >= 50%**, and the stall window carries disc reads (**R2** above the fight's rate, on the
thread that issues IDE reads), with each read's latency, not the guest's CPU, setting the
stall's length.

**What refutes it, leg by leg:**

- R1 < 20%: the guest is computing. M1 is refuted and the stall is (ii), guest work slowed by
  TCG; R3 and the hot pcs then say which (translator churn, MMIO exits, or plain JIT code).
- R1 >= 50% but R2 at or below the fight's rate: the guest is idle and *not* on the disc.
  M1 is refuted; the wait is on another device (the hot non-idle pcs and MMIO helpers name it).
- 20% <= R1 < 50%: mixed. M1 is not confirmed; report both shares and the hot pcs.
- The tool's self-checks fail (header delta mode not 192, promote pcs not among the headers,
  mapped share < 50% of JIT samples): the session measured nothing about R1, and says so.

No arm is registered: a profile moves no pixels, and no code is changed here.
