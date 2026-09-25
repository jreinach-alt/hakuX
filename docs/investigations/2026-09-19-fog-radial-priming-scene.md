# #112 item 2: separating the radial-fog carryover from a constant with four pixel-identical priming scenes

Written 2026-09-19 by `lane.cloud-112`, ahead of hardware. The geometry below
is recomputed from `docs/testing/fog_radial_stale_vertex.py`'s own model --
the one that agrees with silicon's fixed-function radial cell to within one
quantisation step over 360 unclipped quads -- and reproduces that script's
published figure for quad 373 (215.93) exactly. No device, no new measurement.

The prediction this derivation binds is
[`docs/testing/predictions/2026-09-19-fog-radial-carryover-priming.md`](../testing/predictions/2026-09-19-fog-radial-carryover-priming.md).
Background: [`fog-vs-radial-band.md`](fog-vs-radial-band.md) and
[`fog-carryover.md`](fog-carryover.md).

## The state of the question

`fog-vs-radial-band.md` pins silicon's program-mode RADIAL fog coordinate to
**(204.06, 221.81)** -- one value on all 181,016 drawn pixels of all six
`FogGen_VS-*-radial` captures. `fog_radial_stale_vertex.py` then shows the
last vertex the *fixed-function* scene draws, quad 373's LL, sits at
**215.929**, inside that window; and excludes the printed text overlay by
noting that the two captures which pin the coordinate have labels 40 px apart
in x while the band is only 17.74 wide.

Three models survive that, and #41 and #112 both name the experiment that
separates them rather than performing it:

| | the coordinate is... |
|---|---|
| **S** | the radial distance of the **last vertex the fixed-function scene transformed** -- a register the vertex engine keeps and a program never writes |
| **T** | the same register, but the last fixed-function vertex is the **printed label**, not the scene |
| **H** | a **hardware constant**, independent of everything before it |

S and T are the same mechanism disagreeing about which draw is last; H is a
different mechanism. All three reproduce every existing golden, which is why
the corpus cannot choose between them: `fog_tests.cpp:27` and
`fog_exceptional_value_tests.cpp:98` both comment RADIAL out of their gen-mode
lists, so `fog_gen_tests.cpp` is the only place a VS RADIAL scene exists and
it always follows the same fixed-function scene.

## The design: change the draw ORDER, not the scene

The obvious experiment -- draw a *different* fixed-function scene first --
changes the priming frame's pixels, so any difference downstream has a second
possible cause. A rotation of the draw order does not.

`fog_gen_tests.cpp` lays 374 non-overlapping 22 px quads (2 px spacing, no
quad touches another), each carrying its own fog factor computed from its own
vertices. **Rotating the order by r -- draw r, r+1, ..., 373, 0, ..., r−1 --
therefore produces a bit-identical frame** and changes exactly one thing: which
vertex the transform unit saw last. That is the only variable the mechanism
under test reads.

Three rotations, and the coordinate each puts in the register under S:

| rotation r | first quad | **last quad** | last quad's four vertices |
|---:|---:|---:|---|
| 0 | 0 | **373** | coord **213.514 .. 219.671** |
| 188 | 188 | **187** | coord **94.577 .. 95.803** |
| 21 | 21 | **20** | coord **12.020 .. 13.382** |

r = 0 is the existing scene, and its window contains 215.929 -- so **r = 0 is
the validity gate, not a discriminator**: S and H both predict it lands in the
measured band. The other two move the coordinate by a factor of 2 and a factor
of 18.

A rotation also separates "the register holds the **last** vertex" from "it
holds the **first**", which two priming scenes could not: at r = 0 the first
quad is quad 0 at coordinate ~1.1 and the last is quad 373 at ~216, and those
invert to opposite ends of the factor range. At r = 188 and r = 21 the first
and last quads are adjacent in the grid and their windows overlap, so the
separation rests entirely on r = 0 -- which is enough, because it is a
200-step separation.

## The fog parameters have to move, for the reason the band is only 17.74 wide

