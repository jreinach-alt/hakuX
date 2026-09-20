# lane.drvab77 -- does #77's stipple rate move with the GPU driver?

Issue: #77. Base: master @ 0efbe904df (post PR #165, lane.diagsoak77).
Files: `docs/lanes/drvab77/**` only. No source file, no board file, no
prediction (there is no golden and no suite behind #77, so there is no arm to
register -- the falsifier below is registered here instead, in the same
commit discipline a prediction would have).

---

# PRE-REGISTERED, before any run of this lane existed

Everything from here to the `---` was committed before this lane queued
anything. The four runs it rests on (`C3`-`C6`) are lane.diagsoak77's, taken
on 2026-09-19 and already published in PR #165.

## P0. The question, and why it is askable now and was not before

#77's driver A/B was run once, at `c866527e03`, T30/T26/stock, 180 s each, and
came back **void**: the Turnip arms never reached a scene with enough texture
detail for the old instrument's bar to mean anything. That verdict is about
the old soak length and `galleon_flash_rate.py`'s default bar, not about the
driver. Two things have since changed, both from lane.diagsoak77:

- a soak of `600,after165,cap200` reliably lands inside the attract demo's
  cave scene, which *does* show the artifact; and
- `stipple_classify.py` classifies on an absolute, artifact-anchored ratio
  (`hf >= 1.45 x local median`) instead of on a MAD bar that a smooth
  sequence manufactures a 13.3-per-100 reading out of.

## P1. The yardstick, re-derived here rather than quoted

The brief's "6.6 to 16.4 per 100 same-driver spread" was re-computed from the
PPMs on disk before registering anything against it, with this lane's own
`score_arms.py` (whole frame, window 10, ratio 1.45 -- all defaults, nothing
tuned):

| arm | run id | images | stipple | per 100 | median HF | median mean px |
|---|---|---|---|---|---|---|
| C3 | `1789845130-diagsoak77-C3-244939` | 73 | 7 | **9.6** | 1.686 | 34.4 |
| C4 | `1789845134-diagsoak77-C4-245190` | 73 | 5 | **6.8** | 1.649 | 34.2 |
| C5 | `1789846228-diagsoak77-C5-310205` | 73 | 12 | **16.4** | 1.712 | 33.9 |
| C6 | `1789846232-diagsoak77-C6-310227` | 76 | 5 | **6.6** | 1.706 | 34.1 |

Reproduces PR #165's four numbers to the decimal, so the instrument in this
lane is the instrument that produced the band.

**And all four ran the SAME driver, read off the dump and not off a note.**
Each `framedump_*.jsonl` opens with a session record carrying the driver
string the emulator got from the Vulkan implementation it loaded. All four
say `PurpleVK public driver (PurpleVK 26.3.0-devel (git-62ac221a33))`.
`~/hakux-work/drv/T30/meta.json` is `driverVersion 26.3.0-T30-1.4.359` and
`T26/meta.json` is `26.1.0-T26-1.4.344`, so **the published band is the T30
band**, and `26.3.0` vs `26.1.0` in that header is a clean, machine-read
discriminator between the two Turnip arms.

**Two things the re-derivation turned up that PR #165 does not say:**

1. **The kept images are not consecutive frames.** `cap200` fills at frame
   ~73 of 600, and the dump spreads its image budget: the PPMs are `f004,
   f013, f023, f032, ...`, one every 9-10 frames. So
   `stipple_classify.py`'s `+-10 frame` local window is in truth a `+-~95
   frame` window of wall time. This does not weaken the comparison -- it is
   the same instrument on the same spec that produced the band, and a sampled
   sequence is the case the classifier's ratio bar was validated on -- but a
   reader must not think "10 neighbouring frames".
2. **The content regime is extremely repeatable.** Median HF over the four
   runs spans 1.649-1.712 (a 3.8% spread) and median frame brightness
   33.9-34.4 (1.5%), while the stipple *rate* over the same four runs spans
   2.5x. The scene is the same to within a few per cent every time; the rate
   is not. That is what makes P3's content guard cheap and sharp.

## P2. The arms, fixed before any of them ran

Six soaks, all on the **thor** (`bdc158a5`, the device the band was measured
on), all at **`ref 732b97e2df`** -- the same commit and the same cached
`apk_sha f326072aa6c8` the band was measured with, so the binary is not a
variable and no arm needs a build -- all `--title "Galleon (USA).xiso.iso"
--seconds 220 --env XEMU_FRAME_DUMP=600,after165,cap200 --pull 'framedump_*'`.

| arm | driver installed by | expected header |
|---|---|---|
| `t30-1`, `t30-2` | resting state, no swap | `PurpleVK 26.3.0-...` |
| `t26-1`, `t26-2` | `swap_driver.sh t26` | `PurpleVK 26.1.0-...` |
| `stock-1`, `stock-2` | `swap_driver.sh stock` | a Qualcomm/Adreno string, not PurpleVK |

Two runs per arm because this issue has already withdrawn one conclusion
drawn from one run, and because P1's own band shows two same-driver runs
landing at 6.6 and 16.4.

**The arm label is DERIVED, never typed.** Every run is scored by
`score_arms.py`, which reads the driver out of that run's own dump header. A
run whose header does not name the driver its arm asked for is **void and
retaken**; it is not relabelled to match what the header says, because a swap
that silently did not take also means the device was in an unknown state.

## P3. The two guards, registered before the numbers exist

**G1 -- content.** A rate is only comparable across arms if the arms saw the
same scene; the old void result was exactly a content failure wearing a
driver label. From P1, a run of this spec has median HF `1.65-1.71` and
median frame brightness `33.9-34.4`. Registered bounds, deliberately wider
than that spread: a run is **void on content** if its median HF falls outside
**1.24-2.14** (+-25%) or its median frame brightness outside **29.1-39.3**
(+-15%). A void-on-content arm is reported as *this driver did not reach the
scene*, which is a finding about the soak and **not** evidence about the
stipple rate.

**G2 -- the dump fired at all.** A run with fewer than 60 images, or with a
missing/unparseable session header, is void and retaken. (The band's runs
have 73-76.)

## P4. The falsifier, in the brief's own terms

- **REFUTED AT THIS SENSITIVITY (the null).** Every arm's two runs land
  inside or overlapping the T30 band **6.6-16.4 per 100**. This is a result,
  not a failed lane: it says the driver does not move the stipple rate by
  more than the run-to-run spread of one driver.
- **DRIVER-DEPENDENT.** *Both* runs of one arm land clearly outside
  `6.6-16.4` **on the same side**, so that arm's range does not overlap the
  band. One outlying run is not a result and will be reported as one run.
- **VOID for an arm** if G1 or G2 takes it out, stated as such.

**THE SENSITIVITY, STATED BEFORE THE ANSWER SO IT CANNOT BE STRETCHED
AFTERWARDS.** The band is 6.6-16.4 over four runs of one driver, i.e. a 2.5x
run-to-run spread on a mean of ~9.9. Two runs per arm against that band can
only see an effect that pushes *both* runs past 16.4 (roughly `>=1.7x` the
T30 mean) or below 6.6 (`<=0.67x`). A null here therefore bounds the driver
effect at *roughly a factor of 1.7*; it does **not** say the driver effect is
zero, and nothing downstream may quote it as if it did. Buying a tighter
bound means more runs per arm, and the cost is ~11 min of device time each.

---

# Results

Nothing above this line has been edited since it was committed. Where a run
made a registered choice look wrong, it is recorded below rather than by
editing the registration.
