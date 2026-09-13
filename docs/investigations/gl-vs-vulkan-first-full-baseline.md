# The first full OpenGL baseline, beside Vulkan on the same disc

Until `fada1d89` the OpenGL renderer aborted at 44 of 236 captures on the
surface disc, so there was no GL column to compare anything to. There is
one now. Both renderers, one binary, one disc, scored against the same
hardware goldens: `docs/testing/gl-vs-vulkan-surf1-2026-09-13.tsv`.

| | OpenGL | Vulkan |
|---|---:|---:|
| captures | 236 | 236 |
| bit-exact against golden | **102** | **108** |
| differing pixels (advisory total) | **4,320,179** | 4,443,147 |

The table and the TSV are as of `2c25f719`. The first reading of this
baseline, at `fada1d89`, had OpenGL at 100 bit-exact and 5,271,728 px. Three
fixes came straight out of it the same afternoon — #70 (the clip-bounded
clear, 742,832 px), the blit range download (#7 on GL, 49,143 px) and #72
(`noperspective`, 159,574 px) — and **OpenGL's total is now below Vulkan's**.
That is the argument for keeping the column: every one of the three was
found by reading the column, and two were ports of something the other
renderer already had.

**225 of 236 captures score identically between the two renderers.** That
is the headline. The renderers are not two independent guesses that happen
to land nearby — they agree exactly almost everywhere, which means each of
the 27 disagreements is a specific nameable defect in one of them rather
than noise, and which of the two is wrong is decided by the golden, not by
majority.

Vulkan is better on 9, OpenGL on 2.

## Where OpenGL is worse

| suite | n | exact GL | exact VK | px GL | px VK | delta |
|---|---:|---:|---:|---:|---:|---:|
| `Blend_surface` | 32 | 3 | 3 | 1,347,043 | 1,325,236 | +21,807 |
| `Surface_pitch` | 1 | 0 | 0 | 15,360 | 10,240 | +5,120 |
| `Surface_clip` | 47 | 41 | **47** | 1,426 | **0** | +1,426 |

`Texture_perspective` (+150,017), `Texture_perspective_enable` (+10,069) and
`Image_blit` (+49,143) are gone, closed by #72 and the blit range download.

**What is left may be one defect.** Eleven captures still differ between the
renderers and two of those are `Color_zeta_overlap`, where OpenGL is now
ahead. Of the nine where OpenGL is behind, the two `Blend_surface` ones are
`R5G6B5_*`, the six `Surface_clip` ones are the R5G6B5 render-target
residual left by #70, and `Surface_pitch::Swizzle` is a swizzled surface.
Every one of them is a 16-bit surface format, and the differences are small
per-channel steps — `#104010` against a golden `#103C10`, `#00FE00` against
`#00FF00`. That points at one thing, GL's R5G6B5 expansion, rather than
three.

`Surface_clip` is what this baseline was worth on its first reading. Vulkan
was bit-exact on all 47 and OpenGL failed 8 for 743,746 px — seven
render-target variants and the clipped debug text. That became #70, and it
turned out to be a straight port: `pgraph_gl_clear_surface()` scissored a
clear with the clear rect alone and never intersected the surface clip,
which `vk/draw.c` had done for some time with a comment naming these very
captures. Eight captures better, none worse, 742,832 px, and what is left
in the suite is 1,426 px of an R5G6B5 expansion difference.

A defect with a working implementation of the same thing sitting next to it
in the tree is the cheapest kind to fix: the question is not *what should
this do* but *what does the other renderer do differently*. That question
is the whole reason to keep this column, and the five suites still above
are each an instance of it.

`Image_blit`'s 49,143 is almost entirely one capture,
`DirtyOverlappedDestSurf` (GL 49,142, Vulkan 6); the seven `Overlap_*`
captures differ by exactly 1 pixel each, which is a rounding floor and not
a rule.

## Where Vulkan is worse, and why it is the same bug

| capture | GL | Vulkan |
|---|---:|---:|
| `Color_zeta_overlap::ColorIntoZeta_ZB` | 10,766 | 131,495 |
| `Color_zeta_overlap::ZetaIntoColor` | 71,663 | 102,255 |

Those are exactly the two values the OpenGL renderer produced *before*
`fada1d89`. The Vulkan renderer carries the same "whoever asks last takes
the shared surface" policy, so the same fix ports: colour may take a
surface zeta holds, zeta declines one colour holds. See
`docs/investigations/color-zeta-same-surface.md` for the measurement the
choice rests on. `vk/surface.c` is not this lane's file, so this is a
report and not a patch.

## What this is not

One disc. `surf1` is 236 captures of surface, blend, clip and blit
behaviour; it is not the corpus, and a renderer that agrees with Vulkan
here can still diverge anywhere the disc does not go. It is also a desktop
measurement on llvmpipe, so it says nothing about the Android GL path,
whose driver differences are the whole reason that lane exists.

Whether this becomes a scoreboard column is the orchestrator's call — the
existing board is per-category over the whole corpus on device, and pasting
a one-disc desktop pair into it would put two incomparable things in
adjacent cells.
