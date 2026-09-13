# The first full OpenGL baseline, beside Vulkan on the same disc

Until `fada1d89` the OpenGL renderer aborted at 44 of 236 captures on the
surface disc, so there was no GL column to compare anything to. There is
one now. Both renderers, one binary, one disc, scored against the same
hardware goldens: `docs/testing/gl-vs-vulkan-surf1-2026-09-13.tsv`.

| | OpenGL | Vulkan |
|---|---:|---:|
| captures | 236 | 236 |
| bit-exact against golden | **100** | **108** |
| differing pixels (advisory total) | 5,271,728 | 4,443,147 |

**209 of 236 captures score identically between the two renderers.** That
is the headline. The renderers are not two independent guesses that happen
to land nearby — they agree exactly almost everywhere, which means each of
the 27 disagreements is a specific nameable defect in one of them rather
than noise, and which of the two is wrong is decided by the golden, not by
majority.

Vulkan is better on 25, OpenGL on 2.

## Where OpenGL is worse

| suite | n | exact GL | exact VK | px GL | px VK | delta |
|---|---:|---:|---:|---:|---:|---:|
| `Surface_clip` | 47 | 39 | **47** | 743,746 | **0** | +743,746 |
| `Texture_perspective` | 8 | 0 | 0 | 883,115 | 733,098 | +150,017 |
| `Image_blit` | 41 | 19 | 19 | 251,028 | 201,885 | +49,143 |
| `Blend_surface` | 32 | 3 | 3 | 1,347,043 | 1,325,236 | +21,807 |
| `Texture_perspective_enable` | 2 | 0 | 0 | 38,058 | 27,989 | +10,069 |
| `Surface_pitch` | 1 | 0 | 0 | 15,360 | 10,240 | +5,120 |

`Surface_clip` is the one to take first, and it is unusually clean:
**Vulkan is bit-exact on all 47 captures in the suite and OpenGL fails 8 of
them.** Seven are render-target variants and one is the clipped debug text:

```
rt_x320y240_w320h240   228,796      rt_x0y0_w0h384       61,546
rt_x0y240_w640h240     152,172      rt_x0y0_w512h0       61,444
rt_x0y0_w512h384       110,976      rt_x8y16_w632h464    13,952
rt_x16y8_w512h384      110,706      DebugTextShouldClip   4,154
```

A defect with a working implementation of the same thing sitting next to it
in the tree is the cheapest kind to fix: the question is not *what should
this do* but *what does the other renderer do differently*.

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
