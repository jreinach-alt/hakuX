# #79's Stencil defect is the guest↔pgraph skew, on vertex data

Written 2026-09-14 by `lane.stencil` on `73245a6ae8`. **No device time was
spent to reach this**: every figure below comes from Stencil captures already
in `dispatch/results`, the goldens, and the test's own source. The arm that
follows is the first thing here that needs a handheld.

## What it corrects

[`stencil-is-intermittently-wrong.md`](stencil-is-intermittently-wrong.md)
established that the outliers are *wrong* rather than *mismeasured*, and
offered a shape for the mechanism:

> Consistent with **the stencil buffer's contents at test time depending on
> work that is not ordered against the draw that reads it** — a clear, or a
> previous test's writes, landing or not landing before the comparison.

The second half of that sentence is wrong and the first half is right for a
reason it did not reach. **No clear is lost, no zeta surface races, and
nothing in `vk/surface.c`, `vk/draw.c` or `vk/command.c` is the site.** The
work that is not ordered against the draw is the guest's rewrite of the
**vertex array the draw reads** — [#44's skew](guest-pgraph-skew.md), which
that document already names as shared with vertex data and with #39.

## The test, from its own source

`nxdk_pgraph_tests/src/tests/stencil_tests.cpp`. Three draws, and the thing
that matters is that all three go through one `CreateGeometry`, which calls
`host_.AllocateVertexBuffer(6)` and writes **six vertices** — a `DefineBiTri`,
laid out `[ul, ll, lr]` then `[ul, lr, ur]`, two triangles sharing a diagonal.

| draw | geometry | vertex colour | colour mask | stencil test | stencil op |
|---|---|---|---|---|---|
| D1 | 200×200, x220..419 y140..339 | **red** | on | **off** | ZERO / REPLACE |
| D2 | 100×100, x270..369 y190..289 | **blue** | **0** | `params` | ZERO / REPLACE |
| D3 | 200×200, same as D1 | **green** | on | on, `EQUAL ref` | KEEP |

`PrepareDraw` clears stencil to `0xFF` for the ZERO tests and `0x00` for the
REPLACE tests, `ref` is 0 and 1 respectively. So the goldens are exactly what
the table predicts, and they were checked rather than assumed:

```
Stencil_REPLACE_ST_ZB   297,200 px stencil 0   +  10,000 px stencil 1 (inner)
Stencil_ZERO_ST_ZB      297,200 px stencil 255 +  10,000 px stencil 0 (inner)
Stencil_REPLACE_ST      30,000 red ring + 10,000 green inner
Stencil_ZERO_ZB         307,200 px stencil 255, uniform
```

Three consequences, and each one is a discriminator later:

- **Blue must never appear.** D2 draws with `COLOR_MASK = 0`. A blue pixel is
  not a shading error; it is D2's *vertex colour* reaching a draw whose colour
  mask is on.
- **Stencil may only be written inside the 100×100 inner square**, and only
  when `_ST` is in the name. D1's stencil test is off, so D1 writes no
  stencil at all.
- **D1 and D3 have identical geometry.** So "a draw used its neighbour's
  vertices" is invisible between those two and loud between either and D2.

## The measurement: 14 runs already on disk

`docs/testing/stencil_outliers.py --floor` scores every Stencil-only-disc run
in `dispatch/results` against the goldens, counting **(run, capture)
observations that are not bit-identical** — never a differing-pixel total and
never a median, because the whole finding is that the majority image is
correct.

```
TOTAL: 25 wrong of 224 (run, capture) observations over 14 runs
       8 of 14 runs carry at least one wrong capture
```

11.2%, across four refs (`8191d97296`, `0026f00534`, `2501f35211`,
`6762a54c82`, `b63603975c`) and on the 4-suite disc as well. This reproduces
the published 8-run figure (11 of 128, 8.6%) on a larger and independent
sample, and it is the floor the arm below is judged against.

## The `_ZB` captures say the stencil buffer really holds the wrong value

Each `_ZB` capture is the zeta buffer read back: `z24 = A<<16|R<<8|G`, stencil
is `B`. On **every** run where a colour capture is wrong, its `_ZB` companion
is wrong over the identical pixel set, with the stencil byte at the value the
colour flip implies:

```
Stencil_ZERO_ST_ZB     ring: golden stencil 255 -> ours 0      30,000 px
Stencil_REPLACE_ST_DT_ZB  ring: golden stencil 0 -> ours 1     30,000 px
Stencil_REPLACE_ST_ZB  inner: golden stencil 1 -> ours 0        5,050 px
```

So the comparison result did not drift; the buffer's contents differ. That
much the previous document had. What it did not have is **where the wrongly
stencilled region is**.

## The regions are TRIANGLES, and that is the whole answer

Fitted with `docs/testing/stencil_outliers.py`'s geometry helpers (the fit
script itself is throwaway; the numbers are reproducible from the captures
named). Each row is *our drawn region*, not the difference mask, because a
difference mask is a symmetric difference and hides the shape.

