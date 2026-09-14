# #13: the wide-line extent fix, measured on silicon

**Arm run 2026-09-14. A = `e4ac96e2bd` (1789356489), B = `f485bc9035`
(1789356496), `Line width`, one run each, same device, same disc.**

Prediction: [`docs/testing/predictions/line-extent-phase-vk-arm.json`](../testing/predictions/line-extent-phase-vk-arm.json),
registered before either arm was queued and naming
[`line-extent-phase-exact.json`](../testing/predictions/line-extent-phase-exact.json)'s
sha256 rather than editing it.
Implementation: [`line-extent-phase.md`](line-extent-phase.md) is the rule;
this is what happened when it was drawn.

## The headline

| | arm A | arm B | registered |
|---|---:|---:|---:|
| agreement with the goldens' clean cuts, widths 6–48 | **47.8178%** | **99.5838%** | >= 99.60% |
| agreement, all widths (12,056 of them held out) | **67.5738%** | **99.6563%** | >= 99.65% |
| whole-capture ink mismatch, 48 non-void captures | **72,181 px** | **908 px** | <= 1,400 |
| suite differing pixels | 5.50% | 4.95% | not predicted |
| rows voided as `label-differs` | 19 of 61 | **0** | not predicted |

`ab_compare.py` judges the pair **PRE-REGISTERED** — arm B was queued naming
the prediction file and its content still hashes to the sha recorded then —
and scores it:

    better 59    worse 0    same 2    noise 0      (61 compared)
    differing     1,030,368 ->   927,371   (-102,997)
    structural      247,934 ->    94,984   (-152,950, -61.7%)

**No capture regressed.** Its VERDICT is nonetheless FAIL, on eleven
`must_not_move` checks that all moved *better*; that is my registration's
fault and is dealt with under L5 below.

`--vs-goldens` finds the clean cuts in the **goldens** and reads the same
scanline out of the arm, so it asks whether our render agrees with silicon and
not whether it agrees with the model. The patch cannot make it true by
construction, and the tool's own control — pointed at the goldens — reads
8,890 of 8,890.

## Verdict by leg

| leg | registered | measured | |
|---|---|---|---|
| V0 | arm A in [47.0%, 48.6%] | 47.8178% | **PASS** |
| V1 | device reports subPixelPrecisionBits >= 8 | **unreadable** | see below |
| L1 | >= 99.60%, widths 6–48 | 99.5838% | **FAIL by 2 cuts** |
| L2 | bits == 8 -> [99.60%, 99.85%] | 99.5838% | **FAIL**, and see below |
| L3 | >= 99.65%, all widths | 99.6563% | **PASS** |
| L4 | <= 1,400 px coverage | 908 px | **PASS** |
| L5 | 13 tripwires bit-identical | 11 moved, **0 worse** | see below |

## L1 failed by two cuts, and the reason was in my own table

8,853 of 8,890 against a bar of 8,891. The shortfall is not a near-miss of the
phase: every near-miss `line-extent-phase-exact.json` registered in advance is
far below this (closed tie-break 93.8133%, high-open 93.4758%, no truncation
98.1665%, 1/16 round 98.7627%, 1/8 truncate 99.1114%, 1/32 truncate 99.3251%,
perpendicular rectangle 53.6670%). It is the **quantisation mode of the
rasteriser**, and the value is one my own pre-registered simulation already
contained:

    docs/testing/line_extent_subpixel.py, 8 bits, bias = one quantum

        quantisation      widths 6-48    all widths
        truncate           99.7525%       99.7947%     <- what I registered
        round-to-nearest   99.5838%       99.6563%     <- what the device did
        measured           99.5838%       99.6563%

Both figures match the round-to-nearest row **exactly, to four decimal
places, on two independent populations** — 8,853 of 8,890 and 20,874 of
20,946. That is a two-point exact hit of a model written down before the arm
ran, so the mechanism is not in doubt: the device rounds its subpixel vertex
coordinates rather than truncating them, and my registered interval was taken
from the truncating rows.

The consequence for the leg is real and is not explained away: **L1 as
registered FAILED.** The consequence for the fix is that the extent rule and
its phase are drawn correctly and the residual is the rasteriser's grid. Those
two statements are both true and the first is why the second is worth
believing.

## What is left, and what it costs

143 of the goldens' 41,892 band edges sit within 1/256 of a pixel centre
without being on one; with round-to-nearest the exposed population is larger
still, because rounding can move an edge either way. 37 cuts of 8,890 wrong is
0.42%.

`line-extent-phase-exact.json`'s **E1 demanded 100.0000% and is not met.** That
was predicted in advance, with the reason, and the reason holds: 100.0000% is
not reachable at 8 subpixel bits by any placement of a parallelogram. The
registered file's own `--vs-goldens` control shows the tool can read 100%, so
this is the device and not the instrument.

