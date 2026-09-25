# Prediction: the program-mode RADIAL fog coordinate under four priming scenes

Registered 2026-09-19 on `01047cf32c` by `lane.cloud-112`, for issue #112 item 2
(and #41), **before any hardware run and before any emulator run of the disc
below**. Nothing in this file has been measured.

Derivation, geometry and the reason each variant exists:
[`docs/investigations/2026-09-19-fog-radial-priming-scene.md`](../../investigations/2026-09-19-fog-radial-priming-scene.md).
The band it is scored against comes from
[`fog-vs-radial-band.md`](../../investigations/fog-vs-radial-band.md).

**This prediction registers no arm and queues nothing.** It names no `a_ref`
or `b_ref` and no golden key, because **every capture it predicts is of a test
that does not exist**: `FOG_GEN_MODE_V_RADIAL` under a vertex program appears
in `fog_gen_tests.cpp` and nowhere else in the corpus, and the two suites that
would produce a second one comment it out citing
[abaire/nxdk_pgraph_tests#214](https://github.com/abaire/nxdk_pgraph_tests/issues/214).
`request.sh` would correctly refuse a key matching no golden. It is a
registered expectation, not a queued A/B.

---

## 0. The models

| | the program-mode RADIAL fog coordinate is... |
|---|---|
| **S** | the radial distance `\|modelview · v\|` of the **last vertex the fixed-function scene transformed**, held in an output register a vertex program never writes |
| **S-first** | the same register, holding the **first** such vertex |
| **T** | the same register, but the last fixed-function vertex is the test's **printed label**, not its scene |
| **H** | a **hardware constant**, independent of every preceding draw |
| **X** | none of the above. Registered as a first-class outcome with its own signature (§3) so that "none of these" cannot be quietly rounded to the nearest model |

Every one of them reproduces all six existing `FogGen_VS-*-radial` goldens.
That is the problem this run exists to solve.

## 1. The run this binds

One nxdk binary, one new test file, one new suite. No change to
`fog_gen_tests.cpp` and no change to any existing golden.

**The scene** is `fog_gen_tests.cpp`'s: 374 non-overlapping 22 px quads,
2 px spacing, 48/70 padding, quad *i* unprojected at world z = −6 + 0.5·i with
its right-hand vertices one unit further, camera at (0, 0, −7), fov π/4, near
1, far 200. Both the fixed-function and the programmable path use it, which is
what lets a distance recovered from a fixed-function capture be evaluated at a
programmable capture's vertex.

**The fog** is exp mode, `FOG_GEN_MODE_V_RADIAL`, **bias 1.5** and
**multiplier −0.000875** (the suite uses −0.00225; §5 says why it must
change). The final combiner is `f·diffuse + (1−f)·fog` with diffuse (0, 0, 1)
and fog (1, 0, 0), exactly as `fog_gen_tests.cpp` does, so the mix clips at
neither end and **every drawn pixel carries the 8-bit fog factor**: blue is
`f8`, red is `255 − f8`. That is the whole instrument and it must not be
changed.

**The variants** differ only in the order the fixed-function priming test
draws its quads -- a rotation, `r, r+1, ..., 373, 0, ..., r−1` -- and, for one
of them, where the priming test prints its label. The quads do not overlap, so
**a rotation changes no pixel of the priming frame** (see V1).

| id | priming rotation | priming label | reads |
|---|---|---|---|
| **A0** | r = 0 (the existing order) | row 0 | the gate |
| **A1** | r = 188 | row 0 | discriminator |
| **A2** | r = 21 | row 0 | discriminator, largest separation |
| **A3** | r = 0 | **row 400** | separates **T** |
| **A4** | r = 21, then an intervening **programmable** scene | row 0 | persistence across a VS draw |

**Run order matters and is the one thing a name can get wrong.** Tests execute
in name order, so each priming test must sort immediately before its
programmable test and nothing may run between them. Names of the form
`A0far_FF` / `A0far_VS`, `A1mid_FF` / `A1mid_VS`, `A2near_FF` / `A2near_VS`,
`A3farLabel_FF` / `A3farLabel_VS`, `A4near_FF` / `A4pad_VS` / `A4radial_VS`
give that ordering. **Set `enable_progress_log: true` and read
`pgraph_progress_log.txt`**: it names every test started and finished, and it
is the only record that the order this file assumes is the order that ran.

## 2. What each model predicts, per capture

The measured quantity is the **8-bit fog factor `f8` of the single drawn
colour over the 181,016-pixel drawn region**, recovered as the blue channel
over the pixels where `red + blue == 255` and `green == 0` -- the same
recovery `fog_radial_band.py` performs, on the same region, with the same
exactness (374 quads x 484 px, no antialiasing, the count is exact).

| | **S** | **S-first** | **T** | **H** |
|---|---:|---:|---|---:|
| **A0** (r=0, label A) | **30.25 .. 32.11** | 249.48 .. 252.21 | X | 29.63 .. 35.20 |
| **A1** (r=188, label A) | **100.64 .. 101.85** | 99.98 .. 101.33 | X | 29.63 .. 35.20 |
| **A2** (r=21, label A) | **223.95 .. 226.92** | 222.32 .. 225.36 | X | 29.63 .. 35.20 |
| **A3** (r=0, label B) | **30.25 .. 32.11** | 249.48 .. 252.21 | **Y ≠ X** | 29.63 .. 35.20 |
| **A4** (r=21, VS between) | **223.95 .. 226.92** | 222.32 .. 225.36 | X | 29.63 .. 35.20 |

Each window spans the four vertices of the quad the rotation puts last (or
first), so it does not depend on knowing which vertex slot the register holds.
H's window is `fog-vs-radial-band.md`'s measured band (204.06, 221.81) carried
through the new multiplier.

**The decisive reading needs no exp-unit model at all**, and should be taken
first:

> **S and S-first predict three different factors across A0/A1/A2; H and T
> predict three identical ones.** That comparison is between captures from one
> run at one multiplier, so silicon's uncharacterised `2^x` cancels out of it
> exactly.

Then the shapes, which separate all four:

| model | shape over (A0, A1, A2, A3) |
|---|---|
| **S** | row effect: A0 = A3 ≠ A1 ≠ A2, low -> high as the rotation moves the last quad nearer |
| **S-first** | row effect with **A0 at the opposite end**: A0 = A3 ≈ 251, A1 ≈ 101, A2 ≈ 224 |
| **T** | column effect only: A0 = A1 = A2 ≠ A3 |
| **H** | flat: all four in 29.63 .. 35.20 |

### Must-move / must-not-move

| | **must move** (differs from A0) | **must not move** |
|---|---|---|
| **S** | A1, A2, A4 | **A3** -- bit-identical to A0 |
| **S-first** | A1, A2, A4 (to the *other* end at A0) | A3 |
| **T** | **A3** only | A1, A2, A4 -- all bit-identical to A0 |
| **H** | nothing | A1, A2, A3, A4 -- all bit-identical to A0 |

Two legs in tension, so that no inert change and no broken test passes both:
**S requires A2 to move and A3 not to.** A disc that mis-programs the fog,
loses the priming draw, or renders the same frame five times fails one or the
other.

## 3. Confirmation criteria

A model is confirmed by the whole row, not by one agreeing cell.

| model | confirmed only if |
|---|---|
| **S** | A0 in 30.25-32.11 **and** A1 in 100.64-101.85 **and** A2 in 223.95-226.92 **and** A3 bit-identical to A0 **and** A4 equal to A2 |
| **S-first** | A0 in 249.48-252.21 **and** A1 in 99.98-101.33 **and** A2 in 222.32-225.36 **and** A3 bit-identical to A0 |
| **T** | A0 = A1 = A2 = A4 to the digit **and** A3 differs from all of them |
| **H** | all five in 29.63-35.20, **with V1 and V2 both holding in the same session** |
| **X** | anything else. The named concrete forms are: A1/A2 move but not to their windows (a carryover from a vertex slot this file did not name -- report the triple and fit it); or A4 differs from A2 (the register is touched by a programmable draw after all, which contradicts `fog-carryover.md`'s reading and is the more interesting result) |

**A mixture is an expected outcome, not a failed run.** "The register carries
the last fixed-function vertex *and* the label is one of them" is S and T
together and reads as A1/A2 *and* A3 all moving. Registering the four as
exclusive would be the mistake.

## 4. Emulator-side companion -- no hardware, and it is the positive control

The desktop lane under lavapipe settles all of these, and running them first
is the cheapest way to find out the disc is wrong before silicon time is spent.

| | prediction |
|---|---|
| **E1** | **All five captures are bit-identical in our renderer.** `glsl/vsh.c` takes the programmable fog coordinate from `oFog.x` unconditionally and initialises every invocation to `vec4(0,0,0,1)` (`vsh.c:213`), so nothing in our path can see the preceding scene. Five identical frames is what "the mechanism is absent" looks like here |
| **E2** | Each of them shows a **per-quad gradient**, not one colour -- our coordinate is whatever the test's own vertex program writes, which varies across the grid. Hardware's six existing radial goldens hold **one** colour across all 181,016 px |
| **E3** | The five **priming** (`*_FF`) captures are bit-identical to each other in our renderer, because a rotation of non-overlapping quads is a no-op |

**E1 is the instrument's control and the reason to run it.** Stated the way
this repository asks: *if the carryover were present in our renderer, E1 would
show A2 differing from A0 by ~195 f8 steps; it will not, because we reset the
register every invocation.* And E1 failing is a finding either way -- it would
mean something in our path does depend on the preceding scene, which nothing
in `fog-carryover.md` predicts.

## 5. Falsifier: which variants carry no information, and why

Silicon time is the expensive part; variants are nearly free. So this is the
half worth settling in advance.

1. **Any rotation whose last quad sits in (204.06, 221.81).** S and H agree
   there by construction -- that is A0's entire job, and a second such
   rotation buys nothing. The final four quads' sixteen vertices span
   210.35 .. 219.67, all inside the band, so the rotations whose last quad is
   370-373 -- **r = 371, 372, 373 and 0** -- are all uninformative, and only
   one of them is worth a capture.
2. **The suite's own multiplier, −0.00225.** It puts A0 at f8 = 1, in the tail
   `psh.c:1456` says is not modelled, where one f8 step is **17.74 coordinate
   units** -- wider than the entire band the result is scored against. It also
   puts A1 at f8 = 23.85 and A2 at 188.81, so the variants *are* separated;
   the objection is not separation but that the incumbent case is read at the
   one place the exp unit is known to be wrong. #41's own note suggests "a
   multiplier around −0.0023 works"; it works and it measures worse.
3. **Any multiplier that clips either end.** f8 = 0 or f8 = 255 collapses
   distinct coordinates into one colour, which is precisely the reading that
   made this cell "unfalsifiable" for two write-ups. At −0.000875 the five
   predicted factors span 30 .. 227 with 28 steps of headroom at each end.
4. **Changing the programmable scene instead of the priming one.** A program
   never writes the register under S, T or H, so no change to the VS geometry
   moves anything under any model. This is the obvious knob and it is inert.
5. **Priming with a scene that differs in pixels as well as in order.** Not
   uninformative -- *confounded*. A difference downstream would then have a
   second possible cause, and the whole point of the rotation is that the
   priming frame is bit-identical across variants.
6. **A fourth and fifth rotation.** The ladder is log-linear in the
   coordinate, so three points already over-determine it; a fourth costs a
   capture and buys a residual.

So the capture budget is: **A2 first** -- one capture, 189 f8 steps of
separation between S and H, and the largest in the set. Then A0, without which
A2's movement has no reference. Then A3, which is the only thing that
separates T. A1 and A4 are the cheap remainder and should not be dropped: A1
is the middle rung that stops a two-point fit passing, and A4 is the only test
of the persistence half of the mechanism.

## 6. Validity gates -- what voids the session

| | gate |
|---|---|
| **V0** | **A0 must land in 29.63 .. 35.20.** It is the one variant whose answer is already known from the existing goldens, carried through the new multiplier. If it does not, the fog parameters, the combiner or the scene are not what §1 names, and every other capture in the session is void rather than interesting |
| **V1** | **The five `*_FF` priming captures must be bit-identical to each other**, outside the label rows and excluding A3 whose label is moved on purpose. They differ only in draw order over non-overlapping quads. If they are not, the rotation did something other than reorder and no downstream difference is attributable |
| **V2** | Each programmable capture's drawn region must be **exactly 181,016 px of a single `red + blue == 255, green == 0` colour**. A second colour means the coordinate is not constant across the scene, which no model here predicts and which voids the single-value reading |
| **V3** | The six existing `FogGen_VS-*-radial` captures, re-run in the same session on the same binary, must reproduce their goldens. They are untouched by this test file; a difference means the build or the rig moved |

## 7. Known risks to the run

**R1 -- the label may not be a fixed-function draw at all.** If `pb_print`
does not go through the transform unit, T is empty and A3 is predicted
identical to A0 by every surviving model. That is not a failure: A3 then costs
one capture and retires a model the corpus could only exclude by an argument
about where text vertices live.

**R2 -- silicon's exp unit is uncharacterised in the mid-range.**
`fog_param_tests.cpp`'s sweep only bounds f8 = 0..3. The f8 windows in §2
therefore carry an unquantified systematic. It cannot close a 65-step gap, and
the shape reading in §2 does not depend on it at all -- which is the reason
that reading is listed first.

**R3 -- test order.** Everything here assumes each `*_FF` test runs
immediately before its `*_VS` test. If the suite reorders, or another suite
interleaves, the priming is not what the name says. V1 does not catch this;
the progress log does.

## 8. Outcome

Not run. No hardware, no disc, no emulator run. This section is left for
whoever runs it, and the rule that applies is the one that applies to every
prediction here: score against §2 and §3 rather than rewriting them to match
what came back.
