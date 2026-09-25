# #31 on silicon: `ClipF` at `clip_top = 35` anchors at 34 -- the 4-grid at phase 2

**Measured 2026-09-25 on the project console (NV2A, GPU rev 163 / MCP rev 212,
V1.1).** Registered beforehand in
[`docs/lanes/xbox/wbuf31-clipf35-prediction.md`](../lanes/xbox/wbuf31-clipf35-prediction.md);
the verdict table itself dates from 2026-09-19,
[`docs/investigations/wbuffer-31-clipf-phase.md`](../investigations/wbuffer-31-clipf-phase.md).

## The answer

`ClipF-150-035`'s second triangle recovers an anchor of **34.000** (interval
33.9998, miss 1.9e-4 -- the same interval `clip_top = 32` gives). By the
registered table that is `4*floor(ct/4)+2`: **the absolute 4-row grid at
phase 2**, the rule `TriH` already pins on all 24 of its triangles.

| rule | at 32 / 128 / 224 | at 35 | on silicon |
|---|---|---:|---|
| `4*floor(ct/4)+2`, the 4-grid at phase 2 | 34 / 130 / 226 | **34** | **fits** |
| `ct+2`, recorded as measured on #31 | 34 / 130 / 226 | 37 | refuted |
| `2*floor(ct/2)+2`, the 2x2-quad snap plus 2 | 34 / 130 / 226 | 36 | refuted |
| phase variants of the 2- and 4-grids | 34 / 130 / 226 | 38 | refuted |
| the shipped rule, the first covered row snapped to the quad | 32 / 128 / 224 | 34 | refuted at 32, 128, 224 already |

So `ClipF`'s second triangle is not an exception to `TriH`'s grid, as #31
recorded it. "`clip_top + 2`" was the 4-grid seen only through `clip_top`
values that are multiples of 32, where the two are the same number.

**What it does not settle.** Scored with the registered tool,
`wbuf_clip_phase_choice.py`, over the goldens plus this capture, 48 of the
family's rules fit all four observations. One is on a grid of 4 or finer
(this one). The other 47 are on grids of 8, 16 and 32, fit only because every
earlier `clip_top` was a multiple of 32, and have no mechanism behind them --
`TriH` measures a 4-grid directly, on 24 triangles. A second variant would
exclude them on `ClipF` itself: the same tool ranks `clip_top` 36-39 among
the best, where the 4-grid predicts 38.

**The first triangle is a separate question and stays one.** At `clip_top =
32` t0 anchors at 32 (the quad snap) while t1 anchors at 34, so the two
triangles of one planar quad anchor differently. At 35 both rules give t0 34,
and silicon gives 34.001, so this capture neither widens nor narrows that
split.

## Why the capture can be trusted

| check | result |
|---|---|
| V0: this console anchors like the 1.0 silicon the goldens came from | `wbuf_anchor_recover.py` over the console's 530 `W_buffering` calibration captures (2026-09-19) prints output **byte-identical** to the same tool over the goldens, all 66 anchors |
| C1: the known anchors come back | `ClipF` 032 t0 **32.001**, t1 **34.000**; 128 t1 **130.001**; 224 t1 **226.001**, offset intervals identical to the goldens'. All ten captures of the existing tests, colour and depth, are **bit-identical** to their goldens |
| C2: the new variant is the geometry it was designed to be | t0 **15,773 px**, t1 **189,047 px**, exactly the counts registered from geometry alone |
| C3: the plane control | `FloorQuad` `floor(w)` vs the run's own `ZS0`: **0** mismatches over 221,970 px |

The `-035` pair (colour and depth) is a new silicon capture of a test no
golden set contains.

## The emulator, for comparison

The same XBE ran first on the Thor through the dispatcher
(`1790317302-xbox-wbuf31-dryrun-3980114`, APK `bb993fc18566`, master
`ec1b67a92d`), as the lockup safeguard: it completed normally and wrote all
twelve captures. Its own recovered offset at 35 sits on anchor 34 too,
because the shipped quad snap and the 4-grid coincide at 35. At 32, 128 and
224 they do not, and that two-row miss is #31's `ClipF` residual.

## How it was run

| | |
|---|---|
| tests tree | `abaire/nxdk_pgraph_tests` `6743b6a` + `docs/testing/wbuf31_clipf_phase.patch`, unchanged (`hakux/wbuf31-clipf35` @ `a39bc60fc2`) |
| XBE / ISO sha256 | `d740024a…17973e` / `1b6bcc21…80abc8` (in full in the prediction file) |
| runner | `tools/xbox/pgraph_run.py` (branch `lane/xbox-runner`): preflight at the dashboard, upload to `E:\Apps\PgraphWbuf31\`, `SITE EXEC`, completion only on "Testing completed normally" |
| config | `W buffering`, six named tests, shutdown-on-completion **off**, networking off |
| wall clock | `SITE EXEC` at 23:26:01 PDT on 09-24; back at the dashboard with the log complete at 23:26:55; each test well under a second |

Captures, the log and the runner's `PROVENANCE.json` stay on the host under
`~/hakux-work/hardware/runs/2026-09-25-wbuf31-clipf35/`. To re-score:

```sh
python3 docs/testing/wbuf_anchor_recover.py \
    --goldens ~/hakux-work/hardware/runs/2026-09-25-wbuf31-clipf35/console-run/console
```
