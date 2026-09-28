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

## 2. Session 1 (2026-09-27 20:30-20:36 PDT, Nova, apk a593d8eb85, 370 s of device time)

Data: `~/hakux-work/perf/2026-09-27-doa413c/s1/`. The first scene-load stall came where the
soak's did: the menu -> first fight load, device 20:32:01.8 to 20:32:15.9 (**14.1 s** with no
`fifoskew` and no `gfps` line; the `fifoskew` line that closes it reads `win=14121ms kicks=180`,
110 drained, drain mean 47.6 ms, max 444 ms).

**The profile of that stall was lost.** The trigger fired 5.9 s into it and `simpleperf record`
failed at once (`Event type 'cpu-clock' is not supported on the device`); the second record,
which worked, fired on a 4.1 s pusher gap *inside the fight* that followed (one `[tlb68]` window
at 1814 after it). So R1 and R3 were not read in session 1. `stallwatch.py` now needs two pegged
vCPU windows after the last work line (replayed: it rejects that gap and still catches the real
stall 5.8 s in), and the record retries.

**What session 1 did read, from `taskio.txt` (`taskio.py --win`), uptime windows mapped from
the device clock (the device's logcat clock ran ~3 s ahead of the host's):**

| window | vCPU thread (tid 32681) CPU | its ISO reads | PFIFO thread (tid 32689) CPU |
|---|---|---|---|
| menus, 45 s | 93.3% | 1,318 KB/s, 23.1 calls/s, 57 KB per call | 5.2% |
| **stall, 12.8 s** | **95.7%** | **531 KB/s**, 6.4 calls/s, 83 KB per call | **85.0%** |
| fight just after, 26 s | 57.8% | 852 KB/s, 20.4 calls/s | 53.9% |
| fight, 180 s | 24.3% | 281 KB/s, 8.0 calls/s | 20.1% |

The tids are named from record 2's stacks: 32681 is the only thread with JIT samples (the vCPU),
and 32689's leaves are `pfifo_thread`, `pgraph_method` and Mesa NIR passes (the PFIFO/render
thread). The ISO reads sit on the vCPU thread, as doa413 read from the code
(`XEMU_ANDROID_INLINE_AIO=1`: a read runs synchronously in the thread that issues it).

- **R2: the stall reads the disc at 531 KB/s, below the fight right after it (852 KB/s) and
  under half the menus' rate (1,318 KB/s), and the reading thread stays 96% on-CPU** (a thread
  blocked in `pread` is off-CPU). **M1 (the guest waiting on the disc) is refuted by its own
  R2 leg**, whatever R1 turns out to be: the stall is not the disc delivering slowly.
- **New: the PFIFO thread is busy through the stall** (85% on-CPU, against 5% in the menus).
  PR #417 read the stall's renderer as idle from `Ri` and `vblphase`. `Ri` is printed per 60
  flips, and its stall row read `Ri 0.0` (no idle time), and the perflog soak's `hakuX-phase`
  line whose 60-flip window spans its 14 s stall (12:52:57.863) accounts for only
  60 x 28.2 ms = 1.7 s, with `Shd 0.0` and `Idle 0.1`: **about 12 s of that stall is outside
  every phase timer**. So "renderer idle" was never measured; the renderer is on-CPU doing
  something the phase timers do not cover.
- **`[jc425] lh` (TB lookups through `helper_lookup_tb_ptr` that hit) runs at 57-81 M per 2 s in
  the stall, against 0.13 M in the menus** (20:32:06-14 against 20:32:02). The vCPU goes around
  a very small guest loop ~40 M times a second. That is a spin, not a load's compute.

## 3. Pre-registration for session 2 (committed before it runs)

Session 2 (`capture_stall.sh`, `LAUNCHES=2`): launch 1 with the shader and pipeline caches
cleared, launch 2 straight after with launch 1's caches kept, each with one stall record and a
code-buffer dump; RAM after launch 2.

**Mechanism M2: at a scene load the PFIFO thread is busy on CPU in work outside the phase
timers, and the guest spins waiting on the GPU.** Readings and predictions:

- **R1 (vCPU, `tbmap.py`)**: >= 50% of the vCPU's mapped JIT samples in one small spin
  (<= 4 guest pcs), either the kernel idle loop (`0x8001b000-0x8001b0ff`) or a title loop whose
  hot TB is an MMIO/port read (a GPU poll).
- **R4 (PFIFO thread, `hostsplit.py --tid <pfifo>`)**: >= 50% of its stall samples under one
  host call path. I do not predict which. Candidates, each named by the frames it would show:
  pipeline/shader compile (`vkCreateGraphicsPipelines`, `tu_`, `ir3_`, `nir_`), texture upload
  or swizzle (`pgraph_vk_*texture*`, `swizzle`, `memcpy`), or a spin/poll inside the renderer.
- **R5 (cold vs warm)**: if R4 is compile, the warm launch's first stall is at most half the
  cold one's; if R4 is not compile, the two are within 30% of each other.

**Refutations:** R1 < 20% in a spin (the guest computes: M2's "guest waits" half is wrong); the
PFIFO thread under 30% on-CPU in the stall (`taskio`), which voids session 1's 85%; R4 spread
with no call path over 25% (no single mechanism to name). The session measured nothing about R1
if `tbmap.py`'s self-checks fail.
