# `Texture_anisotropy`: the sampler is configured correctly and the HOST filters differently

`Texture_anisotropy` was the one high-ranked suite the corpus re-triage found
that was both unexplored **and** in this lane — `gl/texture.c` and
`gl/renderer.c` are the only GL files that touch anisotropy. 4 captures,
265,112 channels, 66,278 per capture.

Nothing in this lane is set wrong. The residual is the host's filtering
algorithm, and the suite is not actionable from here.

Every number reproduced by
`docs/testing/anisotropy_pivot.py <pgraph_run_root> <goldens_root>`.

## The run-twice rule, satisfied from data already on disk

The re-triage's standing rule is that no candidate gets attributed on a single
run. Eleven runs carrying this suite were already captured, across three
binaries:

| binary | runs | per-capture channels | total |
|---|---:|---|---:|
| `0.3.3-j1-104-gc43f5f8` | 2 | 24 / 73,492 / 94,945 / 96,691 | 265,152 |
| `0.3.3-j1-106-gc44c43d` | 5 | 24 / 73,492 / 94,945 / 96,691 | 265,152 |
| `0.3.3-j1-111-g2d3bcad` | 4 | 24 / 73,492 / 94,945 / 96,691 | 265,152 |
| `0.4.0-j1-331-gd7dfe146` (corpus) | 1 | 42 / 73,493 / 94,940 / 96,637 | 265,112 |

**Byte-identical across eleven runs.** Two distinct totals over twelve runs, and
the pair differ by 40 channels. This is deterministic — the opposite of
`Window_clip` — and **no emulator run was spent** establishing it.

## The shape of it

| capture | channels | differing px | share of frame |
|---|---:|---:|---:|
| `Anisotropy-1` | **24** | **14** | 0.00% |
| `Anisotropy-2` | 73,492 | 24,908 | 8.11% |
| `Anisotropy-4` | 94,945 | 32,098 | 10.45% |
| `Anisotropy-8` | 96,691 | 33,160 | 10.79% |

**With anisotropy off we are effectively exact** — 14 pixels, clustered near the
horizon. It appears only when the feature is switched on, and is monotone in the
level. That alone confirms the register decode: a wrong decode would move
`Anisotropy-1` too.

The differing pixels sit in rows **y[245..364]** across the full width — the
receding ground plane, which is exactly the region an anisotropy test is built
to stress. (`texture_anisotropy_tests.cpp`: *"The texture is repeated a number
of times to guarantee that anisotropy will have a visible effect."*)

## Four things checked before blaming the host

1. **The decode is right, and identical in both backends.**
   `1 << GET_MASK(NV_PGRAPH_TEXCTL0_0, MAX_ANISOTROPY)` gives 1/2/4/8 at
   `gl/texture.c:703` and `vk/texture.c:1444`. The field is 2 bits (`0x30`).

2. **The host supports far more than the test asks.** Probed the *same*
   llvmpipe the runs use (Mesa 25.2.8, LLVM 20.1.2 — from the run log's
   `GL_RENDERER`) through a surfaceless EGL context:
   `GL_EXT_texture_filter_anisotropic` is **advertised**, and
   `GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT` is **16.000**. So the clamp at
   `gl/texture.c:644-646` is a no-op for every level the test uses. Measured,
   not assumed — this was the one way the suite could have been an in-lane bug.

3. **No Android divergence on this path.** `gl/texture.c` has ten
   `#ifdef __ANDROID__` blocks and the two nearest the anisotropy call
   (`:629`, `:655`) are both about **texture border clamp**. The anisotropy
   block at `:643-651` is unconditional.

4. **The setting reaches the sampler — emphatically.** P1, registered before
   measuring: how far each level moves from `Anisotropy-1`, **measured on our
   side and hardware's side separately**:

   | level | ours moves | hardware moves | ratio |
   |---|---:|---:|---:|
   | `Anisotropy-2` | 81,297 | 46,578 | **1.75×** |
   | `Anisotropy-4` | 97,131 | 66,115 | **1.47×** |
   | `Anisotropy-8` | 99,777 | 67,907 | **1.47×** |

   The kill condition was ours moving **less than 5%** as far as hardware's,
   which would have meant the parameter never reached the texture. Instead we
   move **half again to three-quarters again as much**. llvmpipe's anisotropic
   filter changes the image *more* than NV2A's does at the same setting.

## It is a filter difference, not quantisation

P2, also registered first: of 265,112 differing channels, only **11.30%** are at
|d| ≤ 2 (the prediction needed < 50%), the distribution is flat across small
magnitudes (5.7%, 5.6%, 5.3%, 5.7%, 5.4%, 4.5% …) and **max |d| is 204**. That
is a continuous difference over a filtered region — not a ±1 floor, not a
saturated swap, not an exact geometric subset.

## Conclusion, and what it costs

The GL specification leaves the anisotropic filtering *algorithm*
implementation-defined; so does Vulkan. We ask llvmpipe for N× anisotropy, it
obliges with its own algorithm, and NV2A silicon used a different one. **There
is no value in `gl/texture.c` that would close this**, and the evidence that
there isn't is positive rather than absence-of-evidence: the decode is right,
the host's limit is 16, the clamp is inert, and we respond to the knob more
strongly than hardware does.

Matching it would mean emulating NV2A's filter in the fragment shader —
`glsl/psh.c`, `[free]`, and the grant already wanted by five other leads.
**Six now.**

**And this closes the only high-ranked in-lane candidate the re-triage found.**
I named that as the likely uncomfortable outcome when registering the
prediction, so I will state it plainly rather than reaching for a smaller target
to look busy: at the top of the corpus ranking, this lane currently has nothing
unblocked. The remaining unresolved rows (`Blend_surface` 114,378,
`Texture_DXT` 74,579, `Texture_format` 54,791, `Surface_format` 52,029,
`Attrib_float` 50,893, `Bump_env_lum` 56,710) have not had their fix sites
resolved yet, and that resolution — not another baseline — is the next step.
