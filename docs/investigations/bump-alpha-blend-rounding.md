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

## The host divides by 256, not 255

Work the same blend in integers, as a rasteriser does:

```
  S*A + D*(255-A)  =  127*127 + 254*128  =  48641

     48641 / 255  =  190.749020   ->  191     silicon
     48641 / 256  =  190.003906   ->  190     us
```

A divide by 256 instead of 255 — the standard fixed-point blend shortcut,
since a shift is free and a divide by 255 is not — lands on 190 under *either*
rounding rule. It needs no appeal to tie-breaking or float error, and it
explains the rest of the evidence: `x/256 <= x/255` always, so this renderer
can only ever be low, which is exactly the **8.6:1 one-sided** RGB deltas in
the same quad.

This is not the near-tie explanation that fits elsewhere in the corpus.
`blend-unit-model.md` found the host landing on 33.99999797 where silicon has
34; that is float error at a boundary. 190.749 is nowhere near a boundary.

## Two backends, one rasteriser — a check that does not count

Running the same disc through the OpenGL renderer gives 190 on all 111,496
pixels, identical to Vulkan. I initially read that as two independent
implementations agreeing, which would have been strong evidence. **It is not
evidence at all**: lavapipe is a Vulkan front end built on llvmpipe, so both
paths land in the same Mesa rasteriser and the same blend arithmetic. The
agreement is what you would predict either way. Recorded so nobody spends a
run re-confirming it.

## Where that leaves it, and a convergence worth acting on

Nothing between the combiner and the framebuffer is ours to round: the
attachment is `UNORM8`, the blend is fixed-function, and the capture is a byte
copy out of guest memory. It is not reachable from blend state either — the
equation is `src*sf + dst*df` with no free additive term, so there is no way
to inject the missing fraction; a source-side bias of d moves the result by
`As*d`, not by a fixed amount.

The remedy that does reach it is **blending in the shader** — and that is the
same remedy `signed-blend-equations.md` concluded #43 needs, for an unrelated
reason (Vulkan cannot express a wrap, and fixed-point attachments clamp the
source before blending). So one architectural change would cover #43's
6,499,076 non-precision channels over 30 captures *and* this 6.46M px. That
is the argument for doing it, and it is a decision for the user rather than
something to start unasked.

**One number settles the diagnosis first.** On a host whose blend divides by
255, this quad's alpha reads 191. That is a single pixel on a single capture,
and the device lane is already producing the capture set that answers it.
