# The 1,568-test blend oracle on a second rasteriser

The device lane recovered the retired oracle -- `Blend tests` once had 1,568
individual `<sfactor>_<eqn>_<dfactor>` tests, retired upstream when `#spot_`
replaced them, with goldens still in the repo. The 2025-03-14 release still
generates them. Run here on lavapipe: **1,568 captures in 1,937s**, matching the
golden count exactly.

Verifying the disc first, since the two builds' `sample-config.json` are
byte-identical and authoritative for neither: the old XBE carries `%s_%s` and
no `#spot_` literal, the current one the reverse. Confirmed 0 against 1.

## The fifth-quad defect is real and it is ours

**483 of the 1,120 unsigned captures differ *only* in a 256x64 strip** at rows
112-367, cols 560-623 -- 16,384 px, one quad, nothing else in the frame. That is
the device lane's pattern reproduced on a completely different rasteriser.

That answers the question the run was for. The fifth quad fails on Adreno and on
lavapipe alike, so it is not a host split: **it is a defect in this emulator.**

## Two hypotheses for it, both refuted here

**Channel order.** `1_ADD_0` shows ours `(192,0,0)` where the golden has
`(0,0,192)`, which looks exactly like red and blue exchanged -- the device
lane's first hypothesis, which they discarded because their example had
mirror-image colours that fit either story. Tested properly, by swapping R and B
across every differing pixel of all 1,120 captures:

| | |
|---|---:|
| differing px explained by the swap | 1,003,904 of 20,909,864 (**4.8%**) |
| captures the swap fully explains | **0 of 1,120** |

Discarding it was right, and now it is settled on the suite rather than on an
example.

**"We produce the lower value."** The replacement hypothesis came from one
test's colour inventory: on `1_MAX_1`, silicon has 221 and 48 where we have 192
and 4, and in both pairs ours is lower. Across all 1,120 captures, counting only
channels inside the strip:

| | |
|---|---:|
| channels where ours < gold | 19,976,608 (**50.8%**) |
| channels where ours > gold | 19,334,160 |

Balanced. **It does not generalise.** The direction in that one inventory was
the example, not the defect.

## What differs between the two lanes

The device lane reports **zero** captures differing anywhere outside the fifth
quad. Here, 637 of 1,120 do:

| | |
|---|---:|
| channels differing outside the strip | 7,190,056 |
| of those at \|delta\| = 1 | 7,018,024 (**97.6%**) |
| direction | 45.6% low, balanced |

So the two lanes agree exactly on the structural defect and disagree on a
7.19M-channel one-step population that exists here and not on Adreno. That is
the same shape as the bump alpha: a precision residue on the software
rasteriser that a real GPU does not have. It is not the same everywhere --
`Fog_param` and `Fog_exceptional_value` were shown to be one-step on *both*
hosts -- so one-step is not a synonym for host-specific, and each population
has to be priced separately.

## What this leaves

- The fifth quad is a genuine emulator defect, confirmed on two rasterisers,
  and no mechanism for it currently survives measurement. Both offered so far
  came from a single example; both fail on the suite.
- The 448 signed captures fail more broadly here as well -- 0 of 448 exact,
  most common differing counts 87,168 and 98,304 px, and every one of the 448
  has the same bounding box spanning the full width. Validating #43's rule
  against them needs the source and destination modelled per pixel, which is a
  second piece of work.
