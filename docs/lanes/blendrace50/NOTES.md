# lane.blendrace50 -- #50 full-disc run-to-run instability

Brief: get an honest run-to-run measurement on the FULL 1,673-capture disc,
per capture, and say which captures actually race (vary run-to-run on the
SAME disc) versus which only vary BETWEEN disc compositions.

## Starting state

`nv2a_issues.toml` issue.50 carries `blocker_tested = "REFUTED"`, on the
grounds that three full-disc runs already exist "at ONE apk_sha
(b0cba34acef7) and ONE disc_id (iso:85b525/Blend tests)", and
`fulldisc_instability_50.py` reports 5 of 1,673 captures differ across them,
with the shape "4 of the 5 outliers are the SAME RUN (blendstack-A), the
fifth is run B -- instability is RUN-SCOPED, not per-capture."

The first half is right and worth keeping: the blocker said the cheapest
honest measurement was five fresh full-disc runs, and three were already on
disk. The shape read off them is the part that does not follow.

## Finding 1: the three runs span two devices, so "run-scoped" was one of two readings

`result.json` for each:

| run | requester | device_label | device_serial | apk_sha | disc_id | scorer_rev |
|---|---|---|---|---|---|---|
| 1789318910-blendstack-A-63953 | blendstack-A | **nova** | ee317437 | b0cba34acef7 | iso:85b525/Blend tests | *(absent)* |
| 1789318915-blendstack-B-64031 | blendstack-B | **thor** | bdc158a5 | b0cba34acef7 | iso:85b525/Blend tests | 4a6a98dce4 |
| 1789326864-blendstack-thor2-889257 | blendstack-thor2 | **thor** | bdc158a5 | b0cba34acef7 | iso:85b525/Blend tests | 027fa3d552 |

`fulldisc_instability_50.py` asserted `(apk_sha, disc_id)` equal and refused
to summarise otherwise -- a real control, and it holds. It did not read
`device_serial`, and the three runs span **two devices**. A is the only nova
run. So "4 of the 5 outliers are the same run, A" and "4 of the 5 outliers
are the only nova run" are the same statement about that data.

This was not unknown to the repository -- `devices.sh` says it plainly:
"#50's pair was split across the two handhelds by a scheduler fallthrough,
five of 1,673 captures moved, and nothing here can say whether that is the
disc or the devices". The `nv2a_issues.toml` entry is what dropped the
caveat, and it is the entry a lane reads first.

`scorer_rev` also differs across all three (absent / 4a6a98dce4 /
027fa3d552), a second uncontrolled variable on the same axis. It turned out
not to matter -- see Finding 3, the bytes agree with the counts -- but
nothing in the comparison had established that.

## Finding 2: split on the device and 4 of the 5 movers stop being movers

Same three runs, same five captures, regrouped by device. Values are the
`differing` column; each list is one value per run on that device:

| capture | nova (1 run) | thor (2 runs) | reading |
|---|---|---|---|
| `1-srcRGB_SADD_0` | 76032 | **98304, 76032** | thor disagrees with itself -> **RACE** |
| `cA_MIN_srcRGB` | 66375 | 8192, 8192 | each device constant -> **DEVICE** |
| `1-dstRGB_MIN_1` | 23552 | 8192, 8192 | each device constant -> **DEVICE** |
| `srcA_REVSUB_1-cA` | 23552 | 16384, 16384 | each device constant -> **DEVICE** |
| `1-dstA_SUB_1-cRGB` | 27136 | 16384, 16384 | each device constant -> **DEVICE** |

So on this data the run-scoped set is **one** capture, not four, and it is
not the one the entry attributes to a run: it is `1-srcRGB_SADD_0`, the
capture #50's own blocker already named. The other four are a nova/thor
difference that two thor runs reproduce exactly.

`1-srcRGB_SADD_0` is sharper than the count shows. By capture bytes, nova
run A and thor run thor2 are **bit-identical** (`869c6adc3f2333e7`) and thor
run B alone departs (`04c506d560813fe4`). The two devices agree to the byte
on 2 of 3 runs and one thor run left; that is the signature of a race, not
of a device.

