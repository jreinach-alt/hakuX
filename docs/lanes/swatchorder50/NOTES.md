# lane.swatchorder50 -- separating `DrawColorAndAlphaStack`'s two readings

Issue #50. Brief: build a `blend_tests.cpp` variant with unequal swatch heights
(or three swatches instead of four), run it on device, and read which of two
readings the capture matches:

1. the four quads land at reversed y positions;
2. the four quads land correctly and receive the diffuse colours in reverse.

**Verdict: neither.** No disc variant was built and no device time was used,
because the discriminator the variant was going to manufacture already exists
in 1,120 captures on disk, and it is a single channel.

## Why the brief's measurement was not the cheapest one

The brief is right that the existing frame cannot separate reading 1 from
reading 2, and `swatchorder50_readings.py --equivalence` measures that rather
than assuming it: built independently, in the shape each sentence describes,
the two render targets are **identical on 1,568 of 1,568** tests. The bands are
64 rows and the render target's checkerboard is 16, so "quad `sw` at band
`3-sw`" and "band `p` given colour `CASTACK[3-p]`" are the same map and the
destination phase is band-independent. Unequal heights would indeed break the
tie. That part of the brief is sound.

What the brief missed is that the tie does not need breaking, because **both
readings are already refuted together**, and by something the equal-height
frame shows perfectly well.

## The discriminator is alpha, not geometry

Both readings keep stack C's own draw state, in which
`DrawColorAndAlphaStack` blends **all four** channels. The third reading --
that stack C's blit shows the render target `DrawColorStack` left behind at the
same guest address, `blend-stack-c-is-render-target-aliasing.md` -- keeps stack
A's state, in which `DrawQuad` writes alpha with blending switched off.

Where the three predictions differ, over the 1,120 unsigned captures:

| model vs reading 3 | RGB channels differing | alpha channels differing |
|---|---:|---:|
| reading 1: reversed y positions | **0** | 14,319,616 |
| reading 2: reversed colour order | **0** | 14,319,616 |
| control: stack C drawn correctly | 30,388,224 | 14,319,616 |

Readings 1 and 2 differ from aliasing in **alpha only**. Both permute the same
four colours into the same four places, so their RGB is bit-identical to stack
A's; the one thing they cannot reproduce is stack A's unblended alpha. And the
blit composites with `SRC_ALPHA / ONE_MINUS_SRC_ALPHA`, so that channel is
visible on screen.

Render-target alpha by band on `1_ADD_1`:

| model | band 0 | band 1 | band 2 | band 3 |
|---|---:|---:|---:|---:|
| reading 1: reversed y positions | 255 | 255 | 255 | 255 |
| reading 2: reversed colour order | 255 | 255 | 255 | 255 |
| reading 3: stack A's render target | **221** | **221** | **221** | **221** |
| control: stack C drawn correctly | 255 | 255 | 255 | 255 |

221 is `0xDD`, the source alpha written straight. 255 is `clamp(221 + 51)`,
stack C's blend against the 51-grey checker. The blit's alpha is
`(a*a + 255*(255-a) + 127)//255`, so a render target at 221 lands on screen at
**226** and one at 255 lands at **255**.

Measured on `1_ADD_1`, the capture the issue was filed from: the golden's four
bands read alpha **255**, ours read alpha **226** in all four. That is 221 at
the render target, to the digit. Readings 1 and 2 both predict 255.

## Scores

`swatchorder50_readings.py --score`, stack C region, all four models. See the
PR body for the table; the shape is that readings 1 and 2 score identically to
each other and near zero, the aliasing model takes essentially everything, and
the goldens (control) invert it -- they match the correct-stack-C model and
nothing else, which is what says the models are right rather than that the
comparison is loose.

## What the next lane should not repeat

- **Do not build the unequal-height disc variant for #50.** It separates two
  models that are both refuted. It would have returned "neither", at ~90
  minutes of device time, and a result matching neither reading is exactly what
  the offline measurement already returns for free.
- **Do not re-derive the five dead mechanisms**, and do not re-derive reading 1
  or reading 2 either -- they are now dead on the same evidence.
- **The brief's premise was stale.** It describes "the one existing capture";
  there have been 1,568 on disk at `~/hakux-work/res_oldblend` since
  2026-09-12, and `nv2a_issues.toml`'s own `status_note` already recorded the
  aliasing finding and the landed flush. A brief asserting scarcity is a claim
  worth testing before spending a device on it.
- **The geometry test alone proves nothing here.** `--geometry` shows band
  boundaries at the same rows in ours and the golden, which is true under
  reading 1, reading 2 and aliasing alike. It is not a discriminator, despite
  looking like the obvious one.

## Still open, and not this lane's

The fix `771c8eb4f1` ("record queued draws before a synchronous surface
download") is an ancestor of `origin/master`. Two things it does not settle:

- **`0_ADD_1` is the one capture where our stack C is bit-exact**, and it is
  both the first `TestDetailed` capture of the run and the only one whose
  stack-C draws are a mathematical no-op. Named, not explained.
- Whether the flush actually moves the 1,567 on device is an arm nobody has
  run against this lane's models. `--score` gives it a ready oracle: after the
  fix, our stack C should match **the correct-stack-C control** and stop
  matching the aliasing model.

Also noted in passing, not acted on: `771c8eb4f1`'s subject carries the retired
skip-ci marker.

## Reproduce

    docs/testing/swatchorder50_readings.py --equivalence
    docs/testing/swatchorder50_readings.py --score
    docs/testing/swatchorder50_readings.py --bands 1_ADD_1

No device, no build, no ISO. Captures `~/hakux-work/res_oldblend` (1,568),
goldens `/home/justin/goldens/results/Blend_tests`.
