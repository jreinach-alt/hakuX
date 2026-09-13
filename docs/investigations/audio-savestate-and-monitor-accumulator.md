# Issues #75, #73 and #71: the savestate, the accumulator, and the taper

Date: 2026-09-13. Branch `claude/es-de-launcher-disc-error-ojnl14`, rebased at
`91255df20f`.

Read `audio-assessment.md`, `audio-harness.md`, `audio-baseline.md`,
`audio-headroom-verified.md` and `audio-voice-headroom.md` first. This picks up
the three entries that were left actionable and does not revisit the loudness
question, which those four closed.

Claims are tagged as in the other five:

- **MEASURED** — from a capture, a log off real hardware, a host run of a
  harness in this repository, or from reading the cited source.
- **INFERRED** — needs a fact I do not have.

Audio has no golden oracle. **#75 is the one entry on this stream that does**,
which is why it is first: a save/load round trip must reproduce the device
state, and that is decidable from source with no device and no reference
waveform.

---

## 1. #75 — ACI migrated only its PCI device

### The mechanism

**MEASURED, from source.** `hw/xbox/mcpx/aci.c` held:

```c
static const VMStateDescription vmstate_mcpx_aci = {
    .fields = (VMStateField[]) {
        VMSTATE_PCI_DEVICE(dev, MCPXACIState),
        // FIXME
        VMSTATE_END_OF_LIST()
    },
};
```

`MCPXACIState` embeds an `AC97LinkState` by value. Nothing in that field list
reaches it, so a load restored 256 bytes of PCI config space and left the codec
holding whatever `mcpx_aci_realize` → `ac97_common_init` → `ac97_on_reset` had
put there at boot: the 256-byte mixer page, `glob_cnt`, `glob_sta`, the codec
access semaphore, and all eight bus-master engines with their BD cache. **And
the load reported success.** That is the severe half. A load that refuses is a
bug report; a load that succeeds with reset values is a bug report filed months
later against something else.

**MEASURED: 460 bytes of guest-visible state, 0 of them migrated.** Counted by
the harness below, not by hand.

### Scope, stated before the fix and not after

The ACI is **not in the audible path on this platform**. `ep_sink_samples`
returns `false` for `MCPX_APU_DEBUG_MON_AC97` (`apu/dsp/gp_ep.c`) and the APU
opens its own output device, so a corrupted AC'97 cannot make the emulator
quiet. This is savestate correctness. It is not a loudness fix and no level
claim follows from it.

### The oracle: `docs/testing/aci_vmstate`