## L5: eleven tripwires moved, none regressed

I transcribed the bound file's E3 as `must_not_move`, meaning bit-identical.
That was too strong: E3's stated criterion for the nine `Line_0064.*` rows is
"a fix that draws them at 64 makes them worse. **They must not regress.**"
Measured as differing pixels against the golden:

    capture          arm A    arm B    delta
    Fill_0000.0      21,992   21,992       0
    Fill_0001.0      22,499   22,447     -52
    Fill_0032.0      27,472   26,721    -751
    Line_0000.0           0        0       0    still pixel-exact
    Line_0064.0-.7    1,896    1,402    -494    each of the eight
    Line_FFFFFFFF     1,896    1,402    -494
    Line_0001.0       1,896    1,402    -494    the genuine width-1.0 row

**Zero regressed, eleven improved, two unchanged.** The nine void rows improve
by exactly what the genuine 1.0 row improves by, which is the structural check
that they really are drawn at 1.0: the register rejects 64.0, the width stays
at the previous 1.0, and our footprint at 1.0 is now right. `Line_0000.0` is
still bit-exact — a zero-width line still covers no pixel centre.

So E3 passes on its own terms and my stricter restatement of it does not. The
stricter form was wrong to register: at width 1.0 the derived extent is
`w(max + min/2)/max >= w`, so a correct fix *must* move a 1.0 line that is not
axis-aligned.

## The nineteen `label-differs` rows were ours, not the goldens'

`score_sweep` flagged 19 of arm A's 61 rows `label-differs` and AGENTS.md says
to treat such a row as **void** — the golden came from a different build of
`nxdk_pgraph_tests`. Arm B flags **none**. It was never the suite build.

The flag is `white_mismatch[:64].sum() > 8`: white pixels disagreeing in the
top 64 rows. `Line_width`'s palette contains white (`0xFFFFFFFF`) and its
drawing area starts at **OY = 48**, so rows 48–63 are label band and content at
once — and a wide white edge at width 40 or more reaches above row 48 as well.
Splitting the band on the eight rows the log named:

    capture        A rows 0-47  A rows 48-63   B rows 0-47  B rows 48-63
    Fill_0032.0              0             9             0             0
    Line_0032.0              0             9             0             0
    Line_0040.0              9             0             0             0
    Line_0048.0             10             0             0             0
    Line_0056.0             12             0             1             0
    Line_0057.0             14             2             1             0
    Line_0058.0             15             2             1             0
    Line_0059.0             15             1             1             0

Arm A sits at 9–17 against a threshold of 8; arm B at 0–1. This is the failure
`score_sweep`'s own comment anticipates for `2D_BorderTex_SZ` — "a content test
for any suite whose palette contains white" — arriving here because the band
and the content overlap in rows. **Nineteen Line_width rows have been
discounted for a reason that was not true**, and any suite drawing white above
row 64 can be discounted the same way.

## Two things the run settles that were open

**The width was always arriving.** #13 carried an either/or -
[`line-width-never-reaches-the-rasteriser.md`](line-width-never-reaches-the-rasteriser.md)
could not tell "the device refuses the width through its limits" from "the
width is never asked for", because both answer 1.0. The device reports
`width[1.000,127.500] gran=0.500 wide=1 strictLines=1`. It refused nothing: it
would have drawn 63.875 as 64.0, and our coverage was flat because the *shape*
was wrong, not the width. (The 0.5 granularity is a second reason the native
path could never be exact on a suite that steps width in eighths.)

The log that was supposed to settle this was never readable. It printed under
tag `hakuX-linewidth`, and `run_disc.sh`'s `LOGCAT_SPEC` ends in `*:S` with
that tag not on the allowlist — so it was silenced in every dispatcher run.
The replacement prints under `hakuX-build`, which is captured.

**#67 does not reach this suite.** `line-extent-phase-exact.json` flagged that
every `Line_width` capture set on disk predated `bc4bebcee0` and that #67 was
*expected* to be inert here, "an expectation, not a measurement". Arm A was
rebuilt after it and reads 47.8178% and 67.5738% — the registered baselines, to
four decimal places. Now measured.

## Not settled

The **cap and join phase**: 908 px of coverage residual against 700 px
simulated for the butt cap alone, so roughly 200 px are cap and join and no
rule here selects their floor/ceil. The **overlap colour rule**, which is
#13's separate priority derivation and 76.3% of the issue's residual — the
suite still shows max RGB delta 223, and that is what it is. The **GL
renderer**, deliberately unchanged. Anything at `surface_scale_factor > 1`.
And whether 99.58% can be improved at all without more subpixel bits: the
answer looks like no, and the way to test it would be a device reporting 12.
