# #66 and the same-surface FIXME are one chain

`update_surface_part()` gated binding creation on *is this surface stale*
when the precondition it needed was *is this surface stale **or absent***.
That is #66. Fixing it alone moved `Color_zeta_overlap/ColorIntoZeta_ZB`
from 10,766 differing pixels to 131,495, which looked like the fix breaking
a capture. It was not. The fix made an unrelated, pre-existing policy
reachable, and that policy is wrong.

Both halves are below, measured from a per-call log of `update_surface_part()`
over a full OpenGL run of the surface disc — 292,899 calls.

## The gate

```c
bool mem_dirty = !tcg_enabled() && memory_region_test_and_clear_dirty(...);
if (upload && (surface->buffer_dirty || mem_dirty)) {
```

`mem_dirty` is identically 0 on all 137,816 colour samples, because
`tcg_enabled()` is 1 on every build we run; the memory-dirty half of this
condition has never been exercised. So the gate is `buffer_dirty` alone,
and the three populations it produces are:

| `buffer_dirty` | binding | outcome | n |
|---|---|---|---|
| 0 | set | skip | 136,157 | 
| 1 | null | create | 1,281 |
| **0** | **null** | **skip** | **378** |

The last row is the defect: nothing is stale, so nothing is bound, so the
framebuffer has no attachments, so every `glClear` in that state raises
`GL_INVALID_FRAMEBUFFER_OPERATION` and does nothing. The status is
`GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT` (0x8CD7) and not
`GL_FRAMEBUFFER_UNSUPPORTED`, which is what says this is us building it
wrong rather than the driver declining. The error sits pending until an
unrelated assert in `gl/shaders.c` trips over it and aborts, which is why
the disc stopped at 44 of 236 captures under OpenGL.

## The policy

One GL texture cannot be the colour attachment and the depth attachment at
the same time. When the guest points both targets at one address, xemu
resolves it here:

```c
if (found == other) {
    NV2A_UNIMPLEMENTED("Same color & zeta surface offset");
    pgraph_gl_unbind_surface(d, !color);   /* whoever asks last wins */
}
```

`Color zeta overlap` does exactly that on purpose, and the log shows what
the two halves did together. Addresses are from the run; `C`/`Z` is which
target `update_surface_part()` was called for.

**ColorIntoZeta** — the guest points `NV097_SET_CONTEXT_DMA_COLOR` at the
zeta channel:

```
USP 287157 C addr=02b6c000 dirty=1 cb=null     zb=02b6c000 GATE=1
USP 287157 SAME_OFFSET unbinding Z      -> cb=02b6c000 zb=null
USP 287158 Z addr=02b6c000 dirty=0 cb=02b6c000 zb=null     GATE=0   <-- #66
```

Colour takes the surface; zeta's attempt to take it back is skipped by the
gate defect, so **colour keeps it** and the depth write goes nowhere.

**ZetaIntoColor** — the guest points `NV097_SET_CONTEXT_DMA_ZETA` at the
colour channel. The same chain runs with the roles swapped:

```
USP 287824 Z addr=034cc000 dirty=1 cb=034cc000 zb=null     GATE=1
USP 287824 SAME_OFFSET unbinding C      -> cb=null zb=034cc000
USP 287825 C addr=034cc000 dirty=0 cb=null     zb=034cc000 GATE=0   <-- #66
```

Here colour is the one evicted and never rebinds, so the rest of the test
draws into nothing — including the on-screen banner, which is exactly the
3,304 white pixels the capture was missing.

So the gate defect is a coin: it lands well on one test and badly on the
other. Fixing it alone makes both consistent under "whoever asks last
wins", and on `ColorIntoZeta` that hands the surface to the depth unit.

## Which unit should win

Hardware lets both units write and races them, and the test author
documents the outcome as non-deterministic. The goldens show the race
directly — two populations per capture, scattered in runs of 1 to 32
pixels inside the quad rather than in any coherent region, and in
`ColorIntoZeta_ZB` one of the two values is `#87FCBF`, which takes its low
byte from the colour write and its upper two from the depth write. The
race is sub-word.

A single-attachment model cannot reproduce that. It can only pick a
winner, and the goldens say which one to pick:

| capture | colour-write pixels | other | our residual after |
|---|---|---|---|
| `ColorIntoZeta_ZB` | 120,729 | 10,766 | 10,766 |
| `ZetaIntoColor` | 30,592 | 71,663 | 71,663 |

`#00FFBF` in the first is the little-endian byte order of the test's
`kColor` 0x00BFFF00; `#FF00FF` in the second is its 0xFFFF00FF. With
colour winning, our output equals the colour-write population exactly in
both captures and the residual is precisely the race remainder — one
mechanism, not two unrelated failures. Under the old policy `ZetaIntoColor`
matched *neither* population.

Note the bias is not the same in the two tests (92% colour in one, 30% in
the other), so "colour always wins" is not silicon's rule. It is the best
a model without the race can do, and it is right wherever the race went
colour's way.

The structural argument points the same way and does not depend on the
race at all: evicting the colour attachment leaves a framebuffer with
nothing attached, which is never a state the guest asked for, and #66
showed that state can persist for the rest of a test once entered.

## What landed

Both halves, together — the gate fix alone regresses `ColorIntoZeta_ZB`,
so they are one commit and one bisect point:

1. the gate also passes when the corresponding binding is absent;
2. colour may take a surface zeta holds, but zeta declines one colour
   holds, clearing its own `buffer_dirty` so the absent-binding gate brings
   it back on the next request and it can take the surface once colour
   moves away.

Measured, against the registered prediction in
`docs/testing/predictions/issue66-same-offset-colour-wins.json`:

* `GL_INVALID_FRAMEBUFFER_OPERATION` raised over a full run **378 → 0**,
  counted with a `glDebugMessageCallback` under `GL_DEBUG_OUTPUT_SYNCHRONOUS`
  and with the *same instrumented build* on both arms. (`glGetError()`
  returns and clears one error per call, so it counts pendings, not raises;
  an earlier report of "one error per run" on this issue was that mistake.)
* Captures under `renderer = 'OPENGL'` **44 → 236**, process exit 134 → 0.
* Of the 44 captures that existed before, **43 are byte-identical** and one
  moved: `ZetaIntoColor` 105,559 → 71,663.
* Vulkan **236/236 byte-identical**, as it must be for a change confined to
  `pgraph/gl/`.

One registered leg missed. The prediction put `ZetaIntoColor` at 102,255 —
the value the gate fix alone produced, reasoning only about the restored
banner. It came out at 71,663, because making colour win also changes the
quad itself from the depth write to the colour write. The direction was
right and the size was not: the model of my own change was incomplete on
the capture the change was aimed at.
