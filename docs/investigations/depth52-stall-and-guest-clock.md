# #52: the "stall", the backward guest clock, and the "26 missing tests"

Three anomalies were recorded against #52's full-oracle run
`1789320304-depth52-A-599886` and none of them had an explanation. All three
are answered by artefacts that were already on disk. No device run was
needed and none was requested.

The three, and the short answers:

| anomaly | answer |
| --- | --- |
| a repeating ~-24.3 s backward jump of the guest clock | a 64-bit overflow in the **guest's** TSC->ns conversion; period 25.1547 s; nothing to do with the stall |
| the run stalled inside `DepthFmt_z24_Cy_FZn_Maaaaaf` | Android **minimised the app**; the named test is just whichever one was running |
| "one run reached 654 of 680 tests, so 26 are missing" | those are PNG **files**, against a denominator that is the corpus's own union; the real gap is **65 tests** |

---

## 1. The backward clock jump is a guest-side 64-bit overflow

### What is measured

19 negative per-test durations across the only two progress logs on disk that
record durations at all: 12 in `depth52-A`, 7 in `depth52-cn`. Every one is
close to -24.3 s (-24,083 to -24,344 ms).

The guest computes them in `nxdk_pgraph_tests`,
`src/tests/test_suite.cpp:426`:

```cpp
auto now = std::chrono::steady_clock::now();
auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time);
auto elapsed = static_cast<long>((duration.count() & 0xFFFFFFFF));
```

The mask makes the value non-negative before the cast, and `long` is 32-bit on
nxdk, so a printed -24,338 means the true millisecond difference was congruent
to -24,338 mod 2^32. The only physically possible member of that class is
-24,338 itself; the alternative is 49.7 days. **So `steady_clock` genuinely
moved backwards.**

### The events are periodic, and the period equals the jump

Accumulating only the positive durations between consecutive negative rows:

```
depth52-A   12 events, spacing 23.6 - 24.8 s of positive test time (28-30 tests)
depth52-cn   7 events, spacing 23.7 - 24.6 s of positive test time (25-29 tests)
```

Adding back the ~0.87 s that the wrapped test itself contributes puts the real
spacing at ~25.1 s -- the same size as the jump. *Jump magnitude equal to
event spacing* is the signature of a counter wrapping, not of a clock being
reset or resynchronised: a reset would produce a jump whose size depended on
where in the period it happened, and the observed spread is only 136-169 ms,
which is just the spread of one test's duration.

### The constant, derived rather than fitted

`3375000` -- the Xbox ACPI PM timer frequency, and the frequency of the
emulated timer in `hw/acpi/core.c` under `XBOX` -- **does not appear** in the
disc image. `733333333` does, exactly once. That is the Xbox CPU frequency,
and on Xbox the performance counter *is* the TSC: `KeQueryPerformanceFrequency`
returns 733,333,333.

If the guest converts with `ns = tsc * 1000000000 / 733333333`, the 64-bit
numerator overflows every `2^64 / 1e9` TSC ticks, and the value the guest
reports drops by

```
2^64 / 1e9 / 733333333 = 25.1547 s
```

Nothing in that expression is fitted to the logs. **Prediction:** adding
25.1547 s back to each negative duration must reconstruct an ordinary test
duration -- one inside the range of the positive durations in the same file.
It can fail: an error of a few hundred ms in the period puts the
reconstructions outside that range.

```
depth52-A    positives n=314  min= 770  median=869  max=1116
             reconstructed n=12  min= 811  median=860  max=1072   12 of 12 inside
depth52-cn   positives n=189  min= 714  median=878  max=1124
             reconstructed n= 7  min= 816  median=886  max= 952    7 of  7 inside
```

19 of 19. The medians land within 9 ms of the medians of the positive
distributions they have to belong to.

### Cross-checks

**The host window.** Reconstructing `depth52-A`'s whole timeline with this
period gives `sum(printed) + 12P = -16.3 + 12 x 25.1547 = 285.6 s`. The app's
logcat window -- Android's clock, wholly independent of the guest's -- is
293.5 s, and the first rendered frames appear 2.4 s in. That leaves ~8 s for
boot, disc load and the unfinished test, which is right. A period of 25.8 s
or more overruns the host window outright; a period of 18.4 s (what you would
get if the emulated TSC ran at 1 GHz rather than 733 MHz) leaves 84 s of boot
in one run and 57 s in the other, which cannot both be the same boot.

**The host clock never moves backwards.** `vblphase` reports a `neg=` count of
backward deltas every 2 s. Across all 885 logcats on disk: **13,398 windows,
every one `neg=0`.** So this is the guest's view of time, not Android's and
not the emulator's own.

### Where it points

At the **guest**, not at hakuX. The overflow is in nxdk's TSC-to-nanoseconds
conversion, in `nxdk_pgraph_tests`' toolchain, and it affects every nxdk
program that uses `std::chrono::steady_clock` for more than 25 s. It needs no
change in this repository.

It is worth knowing anyway, because it is a standing ~25 s sawtooth on every
guest-side duration the test harness prints, and any defect filed on
guest-reported timing should be checked against it first.

**What could not be established.** The nxdk submodule is not checked out on
this machine (`third_party/nxdk` is empty), so the conversion was inferred
from the disc image's constants and confirmed against the logs, not read in
source. The identification is strongly supported and not proven. What would
settle it: one `grep` for the expression in a populated nxdk tree.

