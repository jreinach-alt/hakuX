# What is left of #4, and the two wrong numbers on the board for it

Written 2026-09-12 from captures already on disk, on the lavapipe lane. No
device time and no build: every figure below is a direct comparison of a
capture in `/home/justin/hakux-work/` against its golden in
`/home/justin/goldens/results/Texture_render_target/`.

`Texture_render_target` currently carries two figures in the repo, 16x apart,
and both are wrong in different directions. The larger one ranks #4 first on
the structural axis, above `Blend tests`. It is the `RenderTextureLoop`
contamination of #27, reproduced to the channel. The smaller one is real but
stale: four fifths of it is the YUV decode, which was fixed the same day. The
figure that survives both corrections is 88x below the larger one.

## Summary

| figure | source | what it actually is |
|---|---:|---|
| 9,034,555 channels, 1 of 41 exact | `corpus-reranked-by-structure.md` (`01151f7fc6`) | a disc with `RenderTextureLoop` **included**: every later test renders the whole quad wrong |
| 563,668 channels, 11 of 40 exact | `run-2026-09-12-corpus-classes.tsv` | a no-loop disc, correct when written, but predates the YUV fix `52defa5b` |
| **≈102,758 channels, 13 of 40 exact** | predicted below | no-loop disc on the current build |

Of that remainder, **DXT1 is 99,769 channels (97.1%)** and the texel tie is
**2,989 (2.9%)**. Nothing else in the suite differs at all.

## MEASURED: the 9,034,555 figure is the loop contamination

`01151f7fc6` reports "measured directly on the current build, 41 captures from
`iso_rtt.iso`: 1 exact, 9,034,555 differing channels" and concludes the corpus
TSV is wrong by sixteen times and the suite "was never near-exact".

Scoring the two kinds of capture set on disk against the same goldens:

| capture set | captures | exact | differing channels |
|---|---:|---:|---:|
| `res_rt_0cb0` (loop **included**) | 41 | **1** | **9,034,555** |
| `res_probe_rt` (no-loop config) | 40 | 5 | 754,460 |
| `res_v_rt` (no-loop config) | 40 | 5 | 752,908 |

The 9,034,555 is reproduced **exactly**, to all seven digits, from a
loop-included set. That is not a coincidence: in the contaminated regime the
output is deterministic, because the stage is disabled and the quad comes out
flat.

The signature is unambiguous in the per-capture numbers:

| capture | `res_rt_0cb0` (loop) | `res_v_rt` (no-loop) |
|---|---:|---:|
| `RenderTextureLoop` | **0 px — pixel-exact** | not present |
| `TexFmt_A8` | 81,225 px | **0** |
| `TexFmt_A8_L` | 81,225 px | **0** |
| `TexFmt_A4R4G4B4` | 81,225 px | **0** |
| `TexFmt_A1R5G5B5` | 81,225 px | 19,224 px |

**81,225 px is the whole quad**, and it is the count every `TexFmt_*` capture
differs by in the loop-included set — while `RenderTextureLoop` itself, the
test that runs first, is pixel-exact. That is #27 verbatim: the loop test ends
with `texture_stage.SetEnabled(false); SetShaderStageProgram(STAGE_NONE)`, the
40 `TexFmt_*` tests never set the stage up themselves, and `RunAll` iterates
alphabetically so the loop goes first. The whole suite after it renders with
no texture stage.

So the correction in `01151f7fc6` inverted the truth: the TSV was measuring the
meaningful disc and the "direct read" was measuring the poisoned one.

### The "2.8x lane gap" it left open is channels versus pixels

That commit closes on an open question: "the device lane measures the same
suite at 3,209,634 on Adreno... Both are direct measurements, 2.8x apart, and
that gap has to be settled before either is used as a target size."

It is settled, and it is not a lane disagreement. Scoring `res_rt_0cb0` both
ways:

| | value |
|---|---:|
| differing **channels** | 9,034,555 |
| differing **pixels** | **3,209,634** |
| ratio | **2.815** |

Both figures are the same 41 captures of the same loop-included disc, counted
in different units. The three Sep 12 dispatch capture sets are byte-identical
to each other for this suite and give 3,209,634 px as well, so there is no
host disagreement to settle and no 2.8x gap: there is one contaminated
measurement reported twice.

### Why its own staleness check did not catch this

That commit checked its result against captures from two days earlier and got
9,192,290, and concluded from the agreement that "the suite was never near-
exact". Both sets are loop-included, so they agree because they share the
contamination — the degenerate comparison that confirms two rival explanations
at once. The check that separates them is loop-included versus no-loop, not old
versus new.

### The live consequence

`target-ranking-2026-09-12.md` ranks this suite 11th at 308,248 non-precision
channels. `corpus-reranked-by-structure.md` would move it to **1st, above
`Blend tests`' 6,499,208**. On the corrected figure it belongs near the
**bottom** of that table: 308,248 − 247,774 (the two YUV captures, now fixed)
= **60,474**, below `Fog carryover`'s 94,000.

## MEASURED: the YUV half of #4 is already fixed

