# The shape carries no address — and that is not why anything is stale (#92)

`lane.blitsafe`, 2026-09-18. Covers **#92** (the verdict, from reading, with
the run it still needs), **#89** (why the clear-format narrowing is expected to
be inert), and what is left on **#88** and **#91**.

No run happened here. **This session could not execute a build or a run at
all** — every compiler, `configure` and package-probe invocation available to
it requires an approval it cannot obtain non-interactively, and the host has
never had a desktop build (`qemu-system-i386` exists nowhere under `$HOME`, and
`~/.local/share/xemu/xemu/xemu.toml` does not exist). That is a statement about
this session, not about the fleet: `hakux-backup/x1box/` holds `mcpx.bin`,
`flash.bin`, `eeprom.bin` and an HDD image, so the desktop path in
[`../testing/desktop-runs.md`](../testing/desktop-runs.md) is blocked on build
dependencies and an approval, not on ROMs. Everything below is **read**, and
every claim in it names the line it was read from so the next lane can refute
it in a minute rather than re-derive it.

## #92, the verdict

**The premise is true.** `SurfaceShape` (`pgraph/surface.h:25-33`) is formats,
geometry, clip and anti-aliasing. There is no address of any kind in it, and
`framebuffer_dirty()` is a `memcmp` of exactly that struct
(`vk/surface.c:117-126`, duplicated verbatim at `gl/surface.c:997`). It cannot
see a DMA-context swap.

**The consequence does not follow, and that is the finding.** The issue reads
"so the framebuffer reads as clean when the memory underneath it has moved" —
the second half is the part that is not established. The shape is the
*shape*-change signal. The *address*-change signal is `buffer_dirty`, and it is
set at every method that can move a surface:

| method | site | what it sets |
|---|---|---|
| `SET_CONTEXT_DMA_COLOR` | `pgraph.c:2381-2388` | `surface_color.buffer_dirty = true`, unconditionally — **one line below the `dma_color` write itself** |
| `SET_CONTEXT_DMA_ZETA` | `pgraph.c:2390-2394` | `surface_zeta.buffer_dirty = true` |
| `SET_SURFACE_COLOR_OFFSET` | `pgraph.c:2539-2544` | `buffer_dirty |= offset changed` |
| `SET_SURFACE_ZETA_OFFSET` | `pgraph.c:2546-2551` | as above |
| `SET_SURFACE_PITCH` | `pgraph.c:2526-2537` | as above, both targets |

and `update_surface_part()`'s gate is
`!current_binding || (upload && (buffer_dirty || mem_dirty))`
(`vk/surface.c:3308-3312`), so a set `buffer_dirty` re-resolves the binding by
address whatever the shape said. `pgraph_vk_surface_update()` also calls
`unbind_surface()` before it (`:3675-3685`), and that NULLs the binding
(`:1931`), which the `!current_binding` term then catches.

**So a verdict log answers nothing.** `framebuffer_dirty() == false` at a
`SET_CONTEXT_DMA_COLOR` is exactly what both worlds produce:

- (a) the swap went unseen and a stale binding was kept — the defect; and
- (b) the swap was seen by `buffer_dirty` and the binding was re-resolved —
  no defect, same verdict.

An instrument that reads the same in both worlds is not worth an arm. Measure
the discriminating event, not the convenient one.

**What was landed instead.** `surf92_probe()` (`vk/surface.c:186-221`) counts
an upload-side `update_surface_part()` whose **target address differs from the
address of the binding it already holds, while the gate that would re-resolve
it is shut**. That cannot occur in world (b) and must occur in world (a).

- `missed = 0` over a run containing `TestSwap()` **refutes #92's consequence
  and leaves its premise standing.**
- `missed > 0` **confirms it** and the same line names the caller, the held
  address and the wanted one.

**The route most likely to make `missed` nonzero is not in the issue.**
`target->vram_addr` is `dma.address + surface->offset` (`vk/surface.c:3222`),
and `dma.address` is read out of the DMA object *in instance memory* by
`nv_dma_load()` on **every** call. A guest that rewrites that object in place
moves the surface with no method write at all — unseen by *both* signals rather
than by the shape alone. Whether the suite does this is a measurement, and it
is the one `missed` makes.

**The shape is not wholly address-blind in effect, either**, which is worth
recording because it cuts against the issue's framing: `clip_x`/`clip_y` feed
the target address through `populate_surface_binding_target()`, and they *are*
in the shape. A clip change moves the address and `framebuffer_dirty()` does
catch it.

### The one hole reading does find

`framebuffer_dirty()` returns **false on a changed shape** when
`!color_format && !zeta_format` (`vk/surface.c:121-124`). In that state a
format change is not propagated at all. It is the only path by which a binding
can outlive the register that resolved it — and it is why #89's narrowing is
*expected* to be inert rather than *provably* inert.

**Not fixed here, deliberately.** That function is duplicated verbatim in
`gl/surface.c:997`, so changing it changes **surface identity on both
renderers** — #55 and #60's ground. It wants its own arm.

### What #92 still needs

One run of a disc containing `Color zeta overlap`, with the logcat grepped for
`[surf92]`. `missed=` is the answer. Silence is **void**, not pass: both probes
print on a heartbeat as well as on the event precisely so that a filtered tag
is distinguishable from a condition that never occurred
(`docs/testing/dispatcher.sh:934`).

### And the shared-struct argument for `Swap` has a rival

#92's motivating observation is that `Color_zeta_overlap/Swap` reads 165,447 on
GL **and** Vulkan, which a defect in shared structure would explain. So would a
second shared thing: both renderers must pick a winner when the guest points
colour and zeta at one address, because neither API can make one image both
attachments. #91's byte signature — a Z24S8 depth field zeroed *inside* a
colour surface, `0xFE242424` → `0x00000024` — is an aliasing signature, not a
stale-binding one. Two candidates, one of them now instrumented.

