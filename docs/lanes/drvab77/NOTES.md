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

## P5. The second region, registered while the first arm was still running

Timed honestly: this section was written after `t30-1` was queued and while it
was in flight, and **before any result of this lane existed** -- no PPM of
this lane had been scored, and `t30-1`'s result dir held no `DONE`. It is an
addendum to P2's "both regions are reported", not a choice made after seeing a
number.

`R_lower` (`--region 0,288,640,480`, the bottom 40% where ground and deck sit)
over the same four runs, again reproducing PR #165's figures exactly:

| arm | R_lower stipple | per 100 |
|---|---|---|
| C3 | 20 / 73 | 27.4 |
| C4 | 22 / 73 | 30.1 |
| C5 | 17 / 73 | 23.3 |
| C6 | 17 / 76 | 22.4 |

**The T30 `R_lower` band is 22.4-30.1 per 100, and it is a 1.34x spread
against `R_full`'s 2.5x.** That makes it the more sensitive of the two reads
-- on the same four runs it would notice an effect less than half the size.
It is registered here as a **secondary** read, with the same rule and the
same arithmetic as P4: driver-dependence needs both runs of an arm clearly
outside 22.4-30.1 on the same side, which is `>=1.15x` or `<=0.85x` the T30
mean of ~25.8.

**Neither region is promoted over the other after the fact.** If the two
disagree -- `R_full` null and `R_lower` outside its band, or the reverse --
the verdict reported is the one from `R_full` (the pre-registered primary,
and the band the brief names), and the disagreement is reported as a
disagreement. PR #165's own caveat is carried with it: `R_lower` was refused
by that lane's confound guard on C5 and C6, so its *correlation legs* there
were descriptive only. That guard is about pairing frames with draw records
and does not touch the rate, which is measured from pixels alone -- but a
reader who wants to lean on `R_lower` should know the guard has fired on this
region before.

---

# Results

Nothing above this line has been edited since it was committed. Where a run
made a registered choice look wrong, it is recorded below rather than by
editing the registration.

## Why attempt 1 did not finish

It queued two of the six registered arms -- `t30-1` and `t30-2`, the two that
need no driver swap -- and stopped with the PR in draft while they were in
flight. Both landed (`DONE`, 2026-09-20 14:39 and 14:44 local) and were never
scored, because the session that queued them ended waiting on them. Nothing
was lost: the two result dirs are intact and are scored below, so attempt 2
spends no device time re-taking them.

What it did not do is the half of the experiment that needs
`swap_driver.sh` -- `t26-1/2` and `stock-1/2` were never queued at all. So
the answer to the brief's question did not exist when attempt 1 ended, and
`R0` below is the first arm of it to be scored.

## R0. The T30 arms, and the registered band is already too narrow

Both runs pass **G2** (63 and 92 images, bar is 60) and **G1** (median HF
1.758 / 1.635 against the 1.24-2.14 bound; median frame brightness 34.2 /
33.6 against 29.1-39.3). They are valid runs of the registered spec, on the
thor (`bdc158a5`), at `ref 732b97e2df` / `apk f326072aa6c8`, and the driver
string read off each dump is `PurpleVK 26.3.0-devel` -- T30, derived, not
typed.

| arm | run id | imgs | `R_full` per 100 | `R_lower` per 100 | med HF | med px |
|---|---|---|---|---|---|---|
| `t30-1` | `1789940132-drvab77-t30-1-1103129` | 63 | **9.5** | **23.8** | 1.758 | 34.2 |
| `t30-2` | `1789940135-drvab77-t30-2-1104874` | 92 | **5.4** | **16.3** | 1.635 | 33.6 |

**Registered before any run, and the first two runs already fall outside
it.** P1's `R_full` band is 6.6-16.4 and `t30-2` scores 5.4. P5's `R_lower`
band is 22.4-30.1 and `t30-2` scores 16.3 -- 27% below its floor. These are
**T30 runs, the same driver the band was measured on**, so this is not a
driver effect: it is the same-driver spread being wider than four runs of it
could see.

This is recorded here rather than by editing P1 or P5. Its consequence for
the verdict is stated once, now, before any non-T30 number exists:

- the honest same-driver `R_full` spread is now **5.4-16.4 over six runs**
  (3.0x, not 2.5x), and `R_lower` **16.3-30.1** (1.85x, not 1.34x);
- P4's rule is unchanged in form -- both runs of an arm clearly outside, same
  side -- but the band it is applied against is the six-run one above, because
  a band that its own driver's next run falls out of is not a bar;
- so the sensitivity is **worse** than P4 advertised: `R_full` can now only
  see an effect of roughly `>=1.7x` on the high side or `<=0.55x` on the low,
  and `R_lower`'s advantage over `R_full` is largely gone. **`R_lower` is
  still reported as the pre-registered secondary, but it may no longer be
  described as the more sensitive read.** P5 said it was; six runs say it is
  not.

Widening a band after seeing a number is exactly the move a pre-registration
exists to stop, so note what is and is not happening here: the number that
widened it is from the **control** arm, the arm whose driver defines the
band, and it widens the band in the direction that makes a positive result
HARDER to claim. Nothing below may narrow it again.

## R1. The swap protocol, and the window it exposes

`swap_driver.sh` is an out-of-band adb write -- it is not routed through
`request.sh`, and the dispatcher knows nothing about it. Two hazards, both
handled before the first swap rather than after:

1. **It defaults to the wrong device.** The script's `SERIAL` defaults to
   `ee317437`, which is the **Nova**. The band and every arm of this lane are
   on the **thor**, `bdc158a5`. A swap run with the default serial would
   install T26 on a device this lane never touches and leave the thor on T30,
   and the arm would come back "t26" with a T30 rate in it. Every swap here
   is `SERIAL=bdc158a5`, the meta.json is read back off the thor before the
   soak is queued, and `score_arms.py` derives the arm from the dump header
   anyway -- three independent chances to catch the same mistake.

2. **A swapped driver is installed for every request, not just mine.** While
   T26 or stock is on the thor, ANY request the dispatcher claims for the
   thor runs on it. `affinity.py` hashes unpinned requests over the serving
   devices, so another lane's A/B arm can land there, and nothing in that
   lane's result would say its binary ran on a different Vulkan driver. That
   is the "arm B inherits arm A's independent variable" failure
   `dispatcher.sh` names as the purest form of what the queue exists to
   prevent, and this lane would be the one causing it.

   So: the swap windows are **recorded as epoch ranges** below, kept as short
   as the runs allow (both runs of an arm share one window; T30 is restored
   between arms), my own soaks are pinned `--device thor` so they cannot
   wander, and **after the last restore every result dir that started inside
   a window is listed** -- if any request other than this lane's ran on the
   thor in one, it is named here and on its own lane's PR. An empty list is
   reported as an empty list, not as an absence of risk.