`make run`, three seconds, no ROMs, no device and **no configured QEMU build**
— which matters, because the desktop build does not configure on this machine
(`subprojects/curl-8.12.1/meson.build:532`, `Dependency "openssl" not found`;
`/usr/include/openssl/ssl.h` is absent and `pkg-config --exists openssl` fails,
so `docs/orchestration.md`'s "one `apt-get` away" is still accurate). A qtest
was not available for a second reason: `tests/` belongs to the remote lane.

Modelled on `psh_differ`, and for the same reason: the field list and the struct
it describes are **carved out of the tree** by `carve.py`, so the harness tests
`hw/xbox/mcpx/aci.c` and `hw/audio/ac97_int.h` rather than a copy that can
drift. Only `migration/vmstate.h` and `ac97_int.h` are used unshimmed — they are
the subject; everything else those two reach is an opaque stand-in in `shim/`.

Four checks:

1. **Byte coverage.** Walk the field list over `AC97LinkState`, record which
   bytes it touches, and require every `GUEST` member to be fully covered and
   every `HOST`, `DERIVED` or `TRANSIENT` member to be untouched.
2. **The round trip.** Fill the whole struct *and* PCI config space with a
   pattern so no reset value appears anywhere, save through the field list,
   `memset` the device to fresh, load back.
3. **The post-load opaque.** `post_load` must run exactly once and be handed
   `&state->ac97`.
4. **The drift gate.** The member list is generated, and every member needs a
   classification row. Adding a field to `AC97LinkState` fails the run.

**MEASURED:**

| arm | stream | guest state reproduced |
|---|---:|---:|
| `aci.c` as it stands | 716 B | **460 of 460** |
| PCI-only, the pre-fix list (control) | 256 B | **0 of 460** |

and `post_load ran once, with &state->ac97`.

The control arm is the part that makes the rest readable. A check that can only
pass is not a check, and this stream has already had two legs that could not
have failed. The harness *requires* the pre-fix list to report zero; if a future
edit made the two arms agree, the run fails.

The drift gate was verified the same way rather than asserted: adding a dummy
`uint32_t newly_added_thing;` to `ac97_int.h` produces

    FAIL  AC97LinkState.newly_added_thing has no classification in body.c.inc

and the member was removed again.

### The classification is the content of the fix

| class | members | why |
|---|---|---|
| **GUEST** (460 B, migrated) | `glob_cnt`, `glob_sta`, `cas`, `bm_regs[8]`, `mixer_data[256]` | guest-written or guest-visible |
| **DERIVED** (recomputed) | `voice_pi/po/mc`, `invalid_freq[8]` | `reset_voices`/`open_voice` from the mixer's rate registers |
| **TRANSIENT** (reset) | `last_samp`, `bup_flag`, `silence[128]` | the zero-fill generator's position and scratch |
| **HOST** (never migrated) | `pci_dev`, `as`, `audio_be` | installed by realize |

`ac97_link_post_load` is the re-derivation, exported from `hw/audio/ac97.c`
because the mixer register names and `reset_voices` are static there. A field
list without it restores the registers and leaves the open host voice at the
wrong rate, muted or inactive.

### `version_id = 2`, `minimum_version_id = 2`: refusing, on purpose

A v1 stream contains no codec bytes, so there is nothing to load and nothing to
reconstruct from. The only two options are to refuse the stream or to succeed
while silently restoring reset values — and the second **is** the defect. So it
refuses.

That is a real cost, stated rather than waved away: existing savestates of this
branch will not load. It falls where it is cheapest. xemu's snapshot UI lives
in `ui/xui/`, which `android/app/src/main/cpp/CMakeLists.txt:473` excludes from
the Android build outright, and nothing in the `android/` tree calls `savevm`
or `loadvm` — so no handheld user has a savestate to lose.

### The issue's own falsifier, answered

#75 was filed with a condition: "FALSIFIED IF `AC97LinkState` turns out to be
fully reconstructible from the guest's own reprogramming after a load — i.e. if
every field is rewritten before it is next read ... it has not been checked."

**MEASURED, from source. It is not reconstructible, and half of it is not the
guest's to rewrite.**

1. Nothing in the emulator reconstructs any of it. `mixer_data`'s only writers
   are `mixer_store` — reached from the guest's NAM writes — and `mixer_reset`,
   reached from a guest write to `AC97_Reset` or from a device reset. Every
   reader (`nam_read`, `update_combined_volume_out`, `update_volume_in`,
   `reset_voices`) reads it without reprogramming.
2. **`civ`, `piv`, `picb` and `sr` are ours, not the guest's.** They are the
   DMA engine's position through the buffer descriptor list, advanced by
   `transfer_audio` and `write_bup` (`ac97.c:813`, `:1065`, `:1075`), and the
   guest only *reads* them: `:673` (civ), `:689` (piv), `:736` (picb), `:767`
   (civ|lvi|sr), `:776` (picb|piv|cr). Of the bus-master registers the guest
   writes only `bdbar`, `lvi` and `cr`.

So a load that drops them hands the guest a reset position for a stream it
believes is mid-buffer, and no amount of guest reprogramming can restore a
number the guest never had. That second reading is the one that does not depend
on any title's behaviour, which is why it is the one to keep.

### An incidental find, with its own commit

**MEASURED, from source and from `git log`.** `ac97_post_load` in
`hw/audio/ac97.c` — the *generic* AC97 device's hook, not the ACI's — read

```c
    AC97LinkState *s = opaque;
```

That was correct until `7aa5985eba` ("Port AC97 factorization from XQEMU 1.x",
2018-06-26), which split
`AC97LinkState { PCIDevice dev; ... }` into
`AC97DeviceState { PCIDevice dev; AC97LinkState state; }` **precisely so the
Xbox ACI could embed the link state on its own**, and left the cast alone. A
device vmsd's `post_load` is handed the device state, so since then every load
of that device has read `PCIDevice`'s bytes as an `AC97LinkState`: `mixer_load`
returns config-space bytes, those go into `set_volume` and `reset_voices`, and
then `bup_flag` and `last_samp` are written back over the embedded
`DeviceState`.

Latent rather than live on this fork — the Xbox machine instantiates
`mcpx-aci`, not that device — and fixed anyway, because it is two lines and
struct offsets decide it with no oracle needed. It is also why the ACI reaches
its hook as a nested `VMSTATE_STRUCT`: `vmstate_load_state` passes the
sub-struct address there (`migration/vmstate.c:207`), so the same mistake is
not available to it, and the harness checks that pointer rather than trusting
the reasoning.

### What this does not prove

- **Not `post_load`'s re-derivation.** `ac97_link_post_load` is stubbed in the
  harness. The hook is proved reached with the right pointer; that
  `reset_voices` and `set_volume` recompute correctly needs a running emulator.
- **Not QEMU's own walker.** `body.c.inc` implements a minimal save/load walk
  and its own `vmstate_info_uint8/16/32/buffer`. It reads the *real*
  `VMStateField` arrays through the *real* macros, so offsets, sizes and types
  are genuine (a member/type mismatch is a compile error via `type_check`), but
  a defect inside `migration/vmstate.c` would not show up. It refuses rather
  than skips anything beyond fixed scalars, fixed arrays, fixed buffers and
  nested structs — a skipped field would read as covered.
- **Not a full-machine round trip.** Whether a loaded Xbox savestate is
  *usable* is a bigger question than whether this device's state survives.

---

## 2. #73 — the int16 monitor accumulator

### The issue's own premise is wrong, and that is the finding

#73 was filed as a density problem: "the monitor mix accumulates voices into an
`int16_t` that wraps", with the follow-up question "how many simultaneous
voices at what level would be needed". **The answer is that no number of voices
at any level can do it**, and this is the reason the previous pass measured zero
wraps at every density it could find.

**MEASURED, from source.** Voices are summed in **float**, not in the
accumulator: `vp.c:1582` sums each voice into `sample_buf`, `vp.c:1706` sums the
worker threads' partial buffers, and the result is converted **once** by
`src_float_to_short_array`, which clamps to ±1.0 before scaling
(`android/app/src/main/cpp/samplerate_stub.c:161`; the aarch64 path uses
`vminq/vmaxq` then `vqmovn_s32`, the scalar tail an explicit clamp). So the
value stored is already in range whatever the voice count.

What the `+=` accumulates is **slices**, and the schedule normally puts exactly
one value in each:

- `monitor.frame_buf` is `int16_t[256][2]` = eight 32-sample slices
  (`apu_int.h:104`);
- a VP frame writes exactly the slice at `(ep_frame_div % 8) * 32`
  (`vp.c`, the `MCPX_APU_DEBUG_MON_VP` block);
- `apu.c:692` pushes all 256 samples to the FIFO and `memset`s the buffer when
  `(ep_frame_div + 1) % 8 == 0`, and `apu.c:726` is the only increment.

Slice indices therefore run 0,1,…,7 and the buffer is zeroed after the eighth.
Every `+=` lands on a zeroed element and is equivalent to `=`. The other two
writers of `frame_buf` (`gp_ep.c:469`, `gp_ep.c:188`) are gated on different
monitor points and use assignment and `memcpy`, so they cannot contribute.

### The one path that is not ruled out

**MEASURED, from source.** `gp_ep.c:424` sets `ep_frame_div = 0` on **any** guest
write to `NV_PAPU_EPRST`, with a `FIXME: Still unsure about frame sync` already
on it, and does not clear `frame_buf`. If that write arrives with
`ep_frame_div % 8` in 1..7 — seven of the eight possible phases — the slices
already written this cycle are visited a **second** time, and two
near-full-scale samples of the same sign are then enough to overflow. That needs
no density at all, which is the opposite of what the issue assumed.

### What was changed, and what was deliberately not

The accumulation now **saturates** rather than wrapping. Two compares and a
store per sample, 64 per 5.333 ms frame. A wrap flips the sign of a loud
sample, which a band-limited 48 kHz signal does not do, so the artefact is a
click rather than distortion — but **no audible improvement is claimed**, and
the same commit adds the instrument that says why not.

**Deliberately not fixed: the frame-sync rewind itself.** Clearing `frame_buf`
on EPRST, or making the slice write an assignment, changes what the guest hears
on a path nothing has measured, and `gp_ep.c`'s own FIXME says the sync is not
understood. The clamp is the correctness floor; the rewind is the question the
new counter exists to open.

### The instrument measures the event, not the signature

The previous instrument was the level meter's wrap-suspect count: adjacent
*output* samples differing by more than full scale. That is a consequence of a
wrap and not the wrap, and the tracker says so — "a zero count does not prove
the accumulator never wrapped, only that it left no full-scale sign flip
behind".

`mon_acc:` counts the **precondition at the site**: how many samples found a
non-zero accumulator (`nonzero`), how many sums left int16 range
(`saturated`), and the largest magnitude seen (`maxabs`). `nonzero > 0` is the
event. One line per 5 s under `hakuX-audio`, on the census's existing cadence.

### Predictions, registered before either soak

`docs/testing/predictions/monitor-accumulator-saturate.json`, committed at
`f096815cb5` before both requests were queued, so the binding is a content hash
rather than a promise.

### Results

**MEASURED, two titles on two handhelds, both at ref `62eaa2f7f6`, binary
`64b0a6b4789e`.** Each was device-matched to its own reference run on purpose,
because a level compared across handhelds is not a repeat.

| run | device | output | reference | samples | `nonzero` | `saturated` |
|---|---|---:|---|---:|---:|---:|
| Crimson Skies `1789282799` | Thor | 87.941 s | `1789280122` | 8,639,936 | **0** | **0** |
| Galleon `1789282793` | Nova | 84.101 s | `1789279659` | 8,159,936 | **0** | **0** |

    mon_acc: window 480000 samples  nonzero 0  saturated 0  maxabs 30997 of 32767
             cumulative 8639936 samples nonzero 0 saturated 0

Every window is exactly 480,000 samples — 48,000 × 2 channels × 5 s, so the
monitor path is running at real time — and **16,799,872 samples across the two
runs with `nonzero` and `saturated` both zero**. `maxabs` touches 32,767 in
three windows and never exceeds it, which is the arithmetic above showing up
directly: the accumulator holds one already-clamped value.

| leg | verdict |
|---|---|
| **M1** instrument alive (control) | **PASSED** — 18 lines each, all windows non-zero |
| **M2** `nonzero == 0` | **PASSED** — 0 of 16,799,872 samples, both titles |
| **M3** `saturated == 0` | **PASSED** — 0, both titles |
| **M4** level unmoved, ±2.0 dB | **PASSED**, and far inside it (below) |
| **M5** steady-state starvation 0.0000% | **PASSED** on Crimson Skies; **FAILED** on Galleon |

**M4 is stronger than the tolerance it was registered at.** Against result
`1789280122` on the same device:

| statistic | reference L / R | this run L / R | Δ |
|---|---:|---:|---:|
| p50 | −15.95 / −15.65 | −15.85 / −15.65 | +0.10 / 0.00 |
| AC RMS | −14.00 / −13.98 | −13.96 / −13.94 | +0.04 / +0.04 |
| peak | 32,767 / 32,767 | 32,767 / 32,767 | — |
| clipped | 84 / 73 | **84 / 73** | 0 |
| maxjump | 21,866 / 22,628 | **21,866 / 22,628** | 0 |
| wrap suspects | 0 / 0 | 0 / 0 | — |

The clipped counts and the largest adjacent jumps are **identical to the
sample**, on a run 0.49 s longer. #72's correction said a clipped count is a
count of transients and not a property of the level, and two Galleon
playthroughs spread 16–45×; Crimson Skies' first 88 s from a cold force-start
evidently is not a playthrough but a fixed attract sequence, which makes this
a far tighter inertness check than the registered 2 dB. The clamp is inert to
the sample on this title.

Galleon's p50 moved +0.10 / +0.20 dB against `1789279659` (−29.05 / −29.05
against −29.15 / −29.25), peak at 32,767 on both channels, `maxjump`
11,405 / 10,264 inside the 8,970–13,096 range two earlier playthroughs
established, `wrap 0`. Its clipped counts (872 / 55) are wildly asymmetric and
far above the earlier 562/714 and 36/16 — which is #72's already-recorded
correction, not a new finding: a clipped count counts transients and two
playthroughs of a title that peaks at the rails do not contain the same ones.

