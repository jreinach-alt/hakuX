# #77's blocker, tested: what an unattended Galleon soak can and cannot measure

Run 2026-09-14 by `lane.scene77`, offline, over the four 180 s soaks the
driver A/B already left on disk. No device time, no new capture, no build.

## The claim, and the falsifier it was registered with

`nv2a_issues.toml` blocks #77 on this:

> A soak cannot park a camera, so what it renders is Galleon ATTRACT DEMO --
> a scripted loop cutting between cliffs, caves, sky and Loading cards -- and
> `galleon_flash_rate.py` sets its bar from the median/MAD of the frames it
> is handed, which assumes one scene with a parked camera. Over a loop the
> bar is set by the cuts.

and registers its own falsifier:

> if that were false, the attract demo would contain a sustained single-scene
> segment long enough for the median/MAD bar to be set by the deck rather
> than by scene cuts -- observable offline by segmenting any existing 180 s
> soak.

`blocker_tested` said "not run, and it is cheap and offline". It is cheap and
offline. This is it, in `docs/testing/galleon_scene_segments.py`.

## Verdict

**The falsifier as registered FAILS, and the blocker's stated mechanism is
REFUTED. They are not the same finding, and the second is the useful one.**

| clause | answer |
|---|---|
| (a) a sustained single-scene segment of >= 40 frames | **NO** -- longest anywhere is **at most 35 frames** |
| (b) "over a loop the bar is set by the cuts" | **NO** -- windows spanning 4 to 14 cuts still reach bar/median 1.43-1.45 |

So the soak cannot give you one scene, which is what the blocker said. But
the reason it could not judge the artifact is **not** the reason the blocker
gives. The cuts do not float the bar. Something else does, and it is named
at the bottom.

## What was on disk, and where

Four 180 s soaks at `c866527e03`, all on the Thor, `bdc158a5`:

| arm | result dir | frames | sample interval |
|---|---|---|---|
| T30a | `1789363404-galleon77-survey-3334081` | 114 | 1.66 s |
| T30b | `1789364165-galleon77-t30b-3548320` | 108 | 1.74 s |
| T26 | `1789364831-galleon77-t26-3691881` | 105 | 1.79 s |
| stock | `1789365054-galleon77-stock-3695896` | 105 | 1.79 s |

**The frames are not in those directories.** Every one of the four
`result.json` files records `"pulled": []`; the result dirs hold a logcat and
nothing else. The 1920x1080 screenshots live in the A/B lane's scratchpad,
`survey_t30/ t30b/ t26/ stock/`, each with a `frames.tsv` of index,
timestamp and byte count. Anyone re-running this needs to know that, because
the obvious place has no images in it.

## Geometry, measured rather than assumed

  * **Guest viewport**: columns 240..1679 of the 1920x1080 screenshot, all
    1080 rows. Pinned by per-column temporal std over 4 arms x 15 frames:
    column 239 is 0.0 and column 241 is 42.2. 1440x1080 is 4:3 and
    1440/640 = 1080/480 = **2.25**, which is the upscale the A/B measured
    from the other end.
  * **The modal dialog's opaque box**: rows 275..747, columns 372..1547, as
    the >200-luma block. That is 61.3% x 43.8% of the screen -- the 61% x 44%
    already recorded -- and **36% of the guest frame**, which this script
    discards.
  * **The dialog is up in every frame of every arm** bar one: the last frame
    of T30a and of T26, during teardown. An earlier reading that T30a and T26
    had it up only part of the time was an artefact of those two frames: one
    dark frame in 115 otherwise-constant white ones produces a temporal std
    of sqrt(1/115 x 114/115) x 215 = 19.9, which is the ~20 that was seen.
  * **A clean band with no constant overlay in it**: native y336..444, full
    width. Taking the minimum across-arm temporal std, the ONLY pixels in the
    ground half of the frame that are near-constant over a whole run are the
    nav-bar icons at y447..463, 0.66% of the band. Cutting at y=444 leaves a
    640x108 band of pure scene.

## The founding capture is itself a 2x NEAREST upscale

Worth recording because the campaign's registered numbers rest on it.
`images/galleon-deck-normal.png` is 1280x960. Its horizontal power spectrum
has a spike at **exactly** the normalised frequency 0.5 -- 7.4e-04 against
1.3e-05 at 0.45 and 5.2e-06 at 0.55 -- and 38% of its horizontal neighbours
are equal. That is pixel replication, not detail: the guest frame is 640x480
and the capture doubled it.

So `galleon_flash_rate.py`'s baselines (deck HF median 4.655, town 3.340) are
figures on a 2x nearest upscale, not native ones. This is the same class of
error the A/B found on the soak side -- measuring HF on an upscale measures
the resampler -- on the other instrument, and it means **the two absolutes
were never comparable.**

## Calibrating the pass bar through this script's own chain

