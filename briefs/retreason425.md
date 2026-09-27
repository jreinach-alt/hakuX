# lane.retreason425 -- #425: why the vCPU's TBs return to cpu_exec_loop (the split counter)

Lane: retreason425. Issue: #425 (feeds #412). Base: origin/master @ 231d04df51. Release tracker: #433 (0.5).
Files: accel/tcg/cpu-exec.c, accel/tcg/tb-jmp-cache.h, target/i386/tcg/translate.c (read; edit only a counter flag at gen_eob's exit_tb arm), docs/lanes/retreason425/**, docs/testing/predictions/retreason425-*.json
Needs device: yes (a Nova gameplay soak through request.sh; never touch a device). Needs NDK: yes.
Read first: #425 comments from 2026-09-27T01:45Z (lane.aufire412b's hand-off) and 02:04Z (the job.cloud correction); #412's 01:45Z profile;
docs/lanes/jcache425/NOTES.md (PR #443, folded: `[jc425]` counters, HAKUX_TCG68_JC); docs/lanes/aufire412b/NOTES.md (PR #451, folded).

## Why
Agent Under Fire mission play spends 54% of vCPU samples in `cpu_exec_loop` between TBs (37% is the barrier in `cpu_handle_interrupt`),
26% in guest code; Crimson spends 11.7%. `tb_add_jump` never runs, so each return arrives with `last_tb == NULL`: the TBs return
unchained. The exec-loop returns are bounded at 37 ms of a 62 ms frame. That is a BOUND from a profile, not a gain, and the profile
cannot say which cause it is. Pricing a lever before the cause is named is how the last three levers measured ~0 on this title.

## Build: one counter set that separates FOUR causes
1. Misses counted inside `helper_lookup_tb_ptr` itself (an indirect jump whose probe missed).
2. Translator-generated `exit_tb(NULL, 0)` counted separately: `gen_eob()` ends the TB with a plain exit for STI, POPF, IRET, segment
   writes, CLTS, WRMSR, CR writes and any DISAS_JUMP under an interrupt shadow. Book it with a per-TB flag set at that arm, or by the
   guest opcode of the returning TB's last instruction. A loop-side counter books these as lookup misses; do not use one alone.
3. In the loop: `TB_EXIT_REQUESTED`, a page-spanning target (`tb_page_addr1(tb) != -1`, cpu-exec.c ~1770), `interrupt_request` non-zero.
4. Iteration count, and the top returning guest PCs (top 16, with their last opcode).
Print them on the existing `[tlb68]` / `[jc425]` line family so the dispatcher's allow-list already carries them (cputlb.c is
lane.tbflip424's: do not edit it; name any hunk there in NOTES.md and file dispatch/board-requests/retreason425.md).

## Then, only if a number says so
Run one Nova AUF mission-play soak (survey route, 30-60 s, default regimen), A = master, B = counters on. Say which cause dominates
by counted returns per frame. A handful of returning PCs is NOT by itself a poll: a handful of IRQL/IRET PCs looks the same.
If cause 4 dominates the lever is the translator's EOB (chain across it or make it a lookup), not the jump cache; if causes 1/3
dominate, size the jump-cache or page-span change against the counter. Price it in ms per frame from the counted returns; do not
ship a lever without a moved number. Pixels must stay byte-identical (register a must-not-move pixel leg).

## Files and the ready PRs
cpu-exec.c and tb-jmp-cache.h came free with PR #443 (folded) and PR #459 (folded). tb-maint.c, tb-internal.h, cputlb.c are lane.tbflip424's.
Register the prediction (docs/testing/predictions/retreason425-*.json) AFTER your last rebase.

## Falsifier
If the counted returns per frame do not add up to the profile's exec-loop share within a stated margin, the counter is wrong: fix it
before anything else. If the split shows no dominant cause, report that; do not tune.

## Do not
Touch a device; edit board files; edit cputlb.c / tb-maint.c / tb-internal.h; enable HAKUX_TCG68_JC by default (tbflip424's hunk).

## Done when
PR ready, CI green, docs/lanes/retreason425/NOTES.md with the split table (returns per frame by cause, top PCs, run ids) posted to #425 and #412.
