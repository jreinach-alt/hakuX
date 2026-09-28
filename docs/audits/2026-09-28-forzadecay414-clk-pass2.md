# Audit pass 2: PR #588, lane.forzadecay414 -- clocks in every thermal sample (#414)

Head verified: `c6f11f7644` (remediation of pass 1's `ce044d4787`). Pass 1: `2026-09-28-forzadecay414-clk-pass1.md`.

**Result: clean. The M1 scenario can no longer occur as written, L1 is fixed, and L2 and L3 stay LOW as rated. Goes to `fold-ready`.**

## M1. A ceiling `scaling_cur_freq` read as proof that LMh was absent: closed

The pass-1 scenario: a reader of #414 sees `cpu7 3187-3187 of 3187` from a hot soak, takes it as positive evidence that the big core ran at full speed (as the PR's own text implied), and drops LMh as the cause of the decay.

Remediation (a) was required in three places. All three now carry the corrected claim:

- **Module doc (CLOCKS).** The sentence "without these a core held at a fraction of its clock at 95 C reads exactly like one at full speed" is gone. The new text says `scaling_cur_freq` is the clock the governor REQUESTED. It says LMh on qcom-cpufreq-hw moves neither that nor `scaling_max_freq`, and that "a ceiling reading is no evidence either way". It cites gta482 NOTES ("scaling_cur_freq still reads each cluster's maximum"). It names the device check that would decide the question (a hot soak where fps falls with no cooling device set, and whether the cpu7 minimum moves) as #414's post-fold check. It keeps the GPU half's wording, as pass 1 allowed.
- **`CPUFREQ_DIR` comment.** It now reads "requested clock (scaling_cur_freq: LMh may cap below it unseen, see the module doc)".
- **`clock_range` docstring.** "is LMh/DCVS at work" is now "is a cap or an idle core". It adds: "A CPU maximum AT the ceiling does not rule out LMh: the CPU figure is the governor's request".

Replayed: the reader who sees `cpu7 3187-3187 of 3187` now finds text in all three places the claim was made that tells them this reading does not exclude LMh. Nothing left in the file claims the opposite. The remaining sentence ("Qualcomm's LMh/DCVS caps a core's clock ... so no `cd` line shows it") is a true statement about cooling devices, not a claim about `scaling_cur_freq`.

The post-fold check lives in the module doc, not in a comment on #414. The lane's #414 comment for this PR predates the remediation. That is enough for this audit, because the check sits beside the figure it qualifies. The lane should repeat it on #414 when it reports the first post-fold soak.

## L1. `gpu throttling 1` read as live throttling: fixed

The summary clause is now `gpu throttle-switch N`, and the docstring says "throttle-switch is kgsl's enable, not a live state". The selftest's expected string (`99-thermal-pause.sh`, the `clock:` leg) changed in lock-step, both in the `case` pattern and in the `ok` message. A grep of `docs/testing` for `gpu throttling` / `throttling [0-9]` outside `thermal_state.py` finds no other reader of the old clause.

## L2, L3: unchanged, still LOW

- L2 (no middle-policy fixture): no fixture was added. Nothing observable goes wrong on either handheld (at most `policy7`). It remains a quality gap in the selftest.
- L3 (twelve more forks per 30 s sample): unchanged. It is marginal next to the existing per-zone loop.

## Not verified here

This firing could not run the selftest leg locally (the host's tool policy did not permit it). CI on `c6f11f7644` was in progress when this was written, and it is the gate of record for the fold. The only functional change in the remediation is a string in `clock_range` and the same string in the selftest's expectation, so a red leg there would be a typo, not a design problem.
