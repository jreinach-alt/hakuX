# #50 is render-target aliasing, not a reversed draw order

Measured 2026-09-12 on all 1,568 captures of the recovered oracle
(`~/hakux-work/res_oldblend`) against the silicon goldens in
`/home/justin/goldens/results/Blend_tests`. No device, no build; every figure
below comes from captures already on disk. Reproduce with:

    docs/testing/blend_stack_c_aliasing.py --geometry --aliasing --naive
    docs/testing/blend_stack_c_aliasing.py --model --unsigned

## The one-line version

**MEASURED.** `BlendTests::TestDetailed`'s third swatch stack is not drawn
upside down and its colours are not swapped. Its blit shows **the second
stack's render target**. Stack A and stack C render into the same guest address
with the same geometry and draw the same four colours in opposite order, so
"C shows A" and "C is reversed" produce the same swatch colours — and the issue
was filed as the second.

| | captures | channels |
|---|---:|---:|
| our stack C == **model of stack A blitted at C**, unsigned set | **1,119 / 1,120** | 73,346,400 / 73,400,320 |
| our stack C == model of stack C, unsigned set | 1 / 1,120 | 20,107,648 / 73,400,320 |
| our stack A == model of stack A | **1,120 / 1,120** | 73,400,320 / 73,400,320 |
| our stack B == model of stack B | **1,120 / 1,120** | 293,601,280 / 293,601,280 |

Model-free, over the whole oracle including the 448 signed captures where #43
makes both stacks wrong in the same way:

| | captures bit-exact |
|---|---:|
| ours: stack C == stack A, on the 1,024 px/capture where the screen checker is in phase | **1,567 / 1,568** |
| goldens, same test (control) | **0 / 1,568** |

## Why the three stacks are comparable at all

`TestDetailed` runs three render-to-texture blocks and blits each as a textured
quad. All three call `RenderToTextureStart(1, pitch)`, which points
`NV097_SET_SURFACE_COLOR_OFFSET` at **texture memory for stage 1** — one
address, call it `T`, for all three:

| block | draws | RT at `T` | blitted at |
|---|---|---|---|
| 1 | `DrawAlphaStack` (stack B) | 256x256, pitch 1024 | x = 192 |
| 2 | `DrawColorStack` (stack A) | 64x256, pitch 256 | x = 16 |
| 3 | `DrawColorAndAlphaStack` (stack C) | 64x256, pitch 256 | x = 560 |

Blocks 2 and 3 are the same surface: same address, same width, height, pitch,
format (`SCF_A8R8G8B8`, swizzled) and the same texture state at the blit
(`SZ_A8B8G8R8`, stage 1, 64x256). The **only** difference between them is the
draws in between. That is what makes block 3's output diagnosable: any surface,
swizzle, blit or geometry defect would hit block 2 identically, and block 2 is
bit-exact on 1,120 captures.

`DrawColorStack` draws green, red, blue, white top to bottom; and
`DrawColorAndAlphaStack` draws that list **exactly reversed**
(`blend_tests.cpp:337-386`). So aliasing and reversal are the same picture at
the swatch centres, which is how the issue came to be filed as a reversal.

## The geometry does not move, so it is none of reversed, rotated or mirrored

The issue's suggested measurement — the swatch-centre row of each of the four —
is answered directly, and it answers *no movement*:

    golden stack C (1_ADD_0)          ours stack C (1_ADD_0)
      band 0 rows 112..175 centre 144   band 0 rows 112..175 centre 144
      band 1 rows 176..239 centre 208   band 1 rows 176..239 centre 208
      band 2 rows 240..303 centre 272   band 2 rows 240..303 centre 272
      band 3 rows 304..367 centre 336   band 3 rows 304..367 centre 336
      content-change rows: 64,128,192   content-change rows: 64,128,192

Band boundaries land on the same three rows and the centres on the same four.
The 16-texel checkerboard inside the render target keeps its phase, and so does
the stretched 24-texel screen checkerboard behind the blit. `0_ADD_1`, where
stack C's four quads write the destination back unchanged so the region is the
pure background, is **bit-exact** — which on its own rules out any vertical flip
of the render target or of the blit, since a 256-row flip inverts the phase of a
16-row checker.

