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


## UNRESOLVED

- **Phase.** The fix restores the *rate*; p99 says nothing about phase moved.
  Whether a flip lands where hardware would put it relative to VBLANK is still
  open, and FLIP_STALL firing a deferred VBLANK immediately via
  `timer_mod(now)` (`pgraph/pgraph.c:2324`) inverts the causality outright: on
  hardware VBLANK happens on a grid and the flip latches at the next one, here
  the flip can pull the VBLANK to itself. Measuring that needs the flip
  timestamp in the same histogram, which is a `pgraph.c` change and `pgraph.c`
  belongs to nobody.
- ~~**What the period should be derived from.**~~ **CLOSED 2026-09-13, and
  the answer is that it cannot be.** All three candidates are measured out:
  the extension bits cannot help because the character-quantised CRTC cannot
  express the 987.96-pixel total the clock demands; the crystal is right to
  seven digits against the 233 MHz core clock; and the flat-panel raster,
  whose two total registers were never modelled until now, gives −21.5%. The
  premise is what fails — the NV2A is not the timing master. What remains is
  the encoder, `hw/xbox/smbus_cx25871.c`, whose 256 registers the guest writes
  and nothing reads; reaching them from `nv2a.c` is cross-device plumbing.
- **The unlock-mode grid**, which is on by default and unmeasured here.
- **Whether 1.56% coalesced VBLANKs matter to any title.** The count is real;
  no title is yet known to count VBLANKs for timing on this corpus.
- **`PCRTC_RASTER`**, zero on one title. One title is not a survey.
- **Nova against Thor.** Everything here is one device.
