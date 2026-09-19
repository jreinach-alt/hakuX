# #31 `ClipF`: the missing integer is 35, and the capture needs silicon we do not have

**Measured 2026-09-19, offline from the goldens and the test sources. No
device, no build, no arm.**

Tools: [`docs/testing/wbuf_clip_phase_choice.py`](../testing/wbuf_clip_phase_choice.py)
(new), on top of [`wbuf_anchor_recover.py`](../testing/wbuf_anchor_recover.py).
Background: [`wbuffer-31-blocker-audit.md`](wbuffer-31-blocker-audit.md),
[`wbuffer-slope-offset.md`](wbuffer-slope-offset.md).
Source change: [`docs/testing/wbuf31_clipf_phase.patch`](../testing/wbuf31_clipf_phase.patch).

## Two results, and the second is the one that stops the brief

1. **The audit's blocker holds, and holds far more strongly than it claimed.**
   It named two rules that the corpus cannot separate. There are **63**, and no
   `clip_top` the suite can currently generate separates *any two of them*.
2. **The capture that separates them cannot be taken in this lab.** It has to
   come from NV2A silicon, and the only NV2A in this project's loop is a
   third-party golden repository. Our devices run the emulator under test, so
   recovering an anchor from one of our own captures reads back the rule we
   shipped. The brief's "capture it on device" step has no informative form.

So this lane delivers the measurement it *can* make -- **which integer** --
plus the source change and a prediction table fixed before the number exists,
and reports the rest as blocked.

## Result 1 -- the degeneracy, priced over a family instead of two rules

`clip_top` is `kVertSampleCoords[3 + 6*i]` (`wbuf_tests.cpp:343`) and that array
holds only multiples of 32, so every `ClipF` capture has `clip_top == 0 (mod
4)`. Re-deriving the anchors from the goldens (not transcribing them) gives
three observations for `ClipF`'s second triangle:

| clip_top | px | recovered anchor interval | nearest integer misses by |
|---:|---:|---|---:|
| 32 | 189,489 | [33.9998, 33.9998] | 1.9e-4 |
| 128 | 159,250 | [130.0007, 130.0007] | 7.1e-4 |
| 224 | 112,210 | [226.0013, 226.0013] | 1.3e-3 |

Enumerating every rule `a*floor((ct + b)/a) + c` over `a` in 1..32 and keeping
those that fit all three: **63 survive.** Seven of them sit on a grid of 4 or
finer -- the ones with a mechanism behind them (1 = track the clip, 2 = the 2x2
quad the rasteriser already snaps to, 4 = the grid `TriH` pins on all 24 of its
triangles); the other 56 survive only because every measured `clip_top` is a
multiple of 32.

On all **15** `clip_top` values `kVertSampleCoords` can supply, all 63 predict
**one** value. The blocker is not "two rules we cannot tell apart"; it is a
63-member equivalence class that the entire existing corpus cannot enter.

**One caveat recorded rather than buried.** Hardware's offset interval is
~0.002 wide and inverts to an anchor interval under 1e-4 px, and `ClipF`'s
anchors miss the nearest integer by up to 1.3e-3 -- so the interval *alone*
admits no integer rule at all, and every fit above needs the 0.01 px tolerance
`wbuf_anchor_recover.py` already uses. For scale the same model form reproduces
`TriH` to 1.1e-7. "An integer anchor plus one step along the gradient" is
therefore not exactly right for `ClipF` either, and no choice of `clip_top`
fixes that. It is the same shape of reading that, taken silently, made `TriV`'s
refuted column look measured.

## Result 2 -- 35, and **not** 34

The audit prescribed "a `clip_top` that is not 0 mod 4 (33, 34 or 35)". Scored,
those three are not interchangeable:

| clip_top | classes among the 7 fine rules | classes among all 63 |
|---:|---:|---:|
| 33 | 4 | 7 |
| **34** | **3** | **6** |
| 35 | 4 | 7 |

