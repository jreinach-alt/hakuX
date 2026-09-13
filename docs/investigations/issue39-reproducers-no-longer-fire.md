# #39's four reproducers no longer vary run to run

[#39](https://github.com/jreinach-alt/hakuX/issues/39) is "a draw's result is
intermittently lost, same disc and binary, run to run", filed against branch
`claude/docs-tooling-agentic-coding-u152m1` at `c43f5f8`. It names four
reproducers and records a varying failing set for each.

Every one was re-run on `0d14a907`, same lane, same host, same lavapipe,
same discs. **None of them varies.**

| reproducer | renderer | runs | captures | differ between runs |
|---|---|---:|---:|---:|
| `Texture render target` minus `RenderTextureLoop` (40 tests) | Vulkan | 6 | 40 | **0** |
| the same disc | OpenGL | 3 | 40 | **0** |
| `TexFmt_A8B8G8R8` + `TexFmt_A8R8G8B8` (2 tests) | Vulkan | 6 | 2 | **0** |
| five-suite clipping disc (`Window clip`, `Viewport`, `Stencil`) | Vulkan | 6 | 120 | **0** |
| `Depth buffer fixed function` (80 tests) | Vulkan | 4 | 80 | **0** |

**25 runs, 1,402 captures compared by sha256, zero run-to-run variation.**

Comparison is by digest, not by score — a score can be stable while the
image moves, which is the trap `docs/testing/sweep_agreement.py` exists for.

## What each row used to say

* 40-test disc: "7/40 exact then 5/40, **different failing sets**". Now
  **11/40 exact**, and the same 40 digests six times.
* pair disc: "second test lost once" in 6 runs. Now one digest each over 6
  runs; both captures sit 71 px from the golden, which is a small residual,
  not a lost draw — a lost draw was a whole quad, 81,225 px.
* clipping disc: "16/16 seven times; **14/16 twice**", the stencil-only
  middle draw missing. Now 16/16 of the `Stencil` captures byte-stable over
  6 runs, and all 120 captures on the disc byte-stable.
* depth disc: "51-60 structural failures, **varying set**". Now the set does
  not vary across 4 runs. 74 of 80 still differ from the golden, but that is
  #16's depth readback, which is a different issue and is not what #39 is
  about.

## One more thing the runs showed

On the 40-test disc, **OpenGL and Vulkan are 40/40 byte-identical.** The two
renderers fully agree there.

## And a 236-capture search found no Vulkan capture that varies

The four reproducers are the issue's own. Widening the search to the whole
`iso_surf1` disc, three runs per renderer, compared byte for byte with
[`../testing/sweep_agreement.py`](../testing/sweep_agreement.py):

| renderer | captures | runs | agree | disagree |
|---|---:|---:|---:|---:|
| Vulkan | 236 | 3 | **236** | **0** |
| OpenGL | 236 | 3 | 235 | 1 (`Surface_pitch::Swizzle`) |

Adding the reproducer runs above, that is **1,402 + 1,416 captures compared
across 31 runs, with exactly one unstable capture, and it is under OpenGL.**

The guard prints its own caveat and it applies here: three runs miss a
defect that fires half the time about a quarter of the time. This is
evidence of stability, not proof of it.

## What this does and does not establish

It establishes that the four reproducers written into #39 are stale: nobody
should work the suspect list against them, because they no longer separate
anything. A defect that does not fire cannot be bisected either, so the
change that fixed or masked it cannot be attributed from here.

It does **not** establish that the defect is gone. Three reasons to keep the
issue open:

1. A rate can fall without reaching zero. #39's own pair disc lost a test
   once in six; six clean runs of it is consistent with a rate that merely
   dropped.
2. The machinery that produces run-to-run variance is demonstrably still
   alive on this lane — on the same day, `Surface_pitch::Swizzle` under
   OpenGL gave three distinct captures in three runs, and the mechanism is
   measured in
   [`gl-surface-to-texture-is-wrong.md`](gl-surface-to-texture-is-wrong.md):
   pgraph reads guest texture memory when it reaches the draw rather than
   when the guest submitted it, so a guest that reuses a buffer overwrites
   it under a queued draw. Both renderers have that shape
   (`gl/texture.c:875`, `vk/texture.c:1668`).
3. Nothing here was run on a device. These are desktop lavapipe and desktop
   GL only.

So the right next step for #39 is **a reproducer that still fires**, not more
work on the suspects. The cheapest candidate is the one capture that does
still vary, and it varies under OpenGL, which is not where #39 was filed.