The first version of this instrument set its "is this live textured content"
guard at HF >= 3.0, borrowed from those baselines. **That guard rejected every
window in every soak and returned the blocker's own answer**, because the
soak reads HF median 0.54 in the same units. A guard imported across two
different resampling chains manufactures whatever it was set to manufacture.

What transfers is the *ratio*. So the parked deck mosaic was pushed through
this script's chain -- 2.25x upscale, the 0.40 modal dim, BOX resample back
-- with the compositor's filter bracketed, since it is not known:

| parked reference | HF median | bar/median |
|---|---|---|
| deck mosaic, as registered | 4.655 | 1.448 |
| deck -> native -> chain, BILINEAR / NEAREST / BICUBIC | 2.25 / 3.53 / 2.79 | 1.271 / 1.382 / 1.303 |
| deck as native -> chain, BILINEAR / NEAREST / BICUBIC | 1.95 / 2.73 / 2.30 | 1.394 / 1.467 / 1.385 |
| town mosaic, as registered | 3.340 | 1.219 |

**A parked camera lands at bar/median 1.22-1.47 whatever the filter.** The
pass bar used is 1.45, the top of that bracket, which is generous to the
falsifier on purpose.

The guards were re-set in the soak's own units, and the separation there is
not where it was assumed to be:

| | HF | consecutive-frame motion |
|---|---|---|
| black screen / Loading card | 0.00-0.11 | 0.00-0.21 |
| frozen "press START" title card | **1.01** | 0.06-0.12 |
| live gameplay ground | 0.30-1.25 | 4-15 |

**HF alone cannot reject a frozen card: the card reads HIGHER than gameplay,
because its text is high-frequency.** The motion guard is what does that job,
and it sits in a gap two orders wide. The run reports the verdict with each
guard switched off; neither changed any arm's answer.

## (a) The longest single-scene segment

A cut needs a bar, and the bar is not chosen here: it is **each run's own
median histogram distance between two randomly paired frames** -- the
distance between two unrelated frames of that run. A transition short of it
is not called a cut, so segments come out too LONG, which is the direction
that favours the falsifier.

Colour is load-bearing. On a luminance thumbnail a red-lit chamber, a green
outdoor stretch and a grey stone corridor sit 5-15 apart, inside the 9.0 that
one step of ordinary camera motion costs; on a 4x4x4 RGB histogram they are
0.12-0.49 apart, at or above the unrelated-frame level. The first version of
this script was luminance-only and found a 35-frame "cut-free" run that a
contact sheet shows is four or five different places.

| arm | cut bar | cuts | longest segment | as time |
|---|---|---|---|---|
| T30a | 0.114 | 18 | **35** frames [29..64) | 58 s |
| T30b | 0.111 | 21 | 23 frames [36..59) | 40 s |
| T26 | 0.128 | 15 | 32 frames [22..54) | 57 s |
| stock | 0.110 | 18 | 25 frames [38..63) | 45 s |

**35 against the 40 needed** -- and 35 is an upper bound, not a value. Each
of those four segments still contains six or seven transitions at half the
cut bar or more, several within a per cent of the bar itself (T30a's segment
holds one at 0.114 against a bar of 0.114). Tighten the bar and they shorten
at once: at 0.08 the longest anywhere is 23 frames, at 0.06 it is 17.

**So no arm holds one scene for the registered length, and the answer is not
close in the direction that matters.** What would have been needed: 40
samples at ~1.7 s is **68 seconds of one continuous shot**, in an attract
loop that cuts 15-21 times in 180 s -- a mean shot length of 8.6-12 s.

## (b) The cuts are not what sets the bar

This is the half the blocker got wrong, and it is measured on the same data.

| | bar/median |
|---|---|
| whole soak, all 105-114 frames | 2.14-2.36 |
| best 40-frame window, any of the 15 ground regions | **1.300-1.377** |
| longest window reaching <= 1.45 | 47-88 frames, **spanning 4-14 cuts** |
| single-scene segments of >= 5 frames | median 1.31-2.02, **range 1.01-5.45** |

Read the last two rows together. A 67-frame window of T30a that crosses
**nine** scene cuts reaches bar/median 1.448, inside the parked bracket --
while single-scene segments in the same run run as high as 5.45. **Scene
identity and bar tightness are close to uncorrelated here.** Being one scene
does not make the bar tight, and spanning cuts does not make it loose,
because MAD is a median of deviations and a handful of cut frames in a
40-frame window does not move it.

So "over a loop the bar is set by the cuts" is false as stated. The bar over
a soak is perfectly capable of sitting where a parked camera's sits.

## What this instrument cannot see

