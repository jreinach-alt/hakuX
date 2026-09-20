# Is this Xbox a trustworthy instrument?

**Yes.** 3,374 of 3,379 captures are bit-identical to the published hardware
goldens — 99.9%. Zero blank frames, zero captures off by one, and zero label
mismatches. Five captures disagree, and they are named below.

Until now every measurement this project took on real silicon was a claim.
This run makes it evidence, with a stated residual of five captures.

Hardware: see [`xbox-console-provenance.md`](xbox-console-provenance.md) —
reported V1.1, ind-BIOS, kernel 1.0.5003.67, GPU revision 163, MCP revision
212. **The goldens were captured on Xbox 1.0 silicon; this is a 1.1.** That
matters for reading the residual and it was written down before the run, not
after. Cross-reference: issue #112.

## What was run

| | |
|---|---|
| Disc | `nxdk_pgraph_tests_xiso.iso`, sha256 `2371e743…`, 5,767,168 bytes |
| | byte-for-byte the image [`pgraph-harness.md`](pgraph-harness.md) is written against |
| Launch | from HDD at `E:\Apps\PgraphCalib\`, not from disc |
| Goldens | `abaire/nxdk_pgraph_tests_golden_results` @ `6e159f15`, 2026-08-11 |
| Small run | `Alpha func`, 16 tests — **16/16 bit-identical** |
| Full run | everything bar one test, 2,934 tests, all completed |
| Captures | 3,379 = 2,934 colour + 445 depth |

`Texture render target::RenderTextureLoop` was skipped deliberately. It ends
with the texture stage disabled and the 40 `TexFmt_*` tests that sort after it
rely on the suite's `Initialize()`. The decision was made on evidence before
running: the `TexFmt_*` goldens are rich — up to 65,027 distinct colours — so
they were not captured with that contamination present. Leaving it in would
have blanked 40 captures and inflated the residual about tenfold against
goldens that never had it. One capture lost against forty corrupted.

## How "matching" is defined here

Per [`pgraph-harness.md`](pgraph-harness.md), and not reinvented: **differing
pixel count and max delta, never a mean.** A mean cannot separate "this format
is not decoded at all" from "rounding", and that is the whole triage decision.

**Alpha is included.** `score_sweep.py` reports max delta over RGB and over A
in separate columns, so neither is dropped and neither is silently folded into
the other. Depth captures are compared as decoded integers with "off by
exactly one" kept as its own category — there were none.

## The residual: five captures

| suite | test | differing px | share | max RGB | max A |
|---|---|---:|---:|---:|---:|
| `Texture_format` | `TexFmt_R6G5B5` | 134,902 | 43.91% | 223 | 254 |
| `Color_zeta_overlap` | `ZetaIntoColor` | 19,994 | 6.51% | 84 | 0 |
| `Color_zeta_overlap` | `ColorIntoZeta_ZB` | 10,982 | 3.57% | 135 | 220 |
| `3D_primitive` | `LineLoop-inlinearrays-ls` | 4,546 | 1.48% | 100 | 59 |
| `Attrib_float` | `-NaNs_NaNs` | 60 | 0.02% | 155 | 255 |

Two carry the status `white-content`, which is **not** a label mismatch: white
pixels differ in the image *body*, below the 64-row label band. The row stays
scoreable and the difference is real content. `label-differs` — the status that
would mean the golden came from a different build of the suite — **did not
occur once in 3,379 captures.** That is the strongest single piece of evidence
that the comparison is about this console and not about disc versions.

The two `Color_zeta_overlap` rows are one suite and plausibly one mechanism
rather than two findings.

### What those five turned out to be — resolved 2026-09-20

The original verdict left three explanations open and named the experiment that
would separate them. It was run: `Color zeta overlap` twice back to back with
**byte-identical disc composition**, and `Texture format` / `3D primitive` /
`Attrib float` likewise. Holding the disc constant is what makes the answer
clean — contamination is controlled rather than assumed away.

All three explanations turned out to be real, each on different captures.

| capture | verdict | evidence |
|---|---|---|
| `ZetaIntoColor` | **nondeterministic on silicon** | 20,141 px differ between two identical-disc runs |
| `ColorIntoZeta_ZB` | **nondeterministic on silicon** | 3,182 px differ between two identical-disc runs |
| `TexFmt_R6G5B5` | **real disagreement with the golden** | byte-identical across runs and discs; 134,902 px vs golden |
| `-NaNs_NaNs` | **real disagreement with the golden** | byte-identical across runs and discs; 60 px vs golden |
| `LineLoop-inlinearrays-ls` | **contamination** | stable within a disc, 4,546 px different *between* discs |

**Two are hardware nondeterminism.** `ZetaIntoColor` and `ColorIntoZeta_ZB`
vary run to run on the same console with the same disc, in the same screen
region each time (rows 113–367, cols 124–519 for `ZetaIntoColor`). The golden
is one sample from a distribution whose spread — 20,141 px — is the same order
as the distance from the golden itself (21,712–27,787 px). Reported to #88 and
#91, which take absolute pixel targets from those captures' golden histograms.

**Two are genuine.** `TexFmt_R6G5B5` and `-NaNs_NaNs` reproduce byte-for-byte
across runs and across disc compositions and still differ from the golden.
Either this V1.1 silicon differs from the 1.0 the goldens came from, or those
goldens came from a different build of the suite. Both remain open; neither is
noise.

**One is contamination**, and it is the cleanest demonstration of why
`score_sweep` marks every whole-suite capture non-solo.
`LineLoop-inlinearrays-ls` is byte-stable when the disc is held constant and
moves by 4,546 px when the disc composition changes. What ran before it changed
what it drew.

So the residual is five captures for four different reasons, and "the console
disagrees with the goldens" was the wrong summary for three of them. The 3,374
bit-identical captures were never in question and remain usable.

### Stencil was stable

Issue #79 records 9 of 16 `Stencil` captures changing between runs of the same
binary on the Thor. On this hardware, `Stencil` scored **16/16 bit-identical**,
and `Stencil_func` likewise. One run cannot prove stability, but it is
consistent with #79 being an emulator artefact rather than something the
silicon does — which is worth knowing before another campaign is built on top
of that suite.

## Coverage, and why 2,934 is not 5,608

The goldens hold 5,608 captures; this disc ran 2,934 tests producing 3,379
captures. **92 of the 100 suites match exactly** (tests run == goldens minus
depth). The shortfall concentrates in `Blend_tests` (105 of 1,673) and
`Depth_buffer` (144 of 784).

This was not accepted as version skew on the counts alone — skew is the
explanation of last resort. Three things were checked first:

1. **Every name this disc produced exists in the goldens.** There is not one
   orphan capture in any suite. Every capture scored had a golden of the same
   name to be compared against.
2. **The missing goldens use an older spelling this build does not emit.**
   `Front face` is the clearest case: the disc produces
   `FrontFace_FM_0x00_CF_B`, and the goldens carry both that set and a
   12-strong `FrontFace_0x00_CF_B` set. A golden repository accumulates — a
   renamed test leaves its old PNG behind unless somebody deletes it.
3. **`sample-config.json` on the disc is itself stale** against the XBE beside
   it, spelling the same tests `FrontFace_0_CF_B`. It is an enumeration of
   empty `{}` values, not a set of skip directives, so it neither caused this
   nor could have prevented it.

So the 1,905 are goldens for test names this XBE does not produce, not tests
that failed to run. `score_sweep` flags the affected suites as PARTIAL
COVERAGE, and **a score over part of a suite is not the suite's score** —
`Blend_tests 105/105` means 105 of 105 *run*, not 105 of 1,673.

## Reproducing this

Captures, logs and scores stay on the host, under
`~/hakux-work/hardware/runs/2026-09-19-calib/`, with `PROVENANCE.txt` and the
pre-run `PREDICTION.txt` beside them. Only this verdict is in git.

```sh
python3 docs/testing/score_sweep.py \
    --out  ~/hakux-work/hardware/runs/2026-09-19-calib/full/out \
    --goldens ~/goldens/results --jobs 8 \
    --tsv  ~/hakux-work/hardware/runs/2026-09-19-calib/full/scores.tsv \
    --disc-id full-suite-minus-RenderTextureLoop --label xbox-hw-calib-full
```

Scoring 3,379 captures single-threaded runs past fifteen minutes; `--jobs 8`
brings it under two.