**34 is strictly weaker and should not be used.** 33 and 35 tie, and 35 is the
pick because its classes fall where the live question is -- it puts the three
rules anyone would actually propose into three different cells, which 33 does
not (33 fuses the 2x2-quad rule with the 4-grid rule):

```
PREDICTION TABLE -- at clip_top = 35
  recovered anchor  34  ->  4*floor(ct/4)+2          (the absolute 4-grid at phase 2)
  recovered anchor  36  ->  2*floor(ct/2)+2          (the 2x2-quad snap, plus 2)
  recovered anchor  37  ->  ct+2                     (the rule recorded as measured)
  recovered anchor  38  ->  four phase variants of the 2- and 4-grids
  recovered anchor  42 / 50 / 66  ->  grids of 8 / 16 / 32
  any other value       ->  the whole family is refuted
```

35 also keeps the quad's **first** triangle covered -- 15,773 px by geometry,
against 16,801 at `clip_top=32` -- which matters because the audit found the
`(t0, clip_top>0)` cell has exactly one observation, and `clip_top` 128 and 224
cover no `t0` pixel at all. A far-away `clip_top` would separate the rules and
throw that cell away in the same move. (The same geometry routine reproduces
the measured 16,801 and 189,489 px at `clip_top=32` exactly, which is the
control on those two predicted counts.)

If a second variant is ever affordable, `(33, 35)` splits the 7 fine rules 6
ways -- one short of complete -- and both members are individually maximal.

## Result 3 -- why the capture cannot be taken here

The recovered anchor is a property of **silicon**. The goldens are
`abaire/nxdk_pgraph_tests_golden_results`, "captured from real NV2A silicon"
(`docs/testing/pgraph-harness.md:20`) by the test suite's author on XBOX 1.0
hardware; the checkout on this machine is at `6e159f1532`, 2026-08-11. This
project's devices are a Retroid Pocket Nova and an Ayn Thor (`devices.sh`) and
they run hakuX -- the emulator whose anchor rule is the thing under test.

So building the patched disc and running it here would recover
`wbufSlopeStep`'s own rule. At `clip_top=35` that is 34, readable from
`psh.c` in a minute, and `wbuf_anchor_recover.py --simulate` already reproduces
the device's exact/±1/wrong split without a device at all. The run would cost a
device slot and return a number we can already write down. **Do not queue it.**

The unblocking step is therefore upstream, not local: land
`wbuf31_clipf_phase.patch` in `abaire/nxdk_pgraph_tests` and the golden follows
from the regeneration that has produced every other capture here. Latency is
weeks and outside our control, which is exactly why the integer is worth
getting right the first time -- a variant at 34 would come back six weeks later
having fused two of the three rules.

## Ready for the capture

`wbuf_anchor_recover.py`'s `PRIMS` already lists `ClipF-150-035`. The entry is
inert while the golden is absent (missing captures are skipped, and the tool's
output is byte-identical today), so reading the result is one command:

```bash
docs/testing/wbuf_anchor_recover.py --goldens /home/justin/goldens/results
```

and the row is read against the prediction table above.

## Not established here

* Anything about `ClipF`'s **first** triangle. The t0/t1 split is an
  interaction the audit showed no function of (plane, clip, first covered
  pixel, top vertex) reproduces, and `clip_top=35` adds one observation to that
  cell without being chosen to resolve it.
* Anything about `TriV`, whose model family the audit refuted outright.
* That the surviving family contains the truth. All 63 members are fits to
  three points; the table's last row exists because "none of the above" is a
  live outcome and a bigger result than choosing within the family.
* Whether inserting the new test perturbs its neighbours. `tests_` is a
  `std::map`, so `ClipF-150-035` sorts between `-032` and `-128` and shifts the
  run order of the tests after it. The three existing captures are unchanged
  *by construction* (`i < 3` reproduces their `clip_top` exactly), but issue
  #15 is order dependence, so the regeneration should be diffed against the
  current goldens for those three rather than assumed equal.
