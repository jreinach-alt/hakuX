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

### 3. `Stencil/*` was registered `must_not_move` and moved — six times

Five of those are the fix working somewhere I asserted it could not reach:

```
Stencil_ZERO           5,000 -> 0
Stencil_ZERO_ST       30,000 -> 0
Stencil_ZERO_ST_DT    30,000 -> 0
Stencil_ZERO_ST_DT_ZB 30,000 -> 0
Stencil_ZERO_ST_ZB    30,000 -> 0
```

The control's stated reasoning was that Stencil computes its geometry from
`floorf(320)` and `floorf(240)`, exact integers the fix cannot reach. Five
captures say otherwise. **The control is refuted, not the fix** — but that also
means this suite was never the clean scoping check it was registered as, and
whatever else in Stencil goes through a non-integral `floorf` has not been
identified.

## The one genuine open question

```
Stencil_REPLACE_DT     0 -> 40,000     <<< WAS EXACT
```

One capture in 154, regressed from exact. Every other `REPLACE` variant —
`_ST`, `_ZB`, `_DT_ZB`, `_ST_DT`, `_ST_ZB`, `_ST_DT_ZB`, and plain `REPLACE` —
stays at 0. A single lone mover on a single run per arm is also the documented
shape of a device flake, so **the first move is repetition, not theory**: two
further runs of each arm are queued on the same device and the same 4-suite
disc, giving three observations per arm. Narrowing the disc to Stencil alone
would change what it measures and break comparability with these results.

Until those land, this is one observation, and the fix is not recommended for
anything on the strength of it.

## What is NOT claimed

- Not that 1,860,504 → 61,975 is a corpus figure. It is four suites, and
  `Blend_tests` scored 105 of 1,673 goldens — `ab_compare` flags that suite's
  numbers as a **floor, not a score**.
- Not that the prediction passed. It failed, 17 of 29 checks, and the FAIL is
  correct.
- Not that `Stencil_REPLACE_DT` is a regression. It is one observation.
