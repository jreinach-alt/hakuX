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

## Verified on HEAD, 2026-09-18

The fix above landed on 2026-09-13 and the issue was never closed, so it was
re-run before closing, on a binary rebuilt from HEAD for the purpose
(`0.4.0-j1-368-g8c938792`), `renderer = 'OPENGL'`, `iso_surf1`:

| leg | fix arm, 09-13 (as reported on the thread) | HEAD, 09-18 |
|---|---:|---:|
| captures extracted | 236 | **236** |
| process exit | 0 | **0** (47 s) |
| `Assertion` / `Aborted` / `GL_INVALID` lines in the run log | 0 | **0** |
| `Color_zeta_overlap/ColorIntoZeta_ZB` | 10,766 | **10,766** |
| `Color_zeta_overlap/ZetaIntoColor` | 71,663 | **71,663** |
| bit-exact on the disc (GL) | — | **118 / 236** |

Byte-compared with the two unmodified OpenGL runs of this disc from 09-14 --
the control arm of that day's surface-alias experiment (`0.4.0-j1-330-g3cfc2790`)
and the verification run after it (`0.4.0-j1-333-gb0059688`), whose binaries
differ from HEAD's by docs commits and one `gl/draw.c` guard against
`glLineWidth(0)` (`5b707602`): **235 of 236 captures byte-identical to each.**
The one mover in both comparisons is `Surface_pitch::Swizzle` -- 15,360 here
against 14,848 and 15,360 there, byte-different in every pairing -- which is the
texture-memory race #71 established and the only capture on this disc that is
not bit-reproducible. So the `gl/draw.c` change since those runs is inert on
this disc, and the fix has not moved since it landed. (A first draft of this
paragraph compared against a third 09-14 run that turned out to be the
experiment's *treatment* arm, with uncommitted code; it differed on one more
capture, which said nothing about this fix. Reference runs need their
provenance read, not their names.)

The `GL_INVALID_FRAMEBUFFER_OPERATION`
count (378 → 0 at fix time) needs a debug callback the tree does not carry and
was not re-measured; a completed disc with zero assert lines is the durable
form of that leg.

Reproduced by
`docs/testing/verify_surface_disc.py <captures_dir> <goldens_root> [<ref_captures_dir> ...]`.

Two things the thread left open are filed on their own rather than carried
here: #85, the `mem_dirty` half of the gate, which `tcg_enabled()` makes dead on
every build this project runs; and #86, the Android arm of
`pgraph_gl_shader_load_from_memory()`, which still drains every GL error
silently now that the error it was added to hide is gone.

## The Vulkan port, and the third capture it moved (#88, #91)

The policy half of the chain above was ported to `pgraph/vk/surface.c` and
measured. **The gate half was never missing on Vulkan:** `!current_binding` has
sat outside the `upload` condition since `9161e3e14a`, 2024-07-27, upstream —
so only the policy needed porting, and Vulkan's gate is strictly *more*
permissive than GL's fixed form. That is also why Vulkan's `ColorIntoZeta_ZB`
sat at exactly 131,495: gate-correct-with-a-symmetric-policy is the state GL
passed through between `fada1d89`'s two halves.

The arm (`PRE-REGISTERED`, 5 runs per arm, arms differing in `vk/surface.c`
alone, three-suite disc `3-suites:e0a8f913`):

| capture | arm A | arm B | |
|---|---:|---:|---|
| `ColorIntoZeta_ZB` | 131,495 | **10,766** | predicted absolute, exact |
| `ZetaIntoColor` | 102,255 | **71,663** | predicted absolute, exact |
| `Swap` | 165,447 | **304,750** | +139,303, regressed |

Both absolutes were derived from the goldens' own colour histograms rather than
copied from GL's score file, and both landed to the digit. **The policy is
confirmed.** All four values are deterministic 5/5 in both arms.

### `Swap`'s regression is a stray DEPTH CLEAR, not a missing depth test

`[issue.91]` attributes it to the missing depth attachment — no zeta binding,
`pDepthStencilState == NULL`, so the quad draws with no depth test. **The
captures refute that, and it can be settled without a device.**

The three colour populations are partitioned *identically* in both arms —
165,447 quad, 139,303 background, 2,450 text. A change to depth testing moves
the boundary between populations. Nothing moved; only the background's **value**
changed:

| | R,G,B,A as read | bytes in memory (BGRA) | as a word |
|---|---|---|---|
| golden / arm A | `#242424` a`FE` | `24 24 24 FE` | `0xFE242424` |
| arm B | `#000024` a`00` | `24 00 00 00` | `0x00000024` |

`0xFE242424` is the test's own clear colour. Arm B holds that value with **bits
8–31 zeroed and bits 0–7 preserved** — which is precisely a `Z24S8`
**depth-only clear of 0** written over it: the depth field is bits 8–31, the
stencil byte is bits 0–7 and is left alone, and the surviving `0x24` is the
clear colour's own low byte. `PrepareDraw(0xFE242424, 0)` clears colour to that
value and depth to 0.

