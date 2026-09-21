# lane.fulldisc50 -- #50's full-disc instability rate, measured at n=13 with no device time

Issue #50. Brief: dispatch 5 fresh full-disc (`--base-iso` interactive,
1,673-capture) `Blend tests` runs, ~28 min each, then run
`docs/testing/fulldisc_instability_50.py` against the 5-run set and report a
rate split by device with the per-capture spread.

**The 5 runs the brief asks for already exist, and there are thirteen of
them.** They were dispatched by lane.blendrace50 on 2026-09-19 (PR merged),
they carry the exact provenance the brief specifies, and the brief's own
instrument reads them without modification. **No device time was spent by
this lane.** The rate below is the brief's deliverable, computed from those
13 runs.

blendrace50 is not superseded by this and is not repeated here: it was
briefed to produce **a table and deliberately no rate** ("There is no mean
anywhere in the file"). This brief asks for the rate. That is the gap this
lane fills, plus the three limits on it that the rate alone would hide.

## The population, checked rather than assumed

`request.json` for `1789819561-blendrace50-nova-415002`:

    request.base_iso   = '/home/justin/nxdk_pgraph_tests_xiso_interactive.iso'
    request.suites     = ['Blend tests']
    request.runs       = 5
    request.only_tests = []
    request.ref        = '49afee8889'      ->  apk_sha b0cba34acef7

So the brief's `--base-iso the interactive ISO` requirement is satisfied by
the runs on disk, not merely by their `disc_id`. Composition, verified by
set arithmetic rather than by the label:

| | captures |
|---|---:|
| the 1,673-capture composition these runs scored | 1673 |
| the 105-capture release-disc `Blend tests` set, a strict **subset** of it | 105 |
| present only in the interactive composition (the `TestDetailed` captures) | **1568** |

`105 + 1568 = 1673`. This resolves a wording collision between two merged
lanes: blendrace50's addendum calls these "release-disc captures" and
blendarm50 calls the same runs "the interactive disc". blendarm50 is right;
blendrace50 meant only "not the `iso_oldbt` oracle set". Anyone filtering
#50's artefacts on that phrase will pick the wrong 105.

Thirteen runs, one binary, one composition, both devices:

| device | runs | source |
|---|---:|---|
| nova | 6 | `blendstack-A#1`, `blendrace50-nova#1..#5` |
| thor | 7 | `blendstack-B#1`, `blendstack-thor2#1`, `blendrace50-thor#1..#5` |

All at `apk_sha b0cba34acef7`, all `only_tests` empty, all 1,673 captures.
`scorer_rev` is **not** constant (absent / `4a6a98dce4` / `027fa3d552`),
which is why every number below is taken on sha256 of the capture PNG, with
the `differing` column printed alongside as a cross-check. On this data the
two instruments name the same 22 captures.

## THE RATE, split by device

A *departure* is a run whose capture bytes are not that device's modal bytes
for that capture. Denominator is capture-runs = runs x 1,673.

| device | runs | departures | capture-runs | **rate** | 95% Wilson |
|---|---:|---:|---:|---:|---|
| **nova** | 6 | 21 | 10,038 | **0.2092%** | [0.1369%, 0.3196%] |
| **thor** | 7 | 1 | 11,711 | **0.0085%** | [0.0015%, 0.0484%] |
| *(pooled -- do not use)* | 13 | 22 | 21,749 | *0.1012%* | *[0.0668%, 0.1531%]* |

**The pooled row is printed only to be refused.** The two devices' intervals
do not overlap; pooling them is the same error class #50 withdrew the 7.7%
for, one axis over. nova races **~25x more often than thor**.

Per run, which is the shape a fix-judging decision actually runs into:

| device | departures per run | clean runs |
|---|---|---:|
| nova | 2, 2, 3, 4, 4, 6 | **0 of 6** |
| thor | 0, 0, 0, 0, 0, 0, 1 | **6 of 7** |

Fisher exact on clean-run counts, two-sided: **p = 0.0047**. The device
difference is in *how often the race fires*, not in the rendered output --
all 22 movers are races (one device disagreeing with itself) and
**zero** are device-only differences.

## Per-capture spread

All 22 events, `differing` column, odd run against that device's mode:

| statistic | value |
|---|---:|
| delta magnitude, min | **0** |
| delta magnitude, median | 12,288 |
| delta magnitude, max | 58,183 |
| events with delta **0** in the count | **2 of 22** |

Largest: `cA_MIN_srcRGB` 8,192 -> 66,375 (+58,183). Smallest non-zero:
`1-cRGB_SADD_1-dstA` 76,032 -> 75,008 (-1,024).

**The two delta-0 events are the load-bearing part of this table.**
`1-cA_SADD_1-srcA` and `1-srcRGB_SADD_1` moved their *bytes* while their
`differing` count stayed identical. `ab_compare` judges on that count. So a
count-only instrument is blind to **9% (2 of 22)** of this race's events --
wrong replaced by equally-wrong, at an unchanged pixel total.

## What this means for judging a #50 fix on a single run

Observed whole-suite behaviour, and the independent-per-capture model that
reproduces it:

| comparison size | nova, modelled | thor, modelled |
|---|---:|---:|
| 1 capture | 0.209% | 0.009% |
| 4 captures (a typical prediction's legs) | 0.834% | 0.034% |
| 10 captures | 2.07% | 0.085% |
| all 1,673 (a byte-identical whole-suite arm) | **97.0%** | **13.3%** |

The model is checked, not assumed: it predicts 97.0% / 13.3% of runs dirty
and the observed values are **6/6 nova and 1/7 thor**. nova's per-run counts
have mean 3.50, variance 2.30, **index of dispersion 0.66** -- not
overdispersed, so the events do not cluster within a run and multiplying the
per-capture rate over k captures is licensed.

So `#50`'s standing rule needs splitting in two:

- **A whole-suite byte-identical arm on nova cannot be judged on one run.**
  Not "risky" -- it has never once come back clean in 6 attempts, and the
  model says 97%.
- **A targeted 4-leg prediction is a different question**: under 1% per run
  on nova, 0.03% on thor. Naming the legs is worth more than repeating the
  run, and pinning the arm to **thor** is worth ~25x on its own.

Two limits on the k-capture arithmetic, both checked:

- Movers do not concentrate in part of the disc (KS against uniform over the
  run order: D = 0.151, **p = 0.665**), so "any capture can be hit" is not
  contradicted.
- **0 of 22 movers fall in the 105-capture release subset** -- but that
  subset is only 6.3% of the disc, so under uniformity the expected count is
  1.4 and P(zero) = 24%. **This is not evidence that release-disc captures
  are immune.** It is the sample being too small to say, and it is the one
  question 5 more runs would begin to answer.

## The composition axis, unchanged

`1-dstA_SUB_1-cRGB` remains the only capture with a genuine composition
effect: thor reads 12,512 on the 5-test disc in 5 runs and 16,384 on the full
disc in all 7 -- **disjoint** sets. `1-srcRGB_SADD_0` reads 76,032 on the
narrowed discs (15 runs) which is *within* the full disc's {98,304, 76,032},
so it is the race not firing, not a composition effect. Disjointness, not
inequality, is the test.

## Why no runs were dispatched

The brief's premise -- that this measurement does not exist -- is false, and
the board comment it came from
([2026-09-21T15:10Z](https://github.com/jreinach-alt/hakuX/issues/50), "the
full-1,673-capture instability measurement [is] still open") postdates
blendrace50's own result comment on the same issue by two days.

Dispatching anyway would have cost ~140 min of device for one of two
outcomes, neither of which changes a decision:

1. **At `--ref 49afee8889`** (the only ref that keeps `apk_sha
   b0cba34acef7`): pure duplication. Projected, assuming each device holds
   its observed rate:

   | | now | after +5 runs |
   |---|---|---|
   | nova | 0.2092% [0.1369, 0.3196] | 0.2119% [0.1551, 0.2896] |
   | thor | 0.0085% [0.0015, 0.0484] | 0.0100% [0.0027, 0.0363] |

   No conclusion above moves.

2. **At any newer ref**: a different `apk_sha`, which
   `fulldisc_instability_50.py` excludes by its own control 1 and by the
   hardcoded `APK = "b0cba34acef7"`. The brief's literal instruction --
   fresh runs *and* that instrument -- is self-defeating: the instrument
   cannot see the runs.

That is a judgement, not a hold; the session opened with device holds
lifted. If the board wants the newer-binary question, it is a **different**
measurement needing its own brief, its own pin, and an edit to that script's
APK constant (outside this lane's `Files:` grant) -- and note the owner
killed the last #50 arm aimed at master's binary as a side quest.

## A trap the next lane will walk into

Inventorying full-disc `Blend tests` runs by `apk_sha` turns up **a second
binary**, `a0fe6a75cfe2`, with 2 nova runs, 1,673 captures each, no missing
PNGs, same capture set as the 13 above. It looks exactly like a free
second-binary control.

**It is `1789963700-blendarm50-1474765`, the arm the owner killed**, and its
`ERROR` marker says: *"It must never be scored, compared, or used as a
baseline."*

I compared those two runs before checking for the marker. **That comparison
is withdrawn and its values are not recorded here or anywhere else in this
PR.** The marker's stated reason (partial captures) does not visibly apply to
runs 1 and 2, and that is precisely the reasoning to refuse: blendarm50
already worked through it and declined, warning that *"the next lane should
not talk itself past that marker either"*. The owner stopped the question,
not just the third run.

Concretely, for whoever greps next: **`apk_sha a0fe6a75cfe2` with 1,673
Blend captures is the killed arm.** Nothing in a by-apk inventory says so.

## What the next lane should not repeat

- **Do not dispatch full-disc `Blend tests` runs to measure instability.**
  13 exist at one binary and one composition, 6 nova + 7 thor, and the rate
  is above. ~28 min each; ~140 min to learn nothing new.
- **Do not pool the devices.** nova 0.209%, thor 0.0085%, non-overlapping
  intervals, Fisher p = 0.0047.
- **Do not judge a whole-suite byte-identical #50 arm on one nova run.**
  0 of 6 nova runs were ever clean. Pin to thor and name the legs.
- **Do not trust the `differing` column alone for this race.** 2 of 22
  events moved bytes at an unchanged count.
- **Do not read "0 of 22 movers in the release subset" as immunity.**
  P(zero) under uniformity is 24%.
- **Do not score `a0fe6a75cfe2` / `1789963700-blendarm50-1474765`.** See
  above.
