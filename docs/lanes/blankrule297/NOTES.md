# blankrule297 -- the scorer's `blank` rule stops hiding small real residuals (#297)

## Why attempt 1 did not finish

Attempt 1 committed the rule change, the selftest fragment and the 19-capture
before/after, pushed, and ended with the PR in draft. The all-rows scan
(`blank_rule_eval_all.py`) had been started but never finished; its `.out` held
only the header line. CI then went red on `5c63c19559`. The cause was 4
failures in fragments this lane does not touch (`pr-sweep.sh` "a stale failure
ALONGSIDE a live one", and three tag-range checks); `83-blank-rule.sh` itself
passed on the runner. The branch was 75 commits behind master. Attempt 2
merged `origin/master` (no conflict: master had not touched
`score_sweep.py` since `036e6c191f`), re-ran the selftest and the full scan,
and did the eye-checks.

## The change

`score_sweep.py`: new `is_blank(o, g, label_rows)` and `BLANK_MIN_LOST = 0.01`.
The flatness clause (ours is > 90% one colour, <= 4 colours) is unchanged. The
golden-side clause `gold_colours > 4` is replaced by the one measured in
`docs/lanes/cloud-297/NOTES.md` section 3:

    ink  = golden pixels != golden's dominant colour, label band masked off
    lost = ink & (ours == ours' dominant colour)
    blank = flat_ours and lost.sum() >= 1% of the image

**`scorer_rev` needs no manual bump.** `dispatcher.sh` records `scorer_rev` as
`git log -1` of `docs/testing/score_sweep.py` and `scorer_sha256` as the
content hash of the snapshot that ran (027fa3d552). Both change with this
commit, and `ab_compare.py` warns when two arms differ on `scorer_rev`. So an
old TSV cannot be compared silently against one written by the new rule.

## Falsifier: the 19 captures ever tagged `blank`

`blank_rule_eval.before-after.out` (cloud-297's evaluator, run against this
tree's `is_blank`):

| capture | differ px | lost % | old | new |
|---|---:|---:|---|---|
| Depth_buffer/DepthFmt_z16_C{n,y}_FZy_M00000f (x2) | 3,936 | 0.33 | blank | **ok** |
| Depth_buffer_fixed_function/z24_C{n,y}_FZy_M* (x10) | 24 | 0.00 | blank | **ok** |
| Texture_BRDF/BRDF_e{0,1}_l{0,1} (x3) | 614 | 0.20 | blank | **ok** |
| Texture_DXT/DXT1_plasma{,_alpha}_dxt1 (x2) | 65,536 | 21.33 | blank | blank |
| W_buffering/WBuf24D_FloorQuad_V0_ZB{0,1}_ZS1 (x2) | ~230,400 | 49.7 | blank | blank |

- 15 released: every loss is <= 0.33%.
- 4 real blanks kept: 21.33% and 49.7%. There is a 65x gap between the two
  groups, and the 1% threshold falls inside it.
- The 13 #297 rows now read `ok`, each with its real `differing` count
  (24 px x 10 for DBFF, 614 px x 3 for BRDF), so the residual classifier sees
  them. The z16 FZy M00000f pair, also released, reads `ok` at 3,936 px.

### Checked by eye

`eyecheck.py OUT SUITE/TEST...` renders golden | ours | diff (differing pixels
in red) from the newest capture whose TSV row was `blank`, upscaled 2x. It also
prints the differing-pixel count and bounding box. I looked at one capture from
each family:

- **Texture_BRDF/BRDF_e0_l0**: the golden has a small pale-green triangle in the
  bottom-right corner (x 579-639, y 460-479), which ours lacks. That is the
  whole 614 px, and the rest of the frame matches. A real residual, not a
  blank.
- **Depth_buffer_fixed_function/z24_Cn_FZy_M7f8001**: the only differences are
  two tick marks of a few pixels each (x 136-509, y 53-71). Ours is otherwise
  identical. A real residual.
- **Depth_buffer/DepthFmt_z16_Cn_FZy_M00000f** (run `1789240604b-depth-baseline`):
  the golden has two rows of grey squares under the label, and ours draws one
  square. The 3,936 px are a missing row of swatches, which is a wrong-value
  residual, not a frame that did not draw.
- **Texture_DXT/DXT1_plasma_dxt1** (kept blank): the golden has a 256x256
  plasma quad, and ours is background with only the label. Genuinely blank.
- **W_buffering/WBuf24D_FloorQuad_V0_ZB0_ZS1** (kept blank): the golden has a
  checkerboard floor over the right 80% of the frame, and ours is background
  plus labels and leader lines. Genuinely blank.

The other 12 released captures are the same test at other `M*` / `C?` /
`e?_l?` values, with identical differing counts (24 or 614 px) and lost
fractions. I did not render them separately.

## The 13 #297 rows, end to end

`rescore_297.sh` re-scores the two runs that carry the #297 rows with
`score_sweep.py` at `036e6c191f` and with this tree's. It then diffs the
resulting TSVs with `rescore_cmp.py` (`rescore_297.out`):

- `1790373098-brdf315-964945`: of 3 rows, all 3 go `blank -> ok` at
  `differing=614`.
- `0-a-now-8e683b3a26-023-Depth_buffer_fixed_function`: of 80 rows, exactly
  the 10 z24 FZy rows go `blank -> ok` at `differing=24`. The other 70 do not
  move.
- In both runs the old-scorer re-run reproduces the recorded TSV's status
  exactly (0 mismatches), and no column other than `status` changes. The rule
  moves only the blank decision.

## Reverse direction: every ok/blank row on disk

`blank_rule_eval_all.py` re-scores every `ok`/`blank` row that still has its
capture on disk. It runs the old rule inline and the new rule by importing this
tree's `score_sweep.py`, so it measures the code that ships. It reports every
transition. Output: `blank_rule_eval_all.out`.

RESULT_PLACEHOLDER

## For the next lane

- Do not reintroduce a golden-only test such as a colour count. The question
  is what OUR flat frame covered of what the golden drew.
- If a future test's real residual loses more than 1% of the image while ours
  is flat, it will read `blank`. That is the intended outcome: it did not draw.
- The selftest fragment builds numpy in a venv when the runner lacks it, and
  runs two mutants: the old `gold_colours > 4` rule, and the label band left
  unmasked. Each must get its case wrong.
