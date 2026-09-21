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

The two windows, and what ran in them (`window_audit.py`, which is the check
and not a note about the check):

| window | open | T30 back | runs that finished inside | foreign |
|---|---|---|---|---|
| t26 | 17:15:01 | 17:24:45 | `t26-1` 17:19:35, `t26-2` 17:24:03 | **0** |
| stock | 17:24:51 | 17:36:30 | `stock-1` 17:29:20, `stock-2` 17:33:46 | **0** |

Four runs in 21 minutes of exposure, all four this lane's. Nothing else was
claimed for the thor in either window. That is luck as much as design -- four
arms requests sat in `queue/` throughout -- so the finding is "these two
windows were clean", not "this is safe". A dispatcher that knew about drivers
would not need the audit; see the follow-up at the end.

## R2. The stock arm's driver string is not valid JSONL, and it broke the label

Both stock runs first scored with `driver: ?`, which under this lane's own
**G2** ("a missing/unparseable session header is void and retaken") would
have thrown away the two runs the experiment most needs. It was the reader,
and the raw bytes say so: Adreno's driver string has **embedded newlines**,

    "driver":"Qualcomm Technologies Inc. Adreno Vulkan Driver (Driver Build:
    69e13475cb, ... Date: 12/27/23 Compiler Version: E031.41.03.47
    Driver Branch: )"

so a stock dump's session record spans **five physical lines** and
`json.loads(fh.readline())` sees an unterminated string. Both Turnip arms are
one line and parse, which is why nothing caught it until the third arm.

Note the shape of this, because it is the one worth carrying: **the
instrument failed on exactly the arm it was built to identify.** The whole
point of reading the driver off the dump was that "the swap did not take"
must be distinguishable from "the swap took", and the stock arm is the only
one of the three where those two produce different strings -- and it is the
only one the reader could not read.

Fixed in `score_arms.py`: accumulate physical lines until the record parses,
with `strict=False`, bounded at 12 lines, still requiring `t == "session"`.
The fix was made after seeing a run, so it is tested in both directions by
`tests_session_header.py`, and the two mutants were built and run:

| mutant | case that trips it |
|---|---|
| the old one-line `readline` reader | `multi-line driver recovers` FAILs |
| accumulate, but drop the `t == "session"` check | `no session record stays None` FAILs (it returns a draw record and calls the run headed) |

The real file passes all four cases. Neither mutant passes both, so the test
is not green-for-free -- which matters here because the loosening the second
mutant represents would silently disarm G2 for every future arm.

**The rates were never in doubt.** `stipple_classify` reads PPMs; the header
is read for the arm LABEL only. The stock numbers below are byte-identical
before and after the fix, and the fix's effect is that the label says
`Qualcomm Technologies Inc. Adreno Vulkan Driver` instead of `?`.

## R3. The answer: REFUTED at the stated sensitivity

All six runs of this lane are on the **thor**, at `ref 732b97e2df` /
`apk f326072aa6c8`, spec `600,after165,cap200`, 220 s. All pass **G2**
(**63-92** images, bar 60) and **G1**, below, per run and on the quantity G1
actually bounds. Every arm label below is the driver string read out of that
run's own dump.

| arm | run id | driver, from the dump | imgs | `R_full` | `R_lower` | med HF (whole frame) | med px (whole frame) |
|---|---|---|---|---|---|---|---|
| `t30-1` | `1789940132-drvab77-t30-1-1103129` | PurpleVK 26.3.0-devel | 63 | 9.5 | 23.8 | 1.758 | 34.2 |
| `t30-2` | `1789940135-drvab77-t30-2-1104874` | PurpleVK 26.3.0-devel | 92 | 5.4 | 16.3 | 1.635 | 33.6 |
| `t26-1` | `1789949705-drvab77-t26-1-1245715` | PurpleVK 26.1.0-devel | 78 | 5.1 | 15.4 | 1.753 | 35.0 |
| `t26-2` | `1789949708-drvab77-t26-2-1245737` | PurpleVK 26.1.0-devel | 83 | 8.4 | 22.9 | 1.723 | 34.6 |
| `stock-1` | `1789950291-drvab77-stock-1-1271457` | Qualcomm Adreno (build 69e13475cb) | 84 | 4.8 | 20.2 | 1.673 | 35.8 |
| `stock-2` | `1789950294-drvab77-stock-2-1271702` | Qualcomm Adreno (build 69e13475cb) | 76 | 9.2 | 23.7 | 1.658 | 34.7 |

