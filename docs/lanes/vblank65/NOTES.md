# lane.vblank65 — #65's four remaining defects

Base `master @ 6db8217cdb`, 2026-09-19. No device used and none needed: the
answer to all four was already on disk.

## The order I took them in, and why it is "none of them"

The brief asks which of the four I took first and says item 2 looks like it
gates the others. I agree with that reading and it is now moot, because **all
four were closed by the 2026-09-13 batch and #65's `status_note` has not been
updated since 2026-09-12.** The brief is derived from that field, so it
describes the tree as it stood six days ago. What follows is the check, item by
item, with the commit or the measurement that closes each. Nothing here is a
new fix, because none was needed.

This is the second time this lane's inputs asserted something the tree
contradicts. The other: the brief says "the territory row `[lane.vblank65]`
names exactly these" three files. **There is no `[lane.vblank65]` row in
`docs/testing/territory.toml` at wave 94.** All three files are in `[free]`, so
nothing collided and no harm came of it, but a brief that cites a row as a
claim should cite one that exists. Board request at the end.

### 1. Phase — closed, and its named suspect is exonerated by reading

Two clauses, and they are separate things.

**The p99 of 25.15 ms is arithmetic, not a defect.** `period + max_defer` in
normal mode is `16,683,750 + (16,683,750/8)*4 = 25,025,625 ns`, and the
histogram's bucket is 50 µs. Across every VBLANK soak on disk the median window
p99 is:

| ref | title | p99 median |
|---|---|---|
| `19f52510d9`, `bace14275d` | Galleon | 25,100,000 / 25,150,000 |
| `fc59b50726`, `595d258a02` | DOA3 | 25,050,000 |
| `3de282e006` ×2, `e62907fa03` ×2 | DOA3 | 25,050,000 |
| `9931f882bb` ×2, `2e4e8403d9` ×2 | DOA3 | 25,050,000 |

Six refs, two titles, eleven runs, and it does not move — because none of the
three fixes touches the normal-mode pair `defer_cap = 4, poll_interval =
period/8`, and the source comment at `nv2a.c:1096` says so deliberately. A
constant that the mechanism predicts to the bucket and that is invariant under
every change made is not an open defect.

**`FLIP_STALL`'s `timer_mod(now)` cannot pull the VBLANK to itself, and this is
readable rather than inferred.** `pgraph.c:2355` calls `timer_mod(
d->vblank_timer, now)` and never writes `d->vblank_next_target_ns`. `FLIP_STALL`
is not among that field's writers at all — the two grid-driven ones are
`nv2a.c:1209` and `:917`, and the rest are the period recalc, `nv2a_init` and
the pause/resume unstick — so a flip moves one assertion and the next slot is
still `slot_prev + period`. The measurement that confirms
it is the locked-regime control on the cap-12 arm: 59.896 / 59.930 Hz, +0.045
and +0.010 s/min, on a path that services a flip every frame. A writer that
pulled the VBLANK to the flip could not deliver the period to that.

### 2. `unlock_framerate` — the grid half is fixed and measured; the default is a config file this lane does not hold

The half the brief describes — "abandons the grid" — was `d6d84cd0c2`
(2026-09-13), removing `|| unlocked` from the reset condition. It is measured
on #65's own DOA3/thor arms and priced again by the two `defer_cap` steps.
Fully-unlocked windows, DOA3, thor, against true NTSC 16,683,333 ns:

| ref | what it is | fully-unlocked interval | rate | guest time lost |
|---|---|---|---|---|
| `fc59b50726` | before the grid fix | 22,221,024 ns | 45.014 Hz | **+19.916 s/min** |
| `595d258a02` | grid held, cap 16 | 17,526,914 ns | 57.065 Hz | +3.034 s/min |
| `9931f882bb` run 1 | cap 15 | 17,128,090 ns | 58.384 Hz | +1.600 s/min |
| `9931f882bb` run 2 | cap 15 | 17,222,805 ns | 58.063 Hz | +1.940 s/min |
| `2e4e8403d9` run 1 | **cap 12, the tree today** | 16,670,861 ns | 59.985 Hz | **−0.045 s/min** |
| `2e4e8403d9` run 2 | **cap 12, the tree today** | 16,709,805 ns | 59.845 Hz | **+0.095 s/min** |