Whole-region transform tests agree: over 1,568 captures, our stack C is a
vertical flip of the golden's on 0, a reversal of its four 64-row blocks on 0, a
column mirror on 0, and a 180-degree rotation on 0.

## What our stack C actually contains

Recovering the render-target texel by inverting the blit composite, on
`1_ADD_1` (`S + D`, so the destination shows):

| band | golden texel | ours | that is |
|---|---|---|---|
| 0 | white, alpha 255 | green, alpha 221 | stack A's band 3 |
| 1 | blue, alpha 255 | blue, alpha 221 | stack A's band 2 |
| 2 | red, alpha 255 | red, alpha 221 | stack A's band 1 |
| 3 | green, alpha 255 | white, alpha 221 | stack A's band 0 |

Two things fix the identification beyond the colour order. First the **alpha**:
stack C blends all four channels, so its alpha must be `clamp(221 + 51) = 255`;
ours is 221, the unblended source alpha, which is stack A's rule — `DrawQuad`
writes alpha with blending switched off. Second the **destination**: our RGB is
`clamp(S_rgb + D_rgb)` against the render-target checkerboard, exactly stack A's
arithmetic. Our stack C is not stack C computed wrongly. It is stack A.

## Withdrawing the earlier falsification

`blend-stacks-are-two-defects.md` reports this same hypothesis as tested and
dead: *"Render-target aliasing — that stack C shows stack A's content ...
Compared our stack C against both our own stack A and the golden's stack A on
all 1,568 captures: 0 matches either way. Dead."*

That test is invalid, and `--naive` reproduces it to the digit: our stack C
equals our stack A on 0 of 1,568 screen regions, and the golden's stack A on 0
of 1,568.

The reason is `RenderTexturedQuad`: it calls `SetBlend(true)` and composites the
sampled texel over what is already on screen, which is a 24-texel checkerboard
stretched from a 256x256 texture across 640x480 — about 60px wide and 45px tall
in screen space. 45 does not divide the 64-row band spacing and the phase at
x = 16..79 is not the phase at x = 560..623. **Two blits of one identical render
target land as two different pictures.** Comparing the two screen regions
compares their backgrounds.

The corrected test restricts to the 1,024 pixels per capture where the two
checker phases agree, which needs no model and no scene constants, and gets
1,567 of 1,568. The closed-form oracle, which reproduces silicon on
440,401,920 of 440,401,920 channels and can therefore predict what any render
target looks like at any screen position, gets 1,119 of 1,120 on the unsigned
set with the signed set excluded so #43 cannot contaminate it.

The rest of that document stands, and one of its conclusions is strengthened
rather than weakened: stack A remains a clean oracle for #43, and stack C
remains worthless as blend evidence — now for a named reason.

## Where the defect is, and what is inferred rather than measured

**Measured:** block 3's texture bind is served the image block 2 left behind.

**Inferred:** the copy is taken before block 3's draws are recorded.

`vk/texture.c`'s texture bind, finding a draw-dirty surface at the texture
address that it will not bind directly, calls
`pgraph_vk_surface_download_if_dirty()` → `download_surface()` →
`download_surface_to_buffer()` in `vk/surface.c`. That function did not flush
the reorder window or the draw queue before recording its copy.

Its deferred twin, `download_surface_record_deferred()`, does, and says why in a
comment written after `Depth buffer fixed function` readbacks came back as the
clear with none of the quad: *"a download recorded now would sit in the command
buffer ahead of the draws that made the surface dirty, and copy the surface from
before them."* The synchronous path carries the identical hazard.

The finish already in that function does not cover it. It fires on
`r->in_command_buffer && surface->draw_time >= r->command_buffer_start_time` — a
draw still queued has been recorded into no command buffer, so there is nothing
to wait on and no guard notices. The fix makes the two paths agree.

**The single exception is the one thing this does not explain.** `0_ADD_1` is
bit-exact in stack C, and it is both the only capture whose stack-C draws are a
mathematical no-op (`sfactor=ZERO, dfactor=ONE` writes the destination back on
all four channels) and the first `TestDetailed` capture of the run. A queue
flush that is absent on 1,567 captures should be absent on that one too. Either
it is the cold-start path taking a different route, or the race resolved the
other way once in 1,568 — which is what a fence-and-queue ordering defect looks
like. It is named here rather than explained, and it is the reason the
prediction below is stated as a count over captures and not as a claim about any
single one.
