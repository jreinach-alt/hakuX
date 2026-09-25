# Audit pass 2: PR #256 (lane.remote, #184). A write to a surface rebuilds every stage sampling its memory

Auditor: `[job.cloud]`, 2026-09-25. Head audited: `957d1a8e`. Pass 1: `docs-tooling-agentic-coding-u152m1-pr256-pass1.md`, which audited `f5bfe715`.

**Verdict: clean. Pass 1 found no HIGH and no MEDIUM. Neither LOW got worse, and LOW 2 is fixed. Next state: `fold-ready`.**

## What changed since pass 1

`git diff --stat f5bfe715 957d1a8e` shows two files:
- the pass-1 audit file;
- `docs/lanes/remote/clear_swatch_quads.py` (+10 -8), which is the LOW 2 remediation.

No C source changed.

## The two checks pass 1 asked for

1. **`vk/draw.c` differs from `5eab6a87` only in `pgraph_vk_surface_written_while_sampled()`.** Confirmed. `git diff 5eab6a87 957d1a8e -- hw/xbox/nv2a/pgraph/vk/draw.c` is one hunk at line 6725. It holds the comment block and the function body, and nothing else. The arms were measured against `5eab6a87`, so they still judge the code under review.
2. **Neither LOW has become worse.**
   - LOW 1 (overlapping stages miss the pipeline early-out) is unchanged, because `draw.c` did not change. It is still performance-only and still not required for fold.
   - LOW 2 is fixed; see below.

## LOW 2: can the point-sample scenario still occur?

**No.** The old rule sampled the pixel at `(8, 8)`. The new rule marks swatch `i > 0` stale only when both of these hold:
- in the capture, its whole 128x128 RGBA region is identical to swatch 0's (`np.array_equal`);
- in the golden, the two regions are not identical.

A swatch that matches swatch 0 at one pixel but differs elsewhere is no longer flagged. `np` is imported (line 30), and swatch 0 can never flag itself (`i > 0`).

**Run on data.** I ran the pre-remediation script (`f5bfe715`) and the new one over every Clear capture set on this host that has all eight captures, against `~/goldens/results`. That is 28 runs:
- 21 dispatch arms, including `shadeflat224` base/fix, `wparamclip223` base/fix, `clrpad164` base/fix, `padwrite59*` and the `z-*` sweeps;
- 7 `res_*` sets.

The output (totals, per-swatch counts and stale flags) is **identical in every run**. The master-state arms read `.SSSSS` on six captures and `......` on the X1R5G5B5 pair, which is the record the remediation commit cites. The older `res_*` sets show the other pattern (the X1R5G5B5 pair stale, the rest clean), and both scripts agree on those too.

**What this run cannot see.** None of these 28 sets is a run of the fix's arm, so this run does not re-check "no swatch in any run of the fix's arm". That does not weaken the result: the new rule is strictly stricter on the capture side (a whole region equal implies the pixel is equal). The one way it can flag where the old rule did not is when the golden's regions differ but its `(8, 8)` pixels are equal. In that case the region counts printed beside the flag, which are the registered absolutes, would still be the judge.

## Findings

None. No new HIGH, MEDIUM or LOW.

## State

- CI at audit time: `check` passes; the two `build` runs are pending.
- The fold job gates on CI, not this audit.