So in arm B the depth clear reached the **colour** surface. That is a clear
landing on the wrong attachment, not a test being skipped, and the distinction
matters because it points at `pgraph_vk_clear_surface()` rather than at the
pipeline. Note the inline-clear path in `vk/draw.c` guards correctly
(`if (write_zeta && r->zeta_binding)`), so the fall-through pipeline clear is
where to look.

### What is NOT established, and the arm that settles it

Reading `update_surface_part()` against `TestSwap()` does **not** reproduce the
decline firing inside `Swap`. `SET_CONTEXT_DMA_COLOR` sets
`surface_color.buffer_dirty` (`pgraph.c:2387`; `:2386` is
`pg->dma_color = parameter;`, the line before), so colour rebinds to the zeta
address first; zeta then asks for the colour address and finds an object that is
no longer `r->color_binding`, so `surface == other` is false and the decline
does not fire. `SurfaceShape` carries no address, so `framebuffer_dirty()`
cannot see a DMA swap at all — that is worth knowing separately.

**Which leaves two candidates, and they are separable by one cheap arm.**
`ColorIntoZeta` and `ColorIntoZeta_ZB` run before `Swap` in the suite, and the
decline changes the pg-level state they leave behind — it clears
`surface_zeta.buffer_dirty` and leaves `zeta_binding` absent. So:

| `Swap` run SOLO on arm B | meaning |
|---|---|
| back to arm A's value | contamination — an earlier test's decline leaking forward |
| still +139,303 | intrinsic to `Swap`, and the control-flow reading above is wrong |

That is `make_test_iso.py`'s solo/pair classification, and it is the right next
step rather than a fix: the mechanism is half-established, and a fix fitted to
the unestablished half would be a fit. **Predict the arm-A-to-arm-B
relationship, not an absolute** — #89 measured a 141,125 px composition swing on
this very suite, so a solo disc's own numbers are not comparable with the
three-suite ones in either direction.

## #91 judged: `Swap`'s 304,750 is a COMPOSITION value, and the policy is inert on it

The solo arms ran. `Color_zeta_overlap/Swap` on a disc containing only that
test, five runs each, **byte-identical between the two arms**:

| disc | captures preceding `Color zeta overlap` | arm A (no policy) | arm B (policy) |
|---|---:|---:|---:|
| solo (`Swap` only) | **0** | **304,750** | **304,750** |
| 3-suite `e0a8f913` | **1** | 165,447 | **304,750** |

Verdict `PASS`, `PRE-REGISTERED`, one leg, deterministic 5/5 in all four arms.

**304,750 is not the policy's value. It is `Swap`'s value when the disc does
not supply a preceding capture** — both refs reach it with none. So the
registered `must_not_move` violation on the three-suite disc was the policy
*removing a compensation the disc was supplying*, not the policy creating a
defect.

The preceding-capture count is 1 and not 2: the disc orders
`Color Zeta Disable, Color zeta overlap, Null surface`, so only
`Color_Zeta_Disable/MaskOff_ZB` runs before the suite —
`Null_surface/XemuBug893` runs after it. That matters because it puts these
numbers on #89's own ladder.

### `Swap` and `Swap_ZB` respond to composition in OPPOSITE directions

#89 established the invariant for `Swap_ZB`: **≥2 captures in preceding
suites**, own-suite captures not counting. Its ladder is 0 → 0, 1 → 0,
2 → 141,125 — *more* preceding captures make it worse. Both of my discs sit at
0 and 1, and `Swap_ZB` read 0 on both, which is #89's ladder reproduced on two
further discs and two further binaries.

`Swap` goes the other way: 0 preceding → 304,750, 1 preceding → 165,447. *More*
preceding captures make it better.

Two captures of the same test, over the same two surfaces, with opposite
composition sensitivity, and one defect that the colour-wins policy can also
trigger on its own. That is a strong argument they are two faces of one
aliasing defect rather than three issues — and it is consistent with the
byte signature recorded above, which is a `Z24S8` depth field zeroed inside a
**colour** surface.

### What this changes

- **#91 is not a defect in #88's policy.** The policy is exact on its two
  targets and inert on `Swap` once the composition confound is removed. What
  remains is that it cancels a compensation, which is a decision about whether
  to ship a policy that exposes a pre-existing defect — an owner's call, not a
  lane's.
- **Neither 165,447 nor 304,750 is a correct value.** Even at 165,447 the quad
  is `#E91A24` against the golden's `#E91624`, off by 4 in green. The
  "regression" is one wrong value replaced by a worse one.
- **The probe #89 wants should log `Swap`, not only `Swap_ZB`**, and should
  record whether the colour binding was a cache hit or a fresh create *and*
  whether the zeta decline fired, because the policy reaches the same end state
  that zero preceding captures reach. A probe written to the older picture
  would miss the one input that is now known to matter.
