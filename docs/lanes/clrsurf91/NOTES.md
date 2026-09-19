# lane.clrsurf91 -- #91: a zeta image is downloaded over a colour address

**Branch** `lane/clrsurf91`, base `origin/master` @ `6ca12eb803`. **PR #148.**
Files touched: `hw/xbox/nv2a/pgraph/vk/surface.c` only. `vk/draw.c` was granted
and is **not** edited; why is below, because it is the substantive finding.

## What this lane changed

`update_surface_part()`'s gate was

```c
bool gate_open = !current_binding || (upload && (buffer_dirty || mem_dirty));
```

and is now

```c
bool gate_open = upload && (!current_binding || buffer_dirty || mem_dirty);
```

plus a tail that copes with the NULL binding that change makes reachable: it
skips the download and **retires the flags**. Plus `dl91_probe()`, which counts
the declined downloads.

The upload side is bit-identical -- the two predicates agree whenever `upload`
is true. Only the download side changes, and only by declining to invent a
binding.

## The finding, and why the issue's own attribution sent two lanes at a wall

The tracker's live falsifier says the `0xFE242424 -> 0x00000024` background is
"a Z24S8 depth-only clear of 0 landing on the COLOUR surface" and points the
next lane at `pgraph_vk_clear_surface()`. **The byte arithmetic is right and
the word "clear" is wrong.**

Both clear paths in `vk/draw.c` guard `write_zeta && r->zeta_binding` -- the
inline one at the `vkCmdClearAttachments` block and the fall-through pipeline
one the brief pointed me at. I read both. Neither can issue a depth clear with
no zeta binding, and the signature needs *one image to have taken both clears*.
lane.blitsafe hit this wall and said so; the brief's "look at the fall-through
PIPELINE clear path instead" is the same wall one step along. **Do not spend a
third lane there.**

The same word falls out of the surface conversion path with no free parameter:

| step | where | result |
|---|---|---|
| VRAM holds the colour clear | `PrepareDraw(0xFE242424, 0)` | `0xFE242424` |
| a Z24S8 zeta image is uploaded from it | `unpack_z24s8_to_d32_sfloat_s8_uint_glsl` | depth `0xFE2424`, stencil `0x24` |
| the test's own depth clear of 0, on the legitimate zeta target | correctly guarded | depth `0`, stencil **untouched** |
| that image is packed back over VRAM | `pack_*_to_z24s8`, `depth << 8 \| stencil` | **`0x00000024`** |

So nothing mis-clears anything. **A zeta image is downloaded over a colour
address.** That also accounts for the one fact the clear model could not, and
which the record notes and then argues past: the three colour populations are
partitioned *identically* in both arms (165,447 / 139,303 / 2,450) while only
the background's **value** moves. A clear lands on pixels and moves a boundary;
a download lands on a whole surface and moves a value.

### The route

`pgraph_vk_set_surface_dirty()` sets `pg->surface_zeta.draw_dirty` from `zeta`
**alone** -- the per-binding flag on the line below it is guarded by
`r->zeta_binding`, the Surface-level one is not. So the `Surface` can carry
`draw_dirty` with no binding behind it. `pgraph_vk_surface_update()`'s download
branch then re-enters `update_surface_part(d, false, false)` on the strength of
that flag, and the old gate was open **by definition** because the binding was
absent. The gate is not a cache-hit test: it unbinds, resolves the target
address, evicts or creates a surface there and **binds** it -- and then the
tail downloads what it just bound over guest VRAM. The address it resolves
comes from the **current registers**, not from wherever the draw went.
`TestSwap()` is the test that trades the two addresses.

### GL already has the fixed form, and #88's prediction saw the difference and read it as benign

The strongest independent evidence, found after the fix was written and not
used to derive it. `pgraph/gl/surface.c:2956`:

```c
if (upload && (surface->buffer_dirty || no_binding)) {
```

That is exactly the shape this change gives Vulkan. **GL has gated the
absent-binding term on `upload` all along**, so on GL a download has never
been able to resolve a binding.

And this was *noticed*. #88's own registered prediction says, in terms:

> Vulkan's gate is already `!current_binding || (upload && (pg_surface->buffer_dirty || mem_dirty))` [...] and it is **strictly MORE permissive** than GL's fixed form because it is not gated on `upload`. So ONLY THE POLICY IS PORTED.

The observation is exact and the inference from it is the defect: "strictly
more permissive" was read as harmless breadth, and the conclusion drawn was
that the gate needed no porting. The half of #66's chain that was skipped is
the half that mattered here. **A renderer difference that has been written
down and dismissed is worth re-reading before it is worth re-deriving.**

This citation is deliberately **not** added to the code comment in
`vk/surface.c`. It was found after `7980d1caa2` was written, and that commit is
the arm's `b_ref`; leaving the tree byte-identical to the binary the arm
measures is worth more than a comment, which is why it lives here and in #148
instead. It belongs in the code the next time that function is edited for a
reason.

One thing this comparison does *not* license, stated so it is not carried
further: GL's `unbind_surface()` does not clear `draw_dirty` either, so GL's
own tail (`gl/surface.c:3212`) can in principle reach `surface_download(d,
NULL, true)`. Whether that is reachable or guarded downstream was **not**
established here -- `gl/surface.c` is not this lane's file and was read only
for the gate. It is an observation for whoever owns that file, not a finding.

### This resolves blitsafe's impasse rather than picking a side of it

