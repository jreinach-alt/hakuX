# Audit pass 2 — #84's narrow-format refusal and #88's overlap policy, over the remediation of pass 1

**Lane** `lane.audit2-blitsafe` (territory wave 86, claims no files).
**Subject** `lane.blitsafe`, branch `worktree-agent-aa4f3448ff981e82f`, tip
**`4e795536df`**, four commits over base `989854ac9e`, reordered so each arm
tests one change:

| commit | what |
|---|---|
| `70e4073441` | #84 — `BLEND_AND` refuses narrow formats |
| `f343580647` | **M1** — refuse at the entry, not in the leaf; **arm A ref** |
| `4726557b0f` | #88 — colour keeps a surface zeta wants; **arm B ref** |
| `4e795536df` | **M2/M3** — re-bind the prediction |

**Pass 1's record** `docs/audits/2026-09-18-blitsafe-pass1.{md,json}` — 0 HIGH,
3 MEDIUM, 3 LOW.
**Date** 2026-09-18. **Records** `2026-09-18-blitsafe-pass2.json` (flat array,
schema as `2026-09-18-padwrite-pass2.json`: `pass1_id` or `pass2_id`,
`severity`, `file`, `line`, `verdict`, `summary`, `scenario`, `remediation`,
`evidence`, optional `decision`).

**2 MEDIUM CLOSED. 1 MEDIUM OPEN and contained by design. 1 LOW CLOSED, 2 LOW
DECIDED and both declines accepted. 5 new LOW — two with real gate-level
scenarios, one scope limit, one labelled an opinion, one a coverage debt.**

**The compiled code is clean.** M1 is closed, and closed on the strongest form
of the check: the hoist the lane took *beyond* what the finding asked for is
safe, and I verified the reading it claimed rather than the conclusion it drew.
No new HIGH and no new MEDIUM in `hw/`. That is the point of the exercise and
it is what I found, so I say it plainly.

**Two things are not clean, and neither is in `hw/`.** M3 is OPEN — the
prediction copy committed on the campaign branch still names two refs that are
now reachable from **no ref at all**. And the Khronos validation layer is
**owed, not covered**, on two independent blockers where the lane named one.

**The fold should proceed**, with two conditions and one debt named. They are
at the end.

---

## M1 — CLOSED, and the extra hoist is an improvement rather than a risk

### The three line relationships hold

Checked at the commit, not read off the message:

| what | line at `f343580647` |
|---|---|
| guard returns | **`blit.c:498`** (condition `:487-488`) |
| first destructive write, `surf_dest->download_pending = false` | **`:615`** |
| `draw_dirty = false` / `upload_pending = true` / `pg->draw_time++` | `:616` / `:618` / `:619` |
| dirty marks — VGA, NV2A_TEX, NV2A | **`:734`**, `:736`, **`:744`** |

117 lines to the first destructive write, 236 to the first dirty mark. The
commit says the marks are at `:734-746`; `:744` is the third call's statement
and its arguments close at `:745`, so the range is `:734-745` and the claim is
right to within the statement's own extent.

### "Nothing between the switch and the guard" is vacuously true

The `bytes_per_pixel` switch's `default:` arm ends at `:461`. The guard's
comment opens at `:463`. **They are adjacent.** There is no intervening code to
mutate anything, so the claim the lane says it verified by reading is true in
the strongest possible way — and also the least interesting way, because it is
not the question the extra hoist raises.

### The question the extra hoist actually raises, and the answer

Pass 1 asked for the guard immediately before the `surf_dest` block. The lane
put it ~120 lines earlier. What the extra distance skips is three classes and
nothing else:

1. **Two asserts** — `source_offset < source_dma_len` (`:504`) and
   `dest_offset < dest_dma_len` (`:511`). Their only effect is an abort.
2. **Three VRAM download-if-dirty syncs** —
   `pgraph_vk_surface_download_if_dirty(surf_src)` (`:516`) and
   `pgraph_vk_download_surfaces_in_range_if_dirty()` over the source and dest
   ranges (`:547-550`).
3. **Three pure lookups** — `nv_dma_map()`, `pgraph_vk_surface_get()`, and
   `nv_clip_gpu_tile_blit()`, which I read in full at `nv2a.c:101-119`: it
   reads `d->pfb.regs`, returns a length, and mutates nothing.

