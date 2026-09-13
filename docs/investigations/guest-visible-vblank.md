# Guest-visible VBLANK timing

Opened 2026-09-12 on `7821f995b5`. Instrument at `5309ae3957`, `6598c032cc`,
`19f52510d9`. Reader in `docs/testing/vblank_report.py`.

Frame pacing has been looked at twice as a performance question — how fast we
go. This is the other half of it. **A title reads VBLANK, times against it,
and makes decisions.** If our period, its jitter, or its phase relative to a
flip differ from the NV2A's, then animation and physics stepped off VBLANK run
at the wrong rate, a title that double-buffers against VBLANK sees a different
cadence, and anything that measures elapsed time by counting VBLANKs gets a
wrong answer.

**None of that moves a pixel.** A framebuffer records what was drawn, never
when. So the whole golden corpus is bit-identical whether our refresh is
59.94 Hz or 50, which is why nothing on the tracker covered any of this before
#60 and #61, and why the only way to find out was to measure.

What `frame-pacing-and-parallelism.md` already established and this does not
re-derive: Crimson Skies' 30 fps floor is the game's own, and the emulator
delivers exactly 2.00 VBLANKs per flip while it holds. That is a title
synchronising correctly against our VBLANK, and it is real evidence the period
is approximately right. *Approximately* is what follows.

## VERIFIED: what we generate

`nv2a_calc_vblank_period_ns`, `hw/xbox/nv2a/nv2a.c:234-242`, derives nothing.
As it stood when this was opened — the guard is **fixed** by "nv2a: bound the
50 Hz branch, so 720p and 1080i stop running at PAL rate", and the section
below is why; the current one is quoted under MEASURED 2026-09-13. (Every sha
in this file is the one the dispatcher built, before the branch was rebased,
which is the same convention #65 uses: it names the tree a measurement was
taken on, not a commit still reachable from the tip.)

```c
uint32_t vdisplay = d->pramdac.fp_vdisplay_end;
if (vdisplay > 480) {
    /* PAL (576i/576p): ~50 Hz */
    return NANOSECONDS_PER_SECOND / 50;
}
/* NTSC / HDTV (480i/480p/720p/1080i): ~59.94 Hz */
return 16683750;
```

One branch on one register, two constants. Both arrived in `7aae57b77d`
("fps stabilization") with no source for either number.

### The guard contradicts the comment directly under it

The comment says the 59.94 Hz branch covers **480i, 480p, 720p and 1080i**.
The guard above it sends 720p and 1080i to the PAL branch, because a display-
end register holds height−1 and both 719 and 1079 are greater than 480.

| mode | intended | taken | error |
|---|---|---|---|
| 480i / 480p | 16,683,750 ns | 16,683,750 ns | +25 ppm |
| 576i / 576p (PAL) | 20,000,000 ns | 20,000,000 ns | exact |
| **720p** | 16,683,750 ns | **20,000,000 ns** | **+19.9%** |
| **1080i** | 16,683,750 ns | **20,000,000 ns** | **+19.9%** |

A title in an HD mode that steps its simulation off VBLANK runs at five sixths
speed; one that counts VBLANKs to measure a ten-second interval reads 8.3 s.
HD modes are a live path, not a hypothetical one — `vk/display.c:1723` and
`gl/display.c:442` both handle 1080i explicitly.

The minimal correct guard is a **bounded** one — PAL is 576 lines and never
more — rather than the open `> 480`.

### The NTSC constant is 25 ppm long

NTSC's field rate is 60000/1001 Hz, so the period is 16,683,333 ns. Ours is
16,683,750.

| | value |
|---|---|
| ours | 16,683,750 ns → 59.93856 Hz |
| NTSC | 16,683,333 ns → 59.94006 Hz |
| error | **+417 ns per field, +25.0 ppm** |
| drift | 0.09 s per hour of play; 1 s lost every 11.1 hours |
| ticks | 5.4 VBLANKs an hour a counting title never sees |

Small, and a one-character fix. Worth recording because the *suspicion* this
stream was opened on — that we might be running a round 60.00 Hz, a 0.1% error
— is 40× larger than what is actually there. That specific worry is retired.

### The fix that subsumes both — proposed here, and MEASURED OUT below

**This does not work, and the whole of MEASURED 2026-09-13 is the reason.**
The proposal is left standing because it is what P7 tested and what two
further arms closed: the reader who arrives with the same idea should see it
arrived at honestly and then measured out, rather than never mentioned.

Derive it the way the NV2A does: `vtotal * htotal / pixel clock`. Every
ingredient is programmed by the guest into registers this tree already models
— the CRTC totals in the VGA register file, and the pixel clock in
`NV_PRAMDAC_VPLL_COEFF`, which `pramdac.c:108` stores and **nothing has ever
decoded**, unlike `NV_PRAMDAC_NVPLL_COEFF` right beside it at
`pramdac.c:92-100` which is decoded into a frequency.

A derivation needs no table and no guard and gets every mode right at once.
It is conditional on the guest programming those registers with the encoder's
timing, which is what the `vblmode` log line exists to settle.

## VERIFIED: what the guest actually sees, which is not that period

### Deferral shifts the phase grid and never repays it

`nv2a_vblank_timer_cb` holds a VBLANK back when the guest is mid-frame
(`nv2a.c:625-637`), by up to `poll_interval * defer_cap` — half a period in
normal mode, a whole one in unlock mode. Then, at `nv2a.c:686-692`:

```c
if (was_deferred || unlocked) {
    d->vblank_next_target_ns = now + period;
} else {
    d->vblank_next_target_ns += period;
    if (d->vblank_next_target_ns <= now) {
        d->vblank_next_target_ns = now + period;
    }
}
```

The non-deferred branch keeps a **fixed grid**. The deferred branch throws it
away and restarts from wherever the late VBLANK landed, so every deferral is a
permanent forward shift of phase that is never made up. The comment above it
says as much and treats it as the point: resuming from the scheduled position
"caus[es] a cascade where every subsequent frame also misses — locking the game
to 30fps". That is a deliberate trade of the guest's timebase for frame rate,
and only one side of it has ever been priced.

**The error is one-sided.** Every path either advances the grid by exactly one
period or resets it to `now + period`, and a QEMU timer cannot fire early. So a
VBLANK can arrive late and never early; it does not average out, it
accumulates as a slow clock.

**And the rate is a function of the guest's own rendering.** Deferral is gated
on `d->flip_active` — it only happens while a title is drawing. So the rate of
the clock a title times against is modulated by what that title is drawing,
which on hardware it categorically is not.

### In unlock mode there is no grid at all, and it is on by default

Read the condition again: `if (was_deferred || unlocked)`. The second
half of it is not about deferral at all. While
`unlock_mode_active` is set, **every** VBLANK resets the target to
`now + period`, deferred or not, where `now` is when the callback actually ran.
A QEMU timer fires at or after its target and never before, so in unlock mode
the timer's own lateness is added to the period on every single VBLANK and
compounds instead of being absorbed by a fixed grid. A mean lateness of 0.3 ms
is a permanent 16.98 ms period — 58.9 Hz, 1.8% slow, for as long as the mode
is held.

`unlock_framerate` defaults to **true** (`xemu_android.cpp:642` and `:916`,
`SettingsActivity.kt:66`), and the mode is entered whenever smoothed frame time
is under 1.5 periods — that is, whenever a title is running above about 40 fps.

So the titles whose pacing looks healthiest are exactly the ones running with
no phase grid, and the titles that already miss their deadline are the ones
that keep it. That inverts the intuition, and it means Crimson Skies' clean
2.00 VBLANKs per flip in `frame-pacing-and-parallelism.md` is evidence about
the *locked* path only: at two periods per frame it can never satisfy the entry
condition, so it never leaves the fixed grid.

### `simple_vblank` runs two sources at once

The flag is off by default (`xemu_android.cpp:979`, per-game overridable, a
"debug" setting in `SettingsIndexActivity.kt:143`). When it is on:

- the period timer fires VBLANK (`nv2a.c:507`), **and**
- `nv2a_vga_gfx_update` fires it again on every host display refresh
  (`nv2a.c:722-725`), driven from `ui/xemu.c:2217`.

On a 90–120 Hz handheld that is 150–180 assertions a second where hardware
gives 59.94. The comment at `nv2a.c:720` admits it "makes games run too fast".

### Two of the existing pacing numbers cannot see any of this

- `pacing.vblank_fired` counts only the timer source, so in simple mode `Vpf`
  (VBLANKs per flip) is a count of *one of the two things* pacing the guest.
- `s_last_vblank_fire_ns` is written only on the adaptive path, so `J` reads
  **0.0 in simple mode because it was never written**. The 0.0 ms jitter in the
  `simple_vblank` row of `frame-pacing-and-parallelism.md` is that artefact and
  not a clean VBLANK.
- `J` is in any case an exponential mean of |delta − period|. For jitter a mean
  is the wrong summary: a correct mean with a 10 ms tail is a different defect
  from a wrong mean, and the mean cannot tell them apart.

### PCRTC coalesces, so an unacknowledged VBLANK is a lost tick

`pcrtc.c:58` is the only place `NV_PCRTC_INTR_0_VBLANK` is cleared, and it is
the guest's own write. Asserting it while the bit is still set is a no-op, so
an assertion that arrives before the ISR has acknowledged the previous one is a
tick the guest never sees. A title counting VBLANKs to measure time loses it
outright. Nothing counted those before this stream.

### `PCRTC_RASTER` is not a scanline

