# Prediction: Line_width's residual is the boundary-shift floor at a wider band

Registered 2026-09-15 on `b194ac69`, before measuring.

## The claim under test

Seven hypotheses are refuted. What remains on a diagonal is sub-pixel and varies
sample to sample along one segment. `b194ac69` READ that as the documented
precision floor and said so as a reading, not a measurement. This tests it.

`classify_residuals.py:79` defines boundary-shift for a **one-pixel** band: the
pixel differs, the rows or columns at +/-1 agree with the golden (the band is
ISOLATED), and our value equals the golden's one pixel over. Wide lines cannot
satisfy that -- their differing region is as wide as the error band, which is
more than one pixel -- so they classify structural regardless of whether they
are the same KIND of difference.

**The hypothesis: they are the same kind at a wider band.** Generalise the test
to band half-width k -- pixel differs, isolation at +/-(k+1), and our value
equals the golden's at some offset within +/-k -- and the Line_width captures
should qualify at k of roughly the line width.

## Predictions

**P1.** At k = 1 the qualifying fraction is small, reproducing what the shipped
classifier already reports (these captures are structural to it).

**P2.** The qualifying fraction rises steeply with k and is a LARGE MAJORITY by
k ~ W. If most differing pixels are a displaced boundary once the band is
allowed to be as wide as the line, the structural label is an artefact of the
band width rather than a statement about the defect.

**P3.** The k at which it saturates tracks W across captures -- small k for
W=1..4, larger for W=16..48. A fixed k would mean the band is not scaling with
the line and the reading is wrong.

## What kills it

A qualifying fraction that stays low at every k: the differences are not
displaced boundaries at any band width, the floor reading is wrong, and
`Line_width`'s 4.46M stands as genuinely actionable. A fraction that is already
high at k=1 would mean the shipped classifier should have caught it and my
reading of why it did not is wrong.

## Why it matters beyond this suite

`corpus-residual-triage.md` ranks suites by "actionable" channels and puts
`Line_width` sixth on 4,462,131. If those are floor, **that ranking is wrong and
I wrote it.** Confirming would mean correcting my own published triage; that is
the point of running it rather than leaving the reading to stand.

---

## Outcome: FALSIFIED. The residual is not displaced boundary at any band width.

Fraction of differing pixels qualifying as a boundary shift at band half-width k:

| capture | differing | k=1 | k=2 | k=4 | k=8 | k=16 | k=32 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `Line_0001.0` | 2,299 | 42.8% | 43.5% | 43.4% | 43.5% | 43.3% | 43.1% |
| `Line_0004.0` | 9,063 | 16.9% | 21.4% | **44.4%** | 52.3% | 54.6% | 56.6% |
| `Line_0008.0` | 18,151 | 2.2% | 6.7% | 12.5% | **34.7%** | 44.6% | 48.6% |
| `Line_0016.0` | 32,679 | 0.6% | 1.2% | 4.1% | 7.9% | **26.5%** | 33.9% |
| `Line_0032.0` | 54,713 | 0.2% | 0.3% | 1.0% | 3.6% | 6.1% | **16.8%** |
| `Line_0048.0` | 71,167 | 0.1% | 0.2% | 0.4% | 1.2% | 3.6% | 5.5% |

**P1 held.** At k=1 the fraction is small for W >= 4 -- 16.9%, 2.2%, 0.6%, 0.2%,
0.1% -- which is why the shipped classifier calls these structural. (W=1 is 42.8%
at k=1, and a one-pixel line genuinely is substantially boundary shift.)

**P2 falsified.** At k ~ W the fraction is 44.4%, 34.7%, 26.5%, 16.8% -- never a
majority, and **declining as the line gets wider**, which is the opposite of the
prediction. At W=48 only 5.5% qualify even at k=32.

**P3 falsified.** It does not saturate near k ~ W. It creeps upward with k
without converging, and the k needed does not track W -- wider lines qualify LESS
at every k, not more.

## So the floor reading was wrong, and the triage stands

`b194ac69` read the sub-pixel, sample-varying diagonal difference as the
documented precision floor and suggested that most of `Line_width`'s 4,462,131
channels were therefore not actionable, and that
`corpus-residual-triage.md` would need correcting. **It does not.** The residual
is not predominantly a displaced boundary at any band width, so the structural
classification is doing its job rather than mislabelling a floor, and the
ranking I published is right.

I am glad to have run it rather than leaving the reading to stand. It was my own
speculation, it was plausible, it would have retired a real defect by
reclassification, and it is false.

## And it says something new about the residual

The qualifying fraction DECLINES with width. Whatever the difference is, at wide
lines it is overwhelmingly **not "our pixels in the wrong place"** -- if it were,
some band width would capture it. The golden holds content at those pixels that
we do not produce anywhere nearby.

That is a different character from everything tested so far, all of which
assumed our output was right-but-displaced or right-but-scaled. It is the first
positive statement about what the residual IS rather than what it is not, and it
is where the next instrument should aim.