**Is the source download needed by any path that still proceeds?** No path
proceeds — the guard is a full return from the renderer op. And critically,
`pgraph_vk_surface_update(d, false, true, true)` sits at **`:434`, above the
guard**, so the bound colour/zeta flush is *not* skipped.

**Is it needed by anything afterwards?** No. All three syncs are lazy, keyed on
dirty flags they clear themselves, and the comment at `:536-546` states their
purpose exactly: to order VRAM against *this blit's* own read and write, after
issue #7 measured a blit writing a pixel into VRAM that a later surface
download overwrote. With no read and no write there is nothing to order. The
overlapping surfaces stay marked dirty and the next consumer downloads them.

So the lane's argument is correct, and its correctness has a clean form: a
refused blit is now indistinguishable from a blit the guest never issued.

### The leaf's remaining `return` is unreachable, not a second silent policy

This is the check the brief singled out, because pass 2's precedent is an
`assert` implied by the condition it sat under.

- `bytes_per_pixel` is assigned **only** in the switch (`:446`, `:449`, `:455`)
  and never reassigned.
- `image_blit->operation` is **never written** anywhere in `blit.c` — it is
  read at `:487` (the guard) and at `:627`, `:634`, `:648`, `:657` (the four
  blit calls), and written only by the method handler at `pgraph.c:2087`.
- `perform_blit_tiled()` forwards `bytes_per_pixel` verbatim (`:385-386`).

Therefore `operation == BLEND_AND` implies `bytes_per_pixel == 4` at every call
site, and the leaf's `if (bytes_per_pixel != 4) return;` at `:119-120` cannot
be reached.

**And it is the right shape.** It is a bare `return`, not an `assert`, so
nothing depends on it firing — which is exactly why it is not the trap pass 2
caught last time. A *silent policy* would be a path that reaches the leaf with
`BLEND_AND` and a narrow format and quietly declines after the bookkeeping has
been committed. No such path exists.

### The positive control, verified on the object rather than taken on report

The lane's control is symbol-level. I checked it against the actual compiled
object in its worktree:

    b pgraph_vk_image_blit.warned      <- present
      perform_blit.warned              <- ABSENT
    t perform_blit                     <- still present as a function
    t perform_blit_tiled               <- still present
    b pgraph_vk_solid_line.warned      <- its own two, matching its two guards
    b pgraph_vk_solid_line.warned.8
    warn string count: 1

**I dated the artefact before trusting it**, because a stale object measures
beautifully. The object's mtime is **11:48:50** and the commit it is supposed to
demonstrate is **11:50:34** — the object *predates its own commit by 1m44s*,
which on its own cannot distinguish a post-edit build from a pre-edit one.

The string settles it. The object contains
`"nv2a: BLEND_AND blit at %u bytes/pixel is not implemented; skipping the blit
rather than overrunning the destination"`. The pre-hoist leaf wording was
`skipping the blend`. **`blit`, not `blend`** — so the object is unambiguously
built from the hoisted source, and the control is genuine.

---

## M2 — CLOSED

Both arms were queued as a three-suite disc and all eleven legs bound.

    arm A  1789757714-lane.blitsafe-1346028  ref f343580647  runs 5  DONE 12:04
    arm B  1789757726-lane.blitsafe-1346326  ref 4726557b0f  runs 5  DONE 12:13

Both `request.json` carry
`"suites": ["Color zeta overlap", "Color Zeta Disable", "Null surface"]` and
`expect_sha = 82d5435d56d75afc`, which is the sha256 of the corrected
prediction. The file carries 9 `must_not_move` keys plus 2 `expect` keys — the
eleven legs — and the two pass 1 named as out-of-suite,
`Color_Zeta_Disable/MaskOff_ZB` and `Null_surface/XemuBug893`, are in the disc
by name.

Arm A run 1 scoring all eleven on `disc_id 3-suites:e0a8f913` is settled ahead
of this pass and **is not re-derived here**. What I verified is the queue shape
that makes it possible, which is the half pass 1's scenario turned on.