`52defa5bf1` / `57d12c8501` ("hardware rounds each YUV term separately, not the
sum") landed 2026-09-12. In `res_texfmt`, captured after it:

| capture | corpus TSV | after the fix |
|---|---:|---:|
| `Texture_format::TexFmt_UYVY_L` | 388,150 | **0 — pixel-exact** |
| `Texture_format::TexFmt_YUY2_L` | 388,150 | **0 — pixel-exact** |
| `Texture_format::TexFmt_DXT1` | 167,889 | 167,889 (max delta 8) |

`Texture_render_target`'s two YUV captures are 230,455 channels each in every
no-loop set on disk, all of which predate the fix. They decode the same source
format through the same path, so the fix is expected to take them to zero as
well — **INFERRED, not measured**: no post-fix no-loop capture of this suite
exists on disk, and that is the one measurement that settles it.

This also retires the line of work the issue history opens up for YUV — "this
suite cannot settle it, the gradient is rank-deficient, go to `pvideo`". It did
not need `pvideo`; it needed the rounding site. And the `pvideo` goldens are not
on disk in any case.

### A negative worth recording: the bump suites are not the YUV instrument

`BumpMap_UYVY_L`, `BumpEnvLum_UYVY_L` and their YUY2 twins are large (279,621
and 334,488 channels) and look like a second instrument for a YUV rule. They
are not: `golden_colours` is **2** for all four. The golden holds two colours
over the whole region we differ in, so it scores every model identically. Any
YUV rule fitted to them is unfalsifiable by the capture that motivated it —
the `unfalsifiable-goldens.md` failure mode.

## MEASURED: the tie residue is one row, and it is the v-tie

The 26 `boundary-shift` captures hold 2,989 channels between them. In
`res_v_rt`, per capture:

| capture | px | rows differing | band height | columns |
|---|---:|---|---:|---|
| `TexFmt_A8R8G8B8` | 71 | **240 only** | **1** | 392–462 |
| `TexFmt_A8B8G8R8` | 71 | **240 only** | **1** | 392–462 |
| `TexFmt_R8B8` | 71 | **240 only** | **1** | 392–462 |
| `TexFmt_SZ_Index8_p256` | 53 | **240 only** | **1** | 393–462 |
| `TexFmt_AY8` | 12 | **240 only** | **1** | 396–461 |

And on that row, over the **whole** band rather than a sampled pixel:

- ours == `gold[row + 1]`: **100.0%**
- ours == `gold[row - 1]`: **0.0%**

The 71-column extent is **not** the extent of the defect, and this is worth
stating because the pixel count invites the wrong reading. Sweeping the whole
quad width rather than the differing columns:

- on row 240, `ours == gold[241]` for **285 of 285 columns, 100%**;
- the golden itself has `gold[240] == gold[241]` at **214 of 285 columns
  (75.1%)**, so the shift is simply invisible there;
- the 71 observable columns are exactly the 24.9% where the golden's content
  changes between those two rows.

So **row 240 is wholly shifted and only a quarter of it is observable.** The
shift is also not global: sweeping all 285 quad rows, row 240 is the **only**
row where `ours[y] == gold[y+1]`, and the other 284 rows match their own
golden at zero differences. One row, entirely, and no other.

Row 240 is v = 128.0, the exact texel boundary at the quad's vertical centre.
We resolve that tie up to texel 128; hardware resolves it down to 127, which is
the opposite of how it resolves the identical tie in u on the same quad. That
asymmetry is hardware's and is already recorded in `edge-defect.md`, along with
why a one-directional v bias cannot be justified as modelling it: hardware's
v-ties go down at texels 40, 80 and 120 and up at 160, 200 and 240.

The u half of this was fixed and landed (the texel-tie bias in `glsl/psh.c`,
which took column 320 out of all 24 affected captures on both lanes). What is
left is the v half, it is host-independent — 71 px on row 240 on lavapipe and
71 px on row 240 on Adreno 740 — and it sits against the measured ceiling of
the bias method: the closest genuine near-boundary coordinate in this content
is 0.002188 texels away, the shipped bias is 0.00098, so there is about 2.2x of
headroom and a uniform bias cannot tell "exactly on the boundary" from "0.002
below it" at all.

**So this 2,989 channels is a precision floor, not a defect**, and the right
disposition is to leave it classified rather than chase it. It is 2.9% of what
remains in the suite.

## MEASURED DEAD: four mechanisms in the Vulkan surface path

#4 is named "render-to-texture diverges from silicon", so the surface path was
the first place to look. Four candidate mechanisms, all measured dead:

**1. The GPU tile address map cannot reach a 3D render.** `d42a8d79bc` names a
standing hazard: only a blit's destination is remapped, and "3D renders and
scanout still treat tiled memory as linear". For this suite that hazard does
not exist, because *nothing outside `blit.c` consults a tile at all* — a grep
for tile symbols across `hw/xbox/nv2a/pgraph/` returns hits in `gl/blit.c` and
`vk/blit.c` and **nowhere else**. There is no partial remap for a 3D render to
be inconsistent with. The suite also never blits.

**2. The render-then-sample dependency is present and correct.** A colour
surface sampled as a texture is bound directly, in `VK_IMAGE_LAYOUT_GENERAL`,
with no layout change — so `pgraph_vk_transition_image_layout`'s
`oldLayout == newLayout` early return emits no barrier. That is a real sharp
edge and it has cost this project bugs before (#34 finding 4, #29), but
`bind_surface_as_texture` hand-rolls the GENERAL→GENERAL barrier it needs,
`COLOR_ATTACHMENT_WRITE` → `SHADER_READ` across
`COLOR_ATTACHMENT_OUTPUT` → `FRAGMENT_SHADER`, after ending the render pass.
The two upload sites in `surface.c` do the same. Nothing is missing.

**3. The swizzle compute path is not reachable with the wrong element size.**
`pgraph_vk_compute_swizzle`'s shader indexes `uint[]`, so it moves 4 bytes per
texel regardless of the surface format, and takes no bytes-per-pixel argument.
Both callers gate on `surface->fmt.bytes_per_pixel == 4`, so the mismatch
cannot be reached. (Worth keeping in mind if a 16-bit swizzled surface path is
ever added; the API is element-size-blind.)

**4. The diagnostic download is not the capture path.** `diag_download_surface`
in `vk/renderer.c` is reached only through `nv2a_dbg_set_rt_dump_path`. The
harness captures come out of guest VRAM via `extract_results.py` on `hdd.img`,
so a defect there could not appear in these goldens comparisons.

**5. And it is not a memory-layout artefact of any kind.** The differing band
is exactly **1 pixel tall** in all 26 captures, and there is no location in any
capture where it is 2 px tall or has a 2x2 footprint. A tiling or block-address
defect cannot produce a one-pixel band that equals its neighbour row; it
produces rectangles.

Tested properly rather than by eye, on transition-edge alignment — the position
of the difference mask's edges modulo a block size, against the chance level of
1/B. `DXT1` gives 12.2/6.9/3.4/1.7% at B = 8/16/32/64 against chance levels of
12.5/6.2/3.1/1.6%: **exactly chance, no alignment at any block size.** The YUV
captures have **zero** mask transitions — the difference is uniform over the
whole quad, so there is no block structure to align. The 16-bit formats do show
25% at B = 8 and 12.5% at B = 16 and 32, but **0.0% at B = 64**, and a real tile
artefact aligns at 64 above all; that periodicity is the 5-bit quantisation
banding of a ramp upsampled 285/256 ≈ 1.113 px per texel, period ≈ 8–9 px.

One near-miss worth naming so it is not rediscovered: the population-A span maps
to texel columns 192..255, which is exactly 64 texels on a 64 boundary and reads
as a tile signature. It is not one — those are just the columns where the test
pattern's gradient changes between rows 240 and 241, per the sweep above.

## Falsifiable prediction

Build the current tree and run the no-loop disc
(`docs/testing/configs/texture_render_target-no-loop.json`). **Do not score the
newest captures on disk**: the three Sep 12 dispatch sets under
`dispatch/results/*/captures1` are 41-capture loop-included runs, byte-identical
to each other and to the Sep 9 set for this suite's quad despite every
intervening code change. The newest usable set is `res_v_rt` (Sep 11 21:14),
and a fresh isolated sweep is already queued at
`dispatch/queue/z-sweep-085-Texture_render_target.req`, which would supersede
it. Then:

- **`Texture_render_target` should measure ≈102,758 differing channels with 13
  of 40 exact**, not 9,034,555 with 1 of 41.
- `TexFmt_UYVY_L` and `TexFmt_YUY2_L` **must go 230,455 → 0**. If they do not,
  the YUV fix does not transfer through a render target and that is a new
  finding about the surface path.
- `TexFmt_DXT1` **must stay at 99,769** (max delta 8). It is unrelated.
- The 26 boundary-shift captures **must stay exactly as they are**, 2,989
  channels on row 240. Nothing in this document changes them.
- Running the **loop-included** disc must still give 9,034,555 / 1 exact. That
  number is real; it is just not a measurement of this emulator's
  render-to-texture path.

## What #4 reduces to

1. **DXT1**, 99,769 channels, 97.1% of the remainder. Already root-caused on
   the issue: the block decode is intact (the nearest palette entry is the one
   the 2-bit index encodes, 1024 of 1024 texels), and each texel is then
   perturbed with the −0.5 mean and the 2.33/1.13/2.27 per-channel spread of an
   R5G6B5 truncation. The dither was not identified and is not a function of
   texel position mod 2, 4 or 8. Blocked on a device dump of what the texture
   unit emits, or content that isolates the dither. `Texture_DXT` is the better
   instrument (1:1, plasma, `golden_colours` 1,019).
2. **The v-tie**, 2,989 channels, a precision floor at the measured ceiling of
   the bias method. Leave classified.
3. **Nothing else.** No capture in the suite differs outside those two.

So the issue title is wrong in a specific way worth saying: after the YUV fix,
**there is no residual that is specific to rendering into a texture**. Every
remaining difference is the source texture's decode, surfaced through a render
target that is itself exact. That was said once before on this issue, on
2026-09-11, and then buried by a contaminated re-measurement.