Stated before any of the above is allowed to mean anything.

  1. **The frames are 1.4-1.8 s apart, not consecutive.** Galleon runs at
     14-26 fps here, so consecutive samples are 20-40 guest frames apart. A
     cut and 1.5 s of camera motion are not separable by any per-pair
     measure, which is why the verdict on (b) is not routed through a cut
     threshold at all. It also means this can only refute *"no sustained
     segment"*; a single-scene stretch shorter than ~1.5 s is invisible to it.
  2. **36% of every guest frame is behind the modal dialog and is discarded**,
     including the whole centre. The 0.40 dim scales HF median and MAD
     together, so bar/median -- a ratio -- survives it; absolute HF from this
     script does not, and is not comparable to the mosaics'.
  3. **It cannot see the artifact, only whether the bar could.** A window
     that reaches 1.45 says the instrument would work there; it says nothing
     about whether a stipple frame is present.
  4. **The upscale filter is unknown**, so everything calibrated through the
     chain is reported as a bracket over BILINEAR, NEAREST and BICUBIC rather
     than a value.
  5. **The scene descriptor sees only the two unoccluded bands.** A cut
     between two shots that share a colour distribution in those bands reads
     as no cut, which again lengthens segments.

## The real blocker, which is neither (a) nor (b)

Two numbers, both from above:

  * A parked deck through this chain reads **HF median 1.95-3.53**.
  * The soak's ground band reads **HF median 0.54-0.70**, in every one of the
    four arms and in all 15 candidate regions.

**The attract demo's ground carries three to five times less high-frequency
content than the surface the artifact was characterised on.** A bar can be
tight and still be over the wrong surface.

And that feeds straight into the A/B's registered gate. At bar/median
1.30-1.45, how many of the four *known* stipple frames still clear the bar
after this chain? Bracketing the native-resolution assumption:

| | f4 | f8 | f13 | f32 | clear at +45% |
|---|---|---|---|---|---|
| as registered | +93% | +69% | +46% | +77% | 4 / 4 |
| as-native -> chain | +87..+92% | +59..+69% | +23..+43% | +78..+94% | 3 / 4 |
| ->native -> chain | +35..+44% | -2..+18% | -2..-1% | +104..+129% | 1-2 / 4 |

So this chain's detection efficiency for a real stipple event is **25% to
75%**. A true rate of 10-14 per 100 would read as **2.5 to 10.5 per 100**.

**#77's driver A/B registered V0 as ">= 3 stipple frames per 40" -- 7.5 per
100 -- and both T30 arms failed it.** That gate sits inside the band the
instrument would produce *with the artifact firing at full strength*. V0
could not distinguish "the artifact is absent" from "the chain ate half of
it", so the two T30 arms being void by V0 is at least partly a statement
about the instrument and not about the drivers.

It does not rescue those arms. The A/B's own conclusion stands: the artifact
did not appear in any arm, and 0-2 events in ~90 frames is below even the
attenuated floor of 2.25-9.5 events that a firing artifact should have given.
**The null is not explained by the attenuation.**

## What re-judging the A/B on a segment would, and would not, buy

The falsifier's premise was that finding a segment would let the driver A/B
be re-judged on data already collected. Taking that seriously:

**It would buy:** a bar in the right place. (b) shows that is already
available without a single-scene segment -- a 40-frame window at bar/median
1.30-1.38 exists in all four arms, and the A/B could be re-scored on one
today at no device cost.

**It would not buy:** a valid A/B. Three separate reasons, none of which a
segment touches.

  1. **The arms are void by their own registration**, not by later judgement.
     V0 failed before any comparison; a better bar applied afterwards is a
     post-hoc rescue of a pre-registered failure, which is the thing
     registration exists to prevent.
  2. **The artifact was not present to measure.** Re-scoring a null with a
     tighter bar gives a tighter null.
  3. **The arms are not frame-locked.** The A/B leaned on "the demo is
     scripted and repeats", and it does -- but only loosely. Aligning T30a
     against the other three, the best offset is -3 to -5 frames at a
     distance of 10.2-12.2, against 23.1-24.0 for a shuffled pairing and 8.8-
     9.3 for *adjacent frames inside one run*. So two arms at their best
     alignment are about as similar as two consecutive frames of one arm:
     in phase to within 5-8 s, not to within a frame. Per-frame matching
     across arms carries that much slack, and the loop does not repeat within
     a run either -- lag 56 matches only the static title card (distance
     0.12-0.26), while gameplay at the same lag is at the unrelated level
     (14.5-23.4).

So the honest position is the one #77 already holds: **the marker-file-armed
frame dump is still the route**, and the reason is the workload, not the bar.
What changes is the justification. It is not "a soak cannot park a camera so
the bar is set by cuts" -- the bar is fine. It is that an unattended soak puts
the wrong surface under the bar, at a third to a fifth of the texture detail
the artifact needs, for shots averaging 8.6-12 s.

## Reproducing

```bash
python3 docs/testing/galleon_scene_segments.py \
    <scratch>/survey_t30 <scratch>/t30b <scratch>/t26 <scratch>/stock
```

Exit 0 if a qualifying single-scene segment exists, 1 if not. `--cut-bar`
overrides the per-run derived bar for a sensitivity sweep; `--bar-ratio`,
`--min-len`, `--min-hf` and `--min-motion` move the pass bar and the guards.
The baselines it is calibrated against are reproduced by
`galleon_flash_rate.py` on the two mosaics in `images/`.
