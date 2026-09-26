# blankrule297 -- make the scorer's `blank` rule stop hiding small real residuals

Issue: #297 (harness). Base: origin/master tip (rebase before you register or measure anything).
Files: docs/testing/score_sweep.py (GRANTED from lane.toolsmith, standing; job.board wave 215),
       docs/testing/jobs/selftest.d/83-blank-rule.sh (new), docs/lanes/blankrule297/**
Needs device: no. Needs NDK: no. Prediction: none -- a scorer change, proved by the eval script.

## Goal
`score_sweep.py:229-230` tags a capture `blank` when ours is >90% one colour with <=4 colours and the
golden has >4 colours. It fires on 15 captures whose golden ink is tiny (<=0.33% of the image), so the
13 residuals in #297 (Depth_buffer_fixed_function z24_C?_FZy_M* 10 x 24 px, Texture_BRDF 3 x 614 px)
are never triaged. docs/lanes/cloud-297/NOTES.md section 3 and the comment on #297 give the measured
replacement; implement it, do not re-derive it:
    ink  = (g[..., :3] != golden_dominant).any(axis=2); ink[:LABEL_ROWS] = False
    lost = ink & (o[..., :3] == ours_dominant).all(axis=2)
    blank = flat_ours and lost.sum() >= 0.01 * npx     # replaces `gold_colours > 4`
Keep the 90% / <=4-colour flatness clause. `docs/lanes/cloud-297/blank_rule_eval.py` is the evaluator.

## Falsifier
Run the evaluator over the 19 captures ever tagged `blank` in the 1,075 TSVs on disk: the 15 false
positives must stop being `blank` (each loses <=0.33%) and the 4 real blanks (DXT1 plasma x2 at 21.3%,
W_buffering FloorQuad x2 at 49.7%) must stay `blank`. Say which of the 15 you checked by eye and how.
Also confirm `Depth_buffer/DepthFmt_z16_C?_FZy_M00000f` (3,936 px, blank in one run) is released, and
that no capture that was `ok` becomes `blank`. A capture changing status the other way is a refutation.

## Also
- `scorer_rev` records which scorer wrote a row: bump/record it the way the file already does, so old
  TSVs are not silently compared to new ones (see 027fa3d552).
- Add selftest fragment 83-blank-rule.sh: a synthetic pair per case (tiny ink -> ok, large lost ink ->
  blank, flat ours with flat golden -> ok) and a mutant that restores `gold_colours > 4` and must fail.
  No numpy/PIL in jobs-selftest: check how 76-x1a7-model.sh or 88-sweep-cover.sh skip or shim it.
- Do not touch scoreboard.py, collect_sweep.sh, queue_full_sweep.sh (lane.sweepcover's) or
  classify_residuals.py (lane.toolsmith's).

## Done when
The PR is ready, the evaluator output before/after is in NOTES.md, the selftest fragment passes with its
mutant failing, and the 13 #297 rows read `ok` with their real px counts under the new rule.
