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

## 4. Session 2 (2026-09-27 20:46-20:51 PDT, 286 s of device time): cold launch, then warm

Data: `~/hakux-work/perf/2026-09-27-doa413c/s2/`. Both stall records were recorded (14,611 and
9,445 samples) and then **lost to a script bug**: `dump()` set the byte count in `n`, bash's
dynamic scoping handed that to `launch()`'s `local n`, the pull asked for
`doa413c-134213632.data`, and cleanup deleted the real files. The same bug skipped the RAM
dump. Fixed (`dump()`'s variables are local). The logcats and `taskio` of both launches stand.

`stalls.py` over both launches (a gap = consecutive `fifoskew`/`gfps` lines >= 3 s apart):

| launch | the menu -> first fight load, ~85 s after the route starts | vCPU in it | closing `fifoskew` |
|---|---|---|---|
| 1, caches cleared | **12.9 s** (20:47:46.9-20:47:59.8) | 1828-1973 of 2000 | kicks 198, drained 127, mean 37 ms, max 226 ms |
| 2, launch 1's caches kept | **3.1 s** (20:49:58.2-20:50:01.2) | 1962-1968 | kicks 115, drained 47, mean 91 ms, max 219 ms |

**R5: the warm load stalls 76% less than the cold one** (3.1 s against 12.9 s), past the
pre-registered "at most half". The per-60-flip line that closes the cold stall reads
`G:27.2(0.4-12402.3)`: **one guest frame took 12.4 s**.

`taskio` over the cold stall's inner 11.5 s, and the warm load's gap:

| window | vCPU CPU | its ISO reads | PFIFO thread CPU |
|---|---|---|---|
| launch 1 menus, 37 s | 94.3% | 1,467 KB/s | 5.3% |
| **launch 1 stall, 11.5 s** | **98.6%** | **0.0 KB/s** | **96.7%** |
| launch 1 fight after, 19 s | 66.5% | 717 KB/s | 35.5% |
| launch 2 menus, 40 s | 94.2% | 1,514 KB/s | (not among the top 5) |
| launch 2 load gap, 2.1 s | 99.5% | 3,605 KB/s | 56.2% |

The cold stall reads **nothing** from the disc (session 1's 531 KB/s window must have taken in
an edge of it). The PFIFO thread is pegged through it. With a warm cache the same load
reads the disc at 3.6 MB/s and is over in about 3 s.

Offline, from session 1's fight record 2 (`tbmap.py`: 94% of the vCPU's JIT samples map; 5 of 5
tier-1 promote pcs are header pcs; the frequent-delta share is 74.9%, under gta482's 95% bar):
**48% of the vCPU's JIT samples are one 5-instruction title TB at `0x0034a197`**, disassembled
from the RAM dump (`guestcode.py`):

```
34a18d: mov edx,[esi+0x30]   ; pointer to the GPU's read position
34a190: mov esi,[esi+0x2c]
34a193: mov eax,esi
34a195: sub eax,edi
34a197: mov ecx,[edx]        ; <- spin: re-read it
34a199: mov edi,esi
34a19b: sub edi,ecx
34a19d: cmp eax,edi
34a19f: jb  34a197           ; until the GPU has consumed enough pushbuffer
```

A pushbuffer-space wait: the title spins until the GPU's read position has moved far enough.
Its read is of RAM, not a register: 2.7% of the vCPU's samples are in MMIO helpers.

## 5. Session 3 (2026-09-27 20:57-20:59 PDT, 125 s of device time): the cold stall, profiled

Data: `~/hakux-work/perf/2026-09-27-doa413c/s3/`. One launch with the caches cleared. The same
load stalled **12.8 s** (20:58:44.9-20:58:57.7; closing `fifoskew`: kicks 95, drained 28, mean
169 ms, max 425 ms). `rec-1.data`: 6.0 s from 5.0 s into the stall, 13,230 samples.
Code buffer and RAM dumped straight after.

**Threads (`hostsplit.py`):** tid 28143 is on-CPU 98.1% of the record, the vCPU (28132) 78.3%,
and every other thread under 10%.

**R4, the busy thread is compiling shaders in the Vulkan driver.** 97.9% of 28143's samples
have a `vulkan.purple.so` (Turnip) frame; the chains are truncated inside the driver (no unwind
info past it), and their outermost frames are `tu_spirv_to_nir` (3,824, 65%), `tu_shader_create`
(1,229, 21%) and `link_opts` (568, 10%). The leaves are Mesa NIR passes (`match_expression`,
`nir_algebraic_impl`, `dce_cf_list`, ...). **So 96% of the thread is Turnip turning SPIR-V into
GPU code**, which is what `vkCreateGraphicsPipelines` does for a pipeline it has not seen. The
63 samples whose chain does reach libxemu go through `pgraph_vk_bind_shaders` ->
`shader_cache_entry_init` -> `pgraph_vk_create_shader_module_from_glsl` (glslang) on the same
thread: the PFIFO thread's own draw-time bind path, not the compile worker. `async_compile` is
off (the default, `SettingsActivity.kt:69`; not set in the prefs), so every new pipeline is
compiled synchronously, inside the pusher, before its draw is recorded.

Why the perflog soak's phase line did not show it (`Shd 0.0` over its 14 s stall) is not
resolved here. Whatever the reason, the phase timers under-count this stall, and a phase line
cannot be used to rule compile work out of it.

**R1, the guest is idle.** 5,891 vCPU samples; `tbmap.py` maps 682 of its 1,096 JIT samples
(62%; 4 of 4 promote pcs are headers; frequent-delta share 75.8%, the same shortfall as
session 1). **91% of the mapped samples (621 of 682) are the kernel idle loop's TBs**:
`8001b030` 226, `8001b043` 161, `8001b02e` 145, `8001b02f` 89. Title code is 5.3%. The host
side agrees: 77% of the vCPU's samples are leaf `cpu_exec_loop`, half of all of them on two
instructions (`0x447824`/`0x447828` in this apk's `libxemu.so`: the `dmb ish; ldar
interrupt_request` at `cpu_handle_interrupt`'s head), which the idle loop's `sti` (a TB end with
an inhibit-IRQ exit) runs on every pass. `[jc425]` in the stall: exec-loop lookups 58 k per 2 s,
`lookup_tb_ptr` hits 79-82 M per 2 s. So the vCPU at 98% is the guest idling, not loading.

**The mechanism (M2, confirmed on this load):** the scene load's first draws need pipelines
that are not in the Vulkan pipeline cache. With `async_compile` off, the PFIFO thread compiles
each one synchronously in Turnip (96% of its time, one core pegged). The pushbuffer drains only
between compiles (the closing `fifoskew` of each stall: 28-127 kicks drained in 13-14 s, up to
425 ms per kick). The title's thread blocks in a kernel wait for the GPU, the guest drops into
the kernel idle loop, and nothing flips: **one guest frame of 12.4 s** (`G` max 12402.3 ms in
session 2's cold launch). With the pipelines already in the cache (session 2, launch 2) the same
load stalls **3.1 s instead of 12.9 s**: about 9.8 s of the 12.9 s (76%) is compile.

| reading | pre-registered | measured | verdict |
|---|---|---|---|
| R1 idle share | >= 50% in one small spin | 91% in the 4 idle-loop TBs | holds |
| PFIFO on-CPU in the stall | refuted if < 30% | 96.7% (s2 taskio), 98.1% (s3 record) | holds |
| R4 one call path | >= 50% | 96% under Turnip's SPIR-V -> NIR -> ir3 compile | holds |
| R5 warm vs cold | compile: warm <= half | 3.1 s vs 12.9 s | holds |
| M1 disc | R2 above the fight's rate | 0.0 KB/s in the cold stall | refuted |

## 6. Pre-registration for session 4 (committed before it runs)

The stall profiled above is the menu -> first fight load. The brief's is the one after a
ring-out, which the source run hit 44 s after `mark play`. Session 4: one cold launch, a 440 s
soak, recording the first stall *after* `mark play` (`AFTER="mark play"`).

**Prediction:** if a stall of >= 8 s comes after `mark play`, it has the same mechanism: the
PFIFO thread >= 80% on-CPU with >= 80% of its samples under `vulkan.purple.so`, and >= 50% of the
vCPU's mapped JIT samples in the kernel idle loop.
**Refuted if** the PFIFO thread's samples under the driver are < 50%, or the vCPU's idle share
is < 20%: the ring-out hang is then another mechanism, and this lane's fix does not cover it.
**Inconclusive if** no stall of >= 8 s comes after `mark play` (the fight did not ring out), or
the only one is shorter: then the ring-out case stays inferred from the source run's counters,
not measured.
