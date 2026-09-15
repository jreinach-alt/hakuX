# Corpus re-triage, and `Window_clip` is a FLAKE with an exactly-shaped signature

Two of the three standing target suites closed this morning (`Attrib_carryover`
reproduced, `Material_alpha` out of lane), so the target list was stale. This
re-ranks the whole single-binary corpus, resolves where the top candidates'
fixes would live **before** baselining any of them, and reports one finding that
changes how the ranking itself should be read.

Reproduced by `docs/testing/rank_corpus.py <corpus_root> <goldens_root>` and
`docs/testing/window_clip_bisect.py <pgraph_run_root> <goldens_root>`.

## The ranking

2,640 captures over the 16 corpus directories at `5b707602`, deduped (259
duplicates skipped), zero missing goldens, zero shape mismatches. **Ranked per
capture, not by total** — a suite's share of the corpus is a statement about how
many captures it has as much as about the defect.

| suite | n | channels | **per capture** | mean \|d\| | where a fix would live |
|---|---:|---:|---:|---:|---|
| `W_buffering` | 530 | 162,886,125 | **307,332** | 169.60 | `pgraph.c`, `psh.c`, `vsh.c`, `geom.c` — **none in lane** |
| `Texture_perspective` | 8 | 1,427,840 | 178,480 | 9.91 | `glsl/common.c` — in lane, already fixed once |
| `Smoothing_control` | 2 | 310,963 | 155,481 | 3.19 | **no consumer in the tree** |
| `Depth_buffer_fixed_function` | 80 | 9,187,640 | 114,845 | 80.41 | settled: `psh.c` + `gl/constants.h` |
| `Blend_surface` | 32 | 3,660,115 | 114,378 | 92.53 | unresolved |
| `Texture_signed_component_tests` | 19 | 1,955,592 | 102,925 | 107.03 | settled: blocked on `gl/renderer.h` |
| `Swath_width` | 6 | 554,238 | 92,373 | 6.99 | **register not defined anywhere** |
| `Fog_gen` | 60 | 4,666,628 | 77,777 | 91.58 | `pgraph.c` only |
| `Texture_DXT` | 15 | 1,118,699 | 74,579 | 1.79 | unresolved |
| `Line_width` | 61 | 4,514,611 | 74,010 | 41.91 | solved: `glsl/geom.c` |
| `Blend_tests` | 105 | 7,660,673 | 72,958 | 53.95 | parked |
| `Material_alpha` | 24 | 1,627,304 | 67,804 | 1.06 | `vsh-ff.c` + `vsh.c` — not in lane |
| `Texture_anisotropy` | 4 | 265,112 | 66,278 | 20.28 | `gl/texture.c`, `gl/renderer.c` — **in lane** |
| `Window_clip` | 92 | 6,029,312 | 65,536 | 144.50 | **see below — this row is a flake** |
| `3D_primitive` | 160 | 7,254,492 | 45,340 | 2.78 | partly settled |

Seven suites are byte-exact across the corpus: `Color_Zeta_Disable`,
`Lighting_Two_Sided`, `Material_color`, `Null_surface`, `Pixel_shader`,
`Stencil_func`, `Surface_clip`.

## `W_buffering` is the biggest suite in the corpus and none of it is mine

530 captures, 307,332 channels each, mean |d| 169.60 — a third of every frame,
and far too large to be a rounding floor. `NV097_SET_CONTROL0_Z_PERSPECTIVE_ENABLE`
is the bit the test toggles, and it is consumed at `pgraph.c:2320`,
`glsl/psh.c:154`, `glsl/geom.c:45` and `glsl/vsh.c:108`. **No `gl/*.c` file reads
it at all.** So the largest residual in the corpus resolves entirely outside
this lane, and `psh.c`/`vsh.c` now has a **fifth** claimant.

Pivots before I stopped (they cost minutes and are worth recording):

| axis | arms | per capture |
|---|---|---:|
| float vs fixed depth | F / D | **457,584 / 166,950** (2.74×) |
| 16 vs 24 bit | 16 / 24 | 411,254 / 210,236 |
| W-buffer vs Z-buffer | WBuf / ZBuf | 329,882 / 283,914 (only 1.16×) |
| z-bias | ZB1 / ZB0 | 309,390 / 305,409 — **flat** |
| z-slope | ZS1 / ZS0 | 311,024 / 303,555 — **flat** |

**The suite's own name is not its main axis.** W-buffering costs 1.16×; float
depth costs 2.74×, and float depth is the defect already localised in
`Depth_buffer_fixed_function`. `bits` and `flt` are *not* confounded — all four
cells are populated, with `16F` worst at 686,797 and `24F` at 228,372.

**One axis I got wrong and caught before publishing it.** I initially read the
trailing `_ZB` on capture names as a clip flag and produced a "clip" pivot
showing 2.33×. It is not a test axis at all: `MakeTestName` in `wbuf_tests.cpp`
ends at `_ZS<0|1>`, and the trailing `_ZB` is the harness's **depth-buffer
capture** suffix. The table was really colour-capture vs depth-capture. Clipping
appears in the *prim* field (`ClipF-150-224`), not as a suffix. Read the name
generator, not the names.

## Two registers the emulator has never heard of

- **`SWATH_WIDTH` does not exist anywhere** — not in `nv2a_regs.h`, not handled.
  `Swath_width` (6 captures, 92,373 each) tests a register we do not define.
