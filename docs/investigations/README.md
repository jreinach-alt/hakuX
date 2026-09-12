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
| [`diag-capture-cost.md`](diag-capture-cost.md) | Why per-draw capture stalls the guest. Corrected reading; the cost is a GPU sync per draw and a three-byte `fwrite` per pixel |
| [`sweeps/`](sweeps/) | Raw per-subsystem inventories. **Machine-generated, not verified** — read the header on each |

## Missing, and referenced by open issues

| path | referenced by | status |
|---|---|---|
| `cross-test-contamination.md` | #19 body | never committed; the analysis survives only as #19's comments |

`freeze-analysis.md` was on this list until the pre-fork `FREEZE_ANALYSIS.md`
was moved here, which resolves #20's link.

