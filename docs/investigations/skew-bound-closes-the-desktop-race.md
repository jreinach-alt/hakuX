# #44's skew bound closes the desktop race, and GL then equals Vulkan byte for byte

`Surface_pitch::Swizzle` has been this lane's only run-to-run-unstable
capture, and
[`gl-surface-to-texture-is-wrong.md`](gl-surface-to-texture-is-wrong.md)
traced it to the guest overwriting one shared texture buffer under a queued
draw. #79 was since diagnosed as #44's guest↔pgraph skew on *vertex* data,
closed on device by `HAKUX_FIFO_SKEW_BOUND`. The two were suspected to be one
family. They are, and it is testable on the desktop with no device and no code
change: the bound lives in `pfifo.c`, is renderer-agnostic, and is read from
the environment.

Registered first in
[`../testing/predictions/skew-bound-closes-swizzle.json`](../testing/predictions/skew-bound-closes-swizzle.json).

## The result

Binary built from the peer branch `80512e37`, which carries the bound and
none of this lane's fixes. Two-test disc, OpenGL, three runs per arm, caches
cleared between every run.

| `HAKUX_FIFO_SKEW_BOUND` | scores over three runs | distinct captures | wall clock |
|---|---|---:|---|
| **0** (off, default) | 15,360 / 13,056 / **11,392** | **3** | 16–18 s |
| **1** (every submission) | 10,240 / 10,240 / 10,240 | **1** | 97–105 s |
| **2** (draw-carrying only) | 10,240 / 10,240 / 10,240 | **1** | 99–107 s |

`Pixel_shader::Passthru`, the other test on the disc, is byte-stable in all
three arms — the control that says the bound is not simply changing
everything.

**The bound closes it.** Three distinct images become one, on both modes.

## And GL converges on Vulkan's exact image

The bound=1 and bound=2 captures hash to **`15845fa9e1e40032`**. That is the
*same digest* this lane recorded for **Vulkan** earlier, five runs, at the
same 10,240:

> | Vulkan | 5 | 10,240 ×5 | one digest, `15845fa9e1e40032` |

So with the skew bound on, OpenGL produces **byte-for-byte the image Vulkan
produces**, on a tree carrying neither this lane's #66 nor #71 fixes. That
retires an open question: Vulkan was never immune, it was losing the same race
*reproducibly*, and 10,240 is what both renderers give once the race is out of
the way. Everything above 10,240 was the race.

It also bounds the noise floor's cause completely. The measured GL band —
15,360 down to 11,392 here, and 14,848 with 2,341 px moving at a constant
score on the full disc — is this one hazard and nothing else.

## The positive control, because silence would have proved nothing

The `fifoskew` line that reports the active mode goes through
`__android_log_print`, so on the desktop there is no log confirmation that the
environment variable took effect, and a null arm would have been
indistinguishable from an unset variable. The control is wall clock:
**16–18 s becomes 97–105 s**, a six-fold cost that no configuration mistake
produces. The bound demonstrably ran.

## Where the prediction was wrong

Mode 2 was registered before it ran, predicting that it closes the
instability **and costs materially less**, since it holds only segments that
carry a draw.

**Half right.** It closes it, at the same 10,240 and one digest. It is **not
cheaper** — 99–107 s against mode 1's 97–105 s, within noise of each other.

That is a useful negative for whoever tunes the bound's cost: on this
workload essentially every published segment carries a draw, so the
draw-only filter buys nothing. The six-fold cost is not an artefact of
holding too often; it is what holding costs here.

## What this does not say

It does not close #39. #39 is a *lost draw* on the device lane, at 7 of 13
runs on `Stencil`; this is one desktop capture whose *content* varied. They
share a mechanism and the same remedy closed both, which is evidence they are
one family and not proof.

It does not recommend turning the bound on. A six-fold slowdown is a
product decision, and `pfifo.c`'s own comment already says as much. What it
does is make the trade-off measurable off-device: correctness-of-timing costs
6× on this disc, and the draw-only mode does not reduce it.

The residual 10,240 px is not this hazard. It is whatever `Surface_pitch::Swizzle`
still gets wrong once the race is gone, on a tree without #66, #71 or #51.