`fog_gen_tests.cpp` uses bias 1.5 and multiplier `m = −0.025 / (2 ln 256)`
= −0.00225, which with the bias cancelling gives `fogX = coord * m` and
`f8 = 255 · 2^(16 m · coord)`. Under that multiplier the three rotations
predict:

    r = 0    coord 215.93  ->  f8 = 1.15
    r = 188  coord  94.78  ->  f8 = 23.85
    r = 21   coord  12.02  ->  f8 = 188.81

which does separate them -- but puts the incumbent case at f8 = 1, in the tail
`psh.c:1456` warns is "above the true value by up to a step at small factors,
and is not modelled here", and where **one f8 step is 17.74 coordinate
units**. That tail is the whole reason `fog-vs-radial-band.md` had to
calibrate silicon's exp unit from `fog_param_tests.cpp` before it could invert
anything, and the whole reason the answer is a window rather than a number.

Setting the multiplier to **−0.000875** (bias unchanged at 1.5) moves all
three into the interior:

| rotation | coord window | **f8 window** | coordinate units per f8 step |
|---:|---|---:|---:|
| r = 0 | 213.514 .. 219.671 | **30.25 .. 32.11** | 3.29 |
| r = 188 | 94.577 .. 95.803 | **100.64 .. 101.85** | 1.01 |
| r = 21 | 12.020 .. 13.382 | **223.95 .. 226.92** | 0.45 |
| H: the measured band | 204.06 .. 221.81 | **29.63 .. 35.20** | -- |

Three consequences, and the third is what makes the run robust:

1. **r = 0's S window sits strictly inside H's**, as it must -- that is the
   gate working.
2. The separation between r = 188 and H is **at least 65 f8 steps**, and
   between r = 21 and H **at least 189**. A single capture decides.
3. **The decisive reading needs no model of silicon's exp unit at all.** S
   predicts three *different* factors; H predicts three *identical* ones. That
   comparison is between captures from one run at one multiplier, so an
   uncharacterised exp curve cancels out of it exactly. The f8 windows above
   are the second, stronger leg, and they are the one that inherits the exp
   unit's uncertainty -- which at a separation of 65 steps it cannot close.

## Separating T from H needs a second factor, and it is free

S and T both say "the register holds the last fixed-function vertex"; they
differ only on whether the printed label is one. Under T every rotation reads
the same value, because every variant prints the same label in the same place
-- which is exactly what H predicts too. So the rotations alone leave T and H
degenerate, and a fourth capture breaks it: **r = 0 with the priming test's
label moved** to a different screen position.

|   | **S** (last scene vertex) | **T** (last label vertex) | **H** (constant) | **S-first** |
|---|---|---|---|---|
| r = 0, label A | f8 30.3-32.1 | X | 29.6-35.2 | 249.5-252.2 |
| r = 188, label A | **f8 100.6-101.9** | X | 29.6-35.2 | 100.0-101.3 |
| r = 21, label A | **f8 224.0-226.9** | X | 29.6-35.2 | 222.3-225.4 |
| r = 0, **label B** | f8 30.3-32.1 | **Y ≠ X** | 29.6-35.2 | 249.5-252.2 |

Each model owns a distinct *shape*: S is a row effect, T is a column effect, H
is flat, S-first is a row effect with r = 0 at the opposite end. No two of them
produce the same four-capture pattern, and the pattern is readable without
inverting anything.

## Why the corpus cannot already answer this, restated as a bound

The exclusion of T in `fog_radial_stale_vertex.py` is an inference over two
captures whose labels differ by 40 px in x: for a text vertex to be in the
17.74-wide band its position vector must be ~210 long with x dominating, so
40 px of x is ~40 units of coordinate and no single window holds both. That
argument is sound and it rests on a *model of where text vertices live* that
has never been measured -- the failure this repository records as "an
inference can be valid and still wrong, because the model it is valid inside
was never checked". The label-B capture measures it instead of assuming it,
for the cost of one frame.
