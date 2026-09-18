# Tests that render another test's image

**Status:** 328 cases found; two suites classified on device, 2026-09-08. They
turned out to have *different* causes, so the population is not one bug.

## Summary

38% of failing pgraph tests are not rendering the right scene *wrong* — they are
rendering *something else*, namely the image belonging to a different test.
Scoring against each test's own golden could never show this, because "drew the
right thing slightly wrong" and "drew something else entirely" both report as
*N pixels differ*.

Of 3,132 tests in the baseline sweep, 864 fail. Of those, **328 reproduce a
different test's golden more closely than their own**, and in **263** of those
the impersonated test is *itself* correct.

## How it was found

`docs/testing/crossmatch.py`. For every failing test it asks whether some other
golden in the same suite fits our output better than the test's own golden does.

```sh
python3 docs/testing/crossmatch.py results_final --goldens goldens/results
```

## Two causes, not one

Rendering another test's image has (at least) two very different explanations,
and crossmatch cannot tell them apart:

1. **Cross-test contamination.** State from an earlier test leaks into a later
   one. The later test is *correct in isolation*. Order-dependent.
2. **An unimplemented state distinction.** Two tests differ by one state bit
   that we ignore, so they render identically no matter what runs first. The
   test is *wrong even alone*. Not order-dependent.

**The pair/solo isolation disc is the discriminator**, and it must be run before
a suite is attributed to either cause. Build two discs: one enabling the failing
test plus the test it impersonates, one enabling the failing test alone.

### Verify a run actually happened — and how not to

This cost a wrong conclusion, so it is worth stating plainly.

`extract_results.py --newer-than` does not prove a file is fresh: files that
were never rewritten come through it. The obvious fix — comparing FATX mtimes
against the pre-run image — **is also wrong**. An image whose plasma tests
provably never executed (the emulator stalled after a single 32x32 texture bind)
still showed both files with advanced timestamps. Directory entries are
rewritten for reasons unrelated to the test writing output.

The only trustworthy record is the suite's own. Set `enable_progress_log: true`
in the disc config and read `pgraph_progress_log.txt` from the results:

```
Starting [1/2] Texture DXT::DXT1_plasma_alpha_dxt1
  Completed [1/2] 'DXT1_plasma_alpha_dxt1' in 87ms
Starting [2/2] Texture DXT::DXT1_plasma_dxt1
  Completed [2/2] 'DXT1_plasma_dxt1' in 80ms
Testing completed normally, closing log.
```

Nor can completion be inferred from how long a run took: the emulator does not
exit on guest power-off (#20), so every disc runs to the harness timeout.

Every result below has been re-taken on an unmodified build with the progress
log enabled.

## Classified: `Texture DXT` — contamination

| disc | tests enabled | `DXT1_plasma` vs own golden | vs `DXT1_plasma_alpha` |
|---|---|---|---|
| pair | `DXT1_plasma_alpha`, `DXT1_plasma` | **14.86** | 0.79 |
| solo | `DXT1_plasma` only | **0.36** ✓ | 15.35 |

Mean absolute per-subpixel error, same unmodified build. The progress log
records `[1/2]`+`[2/2]` on the pair disc and `[1/1]` on the solo disc, both
ending "Testing completed normally", and the output bytes differ between the two
runs. **One sibling running first is sufficient to corrupt it; alone it is
correct.**

The fault is in texture data specifically, not the frame:

| region of the failing frame | vs own golden | vs sibling's golden |
|---|---|---|
| the textured quad | 69.65 | **1.65** |
| background and the on-screen text naming the test | **0.00** | 0.56 |

The text spelling out which test this is matches its own golden *pixel-exactly*.
The renderer knew what it was drawing and got everything right except the
texture it sampled — ruling out stale framebuffer readback, an off-by-one frame,
and mislabelled output.

## Classified: `Window clip` — **not** contamination

| disc | tests enabled | `rI_x0y0_w0h0-…` vs own | vs `rE_x0y0_w0h0-…` |
|---|---|---|---|
| pair | `rE_…`, `rI_…` | 20.55 | 0.01 |
| solo | `rI_…` only | **20.55** | **0.01** |

Byte-identical output in both runs, and the solo disc's progress log reads
`Starting [1/1] Window clip::rI_x0y0_w0h0-x0y0_w0h0` — it ran, alone, and still
produced `rE_`'s image. (This conclusion was first drawn from mtimes, which do
not support it; it survived re-testing by the sound method.)