The apparatus half pass 1 routed to `lane.toolsmith` — `request.sh` building
its key set from `$GOLDENS/<suite>/*.png`, so it answers "does a golden exist"
and never "will this arm score it" — is unchanged and still blind. Not this
lane's file, not a fold blocker. The residual for a *re-queue* is **N2**.

**Both arms are DONE and neither is judged.** That is a live unblocked action
and it is not mine; it is the lane's or the orchestrator's. My fold verdict is
about the audit findings, and the arm's verdict is a separate gate.

---

## M3 — OPEN, contained by design, and this is what my verdict releases

The arms are re-bound correctly: `a_ref f343580647`, `b_ref 4726557b0f`, both
ancestors of the lane branch, checked with `merge-base` and not assumed. But
the copy **committed on the campaign branch** is still the superseded one:

| copy | sha256 | `a_ref` → `b_ref` | keys |
|---|---|---|---|
| branch, at `048f0a29af` | `a03e76143e99cf8b` | `12870b8fde` → `e71a9952d1` | 9 |
| what the arms are bound to | **`82d5435d56d75afc`** | `f343580647` → `4726557b0f` | 9 + 2 |

### One fact pass 1 did not have, and it makes the window worse

**`12870b8fde` and `e71a9952d1` are now reachable from no ref at all.**
`git cat-file -e` succeeds for both; `git for-each-ref --contains` returns
nothing for either. (For contrast, `79883d81ad` — the commit that folded the
prediction ahead of its code — is reachable from five branches.)

So the failure is bracketed on both sides and nothing tells you which side you
are on:

- a dispatcher that resolves a ref **by sha** still builds them, and still
  produces a clean, confident measurement of the pre-fold tree — pass 1's
  scenario unchanged, failing in the direction that looks like success;
- an **ancestry check** would refuse them, and no such gate exists;
- **gc** will eventually delete them, at which point the same request fails
  loudly instead.

Judging against the branch path additionally reads `TAMPERED`, because
`expect_sha 82d5435d` does not match `a03e7614`.

### The second scenario, and it is the one the fold controls

Both arms' `request.json` point `expect` at an **absolute path inside the
locked worktree**:

    /home/justin/hakuX/.claude/worktrees/agent-aa4f3448ff981e82f/docs/testing/predictions/issue88-vk-same-offset-colour-wins.json

and at refs reachable only from that worktree's branch. Both arms are DONE but
unjudged. If the fold prunes or resets that branch, the two runs on disk can no
longer be rebuilt or reproduced, and the rerun this project's own practice
calls for on a single-run score change becomes impossible.

### The fix is one clean cherry-pick, and I checked that rather than assuming it

    git rev-parse 048f0a29af:<prediction>   == 30d596da3cca4d943717f1aec1c8da7f8682fb40
    git rev-parse 4e795536df^:<prediction>  == 30d596da3cca4d943717f1aec1c8da7f8682fb40

The pre-image is **byte-identical**, so `4e795536df` applies to the campaign
tip with no conflict. Folding code-only is the exact mechanism that broke this
the first time — the prediction commit was folded ahead of its own code, the
rebase found nothing left to apply, and dropped it silently.

---

## L1 — CLOSED

Fixed, and the corrected count is correct. I re-derived it at the commit rather
than accepting the correction: `perform_blit()` has three call sites,
`blit.c:383` (from inside `perform_blit_tiled`), `:634` and `:657`; the
definition is at `:34`; `perform_blit_tiled()`'s own two calls are at `:627`
and `:648` and already carried `bytes_per_pixel`. Three, exactly as stated. The
lane also names its own error — it counted the definition — which is the part
that stops the next reader re-trusting the wrong number.

---

## L2 — DECIDED, and I accept the decline

> "Declining the code change: `width` can only SHRINK there, so it is a wrong
> picture and never an overrun; it is pre-existing and needs a valid GPU tile
> plus a blit that overruns it; and aligning `chunk` would alter the tiled
> `BLEND_AND` path that `BlitBeyondWidth` is bit-exact on, with no arm to catch
> it. My change strictly reduces its surface, since narrow formats no longer
> reach the branch at all."

