# Prediction: `Texture_anisotropy`'s residual is the HOST's filtering algorithm, not a value we set

Registered 2026-09-15, BEFORE the measurement below. Not edited afterwards.

## Established first, so this is not speculation

- **Deterministic, not a flake.** Eleven runs across three binaries give
  byte-identical per-capture totals (24 / 73,492 / 94,945 / 96,691 = 265,152);
  the corpus binary `d7dfe146` gives 265,112. The run-twice rule is satisfied
  eleven times over, from captures already on disk -- no emulator run spent.
- **`Anisotropy-1` is effectively exact** (24 channels = 8 pixels) while
  2 / 4 / 8 cost 73,492 / 94,945 / 96,691. The residual appears only when
  anisotropic filtering is switched on, and is monotone in the level.
- **Both backends decode the register identically** and correctly:
  `1 << GET_MASK(NV_PGRAPH_TEXCTL0_0, MAX_ANISOTROPY)` gives 1/2/4/8
  (`gl/texture.c:703`, `vk/texture.c:1444`). `Anisotropy-1` being exact
  independently confirms the decode.
- **The host supports the feature well past what the test asks.** Probed the
  same llvmpipe the runs use (Mesa 25.2.8, LLVM 20.1.2) through a surfaceless
  EGL context: `GL_EXT_texture_filter_anisotropic` **advertised**, and
  `GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT` = **16.000**. So the clamp at
  `gl/texture.c:644-646` is a no-op for 1/2/4/8 and the sampler is being told
  the right number.

## Hypothesis

**H:** what is left is the *anisotropic filtering algorithm* -- implementation-
defined in the GL spec, and different in llvmpipe than in NV2A silicon. Nothing
this lane sets is wrong; the sampler is configured correctly and the host filters
differently.

If H holds, the suite is **not actionable from this lane**: matching it would
mean emulating NV2A's filter in the fragment shader, i.e. `glsl/psh.c`.

## The decisive prediction

- **P1 -- we respond to the setting.** Using the manipulation-response
  instrument that settled `Attrib_carryover`: measure how far each of
  `Anisotropy-2/4/8` moves from `Anisotropy-1`, **on our side and on hardware's
  side separately**. Under H both sides move substantially and by *different*
  amounts (different algorithms, same knob).
  **KILL:** if our side moves **less than 5%** as far as hardware's does, the
  setting is not reaching the sampler and this **IS** an in-lane bug -- H is
  wrong and `gl/texture.c` is where to fix it.

- **P2 -- it looks like filtering, not structure.** The magnitude distribution
  is broad rather than a ±1 floor or a saturated swap: **fewer than 50%** of
  differing channels at |d| <= 2, and the differing region is a large contiguous
  area rather than an exact subset of the image.
  **KILL:** a ±1 floor (>80% at |d| <= 2) or an exact geometric subset would say
  this is quantisation or a structural error, not a filtering algorithm.

- **C1 (control).** `Anisotropy-1` must stay near-exact under whatever framing
  survives. If a proposed mechanism would also move `Anisotropy-1`, it is wrong.

## The uncomfortable outcome, named in advance

**P1 fails** -- our side barely moves. That would mean I had the host
capability, the decode and the clamp all verified and still missed that the
sampler parameter never reaches the texture, which is exactly the kind of thing
`Anisotropy-1` being exact could mask. I would rather find that than write
another "not actionable" note, so P1 is the first thing measured.

The likelier uncomfortable outcome: **P1 and P2 both hold**, and this becomes the
**sixth** lead resolving to `glsl/psh.c`. That is a real result -- the suite is
characterised and the reason is a host property, not a defect -- but it closes
the only high-ranked in-lane candidate the re-triage found, and leaves the lane
with nothing unblocked at the top of the ranking. I should say that plainly
rather than reaching for a smaller target to look busy.