**G1, stated on its own quantity.** P3 registered G1 against P1's
**whole-frame** medians, so those are the two columns above: median HF
**1.635-1.758** against the 1.24-2.14 bound, median frame brightness
**33.6-35.8** against 29.1-39.3. Every run passes with the whole bound to
spare, and across all ten runs (this lane's six and the band's four)
whole-frame content spans 7.5% in HF and 6.8% in brightness -- tighter than
P1's own 3.8%/1.5% suggested G1 would need to be, and the arms saw the same
scene. **G1's numbers are not transferable to `R_lower`.** That region's
medians run 1.438-1.691 and 27.9-33.7 over the same ten runs, and applying
G1's 29.1 brightness floor to them would void **C6 at 27.9** -- one of the
four runs that define the band this entire verdict is measured against. An
earlier draft of this paragraph mixed the two, quoting `R_lower` lows
(1.44, 29.7) against whole-frame highs (1.76, 35.8); corrected here, and see
R9.

`compare_arms.py` prints the arithmetic:

| | `R_full` | `R_lower` |
|---|---|---|
| t30 (this lane) | 5.4-9.5, mean 7.45 | 16.3-23.8, mean 20.05 |
| t26 | 5.1-8.4, mean 6.75 | 15.4-22.9, mean 19.15 |
| stock | 4.8-9.2, mean 7.00 | 20.2-23.7, mean 21.95 |
| largest between-arm mean gap | **0.70** | **2.80** |
| smallest WITHIN-arm difference | **3.30** | **3.50** |

**P4's rule, applied: no arm has both runs outside the T30 band on the same
side.** On `R_full` the band is 5.4-16.4 over six T30 runs, and **two** of the
six arm runs fall below its floor -- `t26-1` at 5.1 and `stock-1` at 4.8 --
with neither arm's partner joining it (8.4 and 9.2, both inside). So no arm
meets the rule. On `R_lower` the band is 16.3-30.1 and `t26-1` at 15.4 is the
only excursion, again with a partner (22.9) inside. **This is the registered
null: driver-dependence is refuted at this sensitivity.**

Note what the two low excursions are, since an earlier draft of this paragraph
counted only one of them: **every new batch of runs has pushed the low end of
this band down** -- 6.6 from the band's four, then 5.4 from `t30-2`, then 5.1
and 4.8 from the non-T30 arms. That is the pattern R0 flagged and it bears
directly on R5's "effects below the interval": the floor is not converged, and
a future lane that wants a tighter band must buy it with runs rather than
inherit this one.

Two things make it a stronger null than the bare rule requires:

- **Every between-driver gap is smaller than every within-driver gap.** The
  largest difference between two arms' means is 0.70 per 100 (`R_full`),
  while the smallest difference between two runs *of the same arm* is 3.3.
  The driver moves the number less than re-running the same driver does.
- **The three-driver spread is narrower than the one-driver spread.** Six
  runs across three drivers in one hour span 4.8-9.5 (1.98x). Four runs of
  one driver in lane.diagsoak77 span 6.6-16.4 (2.48x).

**And the sensitivity, in the terms registered before the answer.** T30's six
runs have sd 3.97 on `R_full`, so two runs per arm give 2 se of an
arm-vs-T30 difference of **7.9 per 100 -- 88% of the T30 mean**. On `R_lower`,
sd 4.71 and 2 se of 9.4, **39% of its mean**. So this refutes a driver effect
of roughly the size of the artifact itself and no smaller. **It does not say
the driver effect is zero**, and nothing downstream may quote it that way.
Halving the interval costs 4x the runs, i.e. ~6 more soaks per arm.

`R_lower` agrees with `R_full`, so P5's disagreement clause does not fire.
P5's claim that `R_lower` is the *more sensitive* read is withdrawn by R0 and
the numbers here confirm the withdrawal: its 39%-of-mean interval is better
than `R_full`'s 88%, but its band had to widen by the same 6-run correction,
and both give the same verdict.