**Accepted.** All three reasons hold. `chunk / bytes_per_pixel` truncates
downward, so `width` can only shrink and no extra byte is ever touched; the
site is untouched by either commit; and aligning `chunk` would change the
chunking of the tiled path for `SRCCOPY` as well as `BLEND_AND`, which
`BlitBeyondWidth` is bit-exact on and which no arm on this fleet can regression-
check. Bundling an unmeasurable change to a bit-exact path into a memory-safety
fix is the wrong trade, and pass 1 said the documentation *was* the expected
remediation. The comment at `blit.c:108-118` now names the exception, which
completes the "the clamp is authoritative" argument the whole fix rests on.

**I checked the "strictly reduces" claim separately**, because that is the kind
of claim that quietly becomes "and therefore fixed it". It is true and it is
not the stronger claim. Y8 and R5G6B5 can no longer reach the `BLEND_AND`
branch, so the 4x and 2x cases are gone — but the **32bpp case pass 1 actually
described is untouched**: `chunk = 16 - (offset % 16)` at `:380`, with a
`dest_offset` that `pgraph.c:2024` masks with `0x07FFFFFF` and does not align,
so `chunk % 4 != 0` is still reachable and `chunk / 4` still truncates while
`done += chunk` still advances. The lane does not claim otherwise. The residual
stays open as pre-existing, and it is now documented where the next reader will
find it.

---

## L3 — DECIDED, both declines accepted, and one of them is *better* justified than the lane argued

> "Clearing `draw_dirty` would discard true pg-level state on a path that is
> not a draw; gating on `upload` would reintroduce #88's eviction through the
> download path. It accepts a hash lookup instead, arguing it is still cheaper
> than the two render-pass breaks per update the old policy paid."

**Accepted, both — with one correction in the lane's favour.**

**On gating the decline on `upload`:** this is not a smaller version of the
fix, it *is* the defect. With `upload == false` and `zeta_binding == NULL` the
Vulkan gate at `surface.c:3213-3214` opens on the `!current_binding` disjunct
alone, and the tail at `:3536-3549` calls
`download_surface_deferred(d, r->zeta_binding)` — whose **first statement
dereferences its argument** (`if (!surface->draw_dirty || ...)`,
`surface.c:1362-1367`). So without the early return the download path would
have to bind something to survive, which is precisely the create-zeta,
evict-colour, copy-a-never-rendered-image behaviour #88 exists to remove. **The
return is load-bearing, not merely preferable.**

**On clearing `draw_dirty` and `write_enabled_cache`:** accepted.
`pg->surface_zeta.draw_dirty` is pg-level state, set by `pgraph.c:2979` and
`draw.c:6991-6997` independently of whether a binding exists. Clearing it on a
path that is not a draw would discard the record that a draw occurred.

**On the cost framing:** the lane is right, and pass 1's description and its
description are the same cost from the two ends. Under the old policy both
calls opened the gate — zeta evicting colour, colour evicting zeta back — two
`pgraph_vk_ensure_not_in_render_pass()` per update. Under the new one colour's
gate is closed (`current_binding` non-NULL, and on the download path `upload`
is false so the second disjunct cannot fire) and only zeta's call reaches it.
**One break per update instead of two.** Pass 1's "a per-update hash lookup" is
the same event.

**Pass 1's strong form remains unreachable**, and I re-checked it rather than
inheriting it: `download_surface_deferred()` guards on the *binding's own*
`draw_dirty` **and** on `download_generation == draw_generation`
(`surface.c:1362-1372`), so a `draw_dirty` accumulated while zeta had no image
cannot make it download a surface zeta never drew into.

**Recovery is intact.** `!current_binding` reopens the gate on every zeta
request, so zeta takes the surface on the first update after colour moves away,
independently of `buffer_dirty`. The `color && r->zeta_binding && dims differ`
reset at `:3502-3505` is skipped while zeta is absent, which does not matter
for the same reason.

I also checked every reader of `write_enabled_cache`, since it is a **VMSTATE
field** (`nv2a.c:1556`): `surface.c:3600/3604` (the dispatch condition),
`surface.c:3547` (the clear), `pgraph.c:2961/2979` (the accumulate). Leaving it
latched affects the dispatch condition and nothing else, so a savestate
carrying it true reproduces only the extra call.

---

## Five new LOW