## Finding 3: the capture bytes agree with the `differing` count here

The `differing` column is a scalar projection of an image, so it can report
stability that is not there. Hashing all 1,673 PNGs in each of the three
runs: **5 hash-unstable, the same 5 the count names, 1,668 bit-identical
across all three runs.**

That is worth stating as a limit rather than a licence: it establishes the
count hid nothing *in this data*, not that a count is a safe instrument. The
rewritten script reads both and prints any disagreement.

## Finding 4: disc_id still cannot separate the narrowed discs on disk

The narrowed-disc runs (`race-distribution` x2, `movers-stability`) carry
disc_id `iso:85b525/Blend tests` -- **byte-identical to the full 1,673-capture
disc's id** -- because they predate 63db4e4211, which folded `only_tests`
into disc_id. That fix is prospective; it does not retrofit the artefacts.

So any analysis of this data that keys on `(apk_sha, disc_id)` re-commits the
pooling error #50 withdrew a rate for, and would cheerfully average a
1-capture run against a 1,673-capture one. `fulldisc_instability_50.py`
escaped it only by hardcoding three directories. The rewritten script keys
composition on `frozenset(scored keys)`, which cannot lie about what ran.

**For the next lane: do not filter #50's artefacts on disc_id.** Filter on the
capture set.

## Finding 5: the composition axis, separated

Narrowed-disc values (thor only), printed against the same device's full-disc
values and never pooled with them:

| capture | thor, 5-test disc (x5) | thor, 1-test disc (x10) | thor, full disc (x2) | reading |
|---|---|---|---|---|
| `1-dstA_SUB_1-cRGB` | 12512 | -- | 16384, 16384 | **COMPOSITION**: 12512 is a value the full disc never produces on thor |
| `1-srcRGB_SADD_0` | 76032 | 76032 | 98304, 76032 | overlapping -- the race simply did not fire in 15 narrowed runs |
| `1-dstRGB_MIN_1` | 8192 | -- | 8192, 8192 | no composition effect |
| `cA_MIN_srcRGB` | 8192 | -- | 8192, 8192 | no composition effect |
| `srcA_REVSUB_1-cA` | 16384 | -- | 16384, 16384 | no composition effect |

Only `1-dstA_SUB_1-cRGB` shows a composition effect, and the entry already
records it (12,512 narrowed vs 16,384 full). Note the discrimination rule
that matters: a narrowed value must be **disjoint** from the full-disc set to
count. "Not equal" is not enough -- `1-srcRGB_SADD_0` narrowed reads 76032,
which is unequal to `{98304, 76032}` and is simply the race not firing. The
first version of my own comparison flagged it as a composition effect on
exactly that mistake.

## The measurement queued

Two requests, both full disc, both at `--ref 49afee8889`, whose cached APK
`builds/49afee8889.apk` hashes to `b0cba34acef7` -- the *same binary* the
three existing runs used, so no rebuild and all runs are poolable on the
binary axis:

- `1789819556-blendrace50-thor-414959` -- `--runs 5 --device thor`
- `1789819561-blendrace50-nova-415002` -- `--runs 5 --device nova`

`--runs 5` on one request is the right instrument: the dispatcher loops five
times inside one claim, so all five share one device, one APK, one disc build
and **one scorer_rev** -- the three variables the existing trio does not hold
fixed. Runs are 830-1033s each, comfortably inside `run_disc.sh`'s 1800s
ceiling (nova is ~20% slower than thor, itself a datum for a timing race).

Five runs per device, rather than five on one, because the classification in
Finding 2 needs each device to be able to disagree with itself, and because
`devices.sh` names extending its equivalence check to this disc a
**prerequisite** for any cross-device Blend comparison -- the check has never
run on 64x256 RT blits, which is #50's mechanism.

## Finding 6: the device split and the race deposit the SAME KIND of wrong pixel

`blend_mover_content_50.py`. Over the pixels where the odd run departs:

