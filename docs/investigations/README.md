# Investigations

Findings that are too long for an issue comment and too specific for the
README. An issue says *what is wrong*; a file here says *what we looked at, what
we established, and what we could not*.

## Why these live in the repo

Issue #19 was investigated across a week on one machine. The conclusions reached
the tracker; the tooling that produced them and the write-up the issue links to
never left that machine, and it is now offline. `docs/investigations/` and
`docs/testing/` are where that work goes, committed as it is produced.

Two of these documents are still dangling links from open issues, listed below
so they are not silently forgotten.

## Convention

Every claim carries a `file.c:line`. Every document separates:

- **VERIFIED** — read in the code, cited, re-checkable by anyone
- **INFERRED** — reasoning on top of verified facts, labelled as such
- **UNRESOLVED** — what the work could not settle, stated plainly

A finding that reproduces a measurement is not thereby a cause. This project has
twice lost time to a plausible explanation that measured well and was wrong (see
#19's two self-corrections), so a code fact that *predicts* a symptom is written
as a candidate until an isolation run says otherwise.

## Contents

| document | what it covers |
|---|---|
| [`nv2a-sweep-2026-09.md`](nv2a-sweep-2026-09.md) | Verified structural findings across the NV2A subsystems, mapped to open issues |
| [`sweep-2026-09-08.md`](sweep-2026-09-08.md) | The measured side: 1,871 tests run one-per-disc and scored against silicon, by failure shape |
| [`freeze-analysis.md`](freeze-analysis.md) | Pre-fork freeze chase, thirteen hypotheses eliminated, unresolved |
| [`gl-artifacts.md`](gl-artifacts.md) | Pre-fork GL texture artifacts. Scope header matters — Android runs Vulkan |
| [`handoff-2026-09-10.md`](handoff-2026-09-10.md) | State of both lanes at the 2026-09-10 merge: what is verified on hardware, what is only committed, and the three open analytical items |
| [`depth-readback-scale.md`](depth-readback-scale.md) | Why a 24 bit depth word could not round trip: four disagreeing scales, and a unorm grid half a unit out of phase with float32 |
| [`edge-defect.md`](edge-defect.md) | The "one-pixel edge defect" across seven suites decomposed: texel and quantisation ties at boundaries, and two fixed-function vertices a few ULP from the snap grid. What to classify, what to build, what not to touch |
| [`surface-as-texture-decode.md`](surface-as-texture-decode.md) | Why a colour surface sampled as a texture came back with red and blue swapped: the declared texture format decides the decode, and borrowing the surface's own view skips it. Includes the ABGR diffuse convention that inverts the conclusion if read wrong |
| [`blend-unit-model.md`](blend-unit-model.md) | A closed-form model of the blend chain that reproduces silicon on every sampled pixel: the factor and equation tables are right, and what is left is the 8 bit store |
| [`signed-blend-equations.md`](signed-blend-equations.md) | Issue #43 solved: the signed blend equations read the *source* as a signed byte and clamp, ignoring both factors. Fits 7,849 of 7,849 across two suites and four destinations. Implementing it, not deriving it, is now the open question |
| [`bump-fog-cubemap-queue.md`](bump-fog-cubemap-queue.md) | Six suites worked end to end: two have no semantic defect at all, one new cross-suite YUV decode defect, and two located defects whose obvious fixes were measured and rejected |
| [`line-width-residual.md`](line-width-residual.md) | What is left in `Line width` after the register landed: the device's own minimum and granularity below 1.25px, and a 3-4% shortfall at every width that is the line ends. Opens with the mistake that hid it — measuring against captures four days older than the fix |
| [`target-ranking-2026-09-12.md`](target-ranking-2026-09-12.md) | What to work on next, ranked on the reclassified corpus rather than on raw differing pixels, with the contamination caveat that outranks it |
| [`depth-full-oracle-2026-09-12.md`](depth-full-oracle-2026-09-12.md) | Recovering 392 depth tests from a retired 2025 disc, and what five times the oracle says: z16 fixed depth is perfect, z24 fixed is one unit high with a scale-divisor signature, float Z is structural, and the colour path is wrong independently |
| [`unhandled-methods-inventory.md`](unhandled-methods-inventory.md) | Logging the pgraph methods we silently drop, because QEMU's trace for them never reaches logcat. First run names the blit clip rectangle in registers — class 0x19, point (0,0), size 256x256 — plus fourteen other dropped methods |
| [`blend-fifth-quad.md`](blend-fifth-quad.md) | On the recovered 1,568-test oracle the blend arithmetic is right and the whole unsigned residual is one 256x64 quad. Includes the mechanism claim I got wrong by sampling single pixels instead of the region |
| [`blend-surface-dst-alpha.md`](blend-surface-dst-alpha.md) | What #48's destination-alpha tests are *not*: three causes eliminated with numbers, the Z-forces-zero FIXME disproved, and the residual identified as a two-draw pairing that probably shares a cause with the fifth quad |
| [`blend-white-swatch.md`](blend-white-swatch.md) | What is left in `Blend tests` on Adreno after the decode fix: every one of the 1,591 remaining misses is the white swatch, flat across equations and both factor sets, and not one within two steps |
| [`issue-9-lighting-final.md`](issue-9-lighting-final.md) | Why #9 closed: the lighting arithmetic is correct on eight landed commits, 72% of the residual is one step, and the structural remainder is six vertex-program captures (#53) plus the interpolator floor (#38) |
| [`overnight-2026-09-12-log.md`](overnight-2026-09-12-log.md) | **Start here for the night of 2026-09-11/12.** What held, the three mechanisms that did not and why, the six harness defects fixed, and the one lesson |
| [`issue-19-isolation-2026-09-12.md`](issue-19-isolation-2026-09-12.md) | #19 measured on one binary: 2 contamination against 82 missing-state, the ten features those name, and the test-coverage gap the progress logs exposed |
| [`diag-capture-cost.md`](diag-capture-cost.md) | Why per-draw capture stalls the guest. Corrected reading; the cost is a GPU sync per draw and a three-byte `fwrite` per pixel |
| [`sweeps/`](sweeps/) | Raw per-subsystem inventories. **Machine-generated, not verified** — read the header on each |

## Missing, and referenced by open issues

| path | referenced by | status |
|---|---|---|
| `cross-test-contamination.md` | #19 body | never committed; the analysis survives only as #19's comments |

`freeze-analysis.md` was on this list until the pre-fork `FREEZE_ANALYSIS.md`
was moved here, which resolves #20's link.