- **`WINDOW_CLIP` is stored and consumed by nothing.** `pgraph.c:2441-2455`
  writes `NV_PGRAPH_WINDOWCLIPX0/Y0`; no backend reads them. GL's scissor
  (`gl/draw.c:207`, `:433`) is set from `surface_shape.clip_width/height`, a
  different register, and Vulkan does the same at `vk/draw.c:3240`.

## `Window_clip`: the ranking row is a FLAKE, and I nearly called it a regression

The corpus run scores 6,029,312 channels with 8 of 92 byte-exact. Scoring every
run that carries the suite, in time order, with the exact xemu commit read out
of each `run_<tag>.log`:

| mtime (UTC) | dir | xemu_version | channels | exact |
|---|---|---|---:|---:|
| 09-10 19:50 | `score_clip11` | `0.3.3-j1-100-g2af03f7` | **3,282,728** | 54 |
| 09-10 20:05 | `score_clip11b` | `0.3.3-j1-100-g2af03f7` | **3,282,728** | 54 |
| 09-10 20:18 | `score_clip11c` | **`0.3.3-j1-100-g2af03f7`** | **0** | **92** |
| 09-10 20:24 | `score_clip11d` | `0.3.3-j1-100-g2af03f7` | 0 | 92 |
| … 25 further runs … | | | 0 | 92 |
| 09-13 23:08 | `score_i39_c6` | `0.4.0-j1-296-g66fdd6d7` | 0 | 92 |
| 09-14 01:43 | `score_p74_clip` | `0.4.0-j1-306-gf7aec008` | **6,029,312** | 8 |
| 09-14 18:28 | `score_cx_clip11` | `0.4.0-j1-331-gd7dfe146` | **6,029,312** | 8 |

I had this as a regression bisected to `66fdd6d7..f7aec008` — a linear ten-commit
window (reverse range empty, ancestry confirmed) in which **not one commit
touches a source file**, with goldens untouched since 09-10 and `Viewport`
bit-identical across the boundary as a control.

**The script's own output killed that.** `score_clip11` and `score_clip11b` are
BROKEN and `score_clip11c` is clean **on the same commit `2af03f7`**. Same
binary, both outcomes. It is nondeterminism, not a regression, and the
"no code change in the window" fact was the clue I should have taken at face
value instead of hunting for a commit to blame.

It is **rare and bistable, not noisy**: clean in 27 of 31 runs, and when it
fails it fails identically within a session — 3,282,728 twice, then 6,029,312
twice, never an intermediate value.

### It does not co-vary with `Stencil`

| | `Window_clip` | `Stencil` |
|---|---|---|
| `score_clip11`, `clip11b` | **BROKEN** | 0 (clean) |
| `score_clip11d`, `clip11g` | 0 (clean) | **BROKEN** (30,000 / 90,000) |
| `score_tie_clip1`, `flake3` | 0 (clean) | **BROKEN** (80,000 / 50,000) |
| `score_p74_clip`, `cx_clip11` | **BROKEN** | **BROKEN** |

`Stencil` flakes in 6 of 31 runs and `Window_clip` in 4, and they coincide only
in the last two. **These are independent flakes**, so #79's Stencil
nondeterminism and this are not one mechanism on this evidence. `Viewport` sits
at exactly 2,601 in 30 of 31 runs (`score_clip8` is the one exception, 1,600),
which is what makes the above readable as signal rather than churn.

### The failure has an exact shape, which makes it a good reproducer

When it fails, the differing region is **exactly the window-clip rectangle**:

| capture | differing px | expected (w+1)² | exact? |
|---|---:|---|---|
| `E_x0y0_w0h0-x0y0_w0h0` | **1** | 1×1 | **yes** |
| `E_x0y0_w1h1-x0y0_w0h0` | **4** | 2×2 | **yes** |
| `E_x0y0_w255h255-x0y0_w0h0` | **65,536** | 256×256 | **yes** |
| `E_x0y0_w256h256-x0y0_w0h0` | 65,536 | 257×257 | no — clamps at 256 |

`np.array_equal(differing_mask, box)` is **true**. Inside that rectangle our
output is a single constant colour `[255, 119, 51]` where hardware has
`[51, 119, 136]`; the good run has `[51, 119, 136]`, matching hardware exactly.
The rect reads as **inclusive of both bounds** (w=0 still covers one pixel).
What clamps w=256 at 256 is **not** established here.

All 8 byte-exact captures in the failing runs are the `I`-type large rects, so
the `E`/`I` clip type splits it — recorded, not explained.

This is a far better handle on GL nondeterminism than a noise band: a solid
rectangle of one constant colour at a known location, appearing in 4 of 31 runs,
with a stable per-session magnitude.

## What this does to the ranking

**A single-run corpus cannot distinguish a defect from a flake.** `Window_clip`'s
65,536-per-capture row is a flake caught mid-air; the same binary scores 0 on a
rerun. Every row in the table above carries that caveat, and any suite picked off
it should be **run twice before anything is attributed** — which was already the
standing rule for `Surface_pitch::Swizzle` and is now general.

`Texture_anisotropy` (4 captures, 66,278 each, resolving to `gl/texture.c` and
`gl/renderer.c`) is the one high-ranked candidate that is both unexplored and
**in lane**. That is the next target, and its first step is a second run.
