# #31 on silicon, fourth run: `ClipF` at `clip_left` 300, `clip_top` 8 (the `flatTop` clause), registered before the run

**Status: PRE-REGISTERED.** This file was committed and pushed before the XBE ran
anywhere, including the emulator dry run.

The host routed this capture to lane.xbox on #112 (item C, 14:21:56Z). #31 is
`blocked_on` it in the tracker. The question comes from
`docs/lanes/wbuf31fix/NOTES.md`, section "Weakest part: `flatTop`".

## The question

Master's W-buffer top-cut rule (#222, `3d3a646f8e`) is anchor mode `sel` in
`wbuf_anchor_recover.py`. It anchors a triangle's slope offset on the 4-grid at
phase 2, with one exception. When the window clip's own top edge cuts a
flat-topped triangle, and that edge lies on the 8-row grid, it keeps the 2x2
quad snap. This exception is the `flatTop` clause.

On every capture that exists, `flatTop` is interchangeable with
`span_starts_at_clip`, `B_quad_covered_at_c` and `second_of_quad`. At
`clip_left` 300, `clip_top` 8, the first triangle's first covered span starts
at the clip, and the rivals disagree there.

## What runs

- nxdk_pgraph_tests branch `hakux/wbuf31-clipf300`, commit `d504bad`. This is
  `da77078` (the clip_top 8/12/16/64 run, PR #226) plus one variant: loop
  index 9 gives `clip_left` 300 at `clip_top` 8. The patch is
  `wbuf31_clipf300.patch`, against `da77078`. The NOTES call this file
  `wbuf31_clipf_phase.patch`; the file actually folded is
  `wbuf31_clipf_t0.patch`.
- Hashes: XBE sha256 `cd2956a882b3…`, ISO `97c306653dc7…`. Both are under
  `~/hakux-work/hardware/runs/2026-09-25-wbuf31-c300/`.
- Tests, all in `W buffering`:
  - `WBuf24D_FloorQuad_V1_ZB0_ZS0`
  - `WBuf24D_FloorQuad_V1_ZB0_ZS1`
  - the nine earlier `ClipF-150-*` variants
  - `WBuf24D_ClipF-300-008_V1_ZB0_ZS1`
- Order and settings:
  1. An emulator dry run on the Thor, through the dispatcher.
  2. Then the console, via `tools/xbox/pgraph_run.py`, with
     shutdown-on-completion off, network off, and the progress log on. The
     probe writes no registers.

## The prediction, from geometry alone

`score_clipf300.py --predict` reads no capture of the new variant. It runs the
tool's own `features()`, `anchor(..., "sel")` and `coverage()` over the
goldens plus the three silicon runs (clipf35, clipf04, t0).

| triangle | px | first covered row | quad snap | 4-grid | informative |
|---|---:|---:|---:|---:|---|
| t0 | 24,952 | 8 | **8** | **10** | yes |
| t1 | 126,348 | 34 | 34 | 34 | no (control) |

- **t0's literals:** `flat_top` True, `span_starts_at_clip` True,
  `B_quad_covered_at_c` True, `second_of_quad` False.
- **Master's `sel` rule** gives t0 row 8 (quad).
- **The tool's own `--selectors`** search finds 93 four-literal fits over the
  anchors silicon has given. At this t0, 57 of them vote grid (10) and 36 vote
  quad (8).

## Legs

- **T0 (the question).** Read t0's recovered anchor (`A_hw`, axis y) from
  `WBuf24D_ClipF-300-008_V1_ZB0_ZS1_ZB.png`. The tool classifies it as exact
  within 0.02.
  - **8 means quad.** Master's `flatTop` clause stands. The 57 grid-voting fits
    are refuted.
  - **10 means grid.** `span_starts_at_clip` beats `flatTop`. Master's rule is
    wrong at this geometry, and #31's fix needs a change. The 36 quad-voting
    fits, master's among them, are refuted.
  - **Any other value means neither.** Both rules are refuted for this
    triangle. It is reported that way, not rounded to the nearer value.
- **T1 (control).** t1 anchors at 34. If it does not, the model fails
  somewhere else, and T0 is not read.
- **C1 (instrument).** These captures must be bit-identical to the captures
  already on disk:
  - FloorQuad ZS0 and ZS1, and ClipF-150-032, 128 and 224, against the goldens;
  - ClipF-150-035 against the clipf35 run;
  - ClipF-150-004 against the clipf04 run;
  - ClipF-150-008, 012, 016 and 064 against the t0 run.

  A mismatch voids the run as a different build or state. It is not
  re-scored.
- **C2 (geometry).** The tool's `n` for ClipF-300-008 equals the coverage
  prediction exactly: t0 24,952 px, t1 126,348 px.
- **C3 (plane).** The tool's CONTROL (`floor(w)` against ZS0) shows 0 mismatches
  on the floor quad.
- **Dry run (safety only).** The Thor finishes without a crash or hang and
  writes all 12 captures. Its pixels are not scored.

Score with:

```
python3 docs/lanes/xbox/score_clipf300.py \
  --goldens <run>/console-run/console --goldens /home/justin/goldens/results \
  --goldens <clipf35>/console-run/console --goldens <clipf04>/console-run/console \
  --goldens <t0>/console-run/console
```

## Also in this branch

This branch also corrects `docs/testing/xbox-wbuf31-clipf-t0-2026-09-25.md`.
Its "75 four-literal fits" should read 93.

The cause was `score_clipf_t0.py`, which added PRIMS entries after the tool
had built `_QUADS` at import. Those captures' second triangles were scored with
`second_of_quad` False. Two checks confirm the fix:

- The old tool (`37192979a2`), run with the fix, gives 93.
- The pre-run 333 reproduces on master.

Both wrappers now add to `_QUADS`.
