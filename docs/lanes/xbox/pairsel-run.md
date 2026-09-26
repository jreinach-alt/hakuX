# #38 mechanism 2: which draws does silicon's pixel-pair quantisation select?

**Status: PRE-REGISTERED.** This file, [`pairsel_score.py`](pairsel_score.py),
[`pairsel_synth.py`](pairsel_synth.py) and the tests patch
[`pairsel38.patch`](pairsel38.patch) were committed and pushed before the
emulator dry run and before the console run. The branch was cut fresh from
`origin/master` (`aaf01a1cef`).

## Why

#38's mechanism 2 is measured on silicon: the fragment colour is held
constant across an even-aligned pixel pair and evaluated at the pair's right
edge (s = 2·floor(x/2) + 2). It is not implemented, because nothing on disk
says which draws it selects. `nv2a_issues.toml` `[issue.38]` records the tie,
and `docs/investigations/issue38-mech2-blocker-audit.md` §5 names the capture
that breaks it:

> the `Alpha_func` band at its full 512 px submitted through `SET_VERTEX3F`,
> or equivalently the same band narrowed to 128 px on `SET_VERTEX4F` — either
> separates the two survivors alone

The two survivors are immediate mode with w = 1, combined with either width
≥ 512 px or `SET_VERTEX4F`. They are exactly confounded on disk. Every paired
capture is wide and 4F, and every unpaired class member is narrow and 3F.

## What runs

- **The XBE.** nxdk_pgraph_tests `6743b6a` plus
  [`pairsel38.patch`](pairsel38.patch) (tests branch `hakux/pair-selector38`
  `970a6db`), a `Pair selector` suite registered after `AlphaFuncTests`.
  - XBE sha256 `37b421e90349…`, ISO `d94ed2662dc4…`.
- **What each test is.** Every test is `Alpha func`'s
  `AlphaFuncAlways_Disabled`: the same clear, blend, passthrough shader and
  diffuse ramps. The one change is its three gradient bands, drawn W px wide
  and centred, with their vertices submitted by `SET_VERTEX4F` (as `Alpha func`
  does) or `SET_VERTEX3F`. The full-width white rectangle is unchanged, so
  `PairSel_W512_V4F` draws `Alpha func`'s image.
  - Widths are 512, 384, 256 and 128 px, each in both registers: 8 tests.
  - It uses pushbuffer methods only.
- **The session.** `Alpha func::AlphaFuncAlways_Disabled` runs first, as the
  first-test rule and as K1's reference, then the 8. Shutdown on completion is
  off, networking is off, and the progress log is on.
- **The order.** A Thor dry run goes through the dispatcher first. Then the
  console runs through `tools/xbox/pgraph_run.py`.

## Legs

The judge is [`pairsel_score.py`](pairsel_score.py). It reads each band with
the tracker's own instrument, `pair_fill_blocks_38.pair_stats`: E − O over
`pair_census_38`'s qualifying mask, in framebuffer parity. It cross-checks
with `xparity`, the x-step parity skew. It reads the red band (rows 168-210,
clear of `Alpha func`'s text) and the blue band (rows 216-274), 2 px inside
each band's ends.
- A band is **paired** if E − O > 0.5 on both bands, and **unpaired** if
  |E − O| < 0.1 on both.
- On the `Alpha func` golden this reads +0.9944 (red) and +0.9961 (blue),
  with skew 1.000.

**Instrument legs.**
- **K1:** `PairSel_W512_V4F` is pixel-identical to the same run's
  `AlphaFuncAlways_Disabled` over rows 168-372.
- **P:** `PairSel_W512_V4F` is paired. The known positive must reproduce.
- **N:** `PairSel_W128_V3F` is unpaired. The narrow-3F negative from
  `Line_width/Fill_*` must reproduce.

**The question (S), with four rivals and no prediction**, read from
`W512_V3F` and `W128_V4F`:

| `W512_V3F` | `W128_V4F` | selector |
|---|---|---|
| paired | unpaired | width alone |
| unpaired | paired | `SET_VERTEX4F` alone |
| unpaired | unpaired | both (width ≥ 512 and 4F) |
| paired | paired | either |

**T (reported):** the 384 and 256 px cells in both registers. If width is part
of the selector, they bracket its threshold.

**Void, not refuted.** If P or N fails on silicon, the run says nothing about
the selector.

**Mutation tests of the judge**, on seven synthetic worlds from
[`pairsel_synth.py`](pairsel_synth.py), run before this commit:
- The worlds width, register, both and either each return their own selector
  and exit 0.
- A never-pairs world (hakuX's behaviour) fails P and exits 1.
- A K1 reference differing in one pixel fails K1.
- A missing capture exits 2 (void).

**hakuX's expected row, from the dry run.** hakuX has no mechanism 2, so every
cell reads unpaired and P fails. K1 and N must hold there.

## What each answer means for a fix

The quantisation is fitted on the `Alpha_func` band: 0 of 512 wrong on both
bands, with two out-of-sample confirmations. It applies to immediate-mode,
w = 1 draws, plus whichever condition S names.
- **Width.** T gives the threshold between 128 and 512 px.
- **Register.** It is a per-vertex submission property.

Either way the fix is a rule on the draw, and the tracker's populations say how
many captures it reaches.
