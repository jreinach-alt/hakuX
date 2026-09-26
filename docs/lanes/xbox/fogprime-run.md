# #112 item 2 / #41: the radial-fog priming run, registered before it

**Status: PRE-REGISTERED.** This file was committed and pushed before the XBE
ran anywhere.

**Result (2026-09-25):** see
[`xbox-fogprime-2026-09-25.md`](../../testing/xbox-fogprime-2026-09-25.md).
The outcome is X: silicon carries six per-vertex slots from the priming
draw's last two quads. **V3 as registered below could not hold:** the six
radial tests ran with no FF radial draw before them, and their goldens
need Fog gen's FF tests first. That is my error; the results doc covers
it.

It binds a run to
[`docs/testing/predictions/2026-09-19-fog-radial-carryover-priming.md`](../../testing/predictions/2026-09-19-fog-radial-carryover-priming.md)
(PR #179), which registered the models (S, S-first, T, H, X), the windows, the
must-move and must-not-move legs, and the gates V0–V3 and E1–E3. Nothing in
it is changed here.

## What runs

- **The XBE.** nxdk_pgraph_tests `6743b6a` plus a new `Fog radial priming`
  suite: `hakux/fog-radial-priming` `a65ac0b`,
  [`fogprime.patch`](fogprime.patch), sha256 `5dd5b6cd10d8…`.
- **The scene.** `FogGenTests`' scene and vertex program, copied line for
  line. It uses radial exp fog at bias 1.5 and multiplier −0.000875. The 374
  quads are computed first and then drawn in rotated order `r, r+1, …`.
- **The tests**, which run in this order by name:

| test | draws | rotation | label |
|---|---|---:|---|
| `A0far_FF` / `A0far_VS` | FF, then VS | 0 | row 0 |
| `A1mid_FF` / `A1mid_VS` | FF, then VS | 188 | row 0 |
| `A2near_FF` / `A2near_VS` | FF, then VS | 21 | row 0 |
| `A3farLabel_FF` / `A3farLabel_VS` | FF, then VS | 0 | **`pb_printat(15, 0)`, y = 400** |
| `A4near_FF` / `A4pad_VS` / `A4radial_VS` | FF, a programmable draw, then VS | 21 | row 0 |

- **V3's reference.** The six `Fog gen::FogGen_VS-*-radial` tests run in the
  same session.
- **R1, stated before the run.** pbkit draws label glyphs with `pb_fill`
  rectangles, so the label may never pass through the transform unit. A3
  then measures that as "T is empty", which the prediction already allows
  for.
- **Order.** An emulator dry run on a handheld comes first. That run *is*
  the prediction's E1–E3 companion, on hakuX. Then the console, via
  `pgraph_run.py`, with shutdown-on-completion off and the progress log on.
  The log is the record that the order held.

## Reading

- **The quantity.** The 8-bit fog factor over each VS capture's drawn
  region: blue where `red + blue == 255` and `green == 0`, 181,016 px expected.
- **The decisive comparison.** A0, A1 and A2 from one run at one multiplier.
  S and S-first predict three different values; H and T predict three
  identical ones.
- **The gates** are the prediction's own:
  - V0: A0 falls in 29.63–35.20.
  - V1: the FF captures are bit-identical outside the label rows, A3
    excepted.
  - V2: each VS capture shows a single colour over 181,016 px.
  - V3: the six radial captures reproduce their goldens.