`pcrtc.c:39` is `r = d->pcrtc.raster++`: the register advances **once per
read** and is zeroed at VBLANK. On silicon it is the line the beam is on,
advancing at the horizontal rate — about 262 counts across an NTSC field — so a
title can read it to find where in the frame it is, or spin on it to wait for a
line, and get an answer proportional to elapsed time. Here the answer is a
function of how many times it has asked.

Whether that is a defect or a dead register depends entirely on whether
anything reads it, which nothing had ever counted. The instrument counts it.

## The instrument

`hw/xbox/nv2a/nv2a.c` accumulates a histogram at every point where
`NV_PCRTC_INTR_0_VBLANK` is asserted — the assertion, not the timer callback,
because those are not the same set — and dumps two lines under `hakuX-perf`
every two seconds. 50 µs buckets over 0–51.2 ms.

Cost is one clock read and one array increment per assertion at 60–180 Hz. A
log line per VBLANK was the obvious alternative and would have perturbed what
it measures, the same way the per-draw diagnostic path would have closed the
race it was proposed for.

`hakuX-perf` was chosen because `LOGCAT_SPEC` already carries it. Tag filters
are exact and not prefixes, so a new tag would have been silently dropped.

## MEASURED

Galleon, 240 s, **Thor**, ref `19f52510d9`, dispatch result
`1789275041-vblank-timing-4013526`. 14,653 VBLANK assertions in 129 two-second
windows. Split by how many of them went through the adaptive deferral, because
a pooled mean over the two regimes looks like one mildly wrong regime instead
of one correct one and one badly wrong one.

| regime | windows | mean interval | delivered rate | p99 | lost per minute |
|---|---|---|---|---|---|
| **no deferral** | 36 | 16,712,711 ns | **59.844 Hz** | 16,850,000 ns | 0.11 s |
| 1–20 defers | 48 | 17,198,838 ns | 58.186 Hz | 25,050,000 ns | 1.85 s |
| >20 defers | 45 | 19,159,610 ns | **52.285 Hz** | 25,500,000 ns | 8.91 s |
| **whole soak** | 129 | 17,747,165 ns | **56.587 Hz** | 25,100,000 ns | **3.83 s** |

Intended: 16,683,750 ns / 59.939 Hz. Extremes over the soak: min 7,090,520 ns,
max 61,904,479 ns.

### The period is right; the machinery around it is not

**With deferral off the mean is 0.17% above the intended period and p99 is
within 1% of it.** Our VBLANK is correct to about 29 µs in the mean and 170 µs
at p99. That is the result worth having on its own: it closes a class of
suspicion that had no evidence either way.

**The deferral takes the delivered rate 5.6% below what we intend** across the
soak, and 12.8% below it in heavy scenes. A title counting VBLANKs to measure a
minute of play is short by 3.8 seconds, or 8.9 in a heavy scene.

### The shape, which is the whole question for jitter

A very sharp mode at the right period, plus a long right tail:

| | ns |
|---|---|
| p50 | 16,700,000 |
| p90 | 16,750,000 *(no-deferral windows)* / 25,750,000 *(heavy)* |
| p99 | 25,100,000 (worst window 28,700,000) |
| max | 61,904,479 |

So "is the jitter bounded?" has two answers depending on which question is
being asked. The **mode** is accurate to 0.1%. The **tail** is not bounded at
all: p99 is 1.5× the period and the extreme is 3.7×.

`J` in the existing pacing line — an exponential mean of |delta − period| —
reads 0.0 to 2.8 ms over this same material. It cannot tell a 0.25 ms
symmetric jitter from a mode accurate to 0.1% with a 28 ms tail, and those are
different defects.

### Falsifiers, as registered before the run

| | prediction | outcome |
|---|---|---|
| P1 | def>20 mean exceeds intended by ≥ 500,000 ns | **holds** — +2,475,860 ns |
| P2 | def>20 p99 ≥ 25,000,000 ns | **holds** — 25,500,000 ns |
| P3 | `vd` ≤ 480, so the NTSC branch is taken | **holds** — `vd=479` throughout |
| P4 | `coal` > 0 somewhere | **holds** — 229 of 14,653, 1.56% |
| P5 | `smp=0 gfx=0`, simple_vblank off by default | **holds** |
| P6 | `rast=0/0`, this title never reads PCRTC_RASTER | **holds** — 0 across the soak |
| P7 | the CRTC/VPLL derivation lands within 1% of 16,683,333 ns | **FALSIFIED** — 12,293,443 ns, −26.3% |
| P8 | some intervals are shorter than a period | **holds** — min 7,090,520 ns |

**P7 is the important failure.** Every window reports, identically:

```
vblmode want=16683750 derived=12293443
        (vtotal=525 htotal=728 pixclk=31089742 vpll=0003c20d m=13 n=194 p=3)
        cr00=56 cr06=0b cr07=3e cr25=10 cr2d=00 msr=e3 vd=479 il=ff res=640x480
```

`vtotal=525` is exactly right for NTSC and `cr25=0x10` carries no vertical-total
extension bit, so that half of the derivation is sound. The gap is in `htotal`
(91 character clocks, with `cr2d=0x00` setting no horizontal extension bit), or
in the VPLL decode, or in the premise: the Xbox drives an external video
encoder, and the digital stream timings it programs into the NV2A CRTC need not
be the analog NTSC ones at all.

So **the derivation proposed above is not available on what we model today**,
and the fix for #64 is a table keyed on something authoritative about the video
standard. What that something is, is now the open measurement.

**P8 also corrected a mid-flight re-derivation of my own.** After queueing I
argued P8 would fail, on the grounds that every path either advances by a
period or resets to `now + period` and a QEMU timer cannot fire early. That
missed the case that matters: the fixed-grid branch advances from the
*scheduled* position, so a late callback leaves the next target less than a
period away and the short interval that follows is the grid correcting itself.
The 7.1 ms intervals are that correction working. Recorded because it is
exactly the correction the deferred branch discards, and I would not have
looked for it if the prediction had been quietly withdrawn.

### What this run could not exercise

- **Unlock mode.** `Ul:N` on all 129 windows — Galleon's frame time is about
  two periods, so it can never satisfy the entry condition. The free-running
  grid in unlock mode is therefore a source reading and not an observation.
  It needs a fast title; Ninja Gaiden Black ran 55–75 fps in
  `frame-pacing-and-parallelism.md`.
- **HD modes.** `vd=479 res=640x480` throughout. The `> 480` guard is wrong on
  the arithmetic whatever a 720p title would report, but the size of the
  exposure is unmeasured.
- **`PCRTC_RASTER`.** `rast=0/0`. Galleon never reads it, so the per-read
  counter is latent here with no demonstrated symptom.
- **The Nova.** This ran on the Thor, because the Nova worker died at 21:46:43
  re-execing and the request had to be re-routed. Both are kalama/Adreno 740,
  and `devices.sh` is explicit that they are not interchangeable until proven
  so, so every figure above is a Thor figure.


## The fix, and the one leg that could sink it

`ed5df55ccc` is one token: `if (was_deferred || unlocked)` becomes
`if (unlocked)`, so a deferred VBLANK advances the grid instead of restarting
it. The prediction is registered and **committed first** at `bace14275d`
(`docs/testing/predictions/vblank-grid-deferral.json`), because `ab_compare`
cannot score a soak and the commit date is therefore the only binding
available.

- **B1** def>20 mean interval falls by ≥ 1,000,000 ns from 19,159,610.
  *Fails* if it moves less than 300,000 ns — the world where deferrals
  routinely exceed a period, so the `<= now` clamp discards the grid anyway.
- **B2** whole-soak delivered rate rises above 58.000 Hz from 56.587.
- **B3** def==0 windows stay within ±50,000 ns of 16,712,711. The within-run
  control: Galleon's scene varies between soaks, and this is the regime the
  change cannot reach, so it has to stay put whatever else moves.
- **B4, the cost.** Median `gfps` does not fall by more than 2. **This is the
  leg the old comment predicts will fail.** At a drop of three or more the
  trade it made is real, and it is the deferral that needs reworking rather
  than the grid restoring.
- **B5** deferrals per window rise, because a VBLANK arriving sooner after a
  deferral lands inside the next deferral window more often. *Fails* if they
  fall, which would mean the loop is not what I think it is.

`unlocked` is deliberately left resetting the grid. It is the same defect, this
arm cannot measure it, and moving two things at once would make the half it can
measure unreadable.

### Verdict: 5 of 5, including the leg the old comment predicted would fail

Arm B is dispatch result `1789275582-vblank-grid-B-4057320`, same title, same
240 s, same device, binary `9fcf8ecc4642` against arm A's `38402524d163`.

| regime | A mean | A rate | B mean | B rate |
|---|---|---|---|---|
| def==0 *(control)* | 16,712,711 ns | 59.844 Hz | 16,718,178 ns | 59.825 Hz |
| def 1–20 | 17,198,838 ns | 58.186 Hz | 16,759,454 ns | 59.681 Hz |
| def>20 | 19,159,610 ns | 52.285 Hz | **16,701,985 ns** | **59.884 Hz** |
| whole soak | 17,747,165 ns | 56.587 Hz | **16,721,058 ns** | **59.816 Hz** |

| leg | outcome |
|---|---|
| B1 def>20 mean falls ≥ 1,000,000 ns | **holds** — fell 2,457,625 ns |
| B2 whole-soak rate above 58.000 Hz | **holds** — 59.816 Hz |
| B3 def==0 control within ±50,000 ns | **holds** — moved 5,467 ns (0.03%) |
| B4 median `gfps` drops by ≤ 2 | **holds** — 29.0 → 29.0, unchanged |
| B5 defers per window rise | **holds** — 15.8 → 28.2 |

