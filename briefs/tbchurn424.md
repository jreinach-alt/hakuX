# lane.tbchurn424 -- #424: the translation cache's code-write invalidation and dirty re-arm churn

Issue: #424. Base: origin/master @ 15d9406b81. Release tracker: #433 (0.5, target 2026-09-28).
Files: accel/tcg/tb-maint.c, accel/tcg/cputlb.c, accel/tcg/translate-all.c, docs/lanes/tbchurn424/**, docs/testing/predictions/tbchurn424-*.json.
Needs device: yes (Nova/Thor gameplay window before and after). Needs NDK: yes.
Read first: the issue body; docs/investigations/perf-architecture.md (section 2, lever 1); docs/investigations/perf-baseline-2026-09.md;
docs/investigations/performance-next-three.md; docs/lanes/perfarch/NOTES.md and docs/lanes/tcgchurn/NOTES.md (method, what was refuted).

## The goal
the translation cache's code-write invalidation and dirty re-arm churn. The lever's share is a BOUND from a profile, not a measured gain: say which. 0.5 is measured by games, so the number
that counts is fps over a gameplay window of a #397 title (Crimson Skies, Blinx), before and after, same route, same device,
same session.

## The job
1. Re-read what lane.tcgchurn (PR #309) already landed; measure what churn REMAINS on master on a gameplay window (tb_invalidate / dirty re-arm share in simpleperf, count report-sample records).
2. Stop the remaining invalidation/re-arm without breaking self-modifying code (a guest that rewrites code must still see the new code).
3. translate-all.c is yours; #429 waits for you.
Register a prediction (docs/testing/predictions/tbchurn424-*.json) whose falsifier names the counter that must move
(tb_invalidate_phys_range / dirty re-arm samples as a share of the vCPU thread, and the slow-store count) and a must-not-move leg for the pgraph suites. Merge master before marking ready.

## Falsifier
If that counter does not move on the A/B the lever is inert here: report it, do not tune until a number moves.

## Done when
PR ready, CI green, arm verdict posted, docs/lanes/tbchurn424/NOTES.md with the before/after table and run ids.
Owner's rule: no pgraph suite regresses.