## #89: the narrowing is a correctness fix, not the 141,125

`pgraph_vk_get_clear_color()` took its pad-alpha decision from
`pgraph_vk_surface_drawn_format(r->color_binding)` — what the surface was last
drawn with. It now takes it from `pg->surface_shape.color_format`, which is the
register hardware stamps from at the time of the clear. **A narrowing of #59's
stamp and not a revert**: the clear always wrote 1.0 before #59, so a revert
restores a different defect.

**It is predicted to be inert**, and registered that way
(`docs/testing/predictions/issue89-clear-pad-alpha-shape.json`). #59 keyed this
side on the binding so it could not disagree with the sample side; the
invariant that defence protects is now maintained at its source:

1. `vk/surface.c:3500` — the compatible-reuse path — assigns
   `surface->drawn_format` **and** `surface->host_fmt` together from the live
   target, so a reused binding no longer answers for the format that created
   it, and the sample side tracks the live format through the same assignment.
2. `target.drawn_format` **is** `pg->surface_shape.color_format`
   (`vk/surface.c:3215`).
3. `SET_SURFACE_FORMAT` does not set `buffer_dirty` for a format-only change
   (`pgraph.c:2461-2524`), but `framebuffer_dirty()` compares the whole shape,
   colour format included, and forces the re-resolve above.
4. `pgraph_vk_clear_surface()` calls that `surface_update` before every clear
   (`vk/draw.c:6751`), and `pgraph_vk_get_clear_color()` is reached from
   nowhere else.

So the old and new expressions agree by construction in every state the suite
can reach, **except** the `!color_format && !zeta_format` hole above.

This agrees with the device rather than arguing against it: #89's arms D, E and
F each put one `Blend surface` test of one pad-alpha class ahead of the suite —
including the `_O` format, the only shape that reaches `rgba[3] = 1.0f` — and
all three read **0**. The mechanism is withdrawn on the issue. The narrowing is
worth landing anyway because a decision taken from a tracker rather than from
the tracked register is a defect waiting for the tracker to slip; it is not
worth claiming a capture for.

**The brief's falsifier, kept and inverted.** It said: if the divergence is the
mechanism, `Blend surface` moves and `Color mask blend` does not. Both are
registered `must_not_move`, because the reading says neither moves. The
partition still discriminates — `Blend_surface` alone moving means the
divergence is reachable and this reading is **wrong**, which is the finding the
arm exists to get. `Color_mask_blend` alone moving is the impossible row:
`PAD_ALPHA_NONE` takes neither branch of the switch under either source.

## #88 and #91: what is missing, named

**#88 has its patch and its arm, and both landed.** The policy commit is on
this branch; the arm was judged PRE-REGISTERED with both absolutes hit to the
digit, and #91's two solo arms then **exonerated the policy on `Swap`** —
304,750 on a solo disc in *both* refs, byte-identical. What remains on #88 is
not a measurement: the policy cancels a compensation the disc composition was
supplying for a **pre-existing** defect, and whether to ship a change that
exposes one is an owner's call, not a lane's. Recorded rather than decided.

**#91 has no patch and this is why.** Its regression is not what the issue
says: the three colour populations are partitioned identically in both arms
(165,447 quad, 139,303 background, 2,450 text), which a change to depth
*testing* could not do — it would move the boundary between populations.
Only the background's value changed, from `0xFE242424` (the test's own
`PrepareDraw(0xFE242424, 0)`) to `0x00000024`: **bits 8-31 zeroed, bits 0-7
preserved**, which is a Z24S8 depth-only clear written over a colour surface,
stencil byte untouched, the surviving `0x24` being the clear colour's own low
byte.

Reading `pgraph_vk_clear_surface()` against that: the inline path guards
`write_zeta && r->zeta_binding` (`vk/draw.c:6876`) and the fall-through path
guards identically (`:6972`), so neither issues a depth clear with no zeta
binding. The signature therefore needs **one image to have received both
clears**, which is the aliasing case — and that is a design question about
supporting a same colour/zeta target, not a drive-by. Neither 165,447 nor
304,750 is correct in any case: even at 165,447 the quad is `#E91A24` against
the golden's `#E91624`, off by 4 in green.

**What #91 is missing, precisely:** a route by which one image takes the colour
clear and then the depth clear within `TestSwap()`. Reading
`update_surface_part()` against `TestSwap()` does not reproduce the decline
firing inside `Swap` at all — `SET_CONTEXT_DMA_COLOR` rebinds colour to the
zeta address *first*, so when zeta asks for the colour address it finds an
object that is no longer `r->color_binding` and `surface == other` is false.
That gap is exactly what `[surf92]`'s `held=`/`want=` addresses print, which is
why one log run now serves #91, #92 and #89 alike.

## The nv2a index is stale and this lane cannot regenerate it

`nv2a_index.py check` fails on 74 moved sites, all in the two files edited
here, so by `preflight.sh`'s own attribution rule the staleness **is** this
lane's. It is not regenerated, and the reason is a dated artefact rather than a
preference: the committed index was built from `nxdk_pgraph_tests` at
`91a0de45`, and the checkout on this host is `33e7c6b0`, which **does not
contain the `Surface as vertex array` suite**. Regenerating here writes 102
suites where 103 are committed — it would silently delete a suite from the
issue↔suite map to fix line numbers.

The fold needs `nv2a_index.py build --tests <checkout at 91a0de45 or newer>
--support /home/justin/pbkitplusplus`. Checked, not assumed:
`grep "Surface as vertex array"` over the local checkout returns nothing.
