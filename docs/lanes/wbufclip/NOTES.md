# lane.wbufclip -- #31 ClipF phase-2 degeneracy

Brief: add ONE `ClipF` variant at a `clip_top` that is not `0 (mod 4)`, rebuild
the disc, capture it on device, and read which of two candidate anchor rules the
recovered anchor matches.

**Outcome: the integer is measured (35, and *not* 34) and the source change is
written and verified to apply. The capture is blocked -- it needs NV2A silicon,
and this lab has none.** Write-up:
[`docs/investigations/wbuffer-31-clipf-phase.md`](../../investigations/wbuffer-31-clipf-phase.md).

## What the next lane should not repeat

**Do not queue a device run for this.** The lane brief says "capture it on
device", and the device holds were lifted, so the run is available -- and it is
worthless here. The recovered anchor is a property of *silicon*. The goldens
are `abaire/nxdk_pgraph_tests_golden_results`, captured on XBOX 1.0 hardware by
the test suite's author (`docs/testing/pgraph-harness.md:20`); the checkout here
is at `6e159f1532`, 2026-08-11. Our devices (`devices.sh`: Retroid Pocket Nova,
Ayn Thor) run hakuX, the emulator whose anchor rule is the thing under test, so
running the patched disc here recovers `wbufSlopeStep`'s own rule -- 34 at
`clip_top=35`, readable from `psh.c`, and `wbuf_anchor_recover.py --simulate`
reproduces the device split without a device already.

I checked this rather than assuming it (a blocker is a claim): goldens README,
`pgraph-harness.md`, `devices.sh`, and the recover tool's own premise all say
the same thing, and `make_test_iso.py` only injects a runtime config into a
*stock* disc -- there is no path in this repo that rebuilds the suite anyway.

**Do not use `clip_top=34`.** The audit offered "33, 34 or 35" as
interchangeable. They are not, and the cost of the wrong one is a six-week
upstream round trip that comes back with two rules still fused.

## What was tried and what it measured

New instrument: `docs/testing/wbuf_clip_phase_choice.py`. It re-derives the
`ClipF` anchors from the goldens by importing `wbuf_anchor_recover.py` (nothing
transcribed, so it cannot go stale against it), enumerates every rule
`a*floor((ct+b)/a)+c`, keeps those fitting all three measured anchors, and
scores each candidate `clip_top` by how many classes the survivors split into.

* **63 rules fit**, not the two the audit named. 7 of them on a grid of 4 or
  finer; the other 56 survive only because every measured `clip_top` is a
  multiple of 32. Scored separately rather than dropped -- "the data does not
  exclude them" and "they are plausible" are different statements.
* **All 15 `clip_top` values `kVertSampleCoords` can supply fuse all 63 into one
  prediction.** That is the audit's blocker restated over a family instead of
  over two members, and it is a stronger statement than the audit made.
* `clip_top` 33 and 35 reach 4 fine / 7 overall classes; **34 reaches 3 / 6**.
  35 is the pick over 33 because its classes land where the live question is:
  34 -> the absolute 4-grid, 36 -> the 2x2-quad snap plus 2, 37 -> `clip_top+2`.
  33 fuses the first two.
* 35 also keeps `ClipF` t0 covered (15,773 px by geometry vs 16,801 at
  `clip_top=32`), so it adds a second observation to the `(t0, clip_top>0)` cell
  the audit found has exactly one. `clip_top` 128 and 224 cover no t0 pixel.
  Control: the same routine reproduces the measured 16,801 / 189,489 px at
  `clip_top=32` exactly.

**Tolerance, recorded because it is the one number here that can be leaned on.**
Hardware's anchor interval is under 1e-4 px wide and `ClipF`'s anchors miss the
nearest integer by up to 1.3e-3, so the interval alone admits **no** integer
rule -- every fit above needs the 0.01 px tolerance `wbuf_anchor_recover.py`
already uses, and the tool prints the per-observation miss so the widening stays
visible. The same model form reproduces `TriH` to 1.1e-7, four orders tighter.
So "an integer anchor plus one step along the gradient" is not exactly right for
`ClipF` either, and no `clip_top` fixes that. My first run of the tool scored
against the bare interval and reported "0 rules survive" -- that was the
instrument, not a finding, and it is the trap to avoid here.

Then I swept it rather than leaving it as a caveat: `--tol` from 0.002 (just
above the worst miss) to 1.0, a 500x range, gives 63 survivors and 33: 4/7,
34: 3/6, 35: 4/7 at **every** value. The tolerance is a real weakness of the
model form and carries none of the verdict. Keep both statements -- the first
is what the next person needs if they try to fit `ClipF` exactly, the second is
why they can use 35 anyway.

## Delivered

* `docs/testing/wbuf_clip_phase_choice.py` -- the chooser, writes nothing.
* `docs/testing/wbuf31_clipf_phase.patch` -- the one-integer source change
  against `abaire/nxdk_pgraph_tests` @ `91a0de45ca`, **verified with
  `git apply --check` (rc 0)**. Adds `WBuf24D_ClipF-150-035_V1_ZB0_ZS1`;
  `i < 3` reproduces the three existing `clip_top`s exactly, and the generated
  names were re-derived from `MakeTestName`'s own logic rather than assumed.
* `docs/testing/wbuf_anchor_recover.py` -- `PRIMS` now lists `ClipF-150-035`.
  Inert until the golden exists (missing captures are skipped; today's output is
  byte-identical, re-run and diffed), so reading the answer is one command.
* Prediction table fixed in the write-up before the number exists.

## Open, and deliberately not touched

* `ClipF` t0 vs t1 -- the interaction the audit showed no selector reproduces.
  `clip_top=35` adds an observation to that cell but was not chosen for it.
* `TriV` and the 941,308 px per-triangle plane-solve floor: out of scope per the
  issue's own note, and not reopened.
* `tests_` is a `std::map`, so `ClipF-150-035` sorts between `-032` and `-128`
  and shifts the run order of the tests after it. The three existing captures
  are unchanged by construction, but #15 is order dependence, so a regeneration
  should be diffed against the current goldens for those three rather than
  assumed equal. Flagged upstream in the patch header's neighbourhood, not
  tested here -- no device can test it.
