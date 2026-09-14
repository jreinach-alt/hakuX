# #67 on the device: the FRNDINT fix measured, and three things that went wrong with the measuring

**Arms.** A `e2b6abde73`, apk `2bf7afdc6877`. B `7420d389f5`, apk `6bf6a11955f3`.
Thor, one run each, 4-suite disc `4-suites:7254741c` (Blend tests, Point size,
Stencil, Viewport), identical in both arms. `ab_compare` reports
**PRE-REGISTERED**, bound sha256 `e59bbbe2…`.

## The headline

| | A | B |
|---|---:|---:|
| captures | 154 | 154 |
| exact | 21 | **134** |
| differing px | 1,860,504 | **61,975** |
| structural px | 1,826,897 | **61,975** |

Per suite: **Blend_tests 105 of 105 better, 1,711,362 → 0 — every capture in the
suite now byte-exact.** Point_size 4 better. Stencil 5 better, 1 worse. Viewport
12 unchanged.

This is the fix the remote lane wrote in `target/i386/tcg/fpu_helper.c` and
could not measure, because it lives inside `#if defined(XBOX) &&
defined(__aarch64__)` and that lane has no Android device. Its own registration
says so: *"EVERY pixel leg needs an Android device arm and this lane has none."*
Its desktop falsifier — 236/236 byte-identical under both renderers — tests the
**scoping** and is blind to every pixel the fix is for.

## The verdict is FAIL, and two of the three reasons are mine

### 1. Ten `expect` legs matched no capture

Registered as `Blend tests::#spot_0_ADD`. `ab_compare` keys rows
`"%s/%s" % r["key"]` — `Blend_tests/#spot_0_ADD`. All ten were **inert**: they
could not have failed. The arm still returned PRE-REGISTERED, because that
states the file was bound before the device ran, not that anything in it was
measurable.

Fixed at the source: `request.sh` now refuses, at queue time, any `expect` key
that names no capture in the goldens, with a `did you mean`. Negative-tested on
the actual bad file, positive-tested on the same file with keys rewritten, and
tested again with one bogus key among ten good ones.

### 2. The absolutes came from a stale sweep

The legs said fifteen `#spot_*_SADD` must fall to **96,855, not zero** — #43's
ink under the corrected 24-px swatch. I recomputed that from `scores1.tsv`
rather than copying it, and said so in the prediction as the reason to trust it.
The arithmetic was right. The result it came from was `z-tip-009-Blend_tests`,
apk `88452c539d64`, an **old** sweep.

On the ref actually armed, SADD measures **17,024**, not 104,205. #43's ink was
already gone. The leg was built on a residual that no longer existed, and the
captures correctly went to 0.

*A stale artifact re-derives beautifully.* "I derived it myself" is true of the
arithmetic and false of the premise.

### 3. `Stencil/*` was registered `must_not_move` and is not a valid control

Six Stencil captures moved. My first reading was that the control's argument —
Stencil computes its geometry from `floorf(320)` and `floorf(240)`, exact
integers the fix cannot reach — had been refuted by the fix reaching further
than argued. **That reading was wrong**, and the correction came from repeating
rather than from thinking harder.

Three runs per arm, same binary, same disc, same device:

```
capture                     A1      A2      A3      B1      B2      B3
Stencil_REPLACE_DT           0       0       0   40000       0    5100
Stencil_REPLACE_ST           0       0       0       0       0    5050
Stencil_REPLACE_ST_DT        0       0       0       0   30000       0
Stencil_REPLACE_ST_ZB        0       0       0       0       0    5050
Stencil_ZERO              5000       0       0       0       0       0
Stencil_ZERO_ST          30000       0       0       0   30000       0
Stencil_ZERO_ST_DT       30000   30000       0       0       0       0
Stencil_ZERO_ST_DT_ZB    30000   30000       0       0       0       0
Stencil_ZERO_ST_ZB       30000       0       0       0       0       0
```

**Nine of sixteen Stencil captures vary WITHIN a single arm**, snapping between
0 and 5,000 / 5,050 / 5,100 / 30,000 / 40,000. The suite is nondeterministic on
this device. Every Stencil conclusion in the first pass was noise — the five
"better" and the one "worse" alike — and `Stencil/*` cannot control for
anything until that is fixed. Filed separately.

`Viewport/*` is the control that survives: **1,396 px in all six runs,
identical**, in both arms.

## What the repeats establish about the fix

Everything that matters is perfectly reproducible, which is the opposite of
the Stencil picture:

| suite | captures | unstable within an arm | A | B |
|---|---:|---:|---:|---:|
| `Blend_tests` | 105 | **0** | 1,711,362 px | **0 px** |
| `Point_size` | 21 | **0** | 22,746 px | 20,579 px |
| `Viewport` | 12 | **0** | 1,396 px | 1,396 px |

`Blend_tests` reads 1,711,362 px in all three A runs and 0 in all three B runs,
bit-identical. The `Point_size` difference is 2,167 px and is exactly
1,099 + 1,040 + 14 + 14 — the two `LargestPointSize` and the two
`SmallestPointSize` captures, each going to 0 in every B run.

So the fix is confirmed on six runs. The FAIL verdict stands as a fact about
the prediction, not about the fix, and a corrected registration
(`issue67-frndint-device-legs-v2.json`, 109 legs, all derived from arm A here,
Stencil excluded and Viewport as the control) is queued as a fresh pair.

## What is NOT claimed

- Not that 1,860,504 → 61,975 is a corpus figure. It is four suites, and
  `Blend_tests` scored 105 of 1,673 goldens — `ab_compare` flags that suite's
  numbers as a **floor, not a score**.
- Not that the prediction passed. It failed, 17 of 29 checks, and the FAIL is
  correct.
- Not that `Stencil_REPLACE_DT` is a regression. Six runs say it is noise:
  40,000, then 0, then 5,100 on the same binary.
- Not that the Stencil instability is understood. It is measured and filed,
  and its cause is not known.