blitsafe established by reading that the decline **cannot fire inside `Swap`**
(`SET_CONTEXT_DMA_COLOR` sets `surface_color.buffer_dirty`, `pgraph.c:2387`, so
colour rebinds first and `surface == other` is false when zeta asks) and
refused to fit a patch to the half it could not establish. **That reading is
correct**, and it is not in tension with the measurement: this route does not
need the decline to fire in `Swap` at all. #88's policy does not create the
route, it **widens** it, by leaving zeta's binding absent far more often. The
"one of those two halves is wrong" framing had a third answer.

The withdrawn patch's known second defect -- the decline returning early with
`draw_dirty` left set, written into the file by `f147a588b1` -- is the same
mechanism reached by a shorter path. This fixes both, at the consumer.

## The arm, and the branch shape it forced

**The regression is unreachable on master.** Master's overlap policy has
whichever unit asks last evict the other, so zeta rebinds immediately and the
binding-less download essentially never happens. An arm of `master ->
master+fix` would score `Swap` at 165,447 in **both** arms and return a clean
PASS having tested nothing. That is an inert control and it discharges no
blocker: no change in the patch could move the leg.

So the branch is four commits and the middle two are a matched pair:

| commit | what |
|---|---|
| `aec524681e` | **arm scaffolding** -- restores `67dc7724ee`'s decline verbatim. **a_ref.** |
| `7980d1caa2` | the fix, on top of the policy. **b_ref.** |
| `b86517efe7` | **arm scaffolding** -- withdraws the decline again. |
| (tip) | prediction, index, these notes |

The policy is therefore **constant in both arms** and the fix is the single
variable, while the branch's net diff against master is the fix alone. Verified
rather than asserted: `git diff clrsurf91-fix HEAD` is empty, i.e. the tip tree
is byte-identical to master-plus-fix.

**The tension this has with M3, stated rather than glossed:** M3 wants a fix
arm's `b_ref` to be the code that ships, and `7980d1caa2` is not -- it carries
#88's policy. The alternative was an arm that measures nothing. I took the
measurement and made the scaffolding visible and self-cancelling; an auditor
who disagrees should say so on #148 rather than silently re-running it.

`67dc7724ee` is itself a live ancestor and the dispatcher would accept it as a
ref, but it sits **195 commits** behind master, so an arm across it would
differ by those 195 commits too and could attribute nothing.

**Registered:** `docs/testing/predictions/issue91-download-may-not-resolve-a-binding.json`,
sha256 `dfcf84103eb3`, three-suite disc. Not queued by this lane.

## What is NOT established, so the next actor does not inherit it as fact

- **Nothing here was measured on a device.** Every claim above is reading plus
  arithmetic. The arithmetic closes exactly, which is why it is worth an arm;
  it is not why it is true.
- **The fix's effect under master's policy is untested by construction** --
  neither arm is master. It is *expected* to be inert on master's scores. If
  that matters to someone, it is a different arm.
- **`n>0` on `dl91_probe` is a precondition, not the pixel claim.** The old
  code would have downloaded whatever sat at the current target address, which
  is only wrong when that address is not where the draw went. The pixel claim
  belongs to the A/B.
- **No Khronos validation-layer run.** This changes when a binding exists,
  which is exactly the class the layer found eight defects in (#34), and the
  desktop build is a known gap on this host. Reading was substituted. Reading
  is an argument, not a run.
- **Neither 165,447 nor 304,750 is correct**, and this lane does not fix that.
  At 165,447 the quad is still `#E91A24` against the golden's `#E91624`, off by
  4 in green. This arm claims the **background**, not the quad. A PASS means
  the stray download is gone, not that `Swap` is right. That residual is a
  separate defect and belongs to #92's neighbourhood, not here.

## Two corrections to the record the next actor should not re-derive

1. **The tracker's #91 `status_note` still ends on a conclusion its own issue
   comments refuted.** It says the solo disc read 304,750 in **both** arms, so
   "304,750 is simply `Swap`'s value when nothing precedes it" and "the policy
   is exonerated on `Swap`". The 2026-09-19 08:06Z and 09:30Z comments on #91
   record that `jobs/arms.sh` never passes `--only-tests` -- it builds its
   request from `disc.suites` alone -- so that arm ran the **full nine-capture
   suite**, was never solo, and read 165,447 -> 304,750 like the other disc.
   The exoneration does not stand, and the `status_note` has not been updated.
   A board request should correct it; this lane may not edit the tracker.
2. **The brief says the two diagnosis arms "found the regression intrinsic, not
   contamination from ColorIntoZeta".** Cross-suite composition is excluded;
   *within*-suite contamination is exactly what those comments say **remains**
   open. It does not change this fix -- the route is a download, not a
   predecessor -- but do not carry "contamination is excluded" forward as
   settled.

## What the next lane should not repeat

- Do not re-read the clear paths. Both are correctly guarded, three lanes have
  now confirmed it, and the signature is not a clear.
- Do not re-run the solo/contamination classification arm. It cannot be
  narrowed until `arms.sh` passes `--only-tests`, which is a filed harness
  defect, and the two runs that were spent on it are already read.
- Do not register an absolute for `Swap` on a **narrowed** disc. #89 measured a
  capture in this very suite moving 141,125 px on composition alone, so
  composition can violate the leg and read as a refutation of the mechanism.
  This prediction uses #88's three-suite disc for that reason.
