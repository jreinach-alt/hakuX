# lane goldencorr287: #287, the TexFmt_R6G5B5 golden is the outlier

Status: **blocked on two grants** (board: `docs/testing/golden_overrides/**`;
lane.toolsmith: a lookup hook in score_sweep.py + dispatcher.sh). Everything
this lane may do is done: the claim is verified, the fix is proven offline, and
both requests are filed. See "Blocked on" below.

## 1. The claim, re-derived (whole frame, every pixel)

`pairwise.py` over seven captures of `Texture_format::TexFmt_R6G5B5`:

| capture | what | vs golden | vs console K |
|---|---|---:|---:|
| K | console, `hardware/runs/2026-09-19-calib/full/out/run1` | 134,902 px | 0 |
| detA | console, `hardware/runs/2026-09-20-det/detA` | 134,902 | 0 |
| region200 | console, `hardware/runs/2026-09-25-region200/console-run` | 134,902 | 0 |
| F | ours, scored run `1790347539-xbox-region200-dryrun` (thor, a7b9d28e6b84) | 134,902 | 0 |
| H | ours, scored run `z-c866527e03-081-Texture_format` (09-13) | 134,902 | 0 |
| desktop | ours, `desktop/out_texfmt` | 134,902 | 0 |

The three pairwise diffs the brief asks for: **ours vs console = 0 px (byte-identical);
ours vs golden = 134,902 px (43.91%, max RGB 223, max A 254, bbox x 50-504, y 55-424);
console vs golden = 134,902 px, the same pixels.** The golden is the outlier.
Why: its label prints `C: 0` where ours and the console print `C: 1`, and `C`
is the suite's `require_conversion`, which selects a different upload path
(docs/investigations/r6g5b5-golden-packing.md: the golden's texels are
RGB565-packed). So the golden came from a different build of the suite. Neither
silicon nor the renderer explains it.

## 2. Mechanism: the existing one cannot do it, and none exists for goldens

- **`label-differs` (the documented void for this very test, AGENTS.md) does
  not fire.** The `C:` line is at rows 100-115, and `score_sweep.py` `LABEL_ROWS = 64`
  covers only the first two of the seven label lines (N:, F:). The band white-mismatch
  is 0 px and the body mismatch is 40 px (x 50-56, y 100-115, the `0`/`1` glyph),
  so every scored run files the row as `white-content`, a real residual.
- **Even firing it would not remove the pixels.** `label-differs` is in
  `SCORED_STATUSES` (score_sweep, ab_compare, dispatcher), and
  `scoreboard.py:summarise` sums `differing` for every row whatever its status.
  A widened band would also move other rows' status for the same 64-row
  reason the band was narrowed (the 2D_BorderTex_SZ swatch history at
  score_sweep.py:204).
- **Goldens are an upstream checkout** (`/home/justin/goldens`,
  abaire/nxdk_pgraph_tests_golden_results @ 6e159f1), outside the repo. Editing
  the file there would be unversioned and invisible to every other host. That
  was rejected.
- **Chosen: a committed, suite/test-keyed override tree** in the repo, holding the
  console capture, read by score_sweep when passed `--golden-overrides`. This
  makes R6G5B5 score **exact** against a reference that is real hardware
  running our disc, and it stays a live regression guard, where a void would
  blind the row. It is keyed on suite/test because
  `Texture_render_target::TexFmt_R6G5B5` shares the name and has its own golden
  (exact in H, 81,225 px in the 09-08 baseline). A name-keyed override would
  compare it with the Texture_format console frame (checked: unmoved below).

The dispatcher detail that shapes the patch: workers run score_sweep from the
`$SNAP` copy, which holds only `SCRIPT_DEPS`. An override dir resolved relative
to `__file__` would not exist on a worker, so the dispatcher must pass the tree
path explicitly. Full patch text: `request-toolsmith.md`.