| capture | drawn region we produced | fits | IoU |
|---|---|---|---|
| `1968847/captures2` `REPLACE_DT` red | D1's tri1 intact **+ tri2 with `ul.x` = 270 instead of 220** | outer tri1 ∪ tri((270,140),(420,340),(420,140)) | **0.9943** |
| `1968847/captures2` `REPLACE_ST` green | **inner tri1 only** | tri((270,191),(270,290),(369,290)) | **1.0000** |
| `116405/captures2` `REPLACE_ST_DT` green | **OUTER tri2 only** | tri((220,140),(420,340),(420,140)) | **0.9980** |
| `116405/captures2` `ZERO_DT` **blue** | **inner tri2 only** | tri((270,190),(370,290),(370,190)) | **0.9960** |
| `1663172/captures1` `ZERO` red | outer bitri **minus** a wedge whose apex sits at y = 190 | `ll.y` = 190 instead of 340 | 5,000 px missing |

Read the second column. These are not regions a stencil comparison can
produce:

1. **One of a quad's two triangles, and not the other.** A stencil state
   applies to a whole `vkCmdDraw`; there is no state that is true for
   `[ul, ll, lr]` and false for `[ul, lr, ur]` of the same six vertices.
2. **A triangle whose corner takes `x` from the 100×100 quad and `y` from the
   200×200 quad.** `ul` appears twice in the six-vertex array (index 0 and
   index 3) and in row 1 the two copies *disagree*: index 0 still holds
   (220,140) while index 3 holds (270,140). That is one vertex caught with its
   `x` rewritten and its `y` not.
3. **Blue, at all.** Row 4 is D2's vertex colour on screen over exactly one of
   D2's triangles, on a draw whose colour mask is zero — so it is D1 (colour
   mask on) rasterising D2's *vertices*.

This is the same evidential shape #44 closed on, one level up: its decisive
row was "ten wrong pixels that are a byte-level mixture inside **one texel** —
which no stale-allocation or missed-re-upload story reaches, and only a read
while a write is in flight does." Here the mixture is inside **one vertex**.

## The single model that explains all of it

The guest's loop is *write the six vertices, publish the draw, write the next
six vertices into the same buffer*. `Pushbuffer::End()` stores DMA_PUT and
returns; `pgraph_vk_update_vertex_ram_buffer` copies out of `d->vram_ptr` when
the PFIFO thread reaches the draw, which can be milliseconds later —
`guest-pgraph-skew.md` measured that window at p50 **8.65 ms** with **100.0%**
of 148,667 submissions made while PGRAPH was not yet current.

Every failure mode in the corpus is one position of that window:

| what the host read for draw N | what you see | corpus row |
|---|---|---|
| D2's vertices, during D1 | **blue** 100×100, red gone | `ZERO` 114603/c3, `ZERO_DT` z-tip |
| D3's vertices, during D2 | stencil written over the whole 200×200, so D3's `EQUAL` passes everywhere → green 40,000, red 0 | the commonest row, 8 observations |
| D2's vertices, during D2, but only some | stencil on **one** triangle | `REPLACE_ST_ZB` 1968847/c2 |
| mid-vertex | a triangle with mixed corners | `REPLACE_DT` 1968847/c2 |

Nothing else is needed. In particular **`Stencil` is not a specially fragile
suite** — it is a three-draw test that rewrites one vertex buffer between
draws with no fence, which makes it an unusually sensitive detector, and its
red/green pass-fail indicator turns a geometry error into a whole-region
colour flip that a differing-pixel count notices.

## What was ruled out, cheaply, before any of this

Read off the run's own logcat (`1789345832-orchestrator-1968834/logcat1.txt`)
rather than reasoned about — the class-is-empty check `AGENTS.md` asks for:

```
draw reorder: OFF      draw merge: OFF      frame skip: OFF
submit frames: 2       accel tcg,thread=multi
```