Against the real NTSC standard rather than our own constant, the guest's
VBLANK clock goes from losing **3.83 s per minute of play to losing 0.136 s** —
a 28× reduction, and in heavy scenes from 8.91 s/min to 0.067 s/min.

**The trade the old comment made is not there.** Deferrals nearly doubled, as
B5 predicted — a VBLANK arriving sooner after a deferral lands inside the next
deferral window more often — and the frame rate did not move at all. The
cascade it feared did not happen on this title.

Two things deliberately did *not* improve, and should not have:

- **p99 is unchanged**, 25,100,000 → 25,150,000 ns. Individual VBLANKs are
  still late; the deferral still distorts phase *within* a frame. What it no
  longer does is steal time, because the short interval that follows gives it
  back. Phase and rate are different properties and only the second was fixed.
- **The def==0 control barely moved**, which is the point of having it. Galleon's
  scene varies between soaks and one run per arm cannot rule that out on its
  own; a 0.03% control against a 15% effect can.

The honest limits: one run per arm, one title, one device (Thor), and the
locked grid only — unlock mode was never entered in either arm.

## MEASURED 2026-09-13: the guard, and whether the period can be derived at all

Two soaks, Galleon, 240 s and 90 s, refs `cdc3a4b4d8` and `6eddbdbff5`,
dispatch results `1789278960-vblank-period-1231801` and
`1789279332-vblank-period-1362112`. Both read with `vblank_report.py`, which
now parses two more lines: `vblfp` (the flat-panel raster) and `vblpll` (the
PLL decode against clocks whose right answers are known from outside this
tree).

### The guard: bounded, and interlace-scaled first

`vdisplay > 480` is wrong for the reason #64 states, and the fix is the bound
the comment already implies — PAL is 576 lines and never more, so the 50 Hz
branch is 481..576 and nothing above it. The one thing that needed settling
before trusting that bound was **which register convention the modes report
in**, because 1080i is the mode the bound has to exclude and a 1080i raster
can be described either per frame (1079) or per field (539) — and 539 lands
*inside* the PAL window, so a plain bound would have re-created the bug at a
different value.

The measurement settles the convention on the register itself: `vd=479` with
`res=640x480` on every window of both soaks, so `fp_vdisplay_end` is the last
active LINE and a mode's line count is `vd + 1`. And this tree's own answer
for which modes interlace is unambiguous: `vk/display.c:1723` and
`gl/display.c:442` read `cr[0x39]` for exactly one purpose, "used only in
1080i", doubling the viewport height. So the guard scales for interlace before
it bounds:

```c
if (d->vga.cr[NV_PRMCIO_INTERLACE_MODE] != NV_PRMCIO_INTERLACE_MODE_DISABLED) {
    vdisplay = vdisplay * 2 + 1;   /* per-field raster -> per-frame */
}
if (vdisplay > 480 && vdisplay <= 576) {
    return NANOSECONDS_PER_SECOND / 50;
}
return 16683750;
```

| mode | register | before | after |
|---|---|---|---|
| 480i / 480p | 479, il=ff | 16,683,750 ns | 16,683,750 ns *(measured, unmoved)* |
| 576i / 576p | 575, il=ff | 20,000,000 ns | 20,000,000 ns |
| **720p** | 719, il=ff | **20,000,000 ns** | 16,683,750 ns |
| **1080i, per frame** | 1079, il set | **20,000,000 ns** | 16,683,750 ns |
| **1080i, per field** | 539, il set | **20,000,000 ns** | 16,683,750 ns |
| 576i via NV2A interlace | 287, il set | 16,683,750 ns | 20,000,000 ns |

The last two rows are why the scaling is there rather than a bare bound: it is
right whichever convention 1080i turns out to use, and it *also* fixes the
mirror-image error on an interlaced PAL raster, which a bare bound would have
sent to 59.94. Both are still source readings — no title on hand reaches any
mode but 480 — and the 480-line path real titles do take is untouched by
construction and measured unmoved.

### P7 did not fail by a decode bug, and the arithmetic says so before any device does

With `vtotal=525` fixed and the VPLL decoded at 31,089,742 Hz, a 59.94 Hz
frame needs a horizontal total of **987.96 pixels**. The VGA register counts
whole 8-dot characters, so it would have to hold 123.5 of them — not a value
it can express, and no undecoded extension bit helps, because extension bits
add whole characters. No character width helps either (9 dots → 109.8, 4 dots
→ 247.0 at a clock that is then wrong by two), and no PDIV shift helps,
because halving or doubling the clock preserves the fractional part:

| PDIV | pixel clock | htotal needed at 525 lines |
|---|---|---|
| 3 *(as decoded)* | 31,089,742 Hz | 987.96 px = **123.495 chars** |
| 2 | 62,179,485 Hz | 1975.93 px = 246.99 chars |
| 4 | 15,544,871 Hz | 493.98 px = 61.75 chars |

Repairing the clock instead of the raster fails symmetrically: at the CRTC's
728 pixels the period wants **22,909,091 Hz**, which is this VCO over 10.86 —
not a power of two, so not a PDIV misread — and it would need a 12.28 MHz
crystal, which is not one of the parts.

So P7 was not a misdecode of the CRTC. **The VGA CRTC raster and the VPLL
describe different things**, and the question became which other raster the
chip holds.

### The flat-panel raster is real, and it is exactly half an answer

The NV2A's other timing generator is the PRAMDAC flat-panel block, and it
counts in **pixels** rather than characters, so it can hold 988 where the CRTC
cannot. This tree has always chosen the VBLANK period off `FP_VDISPLAY_END`,
so it already believed the guest programs that block — but `FP_VTOTAL`
(0x804) and `FP_HTOTAL` (0x824) fell through `pramdac.c`'s switch and were
never stored. They are stored now, and the whole block goes out as `vblfp`:

```
vblfp want=16683750 derived_fp=13104000 (fp_vtotal=524 fp_htotal=775
       lines=525 px=776) vde=479 hde=639 vcrtc=479 hcrtc=599 vsync=493
       vvalid=479 hvalid=639 genctl=00101030 sr01=01
```

Byte-identical on every window of both soaks. Two things in it are worth more
than the derivation it fails to support:

- **The guest does program the flat-panel timing generator.** It was not a
  partial write, which was the other outcome this arm was registered to
  detect.
- **`fp_vtotal + 1 = 525`, with 480 active and 45 blanking lines.** That is
  the NTSC frame raster exactly as the standard prescribes it, and it is the
  first register in this chip to say "525" without being asked. The
  convention is `total - 1`, confirmed in band: `hde` and `hvalid` both read
  639 for a 640-wide mode, so the horizontal total is 776 and not 780.

And `525 × 776` at 31,089,742 Hz is **13,104,000 ns, −21.46%**. So the FP
raster fails too, differently from the CRTC's −26.3%, and each failure reads
two ways: either the raster is not the output one, or the pixel clock is too
fast by a constant factor. The factors are 1.273 and 1.357; the clocks the two
rasters would need are 24.42 MHz and 22.91 MHz.

### The calibration that closes it: the core clock

VPLL cannot be checked against itself — its right answer is the thing in
dispute. NVPLL and MPLL can: same formula, same crystal, and the parts they
clock have speeds known from outside this tree. So they were logged decoded,
with a prediction registered first, and the answer is unambiguous:

```
vblpll xtal=16666666 nvpll=00011c01(m=1 n=28 p=1) core=233333324
       stored=233333324 mpll=00000000(m=0 n=0 p=0) mem=0
       vpll=0003c20d pix=31089742
```

`crystal × 28 / 2 / 1 = 233,333,324 Hz`. The NV2A core runs at **233 MHz**.
The formula and the 16.6667 MHz crystal are right to seven digits, on a
register whose answer nothing in this stream could have tuned. MPLL reads
zero — the guest never programs the memory PLL in our model — so it
calibrates nothing, which is the void outcome the prediction reserved for it
rather than a failure.

**Therefore 31,089,742 Hz is the pixel clock the guest asked for, and neither
raster the chip holds runs at 59.94 Hz on it:**

| raster | source | refresh at the programmed pixel clock |
|---|---|---|
| 728 × 525 | VGA CRTC (`cr00`, `cr06/cr07`) | 81.34 Hz |
| 776 × 525 | PRAMDAC flat-panel (`FP_HTOTAL`, `FP_VTOTAL`) | 76.31 Hz |
| — | what the display actually runs at | **59.94 Hz** |

### Verdict: the period cannot be derived from the NV2A, and that is the result

Not "not yet" — the three ways out are all closed by measurement rather than
by argument. The clock is not misdecoded (233 MHz, seven digits). The rasters
are not misdecoded (both self-consistent, both with standard active and
blanking counts, the conventions confirmed in band). And the required clocks,
22.91 and 24.42 MHz, are not this VCO over any power of two, so no undecoded
divider bridges the gap.

What is left is the premise: **the NV2A is not the timing master of the analog
output.** The Xbox drives an external video encoder, and the rate the guest
sees is the encoder's. This tree models the encoder as
`hw/xbox/smbus_cx25871.c` — 256 bytes of registers that the guest writes and
**nothing has ever read**. That is where the video standard is, and reaching
it from `nv2a.c` is cross-device plumbing rather than a decode.

So the constants stay, and the guard is what there is. The +25 ppm on the NTSC
constant was deliberately left alone: it is one character, it is 40× smaller
than the suspicion this stream opened on, and changing it in the same arm as
the guard would have made the must-not-move leg unreadable.