| id | file | what |
|---|---|---|
| **N1** | `docs/testing/nv2a_index.json` | index is correct at the tip, **wrong at the arm-A ref** — a by-product of the reorder |
| **N2** | the prediction | the three-suite requirement is **prose only**; a re-queue re-creates M2 |
| **N3** | `vk/surface.c` | #88 **drops a zeta clear** at a colour-shared address — scope limit, not a defect claim |
| **N4** | `vk/blit.c` | the guard is one step later than `solid_line`'s — **an opinion, and it says so** |
| **N5** | `AGENTS.md:845` | the **Khronos validation layer is owed, not covered** |

### N1 — the index is wrong at the commit the arm was built from

`f343580647` regenerates `nv2a_index.json` against the **post-#88** tree, but
the reorder placed it **before** `4726557b0f`. So the index is self-consistent
at the branch tip and at the fold, and inconsistent at the arm-A ref. It claims
`surface.c:3228` holds `* FIXME: Support same color/zeta surface target? One
VkImage` and `:3259` holds the `NV2A_UNIMPLEMENTED`; at `f343580647` those
lines hold the *old* one-line FIXME at `:3227` and the `NV2A_UNIMPLEMENTED` at
`:3232`, because the 59-line comment that shifts them arrives in the next
commit. Seven `surface.c` rows are affected; the two `blit.c` rows in the same
commit (`:240`, `:460`) are correct there.