## R4. The finding that outlives the null: the stipple is not Turnip's

The null says the driver does not move the *rate*. Something else in the same
six runs says more, and it is the thing to carry to the next lane:

**The artifact fires on all three drivers, including Qualcomm's own.** V0 --
does the artifact appear at all -- passes on `t26` (5.1, 8.4) and on `stock`
(4.8, 9.2), at rates statistically indistinguishable from T30's. The stock
arm is not a Mesa/Turnip driver at all; it is the vendor's proprietary Adreno
Vulkan driver, a completely different implementation.

So the deck/ground stipple in #77 is **not a Turnip bug**. A defect that
reproduces at the same rate on two Mesa builds two releases apart *and* on
the vendor's independent driver is a defect in what we hand the driver, which
means `hw/xbox/nv2a/pgraph/vk/` -- and per this lane's brief, changing that is
the follow-up this lane must not do.

**This also explains the void result of the earlier A/B** and closes it out.
Those four arms at `c866527e03` failed V0 on both Turnip arms, and the
tempting reading was "T26 and stock do not show it". They do -- at 5.1, 8.4,
4.8, 9.2 per 100. The old verdict was the 180 s soak never reaching the cave
scene and the old default bar, exactly as `nv2a_issues.toml`'s `blocked_on`
said. Nothing about the driver was ever measured there.

## R5. What this lane did not, and cannot, see

- **Which frames stipple, not how many.** Every number here is a rate. A
  driver that moved the artifact onto *different* frames while keeping the
  count would read as a perfect null. `score_arms.py` writes
  `flagged_frames` into its `--json` for exactly this, and nobody has looked.
- **Effects below the interval in R3.** 88% of the mean on `R_full` is a
  coarse instrument; a 30% driver effect would sit inside this null unseen.
- **Anything outside the cave scene.** All six runs sample one scene of the
  attract demo, because that is the scene the soak reliably reaches. The
  gameplay deck scene #77 was filed against is not what was measured, here or
  in PR #165.
- **The content/mip-level hypothesis**, which diagsoak77 named as the next
  instrument and which needs a code change. Out of scope by the brief.

## R6. For whoever schedules the next driver arm

`swap_driver.sh` defaults to the **Nova**, and the two devices are one
`SERIAL=` away from a silent cross-device measurement. More importantly the
dispatcher has no concept of an installed driver, so the swap window is
unguarded by anything but a lane remembering to audit it afterwards. The
cheap fix, if a second driver experiment is ever scheduled, is a `driver`
field on a request that the worker installs and restores around the run the
way it already does for `env` -- `dispatcher.sh`'s env handling is the exact
shape, including the marker that makes cleanup safe. That is a harness
change, not an issue, and belongs in a lane of its own.

## R7. Lane status at close

- Six arms run, all scored, verdict **refuted at the stated sensitivity**;
  reading posted to #77 and carried in PR #197's body.
- `preflight.sh --allow-tracker` on this branch: every gate green except
  **coverage**, which fails on **#200** -- an unrelated open issue with
  neither a lane nor a `blocked_on`. The three remedies the gate offers are
  all edits to board files, which a lane may not make, and `--allow-tracker`
  does not cover this gate. That red belongs to the board and was red before
  this branch existed; it is recorded in the PR body and in the board request
  rather than worked around.
- Board request filed at `dispatch/board-requests/drvab77.md`: `issue.77`'s
  `blocked_on` is discharged (it was correct -- the void A/B was the soak),
  #200's coverage row needs a board hand, and the `swap_driver.sh` gap in R6
  is recorded there as a harness lane rather than as a new issue.
- No source file, prediction, golden or board file was touched. Files are
  `docs/lanes/drvab77/**` only.

(R8 and R9 below are the remediation pass for audit
`docs/audits/2026-09-20-drvab77-pass1.md`, written after R7 was.)

## R8. The sampling cadence of the ten runs, and what it is worth

The audit's M1: `score_arms.py` warned on `b != a + 1`, which is true of
almost every adjacent pair of a `cap200` dump, so the warning fired on every
run ever taken and the operator therefore never read it -- and the first four
gaps it printed were always the routine ones, so the three runs with a real
hole printed the same reassuring line as the four band runs. **Nothing in
this lane's record ever stated the spacing, which means nothing in it stated
that the six arms and the four band runs were sampled differently.** They
were:

