# nearbar1017b: three more near-cap titles on the 0.5.2 build

State: draft

Lane: nearbar1017b             Issue: #433
Base: master @ f799199e39
Files: docs/lanes/nearbar1017b/NOTES.md, docs/lanes/nearbar1017b/PR.md
Prediction: none: analysis-only (held device runs, judged by hand against the existing ledger bar; no code change to predict against)
Needs device: yes    Needs NDK: no

Second near-cap batch on #433 (first was `nearbar1017`, folded `f799199e39`:
Panzer and Aeon Flux cleared, MoH inconclusive). This batch: Turok Evolution
(41430004), Burnout 3: Takedown (4541005B), Ty the Tasmanian Tiger: Night of
the Quinkan (41560055) -- each missed the Playable bar (>= 30 fps, >= 90% of
gameplay) only on fps on a pre-0.5.2 build, and 0.5.2 turned on
`HAKUX_S2T_CVT` by default, so this is a new measurement, not a retest.

Step 0 (`docs/lanes/nearbar1017b/NOTES.md`): no open `nv2a_issues.toml`
defect names any of the three, so all three need the run. Work in progress;
will update this PR with the final table once all three Nova runs complete.
