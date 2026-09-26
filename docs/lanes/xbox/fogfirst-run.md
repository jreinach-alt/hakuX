# The first planar-fog test of a console session: why was its fog coordinate halved?

**Status: PRE-REGISTERED.** This file and its scorer were committed and pushed
before the emulator dry run and before any console session below.

## The observation this tests

In the #112 item 2 follow-up (PR #346,
`docs/testing/xbox-fogprime-repeat-2026-09-25.md`), the session's first test,
`Fog gen::FogGen_FF-exp-abs_planar`, rendered every drawn pixel with **half**
the fog coordinate its golden has. The ratio was 0.500 across f8 20–255.

- **The same capture matches its golden** when it is not first: PR #340's full
  run, on this console.
- **The next test in that session matches its golden.**
- **Run 1's first test** (`FogGen_VS-exp-radial`) showed no halving.

That is one observation, and there are four candidate explanations:

| | the halving hits |
|---|---|
| **Hα** | the first draw after the XBE starts, whatever it is. It only shows when that draw uses planar fog |
| **Hβ** | the first planar-fog draw after the XBE starts, whatever came before it |
| **Hγ** | `FogGen_FF-exp-abs_planar` (ABS_PLANAR) as the first test, and not plain PLANAR |
| **Hδ** | nothing reproducible: a one-off |

## What runs

- **The XBE:** PR #346's binary, sha256 `5dd5b6cd10d8…`, unchanged.
- **The sessions:** three console sessions, each a fresh launch from the
  dashboard. The tests run in the order shown (suite registration order, then
  name order):

| session | test 1 | test 2 |
|---|---|---|
| **A** | `Fog gen::FogGen_FF-exp-abs_planar` | `Fog gen::FogGen_FF-exp-planar` |
| **P** | `Fog gen::FogGen_FF-exp-planar` | `Fog gen::FogGen_FF-exp2-planar` |
| **N** | `Alpha func::AlphaFuncAlways_Disabled` | `Fog gen::FogGen_FF-exp-abs_planar` |

- **Settings:** shutdown-on-completion off, networking off, progress log on.
  They run in the order A, P, N.
- **The emulator dry run:** one dispatcher request carrying the union of the
  four tests. It runs every test the three configs select on this XBE; each
  session then selects a subset. The sessions only change the selection, so
  one dry run covers them.

## Predictions

The scorer is [`fogfirst_score.py`](fogfirst_score.py). It calls a capture
`golden`, `halved` (the coordinate ratio is 0.49–0.51 in every f8 band) or
`other`. It was mutation-tested before this commit on five synthetic cases,
one of them halved in every band but the middle one, and on run 2's real data
(59 golden, 1 halved).

| capture | Hα | Hβ | Hγ | Hδ |
|---|---|---|---|---|
| A1 `exp-abs_planar` | halved | halved | halved | golden |
| A2 `exp-planar` | golden | golden | golden | golden |
| P1 `exp-planar` | halved | halved | **golden** | golden |
| P2 `exp2-planar` | golden | golden | golden | golden |
| N1 `AlphaFuncAlways_Disabled` | golden | golden | golden | golden |
| N2 `exp-abs_planar` | **golden** | **halved** | golden | golden |

**How the table decides:**
- A1 separates Hδ from the rest.
- P1 separates Hγ from Hα and Hβ.
- N2 separates Hα from Hβ.

**The must-not-move legs**, which no hypothesis moves: A2, P2 and N1 are
bit-identical to their goldens. Each fails in a world where the halving
lasts beyond the first planar draw, or where a session's non-first tests are
affected. Either would void the "first draw" reading altogether.

**Any row outside the table is reported as X**, with its values, and not fitted
to the nearest column.

**hakuX** (the dry run): each Fog gen capture is bit-identical to the same
capture in the fogprime2 dry run (`1790391241-xbox-fogprime2-dry-2157566`,
same ref and APK). hakuX models no session-start state.

**Void:** a session that does not end "Testing completed normally" is void and
is not relaunched.
