# Audit pass 2: PR #586, lane.energymap507 (#507)

Head verified: `b19dbc6eb7`. Pass 1 audited `41154e68e1`. The only change
since then is the pass-1 audit file (`git diff --stat 41154e68e1 b19dbc6eb7`:
one file, 81 insertions), so the code, NOTES and prediction are byte-identical
to what pass 1 read. Pass 1: `docs/audits/2026-09-28-energymap507-pass1.md`.

**Verdict: clean. Pass 1 raised no HIGH or MEDIUM, so no blocking scenario is
left to fire. All five LOWs still stand, and each has a decision logged below.
Fold-ready.**

I re-read the one code change, `hw/xbox/nv2a/pgraph/glsl/geom.c`
(`measure_no_geom()` and the early return in `pgraph_glsl_need_geom`). With
`HAKUX_MEASURE_NO_GEOM` unset or `0` the new branch is never taken and the
original switch runs unchanged, so default behaviour is identical to master.
PR is `MERGEABLE`; the `check` job is green and `build` is in progress on this
head.

## Scenarios from pass 1

| pass-1 finding | still occurs? | where |
|---|---|---|
| L1: section 4's P3 row describes a two-binary design (master vs measurement apk) | yes, unchanged | `NOTES.md:225`, "A = master perflog; B = a measurement-only apk from master". Section 6 and the prediction describe one binary (`5af7b13ee5`), env on and off |
| L2: prediction window says `mark play` +10 s to -10 s; `em_extract.py` reads the baseline with no trims | yes, unchanged | `em_extract.py:2,31,39` reads `mark gameplay`/`mark play` to `soak end` |
| L3: stale citation `glsl/geom.c:81-94` for `pgraph_glsl_need_geom` | yes, unchanged | `NOTES.md:190`; the function is now at `geom.c:106-134` |
| L4: readers run only on `scratch/runs` copies; `em_split.py` / `em_breakdown.py` raise `KeyError` on a run with no data | yes, unchanged | `em_split.py` `r['vcpu_share']`, `em_breakdown.py` `ex[r]` |
| L5: B's `prefix_outputs=false` VS keys persist into `shader_module_keys.bin` and are recompiled by later default runs | yes, unchanged, not noted in NOTES | `vk/shaders.c:1049` `shader_module_key_persist` |

## Decisions logged

- **L1, L3: not fixed in this PR.** Both are text in the lane's own NOTES.
  Section 6 is the record of what was queued, it names the ref and both run
  ids, and the prediction file is what the judge reads. So nothing scores
  against the section 4 wording. Carried forward: the lane should correct both
  lines in its next NOTES commit. Neither can change a verdict.
- **L2: not fixed.** The judged quantity is R(B)/R(A) over two arms read with
  the same window, so the trim does not bias the ratio. The baseline figures
  are context only. Carried forward: before any figure from this window is
  quoted next to the `em_extract.py` baseline as the same measurement, align
  the two (trims in `em_extract.py`, or drop them from the window text).
- **L4: not fixed.** These are the lane's analysis scripts. Nothing in CI or
  the jobs imports them. A `KeyError` on a missing run is a loud failure, not
  a wrong figure. The run ids in NOTES let the figures be re-derived from the
  host results.
- **L5: not fixed.** Pixels are unaffected, because the binding recomputes
  `need_geom` and never selects the persisted keys. The cost is extra warm-up
  compile before `mark play`, which is outside every scored window. Carried
  forward: whoever reads A1's startup time from `1224865`/`1227971`, or from
  any later default run on the same Nova install, should expect it to be
  longer. Clear the shader cache first if startup time is the quantity.