The startup starvation windows read 45.4545% (Crimson, 55 of 121 callbacks) and
23.1405% (Galleon, 28 of 121), all of them *empty* callbacks — the guest not
having produced a sample yet — which is excluded per the corrected predicate in
`audio-baseline.md` 4a.

### M5 failed on Galleon, and the failure is an event rather than a shape

**MEASURED.** Galleon printed a **fourth** `starve:` line: 3 of 303 callbacks
short, 2 of them empty, 23,552 of 2,482,176 bytes zero-filled — **0.9488% of
that window and 0.1682% of the run's post-startup output**. M5 was registered
as "every steady-state `starve:` line reads 0.0000%", so this is a fail. It is
recorded as one rather than reclassified, because "a different exclusion reason
per case, chosen after seeing the result, is a curve fit".

And it cannot be dismissed as the shape of a run being torn down.
`apu_starve_report` prints **either** on a 30 s heartbeat **or** the moment
`d_short` becomes non-zero (`apu.c`, `if (d_short || heartbeat)`), so the three
reference runs' three lines each — `1789279659` Galleon, `1789280122` Crimson,
`1789279792` DOA3 — mean those runs had **zero** post-startup short callbacks.
The fourth line is an event report, not a partial window.

Two things argue the counter is not the cause, and both are arguments rather
than measurements, which is why they did not settle it:

