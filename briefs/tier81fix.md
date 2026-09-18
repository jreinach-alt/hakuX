# lane.tier81fix -- #81's fix, then #90

Base: 55bc6c6c2beed87350cf1c02f67403afddc2acef (origin/master).
Files (yours): accel/tcg/cpu-exec.c, accel/tcg/translate-all.c.
accel/tcg/tb-maint.c is NOT granted: 937848c9e7 (#68's range-test
restoration, ~200 lines) is held unfolded pending its own arm. If your fix
needs it, stop and say so in the PR rather than editing it.

THE MEASUREMENT IS DONE AND IT DECIDES THE FIX. The tier-1 mechanism FIRES
and is STARVED, not dead: eight of the first ten promotion requests name ONE
pc inside ONE millisecond; cflags goes 0xff020000 -> 0xff024000 between
promote #0 and #1, so the block kept CF_INVALID and was re-promoted seven more
times; exec_count climbs 64..71 past thresh=64 and a later request reads
exec=128, the clamp ceiling, so the promotion test is TRUE FOREVER for such a
block. Saturation in 2.2-2.7 s on four of four Crimson Skies runs.

GOAL:

1. #81 = the audit's M2: dedup on (pc, cs_base, flags) plus reset-or-latch of
   exec_count in tb_request_tier1_promotion(). NOT unmasking the two
   CF_INVALID comparisons -- the numbers point at eight duplicate requests for
   one pc, not at the lookup.
2. #90, SEPARATELY and measured SEPARATELY: the anti-churn tier-hint restore
   at translate-all.c:659-688, whose own comment says it prevents "endless
   re-promotion churn", sits inside #ifndef __ANDROID__ with its
   __android_log_print nested in an #ifdef __ANDROID__ INSIDE it -- dead
   preprocessor on the only platform that ships. #81's own entry says doing
   both at once makes either unattributable.

THERE IS NO SPEC FOR THE TIER-1 MECHANISM. The remediation is an auditor's
reading of intent from comments, and the #ifndef may be deliberate and
undocumented rather than a typo. AGREE THE INTENT IN WRITING FIRST, in the PR,
before implementing #90 -- and if you cannot, say which reading you took and
why.

FALSIFIER: if duplicate requests are the starvation mechanism, then with the
dedup in place the promotion-request count for an already-promoted pc FALLS
and distinct pcs promoted RISES on the same 240 s Crimson Skies soak. A flat
total count proves nothing -- wrong-replaced-by-wrong reads identical -- so
diff the per-pc request multiset between arms, not the total.

DONE WHEN: #81's patch with a prediction registered AFTER your last rebase and
stating the per-pc multiset comparison above; #90 either patched with its
intent argued, or written up as a decision the board must take. Two commits,
never one. Draft PR from lane/tier81fix. Do not queue the soak yourself --
register and say it is ready.
