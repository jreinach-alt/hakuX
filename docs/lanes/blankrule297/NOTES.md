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
`score_sweep.py` since `036e6c191f`) and did the eye-checks. It then started
the full scan, which was still running when the session ended. It had printed
only its header line, and a background task does not outlive its session.

Attempt 2's session also ended with nothing pushed past `5c63c19559`.
Attempt 3 found the scan could never finish. Each flat capture costs about
10 s here, from three `np.unique(axis=0)` calls, and 8k of the 96k rows are
flat, so the full scan would take about 3 hours. Attempt 3 rewrote the scan
on packed RGB keys (below), and the finished scan **refuted the brief's
rule**. That rule ran into the reverse direction the brief itself names as a
refutation (see "Reverse direction"). The shipped rule is therefore the
brief's `lost` clause ADDED to the old golden-colour clause, not
substituted for it.

The CI red on `5c63c19559` was 4 failures in `pr-sweep.sh` and the
nightly-notes tag-range checks, on a head based on a 75-commits-old master.
Master's own selftest is green. After merging `origin/master` again, the full
`selftest.sh` passes locally with 0 FAIL.

## The change

`score_sweep.py`: new `is_blank(o, g, label_rows)` and `BLANK_MIN_LOST = 0.01`.
The flatness clause (ours is > 90% one colour, <= 4 colours) is unchanged, and
so is the golden-side clause (golden > 4 colours). The `lost` clause measured in
`docs/lanes/cloud-297/NOTES.md` section 3 is added to them:

    ink  = golden pixels != golden's dominant colour, label band masked off
    lost = ink & (ours == ours' dominant colour)
    blank = flat_ours and golden_colours > 4 and lost.sum() >= 1% of the image

The new rule is the old rule plus one more condition, so it can only
release a capture from `blank`, never add one.

**`scorer_rev` needs no manual bump.** `dispatcher.sh` records `scorer_rev` as
`git log -1` of `docs/testing/score_sweep.py` and `scorer_sha256` as the
content hash of the snapshot that ran (027fa3d552). Both change with this
commit, and `ab_compare.py` warns when two arms differ on `scorer_rev`. So an
old TSV cannot be compared silently against one written by the new rule.

## Falsifier: the 19 captures ever tagged `blank`

`blank_rule_eval.before-after.out` (cloud-297's evaluator, run in attempt 1
against the `lost`-only rule). All 19 captures have goldens with > 4 colours,
because the old rule tagged them `blank`. So the added golden clause cannot
change any row here, and the full scan below confirms the same 15 against the
shipped function:

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
capture on disk, under both rules, and reports every transition. The rules
are evaluated on packed RGB keys (one int32 per pixel). Those keys sort in
the same order as `np.unique(axis=0)`, so the dominant colour is the same.
They are also skipped where ours is not flat, since both rules are False
there. It then re-runs the shipped `score_sweep.is_blank` on every changed
capture plus 100 random flat rows, and prints any disagreement.

**The brief's rule (`lost` alone) is refuted.** From
`blank_rule_eval_all.lost-only.out` (96,359 rows, 1,175 TSVs; shipped rule
re-run on 135 rows, 0 disagreements):

| old -> new | rows |
|---|---:|
| blank -> blank | 50 |
| blank -> ok | 257 (the 15 captures, exactly) |
| **ok -> blank** | **436** |
| ok -> ok | 95,616 |

The 436 rows are 35 captures in two families, all with goldens of <= 4
colours:
- Stencil `REPLACE`/`ZERO` variants: 1.6-11.4% lost, 5k-40k px differing.
- W_param `ff_w_zero_inf__*` and `prog_w_zero_inf__bitri_w-0.00`: 4.2-37.8%
  lost, 12.9k-271.5k px differing.

Residual triage reads `ok` rows, so these real residuals would have left
triage. That is #297's harm in the other direction, on more rows than it
fixes.

**The shipped rule (golden > 4 colours AND `lost`)**, from
`blank_rule_eval_all.out` (96,440 rows, 1,178 TSVs; shipped rule re-run on
115 rows, 0 disagreements):

| old -> new | rows |
|---|---:|
| blank -> blank | 50 |
| blank -> ok | 257: the 15 captures, nothing else |
| ok -> blank | **0** |
| ok -> ok | 96,133 |

The recorded TSV status matches the old-rule re-run on every row (307 blank,
96,133 ok), so every TSV scanned was written by the old rule.
`rescore_297.out` was made with the `lost`-only rule. It still holds: its 13
rows were old-rule `blank` (golden > 4 colours), and the full scan finds no
other row in those two runs that moves.

## For the next lane

- Do not drop either golden-side clause. The colour count alone hides
  near-exact captures (#297), and `lost` alone hides Stencil and W_param
  residuals (436 rows). Test any future change to `is_blank` with
  `blank_rule_eval_all.py`, which scans every row on disk, not with an
  evaluator that reads only rows already tagged `blank`. That kind of
  evaluator cannot see the reverse direction, and it is how the brief's
  rule got past cloud-297.
- Do not call `np.unique(axis=0)` over 96k captures on this host. Use the
  packed keys in `blank_rule_eval_all.py` (about 6 min on 6 workers) and
  cross-check them against the shipped function.
- Stencil and W_param lose 1.6-38% of the image with a flat capture. Whether
  those count as "did not draw" is an open question the old rule settled as
  `ok`. This lane kept that answer, and `blank` would take them out of triage.
- The selftest fragment builds numpy in a venv when the runner lacks it. It
  runs three mutants: the old colour-count-only rule, the label band left
  unmasked, and `lost` without the colour count. Each must get its case wrong.