So the draw-reorder window, the draw-merge queue and the frame-skip early
return in `pgraph_vk_clear_surface` are all provably inert on every run in the
corpus, and none of them can be the mechanism. `thread=multi` is what makes
the guest CPU thread and the PFIFO thread genuinely concurrent.

Also ruled out by reading the code, and recorded so nobody re-reads it:

- **The stencil clear is not lost.** `pgraph_vk_clear_surface` records
  `vkCmdClearAttachments` with `VK_IMAGE_ASPECT_STENCIL_BIT` on the main
  command buffer on both its inline and its pipeline path, in guest order.
- **The render pass never discards stencil.** `create_render_pass` hardcodes
  `stencilLoadOp = LOAD` / `stencilStoreOp = STORE` for the zeta attachment.
  Note in passing that it also *ignores* `RenderPassState.{color,zeta,stencil}
  _load_op` entirely while those fields are part of the `memcmp` cache key, so
  `get_optimal_zeta_load_op` is dead code that only makes `get_render_pass`
  allocate redundant, behaviourally identical passes. That is waste, not a
  correctness bug, and it is in `vk/draw.c` which this lane does not hold.
- **Surface upload/download is ordered.** `pgraph_vk_begin_nondraw_commands`
  returns the **main** command buffer (`vk/draw.c:3231`), not the aux one, so
  a zeta upload or download cannot run ahead of the draws recorded before it.

## The fix already exists, and it is not in this lane's files

`XEMU_OPT_FIFO_SKEW_BOUND` in `hw/xbox/nv2a/pfifo.c`, defaulted to **0**.
Mode 1 holds the guest at its DMA_PUT store until PGRAPH has consumed what
that store published, and `guest-pgraph-skew.md` measured it closing #44's
class outright: `stale_px` 0 on 10 of 10 against 5 of 10 non-zero, all three
stale classes to zero, `held(n)/kicks = 1.0000` over 148,704 submissions. It
is off because it cost `gfps` p90 29 → 13 on Galleon, and mode 2's selectivity
did not recover that.

So #79 does not need a new mechanism. It needs one measurement: **does the
bound that closed the texture half close the vertex half too?** If it does,
#79 is a duplicate of #44's class, the stencil path is exonerated, and the
board carries one cost decision instead of two open defects.

## The arm

`docs/testing/predictions/issue79-stencil-is-skew.json`. Stencil disc ×4 per
arm on the thor, arm A `d97d506514` and arm B `ec7f50e859` — the same pair
`guest-pgraph-skew.md` used, verified here with `git diff --stat` to be **one
line in one file**, `XEMU_OPT_FIFO_SKEW_BOUND` 0 against 1, and both APKs are
already in the dispatcher's build cache so the arm costs no build. Both refs
sit 292 commits behind the campaign tip, *equally*, which is what makes them a
pair; the flake reproduces at every ref in the corpus, including the tip, so
the base is not doing the work.

Four runs per arm, because a single Stencil number means nothing — that is
this issue's whole content.

**V0 (VALIDITY GATE, arm A alone; the pair is VOID if it fails).** Arm A shows
at least **2** wrong (run, capture) observations in its 4 × 16 = 64. At the
measured 11.2% the expectation is 7.2 and P(fewer than 2) ≈ 0.5%, so a clean
arm A means the instrument is pointing at nothing and V1 proves nothing.

**V1 (THE BAR).** Arm B shows **0** wrong observations in 64. Under the null
that the bound does nothing, P = 0.888^64 ≈ 0.0005.

**V2 (DID IT EXECUTE, on the counter and not a proxy).** `fifoskew`'s
`held(n)/kicks` ≥ 0.90 on arm B and `held(n)` = 0 on arm A. A flat count
cannot separate a change that never ran from one that ran and returned a
different wrong answer.

V1 and V2 are in tension on purpose: turning the bound off passes neither, and
a bound that is in force but irrelevant to Stencil passes V2 and fails V1 —
which is the outcome that would **refute** this document while leaving #44
untouched.

**What a V1 failure would mean.** Not that the skew model is wrong in general
— #44 is settled — but that Stencil's outliers have a second cause that the
bound does not reach, and the place to look next is `sync_vertex_ram_buffer`'s
`OPT_SYNC_RANGE_SKIP` early exit, which can decline to re-copy a range on a
dirty-bitmap read rather than on the draw's own ordering.
