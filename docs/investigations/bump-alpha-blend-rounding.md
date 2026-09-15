# 6.46M px behind one number: alpha 190 where hardware says 191

`Bump_env_lum` and `Bump_map` together are the largest single-cause block in
the corpus, and the cause is one constant.

## What the captures say

The scorer compares RGBA, so a defect living entirely in alpha is invisible to
an RGB diff. That is what this is.

| | |
|---|---|
| `Bump_env_lum` captures wrong | **40 of 40, by an identical 111,496 px each** |
| of those alpha pixels at exactly \|delta\|=1 | **4,459,840 of 4,459,840 — 100%** |
| `Bump_map` alpha pixels at \|delta\|=1 | 2,002,670 of 2,249,809 (89%) |
| distinct (ours, gold) alpha pairs in `Bump_env_lum` | **1** |

That single pair is **ours 190, gold 191**. The alpha-wrong mask is
byte-identical across `A8`, `A8R8G8B8`, `Y16`, `DXT1` and `A1R5G5B5` — it does
not depend on the texture format at all, because it does not come from the
texture. Every RGB-wrong pixel lies inside the same quad (rgb-only = 0), and
the RGB deltas are 8.6:1 one-sided in the same direction (+1 appears 1,362,434
times against 157,832 for -1).

## The blend state, traced rather than assumed

My first reading of this was wrong twice over, so the state was measured. Two
instrumentation attempts returned nothing — the pipeline-creation path in
`draw.c` is legacy (pipelines are built in `compile_worker.c`) and qemu's
stderr does not reach the run log — which is worth knowing for the next person
who tries to trace this. Writing to a file from the dynamic-blend path works.

The bump disc uses five distinct blend states, and the relevant one is
`sf=4 df=5 eq=2`: **SRC_ALPHA / ONE_MINUS_SRC_ALPHA, FUNC_ADD**.

## The arithmetic is pinned, and it rules out a precision wobble

TEX1 is a fixed `A8R8G8B8` checkerboard with alpha `0x7F`; the surface is
cleared to `0xFE202020`, so the destination alpha is 254. Blending gives

```
  As = 127/255,  Ad = 254/255
  result = As*As + (1 - As)*Ad
         = (16129 + 32512) / 65025
         = 48641 / 65025      ->   48641/255 = 190.749020 as a byte
```

`round` is 191, which is what the golden holds. **190.749 is also the global
minimum of that expression over every possible source alpha** — the vertex sits
at exactly As = 0.498 — so no error in what we feed the blender can put the
true result below 190.5. Whatever produces 190 is downstream of the inputs.

## CORRECTION: my divide-by-256 mechanism was wrong

I first concluded the host divides by 256 rather than 255, because
`48641/256 = 190.004` lands on 190 under either rounding rule and a /256 blend
always undershoots, which also fit the one-sided RGB deltas. **That is not what
is happening, and the test that kills it was available locally the whole time.**

`blend_model.py` scores a capture directory against a model of silicon with a
choice of quantiser at each store. Scoring *our own* captures:

| blend store | blit store | matches our captures |
|---|---|---|
| **round** | **round** | **16,625 / 18,000** |
| floor | round | 15,479 |
| /256 round | round | 11,301 |
| /256 floor | round | 8,828 |

If this renderer divided by 256 at the blend store, a /256 model would fit it.
It fits far worse. **Our blend store rounds, to /255, like silicon.**

Two further checks close off the obvious alternatives:

- **The combiner alpha is not the culprit.** Forcing blending off makes the
  quad's alpha exactly **127** — TEX1's alpha, as expected. So the blend
  framing was right: the inputs really are As = 127, Ad = 254, and the
  arithmetic really does have 190.749 as its answer.
- **float32 does not explain it.** Working the blend in float32 the way a host
  would gives 190.749004, which still rounds to 191. The gap to 190.5 is 0.25;
  no float32 rounding reaches it.

So the mechanism inside Mesa is **unidentified**. I am not going to offer a
third theory. What is established is that the exact answer is 190.749, our own
blend model says that rounds to 191, and this host produces 190.

## Settled on hardware: it is the host

The device lane ran it on Adreno: **`BumpEnvLum_A8R8G8B8`, `_A8` and `_Y16` all
differ from the goldens on zero alpha pixels.** The same renderer on a real GPU
gets 191 and these captures come out right.

That makes the diagnosis conclusive without needing Mesa's internals: the
6.46M px are a property of the desktop lane's software rasteriser, not of this
emulator.

## What that changes about target selection

This is the part with consequences. **The desktop lane's corpus ranking counts
6.46M px that do not exist on real hardware.** `Bump_env_lum` at 4.46M and
`Bump_map`'s 2.0M alpha px are host artefacts of lavapipe, so both suites
should drop a long way down any ranking built here, and any future ranking on
this lane should exclude them rather than re-derive them as targets. That is
the second time these two suites have been ranked as work that isn't there --
they were also the queue I had to retract as "YUV plus a boundary floor".

## Where that leaves it, and a convergence worth acting on

Nothing between the combiner and the framebuffer is ours to round: the
attachment is `UNORM8`, the blend is fixed-function, and the capture is a byte
copy out of guest memory. It is not reachable from blend state either — the
equation is `src*sf + dst*df` with no free additive term, so there is no way
to inject the missing fraction; a source-side bias of d moves the result by
`As*d`, not by a fixed amount.

Nor does it need to be reached. Adreno already renders these captures
correctly, so there is nothing here for the emulator to fix. **The earlier
claim in this document that a shader-side blend would recover 6.46M px
alongside #43's is withdrawn** -- those px are not real outside this lane, and
#43's case for shader-side blending has to stand on its own 6,499,076
non-precision channels, which it may well do.