### What the instrument cannot see

Only **2 of the 792** progress logs on disk record per-test durations. The
other 790 use a `[n/m]` progress format with no duration and *could not have
shown a negative one*. So the rate is 2 of 2 logs that could show it, with no
negative control. That is enough to convict these two runs; it is not evidence
about the fleet. (This is `lane.falsifiers`' own correction, re-verified here:
the count is 790 unreadable, not 771.)

---

## 2. The stall is Android minimising the app

### The finding

`depth52-A`'s logcat does not trail off. It ends:

```
09-13 10:30:06.045  vbl n=120 ... rate=59.947Hz        <- still rendering normally
09-13 10:30:06.730  fifoskew win=2014ms kicks=1096 ...
09-13 10:30:06.813  android: window minimized
09-13 10:30:06.813  android: app entering background, flush requested
09-13 10:30:06.813  deferred bdrv_flush_all completed
```

and nothing follows, for the remaining ~1,500 s until the 1,800 s timeout.
There is no `android: window restored`.

`ui/xemu.c:798-804` handles `SDL_WINDOWEVENT_MINIMIZED` by setting
`g_android_paused = true`, which gates the display/refresh path at
`ui/xemu.c:1582`, `1593` and `1848`. Emulator output stops there and never
resumes.

### It is not pace, and not a run budget

The reconstructed guest timeline ends at 285.6 s and the minimise lands at
293.5 s: **the stall coincides with the minimise to within the boot slack.**
The guest did not slow down and did not hit a bad test -- the app was
backgrounded mid-test, and `DepthFmt_z24_Cy_FZn_Maaaaaf` is simply the test
that happened to be running.

### The control, so "1 of 885" is not read as a rate

Only **1 of 885** logcats on disk contains `window minimized`, and it is this
run. On its own that could be trivial -- most runs are far too short to be at
risk (693 of 885 are under a minute). The control that matters is the long
runs:

```
logcats spanning >= 240 s :  50    minimized: 1
logcats spanning >= 280 s :  13    minimized: 1
logcats spanning >= 300 s :  12    minimized: 0
```

**Twelve runs ran longer than this one -- 1147 s, 977 s, 956 s, 697 s, 471 s --
and none was minimised.** So this is not a five-minute screen timeout and not
a fleet-wide run ceiling; it is a one-off lifecycle event on one run.

*Why* Android minimised it is not recoverable from these artefacts. The logcat
carries no `ActivityManager` lines (the capture is filtered to the app), so a
notification, a touch, a thermal action and a dispatcher action are all
indistinguishable here. **What the instrument cannot see:** an unfiltered
logcat would show it; a filtered one never can, so its silence is not
evidence.

### Consequences for #52

- The Cy half needs a **rerun**, not a diagnosis and not a larger timeout.
- "The Cn half sidestepped the stall" stays refuted, and now has a mechanism:
  the Cn retry finished in 185 s and was simply never backgrounded.
- The `--only-tests` arm on the Cy tail that the blocker proposed as the
  "cheapest disambiguation" would answer nothing -- there is nothing wrong
  with those tests.

---

## 3. There are 65 missing tests, not 26

`654 of 680` are counts of **PNG files**, not tests. Each test writes two
(`<name>.png` and `<name>_ZB.png`). The run's directory holds 654 PNGs =
**327 tests**, of which 262 PNGs = 131 tests are `Cy`.

The denominator is the problem. 680 is not the suite size: it is
**2 x 340**, and 340 is the number of distinct `Depth_buffer` tests captured
by *every run on disk put together*. Scoring a run against the union of what
the corpus has ever produced cannot show what the corpus has never reached.

The suite's real size is settled by the goldens: `~/goldens/results/Depth_buffer`
holds **784 files = 392 tests**, and every one of the 340 tests ever captured
has a golden (`union - goldens` is empty), so the golden set is a superset and
the right denominator.

```
suite (goldens)                           392 tests
captured by depth52-A                     327 tests   ->  65 missing
captured by every run on disk, unioned    340 tests   ->  52 never captured by anything
```

The 65 `depth52-A` never reached are exactly the tail of the run order:

- **16 of 49** in `z24_Cy_FZn` -- `Mb00004` through `Mffffff`, i.e. everything
  after `Maaaaaf`, the test it stopped inside;
- **49 of 49** in `z24_Cy_FZy` -- the entire cell, never started.

Both are contiguous suffixes, which is what a run that stops mid-sequence
produces, and it corroborates the minimise independently of the logcat.

The `26` of the original figure is `680 - 654` = 26 PNG files = **13 tests** --
the 13 that other runs happen to have captured and this one did not. The other
52 are invisible to that arithmetic because they are missing from the
denominator too.

**What the instrument cannot see:** capture counts cannot distinguish "the run
never reached this test" from "this test is not on the 2025-03-14 disc". The
52 never-captured goldens are consistent with either. The run-order evidence
says the first kind for these particular 52 -- they are contiguous suffixes of
two cells, and a retired test would not sort that way -- but that is an
inference from ordering, not a measurement.

---

## Cost

Zero device time. All of it is `dispatch/results/`, the golden set, the disc
image and `ui/xemu.c`.