| run | imgs | median gap | max gap | max/median | holes > 2x median |
|---|---|---|---|---|---|
| C3 | 73 | 10 | 15 | 1.5 | 0 |
| C4 | 73 | 10 | 16 | 1.6 | 0 |
| C5 | 73 | 10 | 15 | 1.5 | 0 |
| C6 | 76 | 9 | 15 | 1.7 | 0 |
| `t30-1` | 63 | 10 | **43** | **4.3** | **3** |
| `t30-2` | 92 | 7 | 15 | **2.1** | **1** |
| `t26-1` | 78 | 9 | **38** | **4.2** | **1** |
| `t26-2` | 83 | 7 | **53** | **7.6** | **5** |
| `stock-1` | 84 | 9 | 15 | 1.7 | 0 |
| `stock-2` | 76 | 9 | 15 | 1.7 | 0 |

The four runs that define the band have no hole at all; four of this lane's
six do. The bar (2x the run's own median) is not tuned: the two populations
are 1.5-1.7x and 2.1-7.6x, and 2.0 is the gap between them. Why the holes
appeared in this lane's runs and not in the band's is not established here.

**And whether the rates are stable under it, which is the question M1
actually raises.** A hole matters only through the classifier's local
baseline: across one, a frame's +-10-image baseline is drawn from a longer
stretch of wall time, so the smooth animation trend the local median removes
is removed less well and a frame riding a ramp could clear the 1.45x bar. So
re-score each run over only the frames whose baseline window contains no
anomalous boundary, and compare:

| run | `R_full` whole run | hole-free frames only | `R_lower` whole run | hole-free only | n |
|---|---|---|---|---|---|
| `t30-1` | 9.5 | 10.0 | 23.8 | 26.7 | 30 |
| `t30-2` | 5.4 | 6.9 | 16.3 | 13.9 | 72 |
| `t26-1` | 5.1 | 6.1 | 15.4 | 16.7 | 66 |
| `t26-2` | 8.4 | 8.8 | 22.9 | 26.5 | 34 |
| C3-C6, `stock-1`, `stock-2` | unchanged | (no holes) | unchanged | (no holes) | -- |

Three things follow, and the third is the one that matters:

1. **The direction is wrong for the feared mechanism.** All four `R_full`
   rates go **up** when the hole-affected frames are removed, not down. A
   hole manufacturing false flags would do the opposite. Across the ten runs
   only one flagged frame in `R_full` sits immediately across an anomalous
   hole at all (`t26-2`, image 75); dropping it takes that run from 8.4 to
   7.2, and no arm changes side.
2. **The magnitude is inside the instrument's own resolution.** The largest
   shift is 1.5 per 100 on `R_full` and 3.6 on `R_lower`, against R3's
   stated 2 se intervals of 7.9 and 9.4. On `R_full` it is also well under
   the smallest within-arm difference (1.5 against 3.3); on `R_lower` the
   two are the same size (3.6 against 3.5), which is one more reason
   `R_lower` may not be called the more sensitive read.
3. **The verdict does not move.** On the hole-free rates the arms are
   t30 10.0/6.9, t26 6.1/8.8, stock 4.8/9.2: no arm has both runs outside
   the band on the same side, every between-arm mean gap (max 1.45) is still
   smaller than every within-arm difference (min 2.7), and `R_lower` agrees.
   Same null.

Caveat, stated rather than buried: the hole-free subsets are small (30 and 34
images for `t30-1` and `t26-2`), so those two columns are noisier than the
whole-run ones. They bound the effect of the holes; they are not a better
estimate of the rate.

`score_arms.py` now reports median gap, max gap and the LARGEST holes, and
says `SPACING ANOMALY` only when the max exceeds 2x the run's own median --
so the line is silent on the band's four runs and loud on the four that
earned it.

## R9. The remediation pass, and the decisions on the LOWs

Audit `docs/audits/2026-09-20-drvab77-pass1.md`: 0 HIGH, 5 MEDIUM, 4 LOW. The
audit re-derived all twenty rates from the PPMs and confirmed them, so no
number in this lane changed; what changed is the reporting and the tooling.

| finding | what changed |
|---|---|
| **M1** gap detector fires on every run, hides the real holes | `spacing()` in `score_arms.py` reports median/max gap and the largest holes, flagging only above `ANOMALY_RATIO`; R8 states the profile and measures what it is worth |
| **M2** R3's G1 range mixes whole-frame and `R_lower` numbers | R3's table now carries per-run whole-frame med HF and med px, with a paragraph on why G1's bound does not transfer to `R_lower` (it would void C6) |
| **M3** the P4 sentence counts one low excursion where there are two | corrected in R3: `t26-1` 5.1 **and** `stock-1` 4.8, neither partner joining |
| **M4** `window_audit.py` asks "finished inside", not "overlapped" | rewritten as an overlap test on `[queued, done]`, plus an artifact-evidence second pass so a queue-straddler is `QUEUED-THRU` rather than a false contamination; `tests_window_audit.py` pins both |
| **M5** case 4 does not pin the bound (the unbounded mutant passes) | cases 5 and 6 added: a record closing one line past `MAX_HEADER_LINES` must not be read, and one spanning exactly it must be, with `_header_lines` asserted |

M4's remedy needed one thing the audit did not call for. Re-running the audit
as a plain `[queued, done]` overlap turned up
`1789893938-arms-remote-base-4039343` -- **queued 01:45, ran 21:53-22:00 on
the thor** -- straddling both windows by queue time while running four hours
after the last one closed. Reporting that as contamination would have
rebuilt M1's defect inside M4's fix: a check that is always right and
therefore never read. Hence the two classes. **R1's published finding is
unchanged: 4 runs executed inside the two windows, all four this lane's, 0
foreign.** The one queue-straddler is now named in the output instead of
being invisible.

Both checks were run against mutants of themselves rather than asserted to
work. `tests_session_header.py`: the old one-line reader fails cases 1 and 6,
dropping `t == "session"` fails 3, deleting the bound fails 5, an off-by-one
bound fails 6. `tests_window_audit.py`: the original finish-time test fails
the straddle case, and an overlap test with no artifact evidence fails the
queue-straddler case. A positive control on real data confirms the second
file is not blind by construction -- given a window placed inside
`arms-remote-base`'s actual run, it reports that run as FOREIGN.

**R7's board red has cleared.** This pass merged `origin/master` (21 commits;
`git log HEAD..origin/master` over `galleon_flash_rate.py` and
`stipple_classify.py` is empty, so the ten scored runs are unaffected by it),
and `preflight.sh --allow-tracker` is now green on every gate including
**coverage** -- #200 was handled on the board side. R7's "every gate green
except coverage" is superseded here rather than by editing it.

