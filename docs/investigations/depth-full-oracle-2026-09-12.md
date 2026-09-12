# The depth oracle is five times larger than we were using, and it decomposes

Measured 2026-09-12, APK `64c01cc70067`. 784 captures, 392 tests.

## Recovering the oracle

Our sweeps run **72** `Depth buffer` tests. The goldens hold **784** entries —
392 tests, each writing a colour and a `_ZB` depth capture. The missing 320
were not a disc we needed to upgrade to: their goldens date from **February
2025**, older than our disc, and those tests were **retired upstream** when the
suite was refactored.

Two wrong turns worth recording before the result, because each cost something:

1. I read the disc's `sample-config.json` — which lists all 392 and marks none
   skipped — as proof the XBE could run them. A config naming all 392
   explicitly ran the same 72. **That file is byte-identical between our disc
   and a 2025 one**, so it is a stale artefact in both and tells you nothing
   about either XBE. Only a progress log from a real run does.
2. I then assumed the goldens must come from a *newer* suite. They come from an
   older one. Our disc is byte-for-byte the latest published release
   (2026-09-01); the tests were removed, not added.

The fix is the **2025-03-14 release** (`v2025-03-14_04-46-00-647229543`). Its
XBE still generates the retired names — it carries the `%s_%s_%s_%s` format
string for `Blend tests`' individual factor triples where the current disc
carries `#spot_`. Run against it, `Depth buffer` produces **784 captures in
338 seconds, exactly matching the golden count.**

This is additive: it recovers silicon truth the project already owns goldens
for and cannot otherwise reproduce. It changes no existing baseline.

## What the full oracle says

| | 72-test subset | full 392 |
|---|---|---|
| bit-identical | 28 / 144 (19.4%) | **108 / 784 (13.8%)** |
| within ±1 | 34 | **244** |
| differ | 80 | **430** |
| pixels differing | 3.73% | 2.17% |

The subset was flattering on the exact rate. More usefully, 430 differing
captures is 5.4× the evidence, and it splits three ways:

| format | Z mode | capture | exact | within ±1 |
|---|---|---|---:|---:|
| `z16` | fixed | **depth** | **98 / 98** | — |
| `z16` | fixed | colour | 2 / 98 | 14 |
| `z16` | float | depth | 0 / 98 | 0 |
| `z16` | float | colour | 0 / 98 | 52 |
| `z24` | fixed | **depth** | 2 / 98 | **96** |
| `z24` | fixed | colour | 2 / 98 | 14 |
| `z24` | float | depth | 2 / 98 | 0 |
| `z24` | float | colour | 2 / 98 | 68 |

Clearing the buffer first has **no effect whatever** — 54 exact either way, to
the capture. So none of this is initialisation.

### Three separable defects

**1. `z16` fixed-point depth is perfect.** 98 of 98 bit-identical across all 49
mask values. The 16-bit fixed write path is correct and should be left alone.

**2. `z24` fixed-point depth is one unit high.** 96 of 98 differ by exactly one
step, and the direction is consistent: our value is higher on 74,212 subpixels
against lower on 36,917, where the "lower" cases are the byte carry of a +1
(a channel reading 0 where hardware reads 255, hence −255). Only **one** mask
is exact, `M00000f`, the smallest value in the sweep — which is the signature of
a **scale divisor**, not a rounding choice: the error vanishes near zero and is
one unit everywhere else. That is the same defect
`depth-readback-scale.md` describes as a unorm grid half a unit out of phase,
now with 96 captures constraining it instead of a handful.

**3. Float Z is structurally wrong, and the colour path is wrong independently
of depth.** Float depth captures are 0/98 and 2/98 exact with **nothing within
one step**, so it is not precision. And the colour capture is ~2% exact in
*every* cell — including the one where the depth buffer is 100% bit-identical.
Whatever derives colour from depth in these tests diverges on its own, and
fixing the depth values will not move it.

## What this changes

Issue #16 is filed as "depth surface readback converts incorrectly". On the full
oracle that is three issues: a correct path (`z16` fixed), a one-unit scale
error with 96 captures pinning it (`z24` fixed), and a structural float path.
Only the middle one is a readback conversion.

Every depth number either lane has quoted came from the 72-test subset. They
are not wrong, but they are drawn from a ninth of the masks, and the split above
was not visible at that resolution — 98 captures per cell is what makes
"98/98 exact" and "96/98 one step" claims rather than impressions.