## 3. Falsifier (offline; no arm can see this)

The captures do not change; only the reference and the scorer do. An arm is
scored by the host's snapshot scorer, not by either ref's, so both arms would
score identically. So `Prediction: none: no arm`, and the falsifier is a re-score
of real sweep captures: stock `score_sweep.py` against upstream goldens (A) vs
the scratch patched scorer with the one override (B), `falsify.sh`.

Re-scored sweeps of scored run `z-c866527e03` (every row in both suites, 40 each):

| sweep | rows | A sum px | B sum px | rows moved A -> B |
|---|---:|---:|---:|---|
| 081-Texture_format | 40 | 134,902 | 0 | `TexFmt_R6G5B5`: white-content 134,902 -> ok 0 |
| repeat 081-Texture_format | 40 | 134,902 | 0 | the same, only that row |
| 085-Texture_render_target | 40 | 1,473 | 1,473 | none (its `TexFmt_R6G5B5` stays ok 0) |

R6G5B5 moves to exact, and no other row moves in status or pixel count,
including the same-named render-target row.

What this tests and what it cannot: once the override is the console capture,
R6G5B5 going exact is forced for any capture byte-identical to K. The
non-tautological evidence is in section 1: three console runs on three dates,
and ours on two devices and the desktop across 12 days, all agree byte for
byte. The re-score's real job is the must-not-move leg: every other row in the
same suites, including the same-named render-target row, stays put.

## 4. Siblings (goldens where console == ours != golden)

One query (`siblings.py`): console K differs from its golden on only 5 of 3,379
captures, so any sibling is one of those 5. Compared against our H sweep:

| capture | console vs golden | ours vs console | ours vs golden | sibling |
|---|---:|---:|---:|---|
| Texture_format::TexFmt_R6G5B5 | 134,902 | **0** | 134,902 | **yes (this issue)** |
| Attrib_float::-NaNs_NaNs | 60 | 14,637 | 14,697 | no, emulator defect |
| 3D_primitive::LineLoop-inlinearrays-ls | 4,546 | 4,675 | 4,675 | no |
| Color_zeta_overlap::ZetaIntoColor | 19,994 | 102,255 | 102,255 | no (silicon nondeterministic) |
| Color_zeta_overlap::ColorIntoZeta_ZB | 10,982 | 131,495 | 131,495 | no (silicon nondeterministic) |

**No siblings.** Limit: this only covers suites K ran (3,379 captures). A
golden that is wrong in a suite K did not capture is not visible to this query.

## Blocked on

1. Board: grant `docs/testing/golden_overrides/**` (request-board.md, filed in
   `$DISPATCH_DIR/board-requests/goldencorr287.md`).
2. lane.toolsmith: the `--golden-overrides` hook, score_sweep.py line 152 (+ args
   threading at 317) and dispatcher.sh line 1039 (request-toolsmith.md,
   delivered with `deliver.sh send toolsmith 287`).

Either order is safe: the data moves nothing until the hook reads it, and the
hook moves nothing until the data exists.

## Why attempt 1 did not finish (written on attempt 2, 2026-09-25)

Attempt 1 ended with the PR in draft, the falsifier table still a placeholder
(the TSVs were on disk in the untracked `scratch/`, never summarised), the PR
body still saying `Prediction: pending`, nothing posted on #287, and the
toolsmith request drafted but never sent (#287 carried no delivery comment).
The board request was filed. Attempt 2 summarised the TSVs above, sent the
toolsmith request, answered #287, and marked the PR ready as blocked on the
two grants. Nothing was re-measured.

## Do not repeat

- Do not widen `LABEL_ROWS` to catch this: it moves other rows, and a void is
  still summed by scoreboard.py.
- Do not edit `/home/justin/goldens`: it is an upstream checkout, off every ref.
- Do not key an override on the test name alone: Texture_render_target has
  a `TexFmt_R6G5B5` too.