- Crimson Skies carried the same counter on the same binary and printed the
  reference three-line shape with 0.0000% in both heartbeats.
- The counter's cost is **title-independent by construction**:
  `mon_acc_observe` runs once per *output sample*, not per voice — exactly
  480,000 per 5 s window in both runs, as both logs show. So the run that
  starved is the *sparser* title at identical instrument load, which is the
  wrong way round for an instrument cost.

The registered consequence of an M5 failure was that the counter comes out, so
the follow-up is the arm that decides it rather than an argument:
`docs/testing/predictions/monacc-starve-followup.json`, committed before either
arm was queued, with all four outcomes written down in advance.

- **A1** — Galleon on the Nova at `91255df20f`, which contains no `mon_acc`,
  shows at least one post-startup short callback. That exonerates the counter.
  *Fails* if arm A comes back with the clean three-line shape, in which case
  `mon_acc_observe` leaves the per-sample path.
- **B1** — the same Galleon soak at `62eaa2f7f6` again shows one. *Fails* if the
  repeat is clean, which would make the first observation a single-run draw —
  the failure mode this project already records as "a lone score change on one
  Nova run can be a one-off band".

`mon_acc`'s own numbers are unaffected either way: a starved sink callback drops
output it has already been handed, downstream of the accumulator.

