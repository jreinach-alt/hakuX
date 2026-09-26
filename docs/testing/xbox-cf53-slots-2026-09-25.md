# #53: the lit vertex-program quads read #41's six slots

**Analysis of existing silicon captures, 2026-09-25; no new console run.** The
inputs are the published goldens of `Specular` and `Specular_back`, and the
project console's own captures of the same tests (PR #340), which are
byte-identical to them.

**In short:**
- **The mechanism.** #53's "association" defect is the six-slot carry
  measured for #41 in PR #346. Under a vertex program with `LIGHTING_ENABLE`
  set, each lit vertex takes the **fixed-function lighting result held in one
  of six slots**. The slots hold the results of the **preceding FF draw's last
  six vertices**, not the vertex's own.
- **Every lit quad fits.** In both suites, all eight lit quads' corner codes
  are windows of the slot word predicted from `ControlFlags_FF`, read four
  consecutive slots per quad.
- **The step is regular.** Each quad's window start steps by a constant +4
  (≡ −2) per quad draw within a row: one slot per vertex of a four-vertex
  draw.

## The method

[`cf53_slots.py`](../lanes/xbox/cf53_slots.py) reads the eight lit diffuse
quads (rows 1 and 3) of each suite's `ControlFlags_VS`:
- **Corner values:** red at UL, UR, LR and LL, from a plane fit per triangle
  split on the UL–LR diagonal.
- **H/L codes:** each corner is classed H or L at the midpoint of
  `ControlFlags_FF`'s two corner levels. No value lies near the midpoint.
- **The slot word is predicted, not fitted.** It is the H/L pattern of
  `ControlFlags_FF`'s final two quads, read as a vertex stream, with the last
  six taken. `ControlFlags_FF` runs immediately before `ControlFlags_VS`.

## The result

| suite | predicted word | lit quads' codes (draw index, code, window start) | step within rows |
|---|---|---|---|
| `Specular` | `LHHLLH` | (4 LLHL 3) (5 HHLL 1) (6 HLHH 5) (7 LLHL 3) · (12 LHLH 4) (13 HLLH 2) (14 LHHL 0) (15 LHLH 4) | +4, +4 |
| `Specular_back` | `HLLHHL` | (4 HLHL 4) (5 LHHL 2) (6 HLLH 0) (7 HLHL 4) · (12 LHLL 5) (13 HHLH 3) (14 LLHH 1) (15 LHLL 5) | +4, +4 |

- **Every one of the 16 codes is a window of its suite's predicted word.**
  `Specular_back`'s word is `Specular`'s inverted, because back lighting
  swaps the two levels.
- **The codes are not the quads' own normals.** Each FF quad reads HLLH (or
  LHHL in `Specular_back`), its own normals. The VS quads show six distinct
  codes. That is #53's non-permutation, and its "five of six shared, the quad
  each attaches to permuted": the two suites read the same windows at phases
  one apart.
- **The step and phases:**
  - Within each lit row, the window start steps +4 (mod 6) per quad in both
    suites.
  - Row 1 to row 3 adds the same extra −1 in both suites. That is not
    explained.
  - `Specular_back`'s phase is `Specular`'s + 1 throughout.
- **Chance.** Random codes would all fall in the six windows with probability
  (6/16)^8 ≈ 4 × 10^-4 per suite, before the constant-step condition is
  applied.

**The tool was mutation-tested** on three cases, and each fails:
- one quad forced to a non-window code;
- the lit quads shuffled, which still passes the windows but loses the
  constant step;
- the FF image in place of the VS one, which passes the windows but has
  step 0.

It also passes on the console's own captures.

## What it changes for #53

- **#53 is modellable.** The "association" is not a rule over the quad's own
  vertices. It is the stale FF lighting result in the slot each vertex reads,
  the same mechanism hakuX already models in part for #41's radial fog (as one
  scalar).
- **The proposed test would be blind.** #53's blocker suggested a quad with
  four distinct light terms, but a lit vertex-program quad's own normals do not
  enter its colour. The discriminating test is PR #346's design applied to
  lighting:
  - a fixed-function priming draw whose final vertices carry four distinct
    lighting results;
  - then lit vertex-program quads.
  - That names each slot's source vertex directly.
- **Not settled by this analysis:**
  - what the row-to-row shift is;
  - the absolute phase;
  - why a single long QUADS draw (#41's scene) advanced differently from one
    quad per draw here.

## Files

- **The analysis:** [`cf53_slots.py`](../lanes/xbox/cf53_slots.py).
  - It runs on the goldens by default.
  - `--root` takes a console capture set laid out like the goldens.
