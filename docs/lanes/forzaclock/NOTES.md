# lane.forzaclock: why Forza's game clock runs at about 26% of real time (#414, #462)

Base master e5db66fa37. Title 4D53006E (Forza Motorsport), Ayn Thor. No device
time was used. Everything below reads two runs already on disk:

- `1790450265-forza414-1731727`: perflog, apk 853368f2e827, 13:42-13:49 PDT,
  race at 14-20 fps throughout.
- `0-0-y-1790433159-titleplay-p1-forza`: non-perflog, apk 25abcaccbf45,
  11:42-11:49 PDT. It holds the 12-20 fps race and then the 2-3 fps step at
  11:47:28.

## Answer: world (a). The race clock is a frame counter

Forza advances its race clock by exactly 1/30 s for each frame it renders.
No emulated timebase is slow. Slow frames mean slow motion, and fixing fps
fixes the clock. The clock is not a defect of its own.

### 1. Every clock reading is an integer number of 1/30 s ticks

These are the RACE readings off the HUD in all 13 play screenshots of the two
runs. Each is k/30 s to within the display's 1 ms rounding:

| run | readings (s) | k = reading x 30 | max error |
|---|---|---|---|
| 1790450265 | 24.767, 44.066, 64.233, 78.732, 95.332, 115.599 | 743, 1322, 1927, 2362, 2860, 3468 | 1.3 ms |
| 1790433159 | 17.967, 32.133, 48.800, 52.066, 55.333, 58.499, 61.433 | 539, 964, 1464, 1562, 1660, 1755, 1843 | 1.3 ms |

A clock that samples a real-time timer (TSC, ACPI PM timer, KeTickCount)
would show arbitrary milliseconds. A clock that steps by elapsed VBLANKs would
show multiples of 1/60, and the chance that 13 of those all land on even
counts is 1 in 8192.

### 2. Clock advance equals flips / 30, and not VBLANKs / 60 or wall time

`clockcount.py` sets Δrace between consecutive screenshots against the flips
(`hakuX-pace f=`) and VBLANKs (`vb=`) interpolated to each `shot play` time
in run.log:

| run, interval (PDT) | Δwall s | Δrace s | race/wall | Δflips | Δrace x 30 | ratio | ΔVBLANKs | Δrace x 60 |
|---|---|---|---|---|---|---|---|---|
| 450265 13:46:57-13:47:28 | 31.23 | 19.299 | 61.8% | 575.8 | 579.0 | 1.006 | 1863 | 1158 |
| 450265 13:47:28-13:47:58 | 30.35 | 20.167 | 66.5% | 616.1 | 605.0 | 0.982 | 1798 | 1210 |
| 450265 13:47:58-13:48:28 | 29.24 | 14.499 | 49.6% | 457.3 | 435.0 | 0.951 | 1739 | 870 |
| 450265 13:48:28-13:48:57 | 29.59 | 16.600 | 56.1% | 506.4 | 498.0 | 0.983 | 1759 | 996 |
| 450265 13:48:57-13:49:27 | 30.13 | 20.267 | 67.3% | 600.7 | 608.0 | 1.012 | 1791 | 1216 |
| **450265 total** | 150.53 | 90.832 | 60.3% | 2756.3 | 2725.0 | **0.989** | 8950 | 5450 |
| 433159 11:46:35-11:47:02 | 27.62 | 14.166 | 51.3% | 429.4 | 425.0 | 0.990 | 1641 | 850 |
| 433159 11:47:02-11:47:31 | 28.56 | 16.667 | 58.4% | 504.3 | 500.0 | 0.991 | 1699 | 1000 |
| 433159 11:47:31-11:47:59 (step) | 28.59 | 3.266 | 11.4% | 106.0 | 98.0 | 0.924 | 1712 | 196 |
| 433159 11:47:59-11:48:26 | 26.30 | 3.267 | 12.4% | 90.3 | 98.0 | 1.085 | 1577 | 196 |
| 433159 11:48:26-11:48:54 | 28.75 | 3.166 | 11.0% | 98.9 | 95.0 | 0.960 | 1723 | 190 |

Δrace x 30 tracks the flip count within 1% over 2756 flips, and it does so
through a 5x change in frame rate. In the 3 fps rows the pace windows are
15-19 s long, so the linear interpolation there is good to about ±8 flips,
which is the spread of those ratios. The VBLANK column is 1.6x to 9x too
large, and wall time is 1.5x to 9x too large. The issue's 26% is the average
of these rows.

The residual ~1% is screenshot latency against interpolated counters. Nothing
in these rows suggests that a frame is ever skipped or doubled.