<!-- FOLLOW-UP VERDICT -->

### What M2's zero does and does not bound

Roughly 8.6M samples, but occurrences would arrive in **bursts of at most
7 × 32 × 2 = 448 samples per rewind**, so the zero bounds *the number of EPRST
rewinds during 88 s of this title's play* — not a per-sample rate. It is
evidence of rarity at this configuration on this title. It is not proof the
rewind cannot happen, which is why the counter is permanent: every audio soak
from here on adds to it whether it was asked to or not.

### Disposition

The defect in the code is real and is now fixed at zero measured cost. The
hazard it guarded against is **unreachable through voice density by
construction** and **unobserved through the one path that remains**. #73 should
close on the arithmetic; the EPRST rewind is a separate, open question about
frame sync that `mon_acc`'s `nonzero` column now watches continuously.

---

## 3. #71 — the volume slider's curve and its label

### The disagreement

**MEASURED, from source.** `ui/xui/main-menu.cc:841` prints
`volume_limit * 100` as `"Limit output volume (%d%%)"`; `apu.c` applies
`pow(volume_limit, M_E)`. At slider 50% the gain is 0.15196, i.e.
**−16.37 dBFS**. `popup-menu.cc:314` labels the same value simply "Volume".

### The tracker's stated reason for blaming the curve is falsified

#71 argues: "There is no principled reason for the exponent to be e. A
perceptual taper uses a power of 2 to 3 by convention, or dB directly; e looks
like a placeholder."

**MEASURED, arithmetic.** *e* is 2.71828 — **inside** the 2–3 band that sentence
names as conventional — and it behaves like the textbook x³ audio taper to
within two percentage points of slider travel:

| curve | travel at which the gain reaches −6 dB |
|---|---:|
| x^e | 0.776 |
| x³ | 0.794 |
| linear | 0.501 |

Whatever the author intended, the curve is what convention would pick for a
linear-travel volume control. So "undocumented" cannot carry a change to it,
and this leg of the issue does not survive its own argument. What is left is
that the **label** makes a claim the control was never making.

### The migration arithmetic, which settles which half to change