**The one thing the register file does say authoritatively is the standard's
own name.** `fp_vtotal + 1` is 525 for NTSC and would be 625 for PAL, 750 for
720p, 1125 for 1080i — the total raster *is* the standard, where an active-line
count needs a bound and an interlace correction to become one. If PAL or HD
material ever arrives, keying the table on the total rather than the bound is
the shape of the fix, and it drops the interlace scaling with it. It remains a
table either way, so it was not worth a second unmeasured mechanism in the
same function today.

### Falsifiers, as registered before each run

Arm 1, `docs/testing/predictions/vblank-period-fp-raster.json`:

| | prediction | outcome |
|---|---|---|
| F1 | FP totals non-zero and `derived_fp` within 1% of 16,683,333 ns | **FALSIFIED** — 13,104,000 ns, −21.46%. The totals *are* non-zero, so the guest does program the block |
| F2 | `fp_vtotal+1` == 525 lines; `fp_htotal+1` in 980..996 px | **half** — 525 exactly; 776 px, outside the window |
| F3 | must-not-move: `want=16683750`, `vd=479 il=ff`, def==0 mean within ±50,000 ns of 16,718,178 | **holds** — 16,736,746 ns, moved +18,568 ns (0.11%) |
| F4 | cost: median `gfps` does not fall by more than 2 from 29.0 | **holds** — 29.0, unchanged |
| F5 | whole-soak rate above 58.000 Hz, confirming the ref carries the grid fix | **holds** — 59.814 Hz |

Arm 2, `docs/testing/predictions/vblank-period-pll-calibration.json`:

| | prediction | outcome |
|---|---|---|
| G1 | core clock within 5% of 233,333,333 Hz | **holds** — 233,333,324 Hz, −0.000% |
| G2 | memory clock within 10% of 200,000,000 Hz | **void** — MPLL coefficient is 0, never programmed |
| G4 | must-not-move: the whole mode line byte-identical to arm 1 | **holds** — `fp_vtotal=524 fp_htotal=775 pixclk=31089742 vd=479 il=ff` |
| G5 | cost: median `gfps` within 2 of 29.0 | **FAILED on the 90 s run** — 16.0, and see below |

**G5 failed, it reproduced, and it is a property of the device's hour rather
than of the change.** One log line every two seconds cannot halve a frame
rate, and the same run's def==0 VBLANK mean was 16,683,623 ns — 127 ns from
the intended period, the most accurate figure in this whole investigation. The
frame rate fell while the VBLANK clock stayed exact, which is a slow
*renderer*, not a slow timer.

The repeat, `1789279639-vblank-period-1501184`, same ref at arm 1's full
240 s, read a median of **16** again. So the drop is real and repeatable on
that ref — which is exactly why the reverse-order control matters: every run
in this series decays *within itself*, and later runs decay sooner.

The control came back at **21** on arm 1's own ref, 25 minutes after the same
binary read 29. So the leg as registered cannot discriminate: its tolerance is
2 and its control moved 8.

| run | ref | s | p50 | p90 | max | at ceiling (≥25) | floor (≤15) |
|---|---|---|---|---|---|---|---|
| arm 1, 22:56 | `cdc3a4b4d8` | 240 | **29** | 29 | 31 | 80% | 7% |
| arm 2, 23:03 | `6eddbdbff5` | 90 | **16** | 29 | 29 | 32% | 50% |
| repeat, 23:10 | `6eddbdbff5` | 240 | **16** | 27 | 30 | 16% | 50% |
| control, 23:13 | `cdc3a4b4d8` | 240 | **21** | 29 | 29 | 29% | 33% |

**The median was the wrong statistic, and the distribution says so.** Galleon's
`gfps` over a soak is bimodal — a mode at the 29-31 ceiling and a mode in the
5-20 range — so the median tracks how much of the run fell in each and flips
with the scene. The ceiling itself is what a per-frame cost would move, and it
does not move: p90 is 29, 29, 27, 29 and the maximum is 31, 29, 30, 29 across
all four runs, on both refs, in both orders. What varies is the *occupancy* of
the ceiling, 80% in the first run of the evening and 16-32% in the three that
followed it on a handheld already serving a full-corpus suite sweep and
charging at about 2 W over the adb cable (`docs/testing/device-power.md`).

That is the same lesson as `J` versus the interval histogram, one layer up: a
mean or a median over two regimes measures the mixture, not either regime. The
leg is recorded as **inconclusive with the noise floor measured at 8 points**,
which is the honest outcome — not "it was thermal", which would be an
explanation standing in for a measurement. The mechanism bound is what carries
the weight instead: the difference between the two refs is 43 lines in
`nv2a.c`, all of them inside a block that runs twice a second, and a cost of
13 fps out of that would have to lower the ceiling. It does not.


## MEASURED 2026-09-13: the deferral machinery, and three of the four are one

#65 left four defects open. The first result is that **three of them are one
mechanism and the fourth is its consequence**, and the way to see it is to
inventory who decides when the guest's VBLANK happens.

`d->vblank_next_target_ns` is the grid. After this pass there are five writers
of it, two assertion sites, and two places that move the timer without moving
the grid:

| site | what it does | verdict |
|---|---|---|
| `nv2a.c` timer callback | `target += period`, clamped | the grid |
| `nv2a.c` simple-VBLANK callback | `target += period`, clamped | the grid |
| `nv2a_vblank_recalc`, from `pramdac.c` on an `FP_VDISPLAY_END` write | `target = now + period` | legitimate: the period just changed |
| `nv2a_init` | `target = now + period` | legitimate: there is no grid yet |
| `ui/xemu.c` pause/resume unstick | `target = now`, `timer_mod(now)` | legitimate: re-arming after a pause |
| the deferral retry, `nv2a.c` | `timer_mod(now + MIN(max_defer, remaining))` | moves the TIMER, never the grid |
| `FLIP_STALL`, `pgraph.c:2355` | `timer_mod(now)` | moves the TIMER, never the grid |

Read against that table the four items collapse:

- **`unlock_framerate` (item 2) was a second clock.** `if (unlocked) target =
  now + period` made the *callback's own lateness* the clock, on every VBLANK,
  deferred or not. Fixed, and measured below.
- **`simple_vblank` (item 3) was a second clock.** `nv2a_vga_gfx_update`
  asserted the VBLANK bit on every host display refresh, so the *viewer's
  panel* was a clock. Fixed; unmeasurable on this harness, and marked so.
- **Phase (item 1) is not a third clock, and its named suspect is
  exonerated.** The deferral retry and `FLIP_STALL`'s `timer_mod(now)` move the
  timer and never the target, so since #65 they shift one VBLANK and the grid
  gives it back on the next. Neither can deliver a VBLANK *before* its slot
  either, because a deferral only happens once the callback has already
  reached the slot.
- **Coalescing (item 4) is the consequence, not a fourth defect.** Every
  assertion the other three misplace lands on a sticky latch. `PCRTC_INTR_0` is
  sticky on silicon too, so coalescing is faithful in KIND; only its rate is
  ours.

### The instrument: phase needs no `pgraph.c` change after all

#65 recorded phase as blocked on the flip timestamp and therefore on a
`pgraph.c` edit. It is not. The grid is a value `nv2a.c` already holds, and
`d->vblank_next_target_ns` is still un-advanced at the moment of the assertion,
so `now - target` **is** the phase error, per assertion, at both grid-driven
call sites. It goes out as a `vblphase` line beside `vbl`, split on deferral,
with the unlock-mode occupancy on the same line rather than correlated off the
`gfps` line a different writer emits on a different cadence.

Two checks were registered on the instrument itself before it ran:

- **`neg = 0`, the row that cannot happen.** A QEMU timer fires at or after its
  deadline, and every early rearm above can only fire a VBLANK already at or
  past its slot. **Zero over 28,448 assertions across both arms**, so the
  writer inventory is complete and the deferred/non-deferred split is sound.
- **U0: in arm A's fully-unlocked windows, `mean interval - period` must equal
  the mean lateness**, because in unlock mode arm A set `target = now + period`
  and therefore `interval = period + late` identically. Measured **5,537,274 ns
  against 5,537,847 ns — 573 ns apart, 0.01%.** The instrument agrees with the
  arithmetic before any of its conclusions are used.

### Two soaks, and the fast title this stream was missing

