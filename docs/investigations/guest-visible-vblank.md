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

`nv2a_calc_vblank_period_ns`, `hw/xbox/nv2a/nv2a.c:234-242`, derives nothing:

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

### The fix that subsumes both

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

## UNRESOLVED

- **What the period should be derived from.** P7 killed the CRTC/VPLL
  derivation at −26.3%. Three candidates remain and the measurement has not
  been designed: the NV2A extension bits we do not decode, a VPLL reference
  other than the 16.6667 MHz crystal, or the premise itself — that the CRTC
  carries encoder-independent digital timings and the video standard has to
  come from somewhere else entirely (the kernel's AV pack / video region).
- **The unlock-mode grid**, which is on by default and unmeasured here.
- **Whether 1.56% coalesced VBLANKs matter to any title.** The count is real;
  no title is yet known to count VBLANKs for timing on this corpus.
- **`PCRTC_RASTER`**, zero on one title. One title is not a survey.
- **Nova against Thor.** Everything here is one device.
