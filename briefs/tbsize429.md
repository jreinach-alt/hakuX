# lane.tbsize429 -- #429: smaller translation blocks on often-rewritten pages

Lane: tbsize429. Issue: #429. Base: origin/master @ deb0903b51. Release tracker: #433 (0.5).
Files: accel/tcg/translate-all.c, accel/tcg/cpu-exec.c, docs/lanes/tbsize429/**, docs/testing/predictions/tbsize429-*.json
Needs device: yes (a gameplay soak A/B through request.sh; never touch a device). Needs NDK: yes.
Read first: the issue body; docs/investigations/performance-next-three.md section 2; docs/investigations/perf-architecture.md;
docs/lanes/tbchurn424/NOTES.md (PR #434, folded: what code-write invalidation churn remains) and docs/lanes/jcache425/NOTES.md.

## Why (evidence)
tb_gen_code is 19% of the vCPU thread; smaller blocks on pages the guest rewrites often cut re-translation, about 4 ms a frame.
That share is a BOUND from a profile, not a gain. 0.5 is judged by games: the number that counts is gfps over a #397 gameplay
window (Crimson Skies route, Blinx), A vs B, same device, same session.

## The trap (the reason this issue waited for both files)
cflags is part of the TB hash key. A page-derived block size must be reproduced IDENTICALLY at both lookup sites,
`cpu_exec_loop` and `helper_lookup_tb_ptr` (both in cpu-exec.c), and at the generate site in translate-all.c, or lookups miss
and the thrash gets worse. Derive the size once, in one helper, and call it from all three.

## File boundary and the ready PR on cpu-exec.c
PR #443 (lane.jcache425, #425) is ready and released cpu-exec.c at ready; it adds `[jc425]` counters there. Branch from master,
and before marking your own PR ready merge master (or lane/jcache425 if #443 has not folded) and re-run your arm.
tb-maint.c, tb-internal.h and cputlb.c are lane.tbflip424's (#424 default flip). Do NOT edit them: if a hunk must live there,
name it in NOTES.md and file dispatch/board-requests/tbsize429.md for the host to sequence.

## Build
1. PILOT FIRST (owner's rule): one short soak or an existing simpleperf capture (perf/2026-09-2*/) to confirm tb_gen_code's
   share and the rewritten-page population on master's gameplay window. Count report-sample records, not rounded percentages.
2. Add a per-page rewrite counter, pick the threshold from the pilot's data, translate at most N insns per block on those pages.
   Self-modifying guest code must still see its new code.
3. Register docs/testing/predictions/tbsize429-*.json after the last rebase: the falsifier names the counters that must move
   (tb_gen_code samples as a share of the vCPU thread, translated-insn count) and a must-not-move leg for the pgraph suites.

## Falsifier
If tb_gen_code's share does not drop on the A/B, or the lookup miss rate rises, the lever is inert or wrong here: report it, do
not tune until a number moves.

## Do not
Touch a device; edit board files; edit tb-maint.c / cputlb.c / tb-internal.h.

## Done when
PR ready, CI green, arm verdict posted, docs/lanes/tbsize429/NOTES.md with the before/after table and run ids. No pgraph suite regresses.