`rI_` renders `rE_`'s image **even when it runs alone**. This is not leakage —
we are ignoring the inclusive/exclusive distinction in the clip region and
implementing both as exclusive. That belongs to
[#11](https://github.com/jreinach-alt/hakuX/issues/11) as a concrete defect, and
it is a considerably better lead than "38 of 92 tests fail".

## Classified: all 24 colour suites

Every suite was run with its most unambiguous substitution enabled alone, on the
#20-fixed build, with the progress log confirming `[1/1]` in each case.

| verdict | suites |
|---|---|
| **contamination** (correct alone) | `Texture_DXT`, `Texture_render_target` |
| **missing-state** (wrong alone) | `Attrib_carryover`, `Blend_surface`, `Blend_tests`, `Depth_buffer`, `Fog_exceptional_value`, `Fog_gen`, `Fog_param`, `Lighting_spotlight`, `Line_width`, `Specular`, `Stipple_tests`, `Surface_format`, `Texture_perspective`, `Texture_shadow_comparator`, `Texture_signed_component_tests`, `W_param`, `Window_clip`, `ZMinMaxControl`, `ZPass_pixel_count` |
| **unclear** | `Bump_map`, `Image_blit`, `Texture_cubemap` |

**Contamination is the rare case: 2 of 24** — updated 2026-09-18 to **3 of 25**
by `Color zeta overlap`, classified below, which was not in this population.
Note also that this table's verdicts are about each suite as a **victim**: a
suite listed under *missing-state* can still be a contamination **source** for
another suite, and `Blend_surface` is now known to be exactly that. The
overwhelming majority are
distinctions the emulator does not implement, where the test renders its
sibling's image no matter what ran before it. That is good news for triage — it
converts "this suite fails a lot" into a named missing feature — but it means
the population is emphatically not one bug, and the original framing of this
investigation was wrong.

The two contamination cases are both *pixel-exact* alone:

| suite | test | in sweep | alone |
|---|---|---|---|
| `Texture_DXT` | `DXT3_plasma` | 15.81 | **0.00** |
| `Texture_render_target` | `TexFmt_A8_L` | 67.42 | **0.00** (0 of 307,200 px) |

`Texture_render_target` matters most: [#4](https://github.com/jreinach-alt/hakuX/issues/4)
records 40 of 41 tests failing and reads as a fundamental render-to-texture
defect. At least part of that is contamination, not render-to-texture.

The three unclear cases each need their own look, and one is genuinely odd:

- `Texture_cubemap` 31.93 → **2.78**. Much better alone but not correct, which
  looks like contamination layered on a smaller real defect.
- `Bump_map` 33.41 → 32.50. Barely moves, and does not match the sibling either.
- `Image_blit` 30.68 → **163.19**. Substantially *worse* alone. A blit test run
  with nothing before it has no source surface to copy, so this may be the test
  depending on prior state by design rather than an emulator fault — worth
  confirming before treating it as a defect.

## Classified: `Color zeta overlap` — contamination, and the first ref-controlled instance

Added 2026-09-18 from lane.disc89's thirteen-arm bisect of
[#89](https://github.com/jreinach-alt/hakuX/issues/89). This suite was **not in
the 24 classified above** and belongs here.

`Color_zeta_overlap/Swap_ZB`, every arm at **one ref (`fc6129b01b`) on one
device (thor `bdc158a5`)**, two runs each, each on its own `disc_id`, so the
predecessor set is the only variable:

| captures in **preceding suites** | discs measured | `Swap_ZB` differing px |
|---:|---|---:|
| 0 | bare 1-suite — which still has **five** within-suite predecessors | **0** |
| 1 | six separate discs: `Color mask blend` alone; `Color Zeta Disable` alone; five single `Blend surface` tests spanning all three pad-alpha classes | **0** |
| 2 | `{ARGB8, R5G6B5}`; `{ARGB8, ARGB8}`; `{X_ZRGB8, X_ZRGB8}`; `{Color mask blend, Color Zeta Disable}` | **141,125** |
| 8, 16, 32, 34, 107 | — | **141,125** |

Correct alone, wrong in a sweep: **contamination**, by this document's own
criterion, and the third case — so 3 of 25 rather than 2 of 24.

### Three things this adds to the taxonomy above

**1. A suite can be a contamination SOURCE while being "missing-state" as a
victim.** `Blend_surface` is listed above under *missing-state (wrong alone)*,
which is a verdict about its own captures. #89 shows it is *also* a
contaminator of a later suite. The two causes in "Two causes, not one" classify
the **victim**; they say nothing about which suites contaminate, and a suite can
sit in both columns at once. Nothing above is wrong — it is incomplete in a way
that reads as complete.

**2. The unit is captures in PRECEDING SUITES, not captures.** The bare disc has
five captures ahead of `Swap_ZB` inside its own suite and scores **0**. Stated
as a raw capture count the threshold is refuted by a disc already in this
corpus. Captures inside the victim's own suite do not count, however many.

**3. No individual predecessor is culpable.** `Color mask blend` alone reads 0,
`Color Zeta Disable` alone reads 0, and the two **together** read 141,125 — two
discs that each produce a correct capture, combined, produce the defect. So the
"which test did it" framing that works for `Texture_DXT` does not apply here,
and a search for the guilty predecessor will not terminate.

### The defect is one byte, and the narrowed disc was hiding it

`max_rgb = 0`: every pixel the guest **drew** is byte-identical to the golden,
including 166,075 px at `0x00A8BF00`, which is the suite's own stated expected
value. The whole difference is the **alpha byte of the cleared region** —
141,125 px at `0xFF000000` against a golden `0x00000000` — which, since
`Swap_ZB` is scored as zeta, is the z24s8 **depth high byte**. Stencil and the
low two depth bytes are bit-identical.

So the direction is unambiguous and it is the opposite of the usual reading
here: **the golden is right, the run-alone `0` is right, and the sweep's
141,125 is the true defect.** Running a test alone can *conceal* a defect as
easily as it can reveal one, and in this case "correct alone" was the
misleading half.

### What this instrument cannot see, measured

A composition effect is only visible by scoring the same capture at the **same
ref and the same skip list** on two different discs. Across the corpus:

| | |
|---|---:|
| goldens | 5,608 |
| captures ever scored | 4,522 |
| captures with a same-ref two-disc pair — the only testable ones | **548 (9.8%)** |
| never testable for a composition effect | **5,060 (90.2%)** |
| suites with **zero** composition coverage | **89 of 100** |

**`Image_blit` has zero coverage, and so does `Blend_tests` (1,673 goldens).**
The `Image_blit` 30.68 → 163.19 case recorded above — this document's most
striking contamination datum — **is invisible to the ref-controlled
instrument.** It cannot currently be confirmed or refuted by this method.

And before these arms, the ref-controlled composition test had **never once
produced a positive result** on this project: 548 eligible captures, zero
movers. A zero from an instrument that has never demonstrated it *can* fire is
not evidence of absence. Arm A vs the 236-capture baseline is now that positive
control — 1 of 10 shared captures moved — which is what makes the other arms'
zeros informative rather than merely quiet.

### Blast radius, and why a narrow one is still worth the row

Across 47,250 scored rows, 4,522 distinct captures and 886 runs, `Swap_ZB` is
the **only** capture that has ever taken two values attributable to
composition. A 236-capture disc narrowed to 41 is byte-identical on all 41
shared captures, including all 32 `Blend_surface` ones; removing one suite from
the full disc moved nothing on all 235 shared captures.

Two families that look composition-correlated and are not, recorded so the next
scan does not re-derive them: `Texture_render_target/TexFmt_*` (24 captures) is
the known `RenderTextureLoop` poison test — `disc_id` encodes the skip list, so
a by-`disc_id` scan reports the skip flag as composition — and
`Depth_buffer/DepthFmt_z16_*` is a ref effect. [#79](https://github.com/jreinach-alt/hakuX/issues/79)'s
`Stencil` `_ZB` variance has `max_a = 0` in all 46 runs and varies *within* one
`disc_id`: genuine nondeterminism, a different mechanism.

### Mechanism: unnamed, with five corpses

Five hypotheses died to their own pre-registered falsifiers and **none should be
re-run**: a leaked `NV097_SET_COLOR_MASK` alpha-write bit; #59's clear
pad-alpha stamp keyed on a stale `drawn_format`; accumulation/occupancy; a
surface-format transition; and "two preceding captures anywhere".

Accumulation died to **format-invariance of the threshold** — `R5G6B5` is
16-bit, `A8R8G8B8` is 32-bit, and the cross-suite pair is different shapes again,
so three resource footprints share one threshold of two — and *not* to the flat
region above the step, which is a ceiling effect: 141,125 **is** the entire
cleared region, so the metric cannot express a gradient and flatness would look
identical under a graded cause. **A step with no gradient is the signature of a
latch, not a level.**

Any surviving candidate must be **latched rather than graded**, must count
captures completed **before the current suite began**, and must be **blind to
any number inside the victim's own suite**.

## Scope correction: depth captures

Of the 328 substitutions, **55 are `_ZB` depth captures**, which the colour
analysis excludes because they fail through readback conversion
([#16](https://github.com/jreinach-alt/hakuX/issues/16)) rather than depth
behaviour. The honest colour figure is **273**.

Two suites — `Depth_buffer_fixed_function` (11) and `W_buffering` (20) — have
*no* colour substitutions at all. Their entire appearance here is #16 and they
are excluded above. `crossmatch.py` should grow a `--exclude-suffix _ZB` flag so
this is not re-derived.

## Candidate mechanism for the contamination case

In `hw/xbox/nv2a/pgraph/vk/texture.c` the content comparison is gated behind the
VRAM dirty flag — when `possibly_dirty` is false the texture is never re-hashed
and never re-uploaded:

```c
uint64_t content_hash = 0;
if (!surface_to_texture && possibly_dirty) {
    content_hash = fast_hash(texture_data, texture_length);
}
...
bool vram_changed = possibly_dirty && content_hash != snode->hash;
```

Two things can clear it wrongly:

1. **Per-frame caching of the dirty result**, added post-fork in `21f7d7c3e5`
   (2026-03-01). `pg->frame_time` advances only on `NV097_FLIP_INCREMENT_WRITE`,
   so a texture rewritten at the same address within one flip interval is never
   re-read. Four sites consume the cached verdict.
2. **`check_texture_dirty` uses `memory_region_test_and_clear_dirty`**, which
   *consumes* the dirty bit across a page-aligned range — the first caller
   clears it for every other texture sharing those pages.

### Hypothesis 1 is disproven

Tested by storing a frame number that can never match `pg->frame_time`, so the
"clean this frame" verdict is never reused, at all three store sites including
the initialiser. Built and run against the pair disc:

| build | `DXT1_plasma` vs own golden | vs sibling |
|---|---|---|
| unpatched | 14.86 | 0.79 |
| per-frame cache disabled | **14.86** | **0.79** |

Output was **byte-identical** (`e8b1b6086245` both times), progress-log verified
on a re-test. The per-frame dirty cache is not the mechanism.

### Hypothesis 2 is still open — the obvious probe destroys the experiment

The sharper question is whether the content comparison would catch the change at
all, so the natural probe is to force `possibly_dirty = true` and hash the
texture unconditionally.

**That probe does not work, and it fails deceptively.** Hashing every texture on
every bind slows the guest enough that the watchdog stops the VM
(`STALL: frames=480 ... get==put`), and the run dies after a single 32x32
texture bind — before either plasma test executes. The stale PNGs from the
previous run are then extracted and compared, and the result reads exactly like
"the probe changed nothing". It was caught only because the probe's own log
showed one bind of the wrong size.

This is the `AGENTS.md` rule about instrumentation cost, met in a new place: the
cost did not merely perturb the measurement, it silently substituted a different
one.

A workable version needs to avoid the per-bind cost — hash only when the shape
key matches an existing binding, or gate the probe to the DXT formats under
test — and must be run with the progress log on so a truncated run is visible.

## Why this matters

`DXT1_plasma` is not a broken DXT decoder; it is a correct decoder handed the
wrong bytes. Until the contamination cases are fixed, any sweep running more
than one test per suite understates accuracy by an unknown margin, and per-test
results are order-dependent — which is
[#15](https://github.com/jreinach-alt/hakuX/issues/15) seen from the other side.

Equally, the cases that turn out to be cause 2 are *good news for triage*: they
convert a vague "this suite fails a lot" into a named missing feature.

## Next

1. Run pair/solo isolation across the remaining 24 suites; it is scriptable and
   each answer is ~4 minutes.
2. Build `wt/texture-staleness` and re-run the DXT pair disc.
3. Re-baseline every affected issue afterwards. The headline 1,110/2,702 is a
   floor, not a measurement, while this is outstanding.
