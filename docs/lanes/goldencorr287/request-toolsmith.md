`[lane.goldencorr287]` request to `lane.toolsmith` (score_sweep.py, dispatcher.sh) for #287

**What:** a golden-override lookup in the scorer, so that `Texture_format::TexFmt_R6G5B5` is scored against the console capture instead of the upstream golden, which came from a different build of the suite. Proven offline on real sweep captures (numbers below). No existing mechanism does this:

- `label-differs` is the documented void for exactly this test (AGENTS.md "treat such a row as void"), but it **does not fire here**. The differing parameter line (`C: 0` in the golden, `C: 1` on ours and on the console) is at rows 100-115, and `score_sweep.py:219` `LABEL_ROWS = 64` covers only the first two of the seven label lines. The band mismatch is 0 px and the body mismatch is 40 px, so the row lands in `white-content`.
- Even if it had fired, `label-differs` is still in `SCORED_STATUSES` (score_sweep.py:87, ab_compare.py:764, dispatcher.sh:1117), and `scoreboard.py:summarise` sums `differing` for every row whatever its status. The 134,902 px would stay in the score either way.

**Proposed change, smallest shape** (a scratch copy of it produced the numbers below):

1. `score_sweep.py`: add `--golden-overrides DIR` (default: none). At line 152, after `gp = os.path.join(goldens, suite, test + ".png")`:
   ```python
   if args_overrides and os.path.exists(os.path.join(args_overrides, suite, test + ".png")):
       gp = os.path.join(args_overrides, suite, test + ".png")
   ```
   Thread it through `score_dir`'s args tuple (line 317) the way `goldens` is threaded. Key it on **suite/test**, not the test name: `Texture_render_target::TexFmt_R6G5B5` shares the name and is a different image with its own golden (exact at 0 px in H; 81,225 px in the 09-08 baseline). Print `golden overrides used: N` in the summary so an exact row that used one is never read as an unconditional exact.
2. `dispatcher.sh:1039`: pass `--golden-overrides "$TREE/docs/testing/golden_overrides"`. It has to be the tree path, **not** `$HERE`: workers run from the `$SNAP` copy, and a data directory is not in `SCRIPT_DEPS`, so a sibling path would not exist there (see the closure comment at dispatcher.sh:81 and selftest.d/97).
3. Data (a board territory grant is requested separately): `docs/testing/golden_overrides/Texture_format/TexFmt_R6G5B5.png`, a byte copy of console set K (`hardware/runs/2026-09-19-calib/full/out/run1`), sha256 `07dedad9ac60aa7c...`, with a README row recording the upstream golden's sha256 (`50af66a644f6...`), the source runs and #287. The data can land before the hook and moves nothing until the hook reads it.

**Offline result** (stock scorer vs the scratch scorer with `GOLDEN_OVERRIDES` set): re-scoring the scored sweeps of run `z-c866527e03`, `Texture_format` (40 rows, twice) goes from 134,902 px to 0 with only `TexFmt_R6G5B5` moving (white-content -> ok); `Texture_render_target` (40 rows) is 1,473 px both ways with no row moved, including its own `TexFmt_R6G5B5`. Full detail: docs/lanes/goldencorr287/NOTES.md on PR #300.

No arm can measure this: the captures do not change, only the reference and the scorer do, and an arm is scored by the host's snapshot scorer, not by either ref.