Dead or Alive 3 **enters unlock mode**, which Galleon never does (`Ul:N` on all
129 windows of both of #65's arms). It reports `Ul:Y` and a `gfps` ceiling of
59-60, and it lives only on the **thor**. Both arms below are DOA3, 240 s,
pinned `--device thor` under one requester, and `device_label` was read out of
each `result.json` rather than assumed — #64's cost leg lost a control to
exactly that.

Arm A `fc59b50726` / apk `09740b583a79`, dispatch `1789284407-vblank-defer-1213578`.
Arm B `595d258a02` / apk `d09639140b65`, dispatch `1789284413-vblank-defer-1213623`.
Both **thor**. Prediction committed first at `docs/testing/predictions/vblank-unlock-grid.json`; judged by `docs/testing/vblank_phase_ab.py`.

| regime | A interval | A rate | A drift | B interval | B rate | B drift |
|---|---|---|---|---|---|---|
| whole soak | 17,899,948 ns | 55.874 Hz | +4.375 s/min | 16,814,769 ns | **59.478 Hz** | **+0.473 s/min** |
| fully unlocked | 22,221,024 ns | **45.014 Hz** | **+19.916 s/min** | 17,526,914 ns | **57.065 Hz** | **+3.034 s/min** |
| unlock-active | 21,072,441 ns | 47.467 Hz | +15.785 s/min | 17,698,324 ns | 56.514 Hz | +3.650 s/min |
| locked *(control)* | 16,684,680 ns | 59.941 Hz | +0.005 s/min | 16,690,187 ns | 59.921 Hz | +0.025 s/min |

Drift is against the true NTSC 16,683,333 ns, not against our own constant.

**A title in unlock mode was being handed a 45 Hz VBLANK clock.** It loses
nearly twenty seconds of guest-visible time per minute of play — five times
the 3.83 s/min #65 fixed, on a mode that is **on by default** and entered by
every title running above about 40 fps. It now loses 3.03 s/min.

**And the locked regime is the control that makes it readable.** It is the
regime this change cannot reach, and it delivers 59.941 Hz at +0.005 s/min in
arm A and 59.921 Hz at +0.025 s/min in arm B, moving 5,507 ns — 0.03%, the same
figure #65's B3 control moved, against a 33% effect. That also retires the
suspicion #65 raised against `FLIP_STALL`: a path that pulled the VBLANK to the
flip and kept it there could not deliver the period to 930 ns over 9,967
assertions.

### Was abandoning the grid intended? Yes — and priced, it is not a trade

#65 asked this explicitly, and the history answers it. The condition was
`if (unlocked)` alone before `ff370c9f5c` ("revert frame pacing experiments",
2026-02-24), and the comment above it was a design statement:

> Advance the VBLANK target. In normal mode, advance by exactly one period to
> maintain a fixed 60Hz grid so games that count VBLANKs for timing see a
> consistent rate.
>
> In unlocked mode, always reset from now so the next VBLANK fires one period
> after this one. Combined with FLIP_STALL rescheduling, this ensures **the
> game drives the pacing**: frames faster than 60fps get VBLANKs sooner, and
> slower frames aren't locked to 30fps.

So it is **deliberate and documented**, and as written it is a legitimate
design: a setting that trades the guest's timebase for throughput, with the
cost named — the fixed grid is promised only to "games that count VBLANKs for
timing", i.e. only in normal mode. Three things are wrong with it anyway, and
only the third needed a device.

**1. `ff370c9f5c` left the code contradicting its own comment.** That commit
added the `was_deferred ||` half and rewrote the comment around it to reason
about deferral, ending: *"When the game is on time (no deferral), advance the
grid by exactly one period to maintain a strict 60Hz cadence for games that
count VBLANKs for timing."* That clause is false in unlock mode, which is
precisely the mode an on-time game is in. From that commit onward nothing in
the surrounding prose defended the half that remained, and #65 then removed the
half that was being reasoned about.

**2. It is on by default and nothing asks.** `unlock_framerate` defaults true
and the mode is entered automatically whenever smoothed frame time drops under
1.5 periods. A trade of the guest's timebase for throughput can be a setting;
it should not be the state every healthy title falls into without asking.

**3. The mechanism is backwards on its own stated goal.** "Reset from now so
the next VBLANK fires one period after this one" **delays** the next VBLANK
relative to the grid. The fixed grid's next target is `target_prev + period`,
which is `late` nanoseconds *earlier* than `now + period` — so the grid always
delivers the next VBLANK sooner than the reset does, never later. "Frames
faster than 60fps get VBLANKs sooner" is better served by the grid that was
discarded to achieve it, and that follows from the source without a device.

The device then priced the trade. It cost **45.014 Hz against 59.94** — a
quarter of the guest's clock — and bought, on the one title on hand that can
enter the mode, a `gfps` p90 of 59 against 59 and a max of 59 against 60.
**Nothing.** Same shape as #65's B4: a trade that was only ever a loss on the
title that could be measured.

### Phase, measured: it is the deferral hold, and its size is `poll_interval * defer_cap`

Arm A, lateness against the grid slot:

| | mean | what it is |
|---|---|---|
| not deferred | **104,923 ns** (0.63% of a period) | the QEMU timer's own latency |
| deferred, locked windows | **5,837,526 ns** | against a cap of `period/8 * 4` = 8,341,872 ns |
| deferred, unlock windows | **10,777,000 ns** | against a cap of `period/16 * 16` = 16,683,750 ns |

So the deferral hold runs at about 0.65-0.70 of its own cap in both regimes,
and it is **88× the timer's latency**. That closes the number #65 could not
explain: its p99 of 25,100,000-25,150,000 ns against a 16,683,750 ns period is
`period + max_defer` = 25,025,625 ns, and the median window p99 here is
**25,050,000 ns — within one 50 µs bucket of it, identical in both arms.**

p99 is therefore not a mystery and not a defect of the grid. It is the deferral
cap, by construction, and the fix deliberately does not move it: **median window
p99 is 25,050,000 ns in both arms, 0.0% apart.**

### The residue, and the one constant that explains it

Arm B's fully-unlocked windows still sit 843,164 ns above the period. The
arithmetic says where it goes, and the instrument confirms it by *diverging*
where arm A's agreed:

| | interval − period | mean lateness | reading |
|---|---|---|---|
| arm A | 5,537,274 ns | 5,537,847 ns | **equal** — there is no grid |
| arm B | 843,164 ns | 1,335,976 ns | **diverge by 492,812 ns** — the grid gives back 37% of every late VBLANK |

The 63% it does not give back is the clamp, and the cause is one constant. In
unlock mode `max_defer = poll_interval * defer_cap = (period / 16) * 16 =
period`, **exactly** — the one value that makes `target += period; if (target <=
now) target = now + period` fire. Any hold at or near a full period discards
the grid through the clamp. In normal mode the cap is `period / 2`, so a
deferral alone can never trip it, which is precisely why the locked regime
lands at +0.005 s/min and the unlock regime does not.

So the identified next step is `defer_cap` in unlock mode, and it is a
one-constant edit. **Deliberately not made here**: it is a second unmeasured
mechanism, it trades frame-rate headroom rather than correctness, and there was
no arm left to price it. Naming it with its arithmetic is worth more than
shipping it unmeasured.

### Coalescing, attributed: mostly faithful, and U7 is falsified

`coal` on its own cannot say whether the guest lost anything, so the instrument
now splits it three ways.

| | arm A, DOA3/thor | arm B, DOA3/thor | gate run, Galleon/**nova** |
|---|---|---|---|
| whole soak | 205 of 13,785 (**1.49%**) | 52 of 14,663 (0.35%) | 124 of 5,391 (2.30%) |
| unlock windows | 114 of 3,818 (**2.99%**) | 31 of 1,812 (1.71%) | — (`Ul:N` throughout) |
| locked windows | 91 of 9,967 (**0.91%**) | 21 of 12,851 (0.16%) | 124 of 5,391 (2.30%) |
| VBLANK bit unmasked in `INTR_EN_0` | **98%** | 90% | 96% |
| after a shorter-than-period interval | **37%** | 52% | 52% |
| mean preceding interval | **0.991 periods** | 1.000 periods | 0.992 periods |

Four readings, and the second is the one that was registered and failed:

1. **1.49% reproduces #65's 1.56% on a different title.** The figure is real
   and not Galleon-specific.
2. **U7 FAILED on its second half, and a third run says the split is close to
   even rather than one-sided.** The leg predicted that `> 50%` of coalescing
   would follow a *short* interval — our own bunching. Arm A gives **37%**, so
   the leg is failed as registered. But arm B gives 52% and the nova gate run
   gives 52%, so the honest statement is not "mostly theirs" either: **roughly
   half of the coalescing follows a full-length interval and half follows a
   short one, and the split moves with title and device.** The half that
   follows a full period is the guest's own ISR failing to acknowledge inside
   one refresh, which silicon has too on the same sticky latch, and is not
   ours to fix. Registering the leg one-sided at 50% put the threshold exactly
   where the data sits, which is the least informative place for it — a
   tolerance should not straddle the answer.
3. **98% of it is with the interrupt unmasked**, on all 123 windows of both
   arms, so the population #65 counted is the right one and its figure needs no
   retraction: these are ticks a title taking VBLANK interrupts does lose.
4. **The machinery modulates the rate 3-11×** — 2.99% against 0.91% in arm A,
   1.71% against 0.16% in arm B, same direction in both. That part is ours.

What is **not** claimed: the whole-soak fall from 1.49% to 0.35%. It fell in
the locked regime too, 0.91% to 0.16%, and the fix cannot reach that regime, so
the drop is scene or load rather than mechanism. Recorded as unattributable
rather than banked.

### Verdict: 6 of 8 legs hold, 2 fail, and both failures are informative

| leg | outcome |
|---|---|
| U8 gate — unlock windows ≥ 5 per arm | **met** — 40 and 16 |
| U0 — arm A's interval−period equals its lateness | **holds** — 0.01% apart |
| U1 — the fall equals arm A's own lateness, ±50% | **holds** — 26.1% apart pooled, **15.2% on fully-unlocked windows** |
| U2 — whole-soak rate rises ≥ 0.20 Hz | **holds** — +3.604 Hz, 55.874 → 59.478 |
| U3 — locked control within ±50,000 ns | **holds** — moved 5,507 ns (0.03%) |
| U4 — `neg == 0` on every window of both arms | **holds** — 0 of 28,448 |
| **U5 — deferred lateness within ±15%, p99 within ±10%** | **FAILED** — p99 exact (0.0%), deferred lateness −28.4% |
| U6 — `gfps` p90 and max fall by ≤ 2 | **holds** — p90 59 → 59, max 59 → 60 |
| **U7 — coalescing majority short AND majority unmasked** | **FAILED** — 98% unmasked, but only 37% short |

**U5 failed on a pooled statistic, and the per-regime measurement is the
diagnosis.** The deferral hold has two different caps — `period/2` locked,
`period` unlocked — so a figure pooled across both measures the mixture:

| | arm A | arm B | change |
|---|---|---|---|
| deferred lateness, pooled | 9,187,596 ns | 6,580,762 ns | **−28.4%** |
| within unlock windows | 10,777,000 ns | 10,845,837 ns | **+0.6%** |
| within locked windows | 5,837,526 ns | 5,954,119 ns | **+2.0%** |
| unlock share of assertions | 27.7% | 12.4% | the mixture |

The hold is unchanged in both regimes, which is exactly what U5 asserted. The
pooled number moved because the unlock occupancy halved between the two soaks.
This is the same trap this document records twice already — "a mean over two
regimes measures the mixture, not either regime" — and I wrote the judge to
pool by assertion count for that reason and then registered the leg on a pooled
figure anyway. The leg is reported FAILED as registered; the claim behind it
holds per regime.

The honest limits: **one run per arm**, and the unlock occupancy differed
between them (27.7% against 12.4% of assertions), which is the confound that
broke U5 and which a second pair would settle. What carries the result instead
of replication is the locked-window control at 0.03% against a 33% effect, the
within-regime deferral holds at +0.6% and +2.0%, and U0's 0.01% agreement
between the instrument and the arithmetic. Everything here is the thor, on one
title.

### The nova, and the build gate on the committed state

`05b4c2bce5` / apk `131db451fd76`, dispatch `1789285307-vblank-defer-nova-2158916`,
Galleon, 90 s, **nova**. Queued under a deliberately different requester so it
cannot be mistaken for a third arm, and pinned `--device nova` so the
cross-device reading is the thing measured rather than a coin flip.

Three jobs, all three answered:

- **It builds and boots.** The `simple_vblank` commit landed after both arms
  were queued against explicit shas, so no dispatcher build had covered the
  committed HEAD. This one did, and Galleon held for the full 90 s.
- **First VBLANK figures on the nova**, which every number in this stream has
  lacked. Whole soak 16,742,068 ns / **59.751 Hz** against the thor's
  post-#65 Galleon 16,721,058 ns / 59.816 Hz — 0.1% apart, on different run
  lengths, which is consistency rather than a controlled comparison.
- **`neg = 0` a third time**, now 33,840 assertions across two devices, two
  titles and three binaries. The grid-writer inventory holds.

Two differences worth recording rather than explaining:

- **The nova's timer latency is 3.4× the thor's** — non-deferred lateness
  360,179 ns against 104,923 ns. Two variables move at once (device and title)
  so this is not attributable, but it is the first sign that the phase floor is
  not a property of the emulator alone.
- **The phase tail is dominated by host stalls, not by the deferral.** Max
  lateness 686,863,907 ns, **41.17× a period**. Nothing in the deferral can
  produce that; the cap is one period. A 0.69 s stall is the host, and it is
  the reason a mean is useless here and the histogram is not.

### Also settled in passing

- **`PCRTC_RASTER` is zero on a second title and a second device.** `rast=0/0`
  across both arms of DOA3 and the nova gate run — 33,840 further assertions.
  Still not a survey, but nothing has yet been observed to read the register.
- **`unl=` cross-checks against the independent `Ul:` field** on 58 of 62
  paired samples (94%), with all four disagreements at a transition where a
  per-window count and a point sample must differ. That is the argument for
  putting the occupancy on the line whose numbers it explains.
- **`nv2a_vblank_recalc` leaves `vblank_deferred` set** if a mode change lands
  mid-deferral, so the next callback counts one deferral that did not happen
  and skips one that would have. It fires once per `FP_VDISPLAY_END` write and
  is instrument noise, not a timebase defect. Not fixed; recorded.

## UNRESOLVED

- ~~**Phase.**~~ **MEASURED 2026-09-13.** It needed no `pgraph.c` change: the
  grid slot is a value `nv2a.c` holds, so `now - target` is the phase error
  directly. The answer is that phase error is the **deferral hold**, mean
  104,923 ns when a VBLANK is not deferred and 5.8-10.8 ms when it is, capped
  at `poll_interval * defer_cap` — which is exactly the p99 of 25.05 ms this
  document could not explain. `FLIP_STALL`'s `timer_mod(now)` is **exonerated**:
  it moves the timer and never the grid, `neg = 0` over 28,448 assertions shows
  it never delivers a VBLANK before its slot, and the locked regime delivers
  the period to 930 ns over 9,967 assertions. What remains open is whether the
  hold *itself* should exist at that size; the residual it leaves in unlock
  mode is +3.03 s/min and traces to `defer_cap` being the one value that trips
  the grid's clamp.
- ~~**What the period should be derived from.**~~ **CLOSED 2026-09-13, and
  the answer is that it cannot be.** All three candidates are measured out:
  the extension bits cannot help because the character-quantised CRTC cannot
  express the 987.96-pixel total the clock demands; the crystal is right to
  seven digits against the 233 MHz core clock; and the flat-panel raster,
  whose two total registers were never modelled until now, gives −21.5%. The
  premise is what fails — the NV2A is not the timing master. What remains is
  the encoder, `hw/xbox/smbus_cx25871.c`, whose 256 registers the guest writes
  and nothing reads; reaching them from `nv2a.c` is cross-device plumbing.
- ~~**The unlock-mode grid**, which is on by default and unmeasured here.~~
  **FIXED and MEASURED 2026-09-13** on Dead or Alive 3, the fast title this
  stream was missing: 45.014 -> 57.065 Hz in fully-unlocked windows,
  19.92 -> 3.03 s/min of guest-visible time. The remaining 3.03 s/min is the
  `<= now` clamp, because `max_defer` in unlock mode is exactly one period.
- **Whether coalesced VBLANKs matter to any title.** The count is real and
  reproduces on a second title (1.49% on DOA3 against 1.56% on Galleon), and
  **98% of it is with the interrupt unmasked**, so a title taking VBLANK
  interrupts does lose those ticks. But it is **mostly faithful**: 63% of it
  follows a full-length interval, mean 0.991 periods, and a hardware ISR that
  misses its window loses the same tick on the same sticky latch. What is ours
  is a 3-11x elevation in unlock windows. Still open: no title is yet known to
  count VBLANKs for timing on this corpus, so the 0.9% floor has no named
  victim.
- **`PCRTC_RASTER`**, now zero on two titles (Galleon and DOA3, 28,448 further
  assertions). Two is not a survey either, and the register is still a
  read-counter rather than a scanline.
- **`simple_vblank`'s single source is unverified.** The second assertion site
  is gone and the `J` artefact with it, but the mode is reachable only through
  the debug settings index and per-game overrides, and nothing in
  `request.sh` can set a pref -- so no soak can enter it. The old comment's
  claim that the extra source "avoids timing-dependent freezes" is untested in
  both directions; it was never measured when it was added either.
- ~~**`defer_cap` in unlock mode is `16`, which makes `max_defer` exactly one
  period**~~ -- the one value that trips the grid's `<= now` clamp. That is the
  whole of the residual +3.03 s/min. **CHANGED 2026-09-13 to 15, with the
  clamp itself counted; see the section below.** The attribution above is right
  and the arithmetic for its SIZE was not written down here, which turned out
  to matter: reasoning from the excess over a period rather than from the whole
  lateness under-prices the available gain by about twelve times.
- **Nova against Thor.** Everything here is one device.

## MEASURED 2026-09-13: the clamp discards the whole lateness, not the excess

Opened to change one constant -- `defer_cap` 16 -> 15 -- and the first thing
it produced was a correction to the arithmetic of the residual this document
already attributes correctly. The conclusion did not move. What moved is the
**instrument**, which is the distinction `AGENTS.md` now records under "a
correction is not evidence of accuracy": a retraction that changes the answer
and keeps the instrument is a coin landing the other way up.

### The error, and it is the natural one

The grid's advance reads:

```c
d->vblank_next_target_ns += period;          /* t + period        */
if (d->vblank_next_target_ns <= now) {
    d->vblank_next_target_ns = now + period; /* t + late + period */
}
```

`now` is `t + late`, so the clamp's replacement slot is a whole `late` further
on than the grid's own -- **not `late - period`.** Mean drift per assertion is
therefore

    E[ late * 1(late > period) ]     and not     E[ max(0, late - period) ]

Working from the second of those, the available gain from taking `max_defer`
from `period` to `period * 15/16` bounds at `L + L'` per capped deferral, about
210,000 ns on the thor, which pools to **72,522 ns per assertion -- 8.6% of the
measured 843,164 ns residual.** That reading says the constant is not worth
changing. It is wrong.

The first model reproduces the measured drift on this document's own arm B
logcat, per window, without fitting anything:

| window | n | def_n | def(mean=) | model `def_n * def_mean / n` | measured `drift` |
|---|---|---|---|---|---|
| 4 | 109 | 11 | 16,810,019 | 1,696,382 | **1,695,881** |
| 5 | 111 | 9 | 16,816,423 | 1,363,331 | 1,364,246 |
| 6 | 110 | 10 | 16,810,270 | 1,528,206 | 1,527,863 |
| 3 | 117 | 3 | 16,862,204 | 432,364 | 432,933 |

0.03% on the first row. Pooled over arm B's seven fully-unlocked windows the
model gives 693,684 ns against a measured 843,164 -- 82%, with the shortfall in
the one window whose deferrals are *not* cap-bound (`def(mean=) = 9,317,831`,
where the clamped assertions are its tail and a window mean cannot see them).

### Which makes the value's justification arithmetic rather than tuning

The next grid slot is one period away; `max_defer = poll_interval *
defer_cap`; a period is sixteen poll intervals. So the largest cap that leaves
the grid **any** room is fifteen, and the room it leaves is one poll interval,
1,042,734 ns, which is what the timer's round trip has to fit inside. That
round trip is directly measurable as `def(mean=) - max_defer` and reads
**126,275 / 126,526 / 132,679 / 178,460 ns** across the four cap-bound windows
above -- 5.8x to 8.3x inside the margin.

And it is an impossibility rather than a probability: a deferral can only trip
the clamp if its hold exceeds `period - (L + L')`, so after the change the
clamp cannot fire from a deferral **unless the timer round trip alone exceeds
`period/16`**. What no cap bounds is a host stall; the 686,863,907 ns of
lateness measured on the nova, 41x a period, still reaches the clamp, which is
why the prediction registers a residual rather than zero.

Predicted from the same logcat, before the arm ran: fully-unlocked drift
843,164 ns -> ~0 per assertion, 17,526,914 -> 16,683,750 ns, 57.055 -> 59.939
Hz, and **2.888 -> 0.001 s/min** against true NTSC.

### The instrument change, which is the point

`clamp=` is appended to the `vblphase` line and incremented **at the clamp
itself**, at both grid-driven assertion sites. Both existing readers' regexes
are unanchored at the end of that line, so `vblank_report.py` and
`vblank_phase_ab.py` keep matching; the new judge,
`docs/testing/vblank_defercap_ab.py`, is a third file rather than an edit to
either, because this document cites both of their verdicts.

Counted rather than inferred so that a change to the cap is judged on whether
**the clamp still fires** -- the mechanism -- instead of on a drift figure,
which is the mechanism mixed with the host's stall tail. `D0` puts that to
work on arm A alone, where the patch cannot force it: over arm A's cap-bound
fully-unlocked windows, `drift * n / clamp` must equal `def(mean=)`.

### Where the value is wrong, named before the arm

A host whose timer round trip exceeds 1,042,734 ns. The nova's non-deferred
lateness is 3.4x the thor's -- 360,179 against 104,923 ns -- which puts its
round trip near 720,000 ns and the margin at 1.4x rather than 5.8x. If the
clamp still fires there, the reasoning is unchanged and the value is fourteen.

Arms: A `3de282e006` (counter only), B `e62907fa03` (`defer_cap` 15), DOA3,
240 s, `--device thor`, one requester, prediction committed at `c8548b6fae`
before either was queued.

**Results: see the `defer_cap 15` comment on #65 — it landed, and D9 failed.**
Unlock-mode loss 11.005 → 0.798 s/min, cap-bound fully-unlocked windows
6, 1 → 0, 0, `gfps` p90 59 → 59 and max 59 → 59. D1, D5 and D7 all failed as
ratios to an arm whose own spread exceeded their tolerance, and D9 failed on
the real residual: arm B's worst fully-unlocked window still clamps 5 times
against a bar of 2.

## MEASURED 2026-09-13: the round trip's tail, and "1.35× the maximum" is refuted

D9's diagnosis named `defer_cap = 12` because `def(max=) − max_defer` reached
**3,083,365 ns**, so twelve's 4,170,938 ns of margin is "1.35× the observed
maximum". **That argument does not survive more data**, and the correction is
worth more than the value it defends. Tool:
`docs/testing/vblank_roundtrip.py`, which writes nothing and carries its own
controls.

### The estimator, and what it can and cannot see

For a **non-deferred** assertion the recorded lateness *is* the timer's own
lateness `L`, because the callback fires at the grid slot and asserts
immediately. For a **deferred** one it is `L + hold + L'` with
`hold = MIN(max_defer, remaining) ≤ max_defer`. So

    def(max=) − max_defer  ≤  max(L + L')

is a **lower bound** on the round trip — and it is the estimator twelve was
derived from, so applying it to more windows is like for like.

Three things it conditions on rather than pools, and the first is what the
original figure got wrong:

- **Mixed-regime windows are excluded.** `max_defer` is `period/2` locked and
  `poll_interval · cap` unlocked, so a window holding both regimes has two
  different holds inside one aggregate and `def(max=)` could belong to either.
  This is exactly the trap U5 failed on. Not conditioning changes the thor's
  `rt_max` from 11.4–13.8 ms to 3.7–6.5 ms, which is the whole difference
  between "no cap can help" and "twelve is the knee".
- **Host-stall windows are dropped** (`nodef(max=) > period`, the only stall
  evidence a window line carries). 1–10 windows per run; no conclusion turns
  on it, so it is reported rather than relied on.
- **The statistic is a window count**, never a rate or a mean, because D1, D5
  and D7 all failed by measuring occupancy instead of the mechanism.

### The correction

**3,083,365 ns is a maximum over the ~32 fully-unlocked windows two thor runs
happened to contain.** The same estimator, on the same device, regime-
conditioned over the **~110 usable windows of each of those same runs**:

| run | `rt_max` | `rt_p90` |
|---|---|---|
| A1 `3de282e006` | 4,075,604 | 2,844,532 |
| A2 `3de282e006` | 3,691,090 | 2,423,885 |
| B1 `e62907fa03` | 3,718,116 | 2,539,321 |
| B2 `e62907fa03` | **6,534,801** | 2,440,989 |

So twelve's margin is **0.64× the observed maximum, not 1.35×**. The tail was
not covered; it was sampled too few times to see itself. That is this
document's own *"a within-ref floor is a lower bound on the floor, never the
floor"*, and *"a bound is not a value"*.

### The value survives, on the statistic that does not move with occupancy

| cap | margin | windows that would clamp (4 thor runs) |
|---|---|---|
| 15 | 1,042,740 | 37, 25, 28, 28 ← what shipped |
| 14 | 2,085,474 | 17, 14, 18, 16 |
| 13 | 3,128,208 | 8, 5, 1, 3 |
| **12** | **4,170,942** | **0, 0, 0, 1** ← eliminated |
| 11 | 5,213,676 | 0, 0, 0, 1 |

**Twelve is the knee**, eleven buys nothing, and the single residual window is
the 6.53 ms event the maximum-based argument had mispriced. The right claim is
*"the exceedance count reaches zero"*, not *"the margin covers the maximum"*.

Cost: the hold loses **25%** of its length against 6.25% for the fifteen step.
So this step is **not free by precedent** and its cost leg is the one to
watch — three arms in a row have failed to show the deferral's frame-rate
defence (B4, U6, D6), but a 4× larger cut has none.

### THE NOVA, measured at last — and it does not support twelve

This was the previous lane's own least-certain point: *"3,083,365 ns is two
runs on one device, and the nova's latency is 3.4× the thor's."* It is now
measured, from **five nova soaks already on disk at zero device cost**.

| | thor (4 runs) | nova (5 runs) |
|---|---|---|
| `rt_max` | 3,691,090 – 6,534,801 | **6,225,835 – 50,353,011** |
| `rt_p90` | 2,423,885 – 2,844,532 | **4,776,972 – 5,768,336** |
| exceedance windows at cap 12 | **0 – 1** | **12 – 29** of ~120 |
| exceedance windows at cap 10 | 0 – 1 | 0 – 8 |
| exceedance windows at cap 9 | 0 – 1 | 0 – 5 |

**The nova's `rt_p90` alone exceeds cap 12's margin on four of five runs.** It
would need **cap 10** to reach the thor's post-change level and **9** to
approach zero.

**And that is still not a reason to ship 10, for a reason that has to be said
rather than assumed.** The nova has never entered unlock mode on any title on
hand — `unl == 0` on every window of all five soaks — so `defer_cap`'s unlock
branch is **dead code there**. Those figures are the **host's** round trip,
read out of *locked-mode* deferrals and transplanted into the unlock
arithmetic. They predict what would happen *if* a title ever put the nova in
unlock mode; they are not something the nova is doing. Spending two further
steps of a real title's deferral headroom against a configuration never
observed is a trade, and it goes to the owner with both numbers rather than
being resolved by whoever writes the constant.

The falsifier, for whoever finds such a title: **if a title is ever found that
puts the nova in unlock mode, this predicts its cap-bound window count will
NOT reach zero at 12.**

One thing the same measurement settles in passing: **the normal-mode pair is
exonerated by measurement and not only by arithmetic.** Locked mode's margin
is `period/2` = 8,341,872 ns and covers even the nova's clean-run round trip
at **1.24×** — which is also why the locked regime delivers 59.941 Hz at
+0.005 s/min on both devices.

### A leg that failed and was relabelled rather than dropped

The cap-16 column was registered as an **impossible row**: cap 16 leaves 6 ns,
so surely *every* window with a deferral exceeds it. It read 91–120 of
110–120. The shortfall is real and is **`remaining`-bound deferrals**, whose
hold is shorter than the cap and which therefore under-read the round trip.
So the column is **coverage, not a control** — it counts windows holding at
least one *cap-bound* deferral. A leg that fails because the world is bigger
than the leg is worth keeping, relabelled. The impossible row is now `neg ==
0` — a QEMU timer cannot fire early — which holds on all nine runs, alongside
`def(max=) ≥ def(mean=)` everywhere and `nodef_n + def_n == n` **exactly**,
which says the three counters are read at one instant rather than across a
gap.

### Arms

A `9931f882bb` (cap 15), B `2e4e8403d9` (cap 12) — one constant apart. DOA3,
240 s, **two runs per arm**, `--device thor`, one `--who`. Prediction
committed before anything was queued in
`docs/testing/predictions/issue65-defercap-12.json`, with E4 registered as an
**intermediate value**: the hold must fall by exactly three poll intervals,
3,128,202 ns, run-paired — the half a merely-helpful change would miss.

### ARM A (cap 15) MEASURED, and it corrects my own device comparison

`9931f882bb` / apk `93c25670227f`, **thor** both runs (`device_label` read out
of each `result.json`), DOA3, 240 s, two runs under one `--who`.

| run | fully-unlocked windows | exceedance windows at c15 | at c12 | `rt_p90` | `rt_max` | clamps |
|---|---|---|---|---|---|---|
| A1 | 28 | **35** | 1 | 2,783,781 | 11,232,895 | 89 |
| A2 | 22 | **28** | 2 | 2,921,898 | **42,453,521** | 84 |

**E0's gate is met** (28 and 22 against a bar of 5), and all three controls
hold on both runs: `neg == 0`, `def(max=) ≥ def(mean=)` everywhere, and
`nodef_n + def_n == n` **exactly**.

**The pre-registered table replicates.** 35 and 28 exceedance windows at cap
15, squarely inside the published 37/25/28/28, and 1 and 2 at cap 12 against
the published 0/0/0/1. So the statistic reproduces across six runs of two
binaries on one device, which is what an occupancy-free statistic is supposed
to do.

### A2's `rt_max` is 42,453,521 ns, and it retracts a comparison I made above

This document, three sections up, contrasts *"the nova's `rt_max` 6,225,835 –
50,353,011"* against *"the thor's 3,691,090 – 6,534,801"* and reads the nova
as roughly twice as bad. **With A2 in hand the thor's range is 3,691,090 –
42,453,521 over six runs, and that contrast largely collapses on the
maximum.**

Two things follow and the second is the useful one.

**My host-stall filter does not catch whatever produces these.** A2's window
had `nodef(max=) ≤ period` — so no *non-deferred* assertion in it was more
than 16.68 ms late — while a deferred one was 58.1 ms late. The nova showed
the same shape at 50.4 ms. Whatever it is, it is **not** a plain host stall by
the only evidence a window line carries, it appears on **both** devices, and
`--keep-stall-windows` is not the difference. I do not know what it is. It is
recorded as unexplained rather than filtered harder, because a filter tuned
until the outliers vanish is a filter fitted to the answer.

**So the maximum is not a usable statistic here at all, on either device**, and
that is the same conclusion the "1.35×" refutation reached by a different
route. Three times today this quantity has grown with n: 3.08 ms at ~32
windows, 6.53 ms at ~440, 42.5 ms at ~660. Any figure quoted as "the observed
maximum" is a floor, **including every one I quoted.**

**The device comparison therefore rests on the two statistics that did not
move**, and it survives on both:

| | thor (6 runs) | nova (5 runs) |
|---|---|---|
| `rt_p90` | 2,423,885 – 2,921,898 | **4,776,972 – 5,768,336** |
| exceedance windows at c12 | **0, 0, 0, 1, 1, 2** | **12 – 29** of ~120 |
| `rt_max` | 3.69 – **42.5** ms | 6.2 – 50.4 ms — **no contrast** |

The nova's `rt_p90` is about double the thor's and its cap-12 exceedance count
is one to two orders of magnitude higher. Those are the grounds for "cap 12
does not cover the nova"; the maximum never was.

### What arm A predicts about E1, said before arm B is read

Arm A's own data gives **1 and 2** exceedance windows at cap 12. E1's
registered bar is **zero on both runs**. If the per-run residual rate is
around 1 in 3, E1 passes with probability near 0.45 — so it is a genuine
falsifier rather than a formality, and a failure by one or two windows is
diagnosed in advance: that residual is the tail above, which no cap reaches,
and **E2** (worst fully-unlocked window clamps ≤ 2) is the leg that bounds it.

### VERDICT: cap 12 fixes D9. 6 of 8 registered legs hold, and both failures are instrument findings

Four runs, **all thor**, `device_label` read out of each `result.json`. Arm A
`9931f882bb` / apk `93c25670227f`, arm B `2e4e8403d9` / apk `bfb13fa5f097` —
distinct binaries, one constant apart. DOA3, 240 s, two runs per arm, one
`--who`. Prediction registered 15:11:44Z, before any arm was queued.

| | A1 | A2 | B1 | B2 |
|---|---|---|---|---|
| fully-unlocked windows | 28 | 22 | 7 | 32 |
| **worst window clamps** | **6** | **7** | **0** | **1** |
| clamp/assertion (full) | 0.0253 | 0.0285 | 0.0000 | 0.0008 |
| fully-unlocked rate | 58.397 Hz | 58.077 | **60.001** | **59.854** |
| **guest time lost** | **+1.544 s/min** | **+1.864** | **−0.062** | **+0.085** |
| deferred hold | 11,571,422 | 11,890,186 | 8,145,533 | 9,634,700 |
| locked interval (control) | 16,683,894 | 16,690,407 | 16,695,711 | 16,686,094 |
| **gfps p90 / max** | 59 / 60 | 59 / 59 | 59 / 60 | 59 / 59 |

**D9 — the leg this change exists to fix — HOLDS.** The worst fully-unlocked
window clamps **0 and 1** against a bar of 2, where cap 15 clamped **5**. And
in these arms cap 15 itself clamped **6 and 7**, so the bar was being missed
by more than the published run suggested.

**Guest time lost goes 1.54–1.86 → −0.06 to +0.09 s/min, with no overlap** —
about 20×, and B1 is very slightly *fast* rather than slow. **At no
measurable frame-rate cost**: p90 59 → 59 and max 60 → 59. That is the
**fourth arm running** in which the deferral's frame-rate defence has not
appeared (#65's B4, its U6, D6, and now this) — and the first at a 25% cut
rather than 6.25%, which is the one that had no precedent.

| my leg | outcome |
|---|---|
| E0 gate, ≥5 fully-unlocked windows per arm | **HOLDS** — 28/22 and 7/32 |
| **E1** arm B has zero exceedance windows at cap 12 | **FAILS** — 2 and 3 |
| **E2** arm B worst window clamps ≤ 2 | **HOLDS** — 0 and 1 |
| E3 arm B worst run ≤ 0.40 s/min | **HOLDS** — 0.085 |
| **E4** hold falls 3,128,202 ns run-paired ±20% | **FAILS** — +9.5% and −27.9% |
| E5 cost: gfps p90/max fall ≤ 2 | **HOLDS** — 0 and 1 |
| E6 locked control within 50,000 ns | **HOLDS** — 11,817 ns (0.07%) |
| E7 `neg == 0`, the impossible row | **HOLDS** — 0 of 58,780 assertions |

### E1 FAILED, and it convicts MY OWN ESTIMATOR rather than the value

Arm B keeps **2 and 3** exceedance windows against a registered bar of zero.
But **D9's direct clamp counter reads 0 and 1 in the same runs.** The
estimator predicted two to three clamping windows where the hardware counter
saw zero to one.

**So `def(max=) − max_defer > margin` over-predicts clamps by roughly two to
three times**, and the reason is the one already written down two sections up
when the cap-16 row was relabelled from "impossible" to "coverage": `def_max`
can come from a **`remaining`-bound** deferral, whose hold was *shorter* than
`max_defer`, so its true lateness never exceeded a period even though the
estimator's difference exceeded the margin.

This is the sharpest result of the pair, because **the exceedance table is
what I used to choose 12 over 15.** Three consequences:

- **The choice survives.** The table's *direction* is validated by the counter
  it was standing in for: clamps went 6, 7 → 0, 1 exactly where the table said
  35, 28 → 2, 3. A conservative proxy that tracks the truth is still a guide.
- **Every exceedance number in this document is an over-estimate**, including
  the nova's. "12 to 29 exceedance windows at cap 12" should be read as
  perhaps 4 to 15 actually-clamping windows. That is still one to two orders
  above the thor's 0 to 1, so **the nova conclusion survives — weakened, not
  withdrawn.**
- **A leg on a proxy failed while the leg on the counter passed.** E1 and E2
  ask the same question; E2 asks it of `clamp=` and E2 is the one to carry
  forward. This is the same lesson the `clamp=` counter was built for in the
  first place — *it was found by building the counter rather than reasoning
  again* — and I then registered a leg against the proxy anyway.

### E4 FAILED on the hold's own occupancy, which is today's fourth instance

Run-paired the fall is **+9.5%** and **−27.9%** against three poll intervals;
my bar was ±20%, so it fails on run 2. Cross-paired it is 38.1%.

The diagnosis is in the table: **arm B run 1 had 7 fully-unlocked windows and
run 2 had 32**, with defers per window **37.9 against 84.8** — a 2.2× swing
inside one binary. `def(mean=)` is a mean over a window mixing **cap-bound and
`remaining`-bound** deferrals, and the mixture moves with occupancy, so **the
hold mean is itself partly an occupancy measurement.** A ±20% bar on it is
tighter than the quantity's own reproducibility.

That is the **fourth** time today a statistic has turned out to measure
occupancy: #64's median, #65's U5, D1/D5/D7 — and now my own E4, registered
knowing all four. The remedy is the same one that keeps working: E2's *count
of windows where a condition holds* survived, and every leg I registered as an
absolute (E3, E6, E7) held.

### The previous lane's legs, for comparison, and one of them makes the point

Run through the same judge: **5 hold, 3 FAIL, 1 VOID.** D2 fails because arm
A's fully-unlocked drift in *these* runs is 444,340 and 539,055 ns against the
published 3,746,966 and 1,170,848 — so its registered floor of a 500,000 ns
*fall* cannot be met when the control only had 444,340 ns to give. **My E3 is
the absolute form of the same question and it holds.** D7 fails at 61.1% on
the defers-per-window quantity whose spread inside one arm is 2.2×. D0 is VOID
because at cap 15 no arm A window is cap-bound *by the mean* — which is itself
the 16 → 15 change having worked.

*The nova residual (E8) is recorded above as measured and not counted: this
pair cannot test it, because the nova does not enter unlock mode on any title
on hand.*
