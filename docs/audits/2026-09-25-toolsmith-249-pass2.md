# Audit pass 2: PR #249 (lane/toolsmith), dispatcher hardening, defects 0-10

Auditor: job.cloud, 2026-09-25. Head verified: `c3b50ac587` (remediation for
pass 1 `2026-09-25-toolsmith-249-pass1.md`). CI on this head: build ×2 and
selftest are green.

**Result: clean. M1 can no longer occur, and L1 is fixed. L2-L5 stand as
LOWs and do not block. Next state: `fold-ready`.**

## M1. INCOMPLETE says "Re-run the arm", and nothing can re-run it: CLOSED

I walked the pass-1 scenario through `jobs/arms.sh` at `c3b50ac587`. One arm's
pull is truncated, it keeps some captures, and ab_compare prints INCOMPLETE.

1. **Judge loop, first INCOMPLETE** (arms.sh ~756-798). The `case` matches
   `"VERDICT: INCOMPLETE"*`, which is the prefix ab_compare prints
   (`ab_compare.py:1700`). With no `incomplete/<sha>`, the loop touches `VOIDED`
   in both `$RA` and `$RB`, writes `incomplete/<sha>`, removes
   `pairs/<sha>.json`, and `continue`s before `judged/<sha>` is written. The
   comment still posts, and says the pair is queued again once.
2. **Next tick, RAN walk** (~321-338). A result directory with `VOIDED` is
   skipped just as `ERROR` is. Both halves are voided, so the sha has fewer
   than two distinct clean refs and is not in `RAN`.
3. **Next tick, `already_ran`** (~254-288). There is no `judged/<sha>` and no
   `pairs/<sha>.json`. No `skipped/<sha>` was written, the queue holds no req
   with that sha, and the sha is not in `RAN`, so it returns 1. The queue loop
   then applies its structural gates. The `$SINCE` watermark is a fixed file
   (`$A/since`, seeded once), so a registration that passed it the first time
   still passes it. request.sh is called for both arms and a new pair is
   written. **The scenario's step 1 (judged marker) and step 2 (sha in RAN)
   both fail to happen, so the pair re-queues.**
4. **Second INCOMPLETE.** `incomplete/<sha>` exists, so it is final. Both
   halves are voided, `judged/<sha>` is written, and the comment names the
   recovery that works: re-register, or delete `judged/` and `pairs/`. That
   deletion now does queue, because the voided halves are out of `RAN`. This
   is remedy (a) and (b) together.

VOIDED results are per-pair. Each pair's two results are queued by their own
request.sh calls, so voiding them cannot strand a different prediction.

**Selftest.** `51-dispatch-hardening.sh` part E2 drives this path end to end.
It checks that the first INCOMPLETE is re-queued, the second is final, a third
tick queues nothing, and the published recipe queues again. A mutant that
deletes the VOIDED skip from the RAN walk must queue nothing, so the leg can
go red. CI's selftest job passed on `c3b50ac587`.

## LOW

- **L1 (wrong fragment name in three comments): fixed.** `ab_compare.py`,
  `dispatcher.sh` and `score_sweep.py` now name `51-dispatch-hardening.sh`.
- **L2-L5: not addressed, still LOW.** L2 is the false "0 captures" message
  when every capture is unscored. L3 is `adb_call` retrying `am start`. L4 is
  the unreachable "arms share no capture" refusal. L5 is the non-atomic
  requeue write. Each still has the bounded blast radius pass 1 gave it, and
  the M1 remediation made none of them worse. Worth a follow-up; they do not
  block the fold.

## New in the remediation

Nothing found. The one new state directory, `$A/incomplete`, is created by the
`mkdir -p` at the top of arms.sh. The only new file markers are `VOIDED` and
`incomplete/<sha>`, and every reader of results state that decides "has run"
goes through the RAN walk, which handles `VOIDED`.
