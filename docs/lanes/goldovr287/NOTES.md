# lane goldovr287: #287 data half (TexFmt_R6G5B5 golden override)

Status: done. Data committed; inert until the scorer hook (lane.toolsmith
defect 17) lands. Analysis is lane.goldencorr287's (`docs/lanes/goldencorr287/NOTES.md`,
folded in #300); nothing here re-derives it.

## What landed

- `docs/testing/golden_overrides/Texture_format/TexFmt_R6G5B5.png`: byte copy
  of console set K, `/home/justin/hakux-work/hardware/runs/2026-09-19-calib/full/out/run1/Texture_format::TexFmt_R6G5B5.png`
  (the calib run is under `hakux-work/hardware`, not `hakuX/hardware`;
  `find_captures.py`'s default bases miss it).
- **sha256 checked**: source and committed file are both
  `07dedad9ac60aa7c36f2791bf877311f66779359912f239bb7815a704ea385f8`, as the
  brief required. Upstream golden:
  `50af66a644f6a2ba3b7026fcb9a2e1fb5034a2ecca3950d830b5612f1cf24d4e`.
  The same run's `Texture_render_target::TexFmt_R6G5B5` is a different file
  (`76277c75...`) and was not copied.
- `docs/testing/golden_overrides/README.md`: provenance row, the inert note,
  and the suite/test keying rule.

## Falsifier

`docs/lanes/goldencorr287/falsify.sh` **does not run on master**: it needs
`scratch/ov` and `scratch/score_sweep_patched.py`, which were untracked in the
old worktree and never committed. `falsify.sh` here replaces it: it derives
the override-aware scorer from master's `score_sweep.py` at run time (one
lookup inserted after the `gp =` line, keyed suite/test, reading
`GOLDEN_OVERRIDES`), points it at the committed `docs/testing/golden_overrides`,
and diffs every row against the stock scorer. It asserts the anchor line is
unique, so it fails loudly if score_sweep moves.

Output, re-scoring the sweeps of run `z-c866527e03` (2026-09-25, master 8a521a3b73):

```
== z-c866527e03-081-Texture_format
rows 40  sum px A 134902  B 0  moved 1
  moved Texture_format::TexFmt_R6G5B5 {'status': ('white-content', 'ok'), 'differing': ('134902', '0'), 'max_rgb': ('223', '0'), 'max_a': ('254', '0'), 'off_by_one': ('0', '0')}
== z-repeat-c866527e03-081-Texture_format
rows 40  sum px A 134902  B 0  moved 1
  moved Texture_format::TexFmt_R6G5B5 (same)
== z-c866527e03-085-Texture_render_target
rows 40  sum px A 1473  B 1473  moved 0
   Texture_render_target::TexFmt_R6G5B5 A ok 0 B ok 0
```

Reproduces goldencorr287's table exactly: 134,902 -> 0 on the one row, no
other row in either suite moves, and the same-named render-target row stays
ok 0 (the suite/test key holds).

As goldencorr287 noted, the R6G5B5 leg is forced for any capture identical to
K; the informative leg is the must-not-move one.

## Prediction

none: no arm. The captures do not change, and no scorer reads this tree yet.

## Do not repeat

- Do not run `goldencorr287/falsify.sh` expecting it to work; use this one.
- The hook itself (score_sweep.py, dispatcher.sh) is toolsmith's, not granted here.
