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

## Unclassified

The remaining 24 suites have not been isolated and must not be attributed to
either cause without running the discs. Counts:

```
44 Texture_cubemap     20 W_buffering      16 Texture_shadow_comparator  12 Attrib_carryover
34 Line_width          18 Fog_param        15 Texture_signed_component   11 Depth_buffer_ff
30 Depth_buffer        17 Fog_gen          15 Blend_tests                 8 ZMinMaxControl
26 Window_clip *       14 W_param          14 Image_blit                  … 11 more
```
`*` classified above.

The pattern across the population — a sibling differing by exactly one state
bit, the first-run variant winning — fits cause 2 at least as well as cause 1,
so the split may well favour unimplemented state distinctions. `Texture DXT` is
so far the only proven contamination case.

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