### 3. The guest's VBLANK is on time under load

The guest-visible VBLANK instrument (`hakuX-perf vbl` / `vblphase`, nv2a.c
`nv2a_vblank_record`) counts every PCRTC VBLANK assertion and every one the
guest had not acknowledged when the next arrived (`coal_en`). In 30-s buckets:

| run | regime | asserted Hz | coal_en per 30 s | guest ISR Hz | mean lateness ms |
|---|---|---|---|---|---|
| 433159 | menus 11:43 | 59.88 | 0 | 59.88 | 0.06 |
| 433159 | race 12-20 fps 11:45:30-11:47:30 | 59.0-59.9 | 0-19 | 58.8-59.7 | 3.0-4.5 |
| 433159 | **2-3 fps, 11:47:30-11:49:30** | **59.87-59.95** | **0-4** | **59.78-59.95** | **0.9** |
| 450265 | race 14-20 fps 13:45-13:49:30 | 58.7-59.9 | 0-4 | 58.6-59.9 | 2.9-4.7 |

So even at 3 fps the guest takes a VBLANK interrupt ~59.9 times a second. If
Forza's clock counted VBLANKs it would run at ~100%, not 12%. The race-regime
lateness (3-4.7 ms mean, with p99 near one period) is the deliberate VBLANK
deferral (nv2a.c:1097-1121, capped at period/2). It shifts phase and leaves
the rate on the grid.

### 4. The other timebases run off wall time by construction

- TSC: `cpu_get_tsc` (hw/i386/x86-cpu.c:35) is
  `muldiv64(qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL), 733333333, 1e9)`.
- ACPI PM timer: `acpi_pm_tmr_get_clock` (hw/acpi/core.c:497) scales
  `QEMU_CLOCK_VIRTUAL`.
- PIT: i8254.c reads `QEMU_CLOCK_VIRTUAL` for counts and reloads.
- Nothing under android/ enables icount, so `QEMU_CLOCK_VIRTUAL` is host
  monotonic time while the VM runs. None of the three can run slow because
  of guest load. Interrupt-driven ticks (PIT IRQ0 to KeTickCount) could drop
  if interrupts were held off, but VBLANK delivery (section 3) shows that the
  guest takes interrupts at full rate. Sections 1-2 make the question moot in
  any case, because the race clock does not read a timer.
- APU timers were not examined. No timer reading can produce the k/30
  quantization, so they cannot be the race clock.

No per-timebase read counter exists (TSC/ACPI/PIT reads per window). None
was needed: the HUD quantization and the flip ratio identify the clock
without one.

## What the fix is, and what it buys

- **Clock fix: none needed.** On this evidence, race clock rate =
  min(fps, 30) / 30. Forza's race is a 30 Hz fixed-step simulation, and on
  hardware it holds 30 fps. The clock reaches 100% exactly when race fps
  reaches 30, and the fps work on #414 (the ~5.5 uncoalesced `SURFACE_DOWN`
  finishes per frame, `sd_complete_def`, vk/surface.c, lane.forza414
  section 6) is the whole fix.
- **What a timebase fix would buy: 0% clock and, as a bound, 0 fps in the
  race.** The race frames are renderer-bound: Ri 0.1 ms per frame, and vCPU
  busy 1821-1930 ms per 2 s (3.5-9% idle, `[tlb68]` cpu). A shorter wait on
  VBLANK or a timer can free at most that idle share of guest time, and it
  cannot shorten a frame whose critical path is the renderer. That is an upper
  bound, not a measured value.
- **What the fps fix should buy (a bound, from lane.forza414 section 6, not
  re-measured here):** frames at max(Tot - Sub, GPU R) = 22-32 ms (31-45 fps), so
  30 fps once capped, against 14-20 today. The clock would go from 50-67% to at most 100%
  in the race regime. The 2-3 fps step (12% clock) has its own unnamed cause
  (lane.forza414 section 1). The same identity holds there: clock = fps/30.

## Do not repeat

- Do not look for a slow timer behind Forza's clock. The HUD reading is k/30 s
  and tracks flips to 1%. Read `clockcount.py` output instead.
- Do not report Forza's game-clock ratio as a separate symptom in a title
  verdict. It is fps/30 and double-counts the fps defect.
- Do not queue a device run for this question. The two runs on disk settle it.
- `hakuX-pace f=` is a cumulative flip counter and `vb=` is per window. Sum
  the `vb` values to get cumulative VBLANKs.

## Tool

`clockcount.py <result dir> <RACE readings in seconds, in shot order...>`.
The readings come off each `*-play.png` HUD (top right) by eye.