`nv2a_index.py`'s `cmd_check` compares full content including every `loc`
(`:874-882`, and its own comment records that catching a moved line number is
the gate's whole purpose), so the gate **fails at `f343580647`**: a bisect that
lands there, a checkout of the arm-A ref, or `nv2a-index.yml` on that sha
reports staleness that is not a defect and cannot be fixed at that commit
without breaking the next one. No runtime effect and no effect on either arm.

This is a by-product of doing the right thing — reordering so each arm tests
one change — not of careless regeneration, and the lane's report that
preflight's index gate passes is accurate, because it ran at the tip. The
general shape is worth a line in `AGENTS.md`: **when commits are reordered, a
derived artefact regenerated against the final tree is wrong at every
intermediate commit.**

### N2 — M2's fix is carried in prose only

The three-suite requirement lives in a sentence inside the `prediction` string.
There is no machine-readable field binding the prediction to a disc — and
that is **not** a schema violation: across all 102 prediction files, zero carry
a `suites` key and exactly one carries `disc_id`. Prose is the established
mechanism and the lane followed it.

It is still the weakest possible carrier for the one fact that decides whether
two of eleven legs are scored. A re-queue done single-suite re-creates M2
exactly, and **rerunning before debugging a single-run score change is this
project's own rule**, so a rerun is the expected next action on either arm.
`request.sh` cannot catch it. Filed LOW and not MEDIUM because the two arms
that ran were queued correctly and the harm requires a future action.

### N3 — #88 drops a zeta clear, which is broader than "which attachment is bound"

With zeta declining there is no zeta binding, and the depth/stencil clear is
gated on one — `draw.c:6774` and `:6870`, both `write_zeta && r->zeta_binding`.
So a guest clear of Z at an address colour holds now performs **no clear**,
where before the change zeta took the surface and the clear applied to it.

That is the intended trade and the right one: what it replaces is create-a-
zeta-image, evict colour, copy a never-rendered image back over VRAM. For the
one corpus configuration that exercises it, the goldens adjudicate it directly.
I file it as a **scope limit rather than a defect claim**, because I cannot
name a title outside these three suites where it is wrong, the corpus contains
no other suite pointing both units at one address, and the alternative
behaviour is measurably worse. Worth naming in the #88 investigation record so
the next reader knows the clear is *dropped* and not merely redirected.

### N4 — an opinion, and it says so

The commit says the guard now sits at "the same position `solid_line` uses". It
is one step later. `pgraph_vk_solid_line()` puts its narrow-format return at
`:827`, **above** its `pgraph_vk_surface_update()` at `:848`;
`pgraph_vk_image_blit()`'s guard at `:487` sits **below** its surface_update at
`:434`. So a refused narrow `BLEND_AND` still performs a full colour/zeta
flush and a refused narrow solid line does not.

**I could not turn this into a failure scenario and I do not think there is
one.** `surface_update` on the download path is a coherency flush that runs for
every blit regardless of operation, advertises no write, and commits no
bookkeeping to a write that will not happen — which is the property M1 was
about. It is also not freely movable: the blit's asserts and its whole
rationale assume the bound surfaces are current. A finding with no failure
scenario is an opinion, so this is recorded as one, downgraded and labelled,
purely so the difference from the cited precedent is on the record rather than
discovered later as a discrepancy.

---

## N5 — The check this change most wants, and I could not run it either

`AGENTS.md:845` makes the Khronos validation layer an obligation: *"run it on
any change to the Vulkan backend before calling the change verified"*, after it
found eight defects in one afternoon that no capture showed (#34). Both commits
are Vulkan backend changes, and #88 alters **which framebuffer attachments
exist** — the class those eight came from.

**I could not run it. Say it plainly: it is owed, not covered.**

And I tested the blocker rather than accepting it, because a blocker is a
claim — which turned up **two independent blockers where the lane named one**:

1. **The desktop build.** `/usr/include/curl/curl.h` is absent, so the
   unconditional `dependency('libcurl')` cannot resolve; `build-linux/` has a
   configured meson tree with **no `build.ninja`**. This is the known named gap
   (`AGENTS.md:322-336`), correctly not claimed by the lane.
2. **The layer itself is not installed on this host**, which I could not find
   recorded anywhere. `/usr/share/vulkan/explicit_layer.d` contains only
   `VkLayer_INTEL_nullhw.json` and `VkLayer_MESA_overlay.json`;
   `implicit_layer.d` only `VkLayer_MESA_device_select.json`;
   `/etc/vulkan/explicit_layer.d` is empty; there is no
   `~/.local/share/vulkan` or `/usr/local/share/vulkan`; `VK_LAYER_PATH` is
   unset; and a filesystem-wide search for `VkLayer_khronos_validation*` finds
   exactly **one** file — a Windows DLL inside Steam's CEF bundle on
   `/mnt/c`. So `[display.vulkan] validation_layers = true` would silently load
   nothing even if the build existed.

**What the instrument could and could not see:** had the layer been installed
the normal way, the search would have found a
`VkLayer_khronos_validation.json` manifest in one of those five directories
plus a `libVkLayer_khronos_validation.so`. A layer installed under a
non-standard prefix *and* renamed would have been missed.

**What was substituted, and it is reading rather than a run.** Recorded so the
next reader knows exactly how far the argument goes:

- every one of the 60 `zeta_binding` references in
  `hw/xbox/nv2a/pgraph/vk/` is NULL-guarded or sits behind
  `assert(r->color_binding || r->zeta_binding)`;
- `create_frame_buffer()` builds `attachments[]` with a running
  `attachment_count` that omits the absent binding (`draw.c:1538-1546`);
- `pDepthStencilState` is conditional on `r->zeta_binding` at `draw.c:1761`,
  `:2561` and `display.c:614`;
- `get_optimal_zeta_load_op()` returns `DONT_CARE` with no binding
  (`draw.c:2932-2935`);
- the zeta layout barrier in `begin_render_pass()` is behind a NULL check
  (`draw.c:2962`).

**The strongest thing reading establishes** is that the colour-only framebuffer
#88 newly reaches *in this situation* is not a novel state: any title binding
colour without zeta reaches it constantly. That is a real argument and it is
still not the layer. **No capture can stand in for it, because a validation
error need not move a pixel.**

**Two owner actions, both one line:**

    sudo apt install libcurl4-openssl-dev      # AGENTS.md:334 already names this
    sudo apt install vulkan-validationlayers   # AGENTS.md:845 names it but it is NOT present

The second is worth correcting in `AGENTS.md`: that line reads as though the
layer is available once you ask for it, and on this host it is not installed at
all.

**My recommendation: this does not block the fold** — the attachment
configuration is pre-existing and reached constantly, and #88 changes when it
is reached rather than introducing it. **It does block calling #88 verified.**

---

## Things checked that hold, recorded so nobody re-derives them

- **The range diff against the campaign tip shows three deleted docs files.**
  They are a **staleness artefact, not deletions**: the branch is based on
  `989854ac9e` and `docs/investigations/issue77-driver-ab-is-not-nova-specific.md`,
  `vram-race-frequency-is-per-title.md` and `vram_race_probe_sweep.py` arrived
  on master afterwards. Same for the 48-line `territory.toml` diff. **No lane
  commit touches any of them** — per-commit file lists checked individually.
- **`pgraph_vk_image_blit()` is the only route to the `surf_dest` block.**
  Reached only through `ops.image_blit` from `pgraph.c:2110`, behind
  `image_blit->width && image_blit->height`.
- **`unbind_surface()` is NULL-safe on both arms** (`surface.c:1828-1844`), so
  the repeated decline calls it harmlessly.
- **`nv_clip_gpu_tile_blit()` is pure** — `nv2a.c:101-119`, reads
  `d->pfb.regs` only.
- **The reorder achieves what it claims.** Arm A to arm B touches
  `vk/surface.c` alone, and both arms carry #84 and its M1 remediation, so #84
  cancels and the A/B isolates the #88 policy.
- **The `[skip ci]` discipline holds** on all four commits.

## What could not be audited, and why

- **The Khronos validation layer** — N5. Two blockers, both needing sudo.
  Owed, not covered.
- **Any narrow-format `BLEND_AND` capture.** All 20 `ImgBlt_BLENDAND_*`
  goldens are XRGB or ZRGB, both 32bpp, so the guard is inert on every capture
  that exists. Pass 1 established this and I did not re-derive it. An arm would
  show zero movement and zero movement would prove nothing — an audit found the
  defect and an audit found its misplacement, and no measurement would have
  found either.
- **The judged #88 pair.** Both arms are DONE and unjudged. Judging is the
  lane's and the orchestrator's, not the auditor's, and my fold verdict is
  about the audit findings only.
- **`nv2a_index.py check` at `f343580647`.** It needs a checkout and I hold no
  files; N1's gate failure is derived from the comparison the checker performs,
  not observed.

---

## Should the fold proceed?

**Yes — and a clean pass 2 is what this was for, so I say so plainly. The
compiled code is clean.** M1 is closed on its strongest form, the hoist beyond
what the finding asked for is safe and I verified the reading rather than the
conclusion, the leaf guard is genuinely unreachable rather than a second silent
policy, and there is no new HIGH or MEDIUM in `hw/`. Both declines and the one
documented-not-fixed are accepted with reasons checked one at a time, and one
of them is better justified than the lane argued.

**Two conditions, both about the fold operation and neither about the code:**

1. **Fold `4e795536df` WITH the three code commits.** Code-only leaves the
   branch carrying a prediction that names two refs reachable from no ref, and
   judging against that path reads `TAMPERED`. The cherry-pick is clean — the
   pre-image blob is byte-identical to the tip's (`30d596da3c`). This is the
   third occurrence of this one mechanism; the first was a code-only fold
   exactly like the one to avoid here.
2. **Do not prune, reset or unlock `worktree-agent-aa4f3448ff981e82f` until the
   pair is judged.** Both arms' `request.json` point `expect` at an absolute
   path inside it and at refs reachable only from its branch, and a rerun needs
   all three to survive.

**One debt to name rather than discharge:** the validation layer (N5). It
should not hold the fold; it should hold the word "verified" on #88.

**One thing that has now relaxed:** the lane declined to rebase because arms
were in flight, leaving the territory gate (wave 84 vs 85) failing. Both arms
are DONE, so that trade has inverted and the rebase is no longer the thing that
breaks a running measurement — subject to condition 2.

Nothing in the five new LOWs should hold the fold. N1 is correct at the fold
point, N2 and N3 are about future actions, N4 is an opinion and says so, and
N5 is a debt.

## Territory

`lane.audit2-blitsafe` claims **no files** and released none. Written this
pass: `docs/audits/2026-09-18-blitsafe-pass2.md` and `.json` (this lane's
deliverable) and `$DISPATCH_DIR/board-requests/audit2-blitsafe.md`, which is
outside this repo and outside any territory row. **Nothing under `hw/` was
edited** — an auditor does not fix what it finds. No device work was queued, no
hold was removed, and the locked worktree was read but **not unlocked**.
