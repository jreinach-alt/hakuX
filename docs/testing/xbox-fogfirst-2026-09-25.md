# The first test after an XBE launches renders planar fog with half its fog coordinate

**Measured 2026-09-25 on the project console,** in three sessions. It was
registered beforehand in
[`docs/lanes/xbox/fogfirst-run.md`](../lanes/xbox/fogfirst-run.md)
(`bb2d0c4aef`, pushed before the dry run and the sessions). The host routed
it on #112 at 03:12Z.

**Result: Hα, on every row of the registered table.** The halving hits the
**first test after the XBE starts**, whatever that test is, and it shows when
that test uses planar fog. A non-fog test in front absorbs it. It is
reproducible bit for bit, and PLANAR and ABS_PLANAR show it identically.

## What ran

- **The XBE:** PR #346's binary, sha256 `5dd5b6cd10d8…`.
- **The sessions:** three, each a fresh launch from the dashboard. Each took
  50 s and logged "Testing completed normally" in the registered order.
- **The emulator dry run:** `1790392087-xbox-fogfirst-dry-2771385` on the Thor
  (hakuX `84a67b9cf8`, APK `a7b9d28e6b84`) ran the union of the four tests
  first. It completed with no crash signal.

## The table, as registered, with silicon's row

Classified by [`fogfirst_score.py`](../lanes/xbox/fogfirst_score.py):

| capture | Hα | Hβ | Hγ | Hδ | **silicon** |
|---|---|---|---|---|---|
| A1 `exp-abs_planar` (first) | halved | halved | halved | golden | **halved** (band ratios 0.502 0.500 0.500 0.505 0.495) |
| A2 `exp-planar` | golden | golden | golden | golden | **golden** |
| P1 `exp-planar` (first) | halved | halved | golden | golden | **halved** (0.502 0.500 0.500 0.505 0.495) |
| P2 `exp2-planar` | golden | golden | golden | golden | **golden** |
| N1 `AlphaFuncAlways_Disabled` (first) | golden | golden | golden | golden | **golden** |
| N2 `exp-abs_planar` (second) | golden | halved | golden | golden | **golden** |

- **Hδ (a one-off) is refuted by A1.** A1 is bit-identical to the follow-up
  run's first capture (PR #346).
- **Hγ (ABS_PLANAR only) is refuted by P1.** P1 and A1 differ only in their
  printed labels (542 px, rows 27–40), as their goldens do.
- **Hβ (the first planar-fog draw, whatever came before) is refuted by N2.**
- **The must-not-move legs** A2, P2 and N1 all held. The effect is confined
  to the first test.
- **hakuX leg:** hakuX does not show it. Its three Fog gen captures in the
  dry run are bit-identical to the fogprime2 dry run's. In that dry run
  `exp-abs_planar` ran first and was not halved.

## What this means for references

- **The rule is now narrower, and it has a remedy:** don't take a silicon
  reference from the **first test after an XBE launches**. Put a non-fog test
  first. Session N shows that a leading `Alpha func` test absorbs the effect.
- **The earlier sessions:** their first tests used no planar fog, so the
  halving could not have shown in them.
  - PR #340's first test, `Lighting normals::NoNormal`, and refs6743's,
    `Alpha func::AlphaFuncAlways_Disabled`, are bit-identical to their
    goldens.
  - Run 1's first test was a vertex-program radial one, which does not use
    the planar path.
- **What is not known:** whether the first test is wrong in some way that
  planar fog merely makes visible. It is visible here only through planar
  fog's coordinate, and a first test that uses neither fog nor the same
  quantity would not show it.
- **The mechanism is not identified.** The same draw sees exactly half the
  planar fog coordinate while its geometry is right: the drawn region is the
  same 181,016 px. That points at the planar path's own inputs rather than
  the transform to the screen. hakuX does not reproduce it in the same order.

## Files

- **The scorer:** [`fogfirst_score.py`](../lanes/xbox/fogfirst_score.py).
- **The captures:** on the host under
  `~/hakux-work/hardware/runs/2026-09-25-fogfirst/{A,P,N}/console-run/console/`.