**The LOWs, decided:**

- **L1** (`score_arms.py` documented a void rule it did not implement) --
  **fixed, as code rather than as a retraction.** `--expect-driver SUBSTRING`
  marks a run `VOID (driver)` and exits 1. P2's rule is now machine-checked
  for the next driver experiment, which is the reader that needs it.
  Exercised both ways on real dirs: `--expect-driver PurpleVK` voids a stock
  run, `--expect-driver Adreno` passes it, and `--expect-driver 26.1.0` voids
  a T30 run -- the discriminating case, since the two Turnip arms differ only
  in version.
- **L2** (`galleon_flash_rate` imported only as a side effect of the line
  above) -- **fixed**: `docs/testing` is inserted explicitly.
- **L3** (R3's "76-92 images" excludes `t30-1` at 63) -- **fixed**: 63-92.
- **L4** (`window_audit.py`'s inputs are unverifiable) -- **partly fixed, and
  the rest declined with a reason.** `--results` (or `HAKUX_RESULTS`),
  `--window` and `--mine` are now arguments. The audit's suggestion to point
  the bounds at `swap_driver.sh`'s own log cannot be taken: that script lives
  outside this repository and writes neither a log nor a marker, so there is
  no artifact to point at. The docstring now says so in place of implying
  provenance the numbers do not have, and R6's request -- a `driver` field on
  the request, which would put the swap in the dispatcher's own log -- is the
  real fix.