`volume_limit` is persisted, it is the slider **position** and not the gain, and
`config_spec.yml` has **no version key** — so an old `0.5` and a new `0.5` are
indistinguishable and no one-time conversion is possible. Changing the curve to
linear would therefore raise the gain of every saved sub-maximum setting silently, and
only ever upward:

| saved `volume_limit` | today | as a linear gain | change |
|---:|---:|---:|---:|
| 0.90 | −2.49 dB | −0.92 dB | **+1.57 dB** |
| 0.75 | −6.79 dB | −2.50 dB | **+4.29 dB** |
| 0.50 | −16.37 dB | −6.02 dB | **+10.35 dB** |
| 0.25 | −32.73 dB | −12.04 dB | **+20.69 dB** |
| 0.0625 | −65.46 dB | −24.08 dB | **+41.38 dB** |

Unbounded as the setting approaches zero, and always louder — the direction that
can actually harm someone. Correcting the label costs nobody a decibel.

**Chosen: keep the curve, fix the label. Migration consequence for a user with
a setting already saved: none. Not one sample changes.**

### And a third convention, which decides the label's units

**MEASURED, from source.** The Xbox's own volume control is dB-denominated:
`AC97_Master_Volume_Mute` is six bits of attenuation at 1.5 dB a step — 94.5 dB
of range — read by `get_volume` with `mask 0x3f` in `hw/audio/ac97.c`. So the
label should print **dB**, not a second percentage, which also stops the same
disagreement recurring the next time the curve is touched.

### What was changed here, and the handoff

`ui/xui/main-menu.cc` belongs to another lane, so the desktop label was **not**
edited. The exact change it wants, for whoever owns it:

```c
    char buf[32];
    double g = pow(g_config.audio.volume_limit, M_E);
    if (g <= 0.0) {
        snprintf(buf, sizeof(buf), "Limit output volume (muted)");
    } else {
        snprintf(buf, sizeof(buf), "Limit output volume (%.1f dB)",
                 20.0 * log10(g));
    }
    Slider("Output volume limit", &g_config.audio.volume_limit, buf);
```

**The half that reaches this fork's users had no label to correct at all**, and
that is the part fixed here. The imgui audio menu is under `ui/xui/`, which
`android/app/src/main/cpp/CMakeLists.txt:473` excludes from the Android build
outright, so on a handheld nothing states this gain anywhere — a
hand-written `volume_limit = 0.5` in the toml produces −16.4 dB in silence.
#70 already named the consequence: "if the launcher ever writes a
volume_limit below 1, this alone produces 'unusually low', and the check costs
one question."

That check now costs zero questions. A non-unity `volume_limit` prints its
applied gain in dB and as a percent of full scale, under the `hakuX-audio` tag
every audio soak already collects, on **change** rather than once — a line
reporting only the first value goes stale the moment the desktop slider moves,
and a stale gain in a log is worse than none. Android never changes it, so
there it is one line per run.

Inert at the default either way: `volume_limit` is 1 in `config_spec.yml`,
forced to 1.0 on Android (`xemu_settings_android.cc:92`), and the block
requires `< 1`. The decision and its arithmetic are recorded **at the site**
so the next reader does not spend a build changing the exponent.

### Not fixed, and recorded instead

`0 <= g_config.audio.volume_limit` means a **negative** `volume_limit` skips the
block entirely and yields **full** volume rather than silence. The Android
loader clamps to [0, 1] (`xemu_settings_android.cc:346-352`); the desktop path
does not, so a hand-edited toml can reach it. One change at a time, and this is
a different one: it is out-of-range input handling, not the label/effect
disagreement #71 is about.

---

## 4. The least certain thing in this document

**That refusing version 1 savestates is the right call rather than merely the
defensible one.**

Everything else here rests on arithmetic or on a harness that fails when it
should. That one is a product decision made from inside the code, on the
argument that a silent wrong-state load is worse than a refusal, plus the
observation that no handheld user can have made such a savestate. If someone on
desktop has a library of states for this branch, the cost lands entirely on
them and they were not asked. The alternative — `minimum_version_id = 1` plus a
`post_load` that resets the codec when `version_id < 2` — loads the old stream
and still restores state the guest did not save, which is the same defect with
better manners. I chose the refusal; it is reversible in one line and the
argument for it should be checked by someone who knows whether this branch's
savestates are used.

A second, smaller one: the harness proves the field list, not
`ac97_link_post_load`'s re-derivation, and the AC'97 path is not audible on this
platform — so nothing here has been heard, only counted.