| capture | odd run | moved px (RGB) | alpha-only | grey (R==G==B) | who matches the golden there |
|---|---|---|---|---|---|
| `cA_MIN_srcRGB` | nova-A | 61502 | 0 | 74.9% | thor-B 58183, nova-A **0** |
| `1-dstRGB_MIN_1` | nova-A | 21504 | 1024 | 90.5% | thor-B 15360, nova-A 1024 |
| `srcA_REVSUB_1-cA` | nova-A | 14336 | 0 | 71.4% | thor-B 8592, nova-A 1728 |
| `1-dstA_SUB_1-cRGB` | nova-A | 21504 | 1024 | 90.5% | thor-B 12688, nova-A **0** |
| `1-srcRGB_SADD_0` | thor-B | 22880 | 0 | 97.3% | thor-2 22272, thor-B **0** |

Two things to take from this:

- **The odd run is always the wrong one.** On the four device captures nova
  is wrong and thor matches hardware; on the racing capture thor-B is wrong
  and both nova and thor-2 match hardware *and each other to the byte*.
- **The wrong content is grey**, 71-97% of it, in the device case and the
  race case alike. One failure signature with two triggers is the reason to
  look for one mechanism rather than two.

Spatially, the four device captures diff identically between nova and each
thor run and are bit-identical thor-to-thor; the racing capture is
bit-identical nova-to-thor2 with thor-B alone departing. Every diff sits in
rows 112-367 -- the 256-row band of #50's 64x256 stack -- which is also why
nearly every `differing` value in this issue is a multiple of 256.

## Finding 7: two mechanisms for that grey, both refuted

1. **It is the alpha channel** (an alpha-stack render landing where a colour
   stack belongs -- `DrawAlphaStack` draws alpha as greyscale, so this is the
   obvious first guess). **Refuted: 0** of every grey pixel equals the
   golden's alpha there, and 0 equals the capture's own alpha. It is not a
   function of the golden pixel at all -- golden `(0,102,0)` and golden
   `(41,0,0)` both map to grey 10.

2. **It is another image** -- a predecessor's framebuffer surviving, the
   RenderTextureLoop class `make_test_iso.py` documents. Searched twice:
   against all 1,673 **goldens**, and against all 1,673 captures **the odd run
   itself produced** (the second is the one that matters, since our output
   differs from the goldens on 1,672 of 1,673, so leaked content would be our
   render, not hardware's). **Refuted: flat.** Best non-self candidate scores
   24.9-33.5%, sitting *at* the pool's own p99 in every case. The immediate
   predecessor scores 0.0% in four of the five.

So the moved pixels hold structured grey content that is not this capture's
alpha, not any golden, and not any other capture the run produced. **No site
is named by this pass** -- three doors are closed, which is the honest state.

## Finding 8: when nova fails #507 and #550 it deposits the same content on both

The one score that stands out of the pool. nova's wrong output on
`1-dstRGB_MIN_1` (#550) reproduces **81.0%** of nova's wrong output on
`1-dstA_SUB_1-cRGB` (#507), and symmetrically -- against a pool p99 of 33.3%.

Controlled, because two similar tests would score high for free: over the
same mask, on the run that got **both right**, thor-B's #550 reproduces
**42.9%** of thor-B's #507. So the failure makes the two captures *more* alike
than correct rendering does, 81.0% against a 42.9% baseline.

Read narrowly: consistent with both failures depositing shared content rather
than each being independently wrong. It is n=2 captures and it names no site.

## Finding 9: a periodic clock excursion, tested against the movers and rejected

The per-test progress log carries **negative** durations -- about -24,500 ms
-- on 38-44 of 1,673 tests per run (2.3-2.6%), on both devices, spaced at a
constant ~24.5s of wall clock regardless of device pace. (It is the guest test
binary's own timer; a `(\d+)ms` regex silently drops these rows, which is how
they were nearly missed.)

Tempting, and wrong: the excursion lands on `1-srcRGB_SADD_0` in **nova-A** --
the run that reads the *correct* 76032. The odd run, thor-B, has a perfectly
ordinary 524 ms. **The race is on the run without the clock event**, so this is
not the mechanism. Recorded so the next lane does not re-find the correlation
and build on it.

## Results of the ten queued runs

(pending)
