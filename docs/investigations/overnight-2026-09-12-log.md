# Overnight 2026-09-11/12: what held, what did not

One page. Detail is in the linked write-ups; this is the log and the honest
scoreboard.

## What was asked for

An unattended run that made real progress on the tracker rather than reaching
for new issues, starting with **#19** — "328 of 864 failing tests render
another test's image" — because that number hung a caveat over every ranking
either lane had built.

## The measurements that held

All of these come from counts over whole frames, or from register logs.

| result | where |
|---|---|
| **#19 is not a contamination problem.** 1,540 captures, 84 accused, **2 contamination against 82 missing-state**, 0 failed rows, 0 binary mismatches. Ten named features replace the issue's premise — radial fog, destination alpha on alpha-less surfaces, the blit clip, degenerate W, the NEARFAR clamp, INF/NaN fog, Y16/YUV bump sources, and three smaller | [`issue-19-isolation-2026-09-12.md`](issue-19-isolation-2026-09-12.md) |
| **The blit clip rectangle, in registers.** Class 0x19 bound, point (0,0), size 256×256, all three methods dropped; no clip-rectangle class in `nv2a_regs.h` at all. Plus fourteen other dropped methods from one suite | [`unhandled-methods-inventory.md`](unhandled-methods-inventory.md) |
| **Two oracles recovered** from a retired 2025 disc: `Depth buffer` 72 → **392 tests**, `Blend tests` 105 → **1,568 captures**, goldens already in the repo for both | [`depth-full-oracle-2026-09-12.md`](depth-full-oracle-2026-09-12.md) |
| **#16 splits three ways.** `z16` fixed depth **98/98 bit-identical**; `z24` fixed **one unit high on 96/98** with a scale-divisor signature; float Z structural with nothing within one step; and the colour path wrong independently of depth | same |
| **The blend arithmetic is exonerated.** The whole unsigned residual is one 256×64 strip and nothing else in any frame differs. Confirmed on lavapipe by the other lane, so it is ours and fixable | [`blend-fifth-quad.md`](blend-fifth-quad.md) |
| **The surface-as-texture decode fix confirmed on Adreno**: 16,409 of 18,000 against a predicted 16,379, and the R/B exchange now explains **zero** of the remainder | [`blend-white-swatch.md`](blend-white-swatch.md) |
| **The bump alpha block is lavapipe's, not ours** — alpha differs on **zero** pixels across three formats and three capture sets, which took 6.46M px out of the ranking | tracker #14 |
| **Line-width limits measured**, bounding that work: 16 of 61 tests need generated geometry, the other 45 already get the exact width so their residual is ours | [`line-width-residual.md`](line-width-residual.md) |
| **The corpus covers half the golden suites** — 50 of 100, with 16 having no scored record in any file on disk | [`target-ranking-2026-09-12.md`](target-ranking-2026-09-12.md) |

## What did not hold

Three mechanisms of mine died, all to the same failure: inference from sparse
or undated evidence. Each is retracted in place rather than quietly edited.

| claim | why it was wrong |
|---|---|
| "`Line width` never reaches the rasteriser" | measured against captures **four days older** than the fix that landed it |
| "the fifth quad renders the first quad's result", 1,119/1,120 | **one pixel per quad** on quads that are not flat; region against region, identical on **0 of 224** |
| "in that strip we produce the lower value" | one test's colour inventory; across 1,120 captures it is 50.8% lower against 49.2% higher — balanced |

A fourth correction was about mechanism rather than result: the coverage gap is
the disc's **age**, not its config. `sample-config.json` is byte-identical
between our disc and a 2025 one, so it is authoritative for neither XBE, and a
config naming all 392 depth tests ran the same 72.

## Harness defects fixed, each of which would have wrecked an unattended night

1. A disc without `--shutdown-on-completion` **reboots**, so the emulator never
   exits and the group re-runs until its timeout.
2. `adb pull` can **exit 0 having written nothing**, surfacing much later as a
   broken extractor.
3. A re-run **inherits the previous run's captures** from the same guest
   directory — one 15-test suite came back as 29 files.
4. The wait loop **broke on a single bad `ps`**, force-stopping a healthy
   1,300-test group after eleven seconds and leaving a progress log that looks
   exactly like a guest crash.
5. A **failed install** left rows stamped with a binary the device was not
   running.
6. A device leaving the USB bus **emptied the sweep queue**, recording every
   queued test as FAILED.

## The lesson, stated once

Counts over whole frames and register logs held up without exception. Every
claim that died came from a sample standing in for a region, or a number whose
date I had not checked. Both are cheap to avoid and neither is visible in the
result — a point sample through structured content will manufacture whatever
agreement you go looking for, and with enough captures it will look convincing.

## Addendum: the five largest unmeasured suites, measured

All five have goldens and no rows in either lane's current corpus. All five run
on the disc we already have — the gap was that the rankings stopped seeing
them, not that they were unrunnable.

| suite | captures | exact | differing | one-step | **not ±1** |
|---|---:|---:|---:|---:|---:|
| `W_buffering` | 530 | 108 | 4,833,156 | 2,303,941 | **2,529,215** |
| `3D_primitive` | 160 | 4 | 3,866,664 | 3,184,200 | 682,464 |
| `Shade_model` | 168 | 12 | 3,896,446 | 3,337,260 | 559,186 |
| `Depth_buffer_fixed_function` | 80 | 6 | 662,890 | 336,802 | 326,088 |
| `Front_face` | 24 | 4 | 404,688 | 287,640 | 117,048 |

962 captures, 4.21M non-one-step channels that no ranking has been counting.

**`W_buffering` differs by 2.2× between hosts.** The remote lane measures
5,553,462 non-one-step channels on lavapipe; Adreno gives **2,529,215**. Every
time a figure has diverged that far between hosts tonight, part of it has
turned out not to be ours — the bump alpha was the clear case, at 6.46M px
that vanished entirely on Adreno. So this suite's ranking position depends on
which host you ask, and it should not be ranked from one.

**`3D_primitive` and `Shade_model` are 82% and 86% one-step**, so most of their
large raw figures is the precision class, the same shape as `Fog_param`.
Their structural remainders, 682k and 559k, are what is worth ranking.

**`Front_face` produced 24 captures against 36 goldens**, so that suite is
another partial-retirement case like `Depth buffer` — a third of its oracle
needs the 2025 disc.

Two harness bugs of mine on the way, both silent rather than loud, both the
same shape as the six above: the guest directory was derived by `cut -c1-5` in
the disc builder and hardcoded in the runner, so all five suites would have
extracted 0 files and read as "renders nothing"; and restarting the run over
the same log path while the killed process still held that descriptor
interleaved a stale `0 files` line from the dead run into the live one. Both
caught by reading the *first* suite's output rather than waiting for all five.