The last two rows are the shipped binary: `git diff 2e4e8403d9 HEAD --
hw/xbox/nv2a/nv2a.c` is empty, so arm B of the `defer_cap` arm IS today's
VBLANK code. Unlock mode now costs at worst 0.095 s/min of guest-visible time,
against 19.916 before, and its own locked control on the same runs reads +0.045
and +0.010. **The claim "any claim about unlock mode is about a configuration
nobody selected" was right when it was written and is now answered: the
configuration nobody selected costs, as measured, about a tenth of a second per
minute.** Two runs per arm, one title, one device, one requester batch.

What is NOT closed: `unlock_framerate` still defaults **true**
(`android/app/src/main/cpp/xemu_android.cpp:642` and `:916`). That file is in
no part of this lane's claim and the decision is an owner's, not a
measurement's — and it is now a much smaller decision than the investigation's
framing implies, because the trade it describes ("a quarter of the guest's
clock for nothing") was a property of the grid reset and the cap, both of which
are gone. Raised on the issue rather than taken.

### 3. `simple_vblank`'s second source — fixed, and say what the harness cannot see

`64c9f000d2` removed the `NV_PCRTC_INTR_0_VBLANK` assertion from
`nv2a_vga_gfx_update`. Verified by reading: `nv2a_vga_gfx_update`, `nv2a.c:1232`, now calls
`vga->hw_ops->gfx_update` and nothing else, and the only two recorders left are
`VBH_SRC_TIMER` (`nv2a.c:1141`) and `VBH_SRC_SIMPLE` (`nv2a.c:903`).
`VBH_SRC_GFX` survives as an enum value with a comment saying it was removed.
One mode, one source.

**What the logs cannot tell you, stated because a zero here is not evidence.**
`src(smp=0 gfx=0)` on all seventeen soaks means only that `simple_vblank` was
off, which is its default. No soak on disk was queued with the mode on, so
nothing on the device has exercised either the old two-source behaviour or the
new one-source behaviour. The fix is established by reading the source, and the
investigation already marks it unmeasurable on this harness. I did not queue a
soak to change that: `simple_vblank` is a diagnostic mode, and a device run
whose only finding would be "the counter we deleted reads zero" is the kind of
measurement my own notes warn about.

### 4. PCRTC coalescing — a consequence, and it followed the fixes

"Coalescing is the consequence of the other three, not a fourth defect" is a
prediction about what should happen to the rate when the other three land. It
did, on DOA3/thor — the same title and device throughout, because the 1.35–1.56%
the brief quotes is from **Galleon** and a rate compared across titles measures
the title:

| ref | coalesced, % of assertions |
|---|---|
| `fc59b50726` (before) | 1.49% |
| `595d258a02` (grid held) | 0.35% |
| `3de282e006` ×2 (cap 16 + counter) | 0.62%, 0.12% |
| `e62907fa03` ×2 (cap 15) | 0.19%, 0.14% |
| `9931f882bb` ×2 (cap 15) | 0.20%, 0.18% |
| `2e4e8403d9` ×2 (**today**) | 0.20%, 0.20% |

Roughly 7× down and stable at two runs per ref. Note `3de282e006`'s two runs,
0.62% against 0.12% on **one ref**: a five-fold spread, which is the runs≥2 rule
earning itself on this very statistic. The residue is ~24 events per 240 s with
the interrupt unmasked, and `PCRTC_INTR_0` is sticky on silicon, so what is
left is faithful in kind.

## What I actually changed, and why it is the live defect on this stream

`docs/testing/vblank_ab.py`. **`--expect` opened the prediction to print a
header and judged five thresholds that lived in the judge.** The registered
`expect` block was read by nothing — and by nothing at queue time either:
`request.sh`'s soak path says so in its own comment, *"there is no queue-time
oracle for that key space ... put it in `expect` as a named rule YOUR OWN
READER CHECKS."* This is that reader. It did not check.

Against `predictions/vblank-grid-deferral.json`, the prediction this judge was
written for, the five legs it reported as held line up with the block it never
opened like this:

| leg | what the code judged | what the prediction registers |
|---|---|---|
| B1 | `def>20` mean **falls** by ≥ 1,000,000 ns | `def_gt20/mean_interval_ns` 18,100,000 — an absolute **bar** |
| B2 | whole-soak rate > 58.000 Hz | `whole_soak/delivered_millihertz` 58,000,000 — **58 kHz**, see below |
| B3 | `def==0` mean moves ≤ 50,000 ns | `def_eq0/mean_interval_ns` 16,712,711 — arm A's own value; **no tolerance is registered anywhere** |
| B4 | median `gfps` falls by ≤ 2 | `gfps_median_drop_max` 2 — agrees |
| B5 | defers per window rise | **nothing at all** |

Two of the five have no registered key. One is judged against a tolerance the
prediction never states. One is judged in a different shape. And the fifth is
the proof that nobody ever read the block: `nv2a.c` emits `rate=` from a
millihertz counter, so **58,000,000 millihertz is a bar of 58 kHz and no VBLANK
stream can pass it.** Three orders of magnitude, sitting in the one registered
prediction on this stream since 2026-09-13, invisible because the file was
opened for its header and closed again.

All five held either way, so **#65's conclusion is not withdrawn and its
verdict still reproduces byte for byte** — the five built-in legs are kept
verbatim and print the same numbers. What was unsound was the binding: the next
prediction on this stream would have been judged by #65's legs no matter what
it said.

The judge now:

- looks every `expect` key up in a table, and **refuses** an unknown one. On the
  soak path nothing upstream can tell a rule from a typo, so this is where it
  has to be caught.
- marks a value-only key **UNJUDGEABLE**, naming the key that would make it
  judgeable, instead of quietly substituting a constant. I did **not** rewrite
  the registered file to add those keys: that is widening a prediction after its
  arm, which is the one thing the commit-date binding exists to prevent.
- makes a leg **VOID** when the data it reads is absent. The old B3 compared an
  empty regime against an empty regime, moved 0 ns, and printed HOLDS — a
  control that cannot fail is not a control. Same for `neg`, which is **absent**
  rather than zero on the six Galleon soaks: those binaries predate the
  `vblphase` line entirely, and summing an empty list gives a passing 0. I made
  that mistake myself in this lane's first survey table before checking.
- scopes B1–B5 to the prediction they were written for. Any other file gets
  NOT APPLICABLE.
- names an out-of-range rate bar as **UNREACHABLE AS REGISTERED** rather than
  failing it silently.
- takes repeated `--a`/`--b` for runs ≥ 2, folds worst-case over run pairs
  without pooling, and says "1 per arm" on the verdict line when it is one.
- accepts a dispatch result **directory**, so `ref` and `device_label` are read
  rather than assumed. A ref the prediction does not register is refused. A
  missing `device_label` is reported — #65's own arm A records none, so "both
  arms, Thor" is an assumption for that arm and not a reading.

`--selftest` builds a mutant per gate; all fourteen checks trip, and it needs
no device and no results on disk.

## For the next lane: do not repeat these

- **Do not re-run #65's rate arm at runs ≥ 2.** It is a real weakness in that
  one arm and the brief is right to name it, but the hypothesis has since been
  superseded three times by arms that *were* run at runs ≥ 2
  (`issue65-defercap-12.json`, `runs_per_arm: 2`, four soaks on disk). Rebuilding
  two 2026-09-12 refs to firm up a superseded conclusion is device time spent on
  the past.
- **The same `--expect`-is-decorative defect is in `vblank_phase_ab.py` and
  `vblank_defercap_ab.py`**, which are not this lane's files. Both open the
  prediction for `registered_utc`/`who`/`a_ref`/`b_ref` and judge hardcoded
  legs. `issue65-defercap-12.json` registers `E0`–`E6` with values; none is
  read. Raised on the issue as a board request — it is one lane holding those
  two files, and `vblank_ab.py` is now the pattern to copy.
- **`--expect` on this stream binds by commit date and by nothing else**, so the
  gap the brief names — "catches a prediction written late but not one widened
  on time" — was the *smaller* of the two problems. The bigger one was that the
  legs were never in the file to widen.
