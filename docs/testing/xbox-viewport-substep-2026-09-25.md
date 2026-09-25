# #112 item 1 on silicon: the sub-step threshold is truncation -- "9/16" is refuted

**Measured 2026-09-25 on the project console (GPU rev 163 / MCP rev 212)**
against [`docs/testing/predictions/2026-09-19-viewport-substep-threshold.md`](predictions/2026-09-19-viewport-substep-threshold.md)
(registered 2026-09-19, PR #179), with the run registered in
[`docs/lanes/xbox/viewport-substep-run.md`](../lanes/xbox/viewport-substep-run.md)
(`e14b332f36`) before either run.

## The answer

**T, truncation (θ = 1), this tree's model at `glsl/vsh.c:548`, holds on
silicon.** R ("the rounding threshold is 9/16") and R' (the same, exclusive)
are refuted: every capture lands in T's column of the registered table.

| id | offset | remainder | silicon | T | R | R' |
|---|---:|---:|---|---|---|---|
| D2 | +0.53515625 | 9/16 | LOW | LOW | HIGH | LOW |
| D3 | +0.5390625 | 5/8 | LOW | LOW | HIGH | HIGH |
| **D1** | +0.548828125 | 25/32 | **LOW** | **LOW** | HIGH | HIGH |
| D4 | +0.55859375 | 15/16 | LOW | LOW | HIGH | HIGH |
| D5 | -0.451171875 | 25/32 | first covered n-1 | n-1 | n | n |
| D6 | +1.548828125 | 25/32 | n+1 | n+1 | n+2 | n+2 |
| C1 | +0.234375 | 3/4 | unmoved | unmoved | unmoved | unmoved |

Read the way the prediction asked, with no arithmetic: **silicon D1's four
fixed-function extents are exactly silicon `+17/32`'s** (`q1 x[220..319]
y[140..239]`, `q3 x[420..519]`, `q4 x[120..219] y[240..339]`, `q6 x[320..419]`),
not our `+9/16`'s. D4 at 15/16 is still LOW, so θ > 15/16.

**And the emulator agrees exactly.** All seven new captures are
**bit-identical** between silicon and hakuX (the Thor, APK `bb993fc18566`,
master `ec1b67a92d`). The rounding model is right across the whole window.
#49's two captures stay the only Viewport residual, and a threshold cannot be
their cause; this is consistent with #49's attribution to the fixed-function
transform one step upstream.

## Why it can be trusted

| check | result |
|---|---|
| validity: the twelve existing offsets on this console | **12 of 12 bit-identical to their goldens**, including #49's `+9/16` HIGH/LOW split |
| E1: our renderer puts the seven in T's column | holds: D1-D4 equal our `+17/32`, D5 one pixel left/up, D6 one right/down, C1 unmoved |
| E2: the disc programs `VPOFF` as registered | holds: our D1 equals our `+17/32` and differs from our `+9/16`. The registration made the console run conditional on this |
| E3: the twelve unchanged by adding seven | holds: 10 exact, and #49's two at 698 px each, as before |
| names | the suite's `%.03f` spellings came out as registered (`0.549`, `0.535`, `0.539`, `0.559`, `-0.451`, `1.549`, `0.234`) |

## How it was run

Tests tree `6743b6a` + [`viewport_substep.patch`](../lanes/xbox/viewport_substep.patch)
(`hakux/viewport-substep` @ `dc9e79bf0f`); XBE sha256 `ede1b033…8732ac`. The
emulator ran first, on the Thor through the dispatcher
(`1790320248-xbox-viewport-dryrun-194063`, 19 captures). The console ran next,
via `tools/xbox/pgraph_run.py` to `E:\Apps\PgraphViewport\` (19 tests, 52 s,
back at the dashboard). It was read with `docs/lanes/xbox/score_viewport.py`,
which extends `probe_viewport_ff_extents.py`'s sweep at runtime. Captures stay
on the host under `~/hakux-work/hardware/runs/2026-09-25-viewport/`.
