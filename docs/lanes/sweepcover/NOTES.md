# lane.sweepcover NOTES

Brief: `briefs/sweepcover.md` (2026-09-25). Issues #291-#296, plus two scorer
defects. Two PRs: #298 (status column, urgent) and a second for the sweep legs
and the unscoreable list.

## PR #298: the status column

### The defect

`score_sweep.py` writes `differing = 0` for a row it cannot score
(`unreadable`, `size`, `no-golden`). `scoreboard.py` `summarise()` did
`exact += (differing == 0)` over every row, so each of those rows counted as an
**exact capture**, and `px += differing` put any number a void row carried into
structural px. `collect_sweep.sh` copied sheets without reading the status at
all. That is the same false win PR #249 removed from arm verdicts, still live
in the sweep columns, and the two sweeps running today (`z-a-now-2b04d4d422`,
`z-b-v040j1`) are collected by exactly this code.

### The change

- `scoreboard.py` carries `SCORED_STATUSES = ("ok", "blank", "label-differs",
  "white-content")`, the same tuple as `score_sweep.py`, `ab_compare.py` and
  `dispatcher.sh`'s result writer. It is a copy, not an import, because
  `score_sweep.py` imports numpy and the scoreboard (and the selftest runner)
  must not need it. Fragment 88 fails if the two drift.
- A row whose status is outside that set (including an empty or missing status)
  is **void**: not a capture, not exact, not in structural px. The category
  cell becomes `exact/captures · structural · n void`, and the provenance table
  gains a `void` column broken down by status (`2 ⚠️ (size 1, unreadable 1)`).
  The coverage floor (⚠️NN%) is computed on scored captures, so void rows lower
  it, which is what they are: unmeasured goldens.
- `label-differs`, `blank` and `white-content` stay scored content, per the
  brief (the console calibration on this disc had 0 `label-differs` rows in
  3,379 captures).
- `collect_sweep.sh` still TAKES a sheet with void rows (the progress-log proof
  gate is about the tests completing; a truncated pull happens after that), but
  names each sheet's void count and prints a total. Its board root, goldens
  root and SCOREBOARD.md path now come from `SCOREBOARD_ROOT`,
  `SCOREBOARD_GOLDENS`, `SCOREBOARD_MD`, defaulting to the old literals, so a
  selftest can run the whole script without touching the live board.
- `CATEGORIES`: removed the phantom `Fog_multiple_vertices` (no golden
  directory has ever had that name); added `Fog_planar_vsh` (Fog) and
  `Surface_as_vertex_array` (Render to texture). Neither has a directory under
  `/home/justin/goldens/results` yet, so today's golden counts do not move;
  they will be categorised rather than `(uncategorised)` once #293 lands them.

### Effect on the existing columns

None. Every collected column under `/home/justin/hakux-work/scoreboard/`
(0026f00534, 6762a54c82, after, c866527e03, pre-fixes-fb4dfafc,
repeat-c866527e03) has only `ok`/`blank`/`label-differs`/`white-content` rows:
0 void, measured 2026-09-25 with a python walk over every TSV. The new code
over two of them prints cells identical to the committed SCOREBOARD.md plus a
`void 0` column. The fix matters for the columns collected from now on.

### Proof

`docs/testing/jobs/selftest.d/88-sweep-cover.sh`: one Fog sheet with rows
`ok 0`, `ok 10 (4 one-step)`, `unreadable 0`, `blank 20`, `label-differs 0`,
`size 1000`, collected by `collect_sweep.sh` into a scratch board.

| code | Fog cell | provenance |
|---|---|---|
| origin/master @ d709a8d1fa (falsification) | `3/6 · 1,026` | captures 6, no void column |
| this branch | `2/4 · 26 · 2 void` | captures 4, void `2 ⚠️ (size 1, unreadable 1)` |

The `size` row carries a nonzero `differing` on purpose: with 0 there, "void
rows are not in structural px" could not fail.

Mutants (each on a copy of `scoreboard.py`, over the collected column):

- `unreadable` added to `SCORED_STATUSES` -> `3/5 · 26 · 1 void` (red);
- the void suffix dropped from `cell()` -> `2/4 · 26` (red).

Falsification: a scratch worktree at `origin/master`, the fragment pointed at
its `docs/testing`. The old `collect_sweep.sh` hardcodes the live board paths,
so in the scratch copy ONLY those four path literals were rewritten to the
environment variables (diff was path-only; logic untouched) -- running it as
written would have created a `fix` column in the live board. Result: 1 pass
(the sheet was copied), 10 FAIL; the old code counts the unreadable row exact.

### For the host: AGENTS.md's label-differs line

Not edited here (brief). `AGENTS.md:649-650` currently reads "`score_sweep.py`
now reports `label-differs` per test; treat such a row as void rather than as
a defect", which contradicts every scorer's `SCORED_STATUSES`. Proposed
replacement for those two lines:

> `score_sweep.py` now reports `label-differs` per test. A `label-differs` row is scored content, not void: the label band check
> flags where the overlay text differs, and the console calibration on the
> stock disc had 0 such rows in 3,379 captures. Void means the status says
> there is no measurement -- `unreadable`, `size`, `no-golden`, or none -- and
> every scorer (`score_sweep.py`, `ab_compare.py`, `dispatcher.sh`,
> `scoreboard.py`) shares one `SCORED_STATUSES` tuple.

## Do not repeat

- Do not run the old `collect_sweep.sh` against a fixture as written: it writes
  `/home/justin/hakux-work/scoreboard/<label>` and regenerates the repo's
  SCOREBOARD.md over every live column.
- A fixture whose void rows all carry `differing = 0` cannot test the
  structural-px leg; give one a number.
