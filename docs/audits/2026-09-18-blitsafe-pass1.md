# Audit pass 1 — `12870b8fde` (#84) and `e71a9952d1` (#88), both held

Review of `lane.blitsafe`'s two unfolded commits on
`worktree-agent-aa4f3448ff981e82f`, plus the prediction bound to the second.
Machine-readable companion:
[`2026-09-18-blitsafe-pass1.json`](2026-09-18-blitsafe-pass1.json).

| | |
|---|---|
| Auditor | `lane.audit-blitsafe` (pass 1 of 2), territory wave 82, claims no files |
| Commits | `12870b8fde` *nv2a/vk: BLEND_AND blit hard-codes 32bpp; refuse narrow formats (#84)*, +109 in `hw/xbox/nv2a/pgraph/vk/blit.c`<br>`e71a9952d1` *nv2a/vk: colour keeps a surface zeta wants, as GL already does (#88)*, +61 in `hw/xbox/nv2a/pgraph/vk/surface.c` |
| Also in scope | `docs/testing/predictions/issue88-vk-same-offset-colour-wins.json`, folded at `201d158e72` |
| Campaign tip when audited | `cce5eec199`. This worktree started **1,158 commits behind** and was fast-forwarded before anything was read. |
| Prior pass this addresses | `docs/audits/2026-09-14-blit-pass1.md` — H1 (the 32bpp overrun) and M1 (the `beta_mult` invariant) |
| Method | reading both diffs and their callers; `git merge-tree` rehearsal of the held divide fix; structural checks against the goldens and the capture corpus on disk; `check_android_guards.py`; **one Android arm64 build of the fold candidate `201d158e72`, clean, `GRADLE_EXIT=0`, on a clean tree**. No device (see [What could not be audited](#what-could-not-be-audited)). |

## Counts

| Severity | Count |
|---|---|
| HIGH | **0** |
| MEDIUM | 3 |
| LOW | 3 |

**Both changes are sound in substance and neither is unsafe.** The three
MEDIUMs are: one placement defect in `#84`'s guard, and two in the
**verification apparatus** for `#88` — neither of the latter is in `hw/` and
neither argues against the code. There is no HIGH, and no LOW was
manufactured; the clean results are recorded in
[What held up](#what-held-up--the-clean-results) as results.

## The two claims I was sent to weigh rather than confirm

### Claim 1 — `#84` refuses narrow formats rather than rescaling. **SOUND. Endorsed.**

The lane's reason is that a real 16bpp blend needs unpack 5/6/5 → blend →
repack, and the repack's rounding rule is on nothing on disk. That is correct,
and I checked the specific thing that makes it more than a preference: the
2²⁴ exhaustive sweep behind this blend's divide is over `(src, dst, β)` with
**8-bit** `src`/`dst`, so it says nothing about a 5- or 6-bit channel. A
rescaling fix would have to invent the rule in the one path whose whole point
is that its arithmetic is measured. Per this project's own rule against a
different exclusion reason per case, inventing it would be a fit.

**Is there a guest-visible regression in refusing?** I looked for one and it is
not there. Before the change, a narrow-format `BLEND_AND` did not draw "a
wrong picture" and stop: at R5G6B5 it walked 2× the intended byte extent per
row and at Y8 4×, so it blended the *following* columns as well as its own,
treated 5/6/5-packed bytes as 8-bit channels, and on the last row wrote past
`dest_offset + dest_size`. "Draws nothing" is strictly better than that in
every configuration I could construct. The refusal's own side effect — the
destination surface reverting to VRAM the blit never wrote — is real and is
filed as **M1** below, but it is a bookkeeping defect with a cheap fix, not an
argument for rescaling.

**Precedent, and it is precedent plus mechanism rather than precedent alone.**
`pgraph_vk_solid_line()` at `blit.c:730` answers the identical question at
`blit.c:782-793` with the same warn-once `fprintf` and early return, under a
comment that refuses to invent an answer for narrow formats; `lane.remote`'s
`b9d845d316` (2026-09-14) is the GL-side twin and I read it — same signature
change, same guard text, same **three** call sites. So the shape is now the
same on both renderers and in two functions of this file.

**And the lane's choice of which fact is authoritative is correct.** I checked
`width` at every call site and it is a count of **destination-format** pixels
in all three:

| site | `width` passed | in destination-format pixels? |
|---|---|---|
| `blit.c:375` (from `perform_blit_tiled`) | `chunk / bytes_per_pixel` | yes |
| `blit.c:589` (linear body) | `row_pixels` = `MIN(MIN(source_pitch, dest_pitch) / bytes_per_pixel, image_blit->width)` | yes |
| `blit.c:612` (leftover row) | `leftover_bytes / bytes_per_pixel` | yes |

So `max_row_pixels`' division by `bytes_per_pixel` is the correct side and the
constant `4` in the indexing was the wrong side. Making the indexing
authoritative instead would have left the clamp wrong for `SRCCOPY` too. One
qualification on the derived invariant, filed as **L2**: at `blit.c:375`
`width * bytes_per_pixel` does **not** equal `width_bytes`, because
`chunk / bytes_per_pixel` truncates.

### Claim 2 — `#88`'s gate half must not be ported. **VERIFIED in all three parts.**

This claim decides how much of `#66` applies, so I checked the commit, the
date and the permissiveness separately.

* **The commit.** `9161e3e14ace05109b26efbe29347e46cf439046`, *"nv2a/vk: Create
  surface if one not currently bound"*, author **Matt Borgerson**. Its entire
  diff to `update_surface_part()` is:

  ```c
  - if (upload && (pg_surface->buffer_dirty || mem_dirty)) {
  + SurfaceBinding *current_binding = color ? r->color_binding
  +                                         : r->zeta_binding;
  +
  + if (!current_binding ||
  +     (upload && (pg_surface->buffer_dirty || mem_dirty))) {
  ```

* **The date.** `2024-07-27 14:44:38 -0700`. This fork's boundary is
  **2026-01-29**, so the commit is upstream, and it predates `#66`'s discovery
  on the GL side (`fada1d89d4`, 2026-09-13) by close to two years. Both halves
  of the claim hold.

* **The permissiveness.** GL's *fixed* form is
  `if (upload && (surface->buffer_dirty || mem_dirty || no_binding))`. Vulkan's
  added disjunct sits **outside** `upload`; GL's sits **inside** it. So Vulkan
  is strictly more permissive, the absent-binding condition is genuinely
  already satisfied here, and only the policy needed porting. **Half of `#66`
  is not missing from Vulkan.**

**But the asymmetry has a consequence the commit identified and did not carry
through**, and it is the one thing on either side that is specific to this
renderer. Because Vulkan's absent-binding term is not gated on `upload`, the
new early return is reachable with `upload == false` — the download path —
which **GL's return cannot be**. That is filed as **L3**. I pushed on it hard,
because "a gate and a policy, and getting one right leaves a plausible
intermediate state" is exactly `#66`'s shape; the honest answer is that I could
not construct a wrong-pixel or unsafe outcome from it, so it is a LOW and is
labelled as such rather than inflated.

## MEDIUM

### M1 — `blit.c:570-573` and `:689-700` — the refusal returns from the leaf after the caller has already committed surface bookkeeping for a write that will not happen

The guard is inside `perform_blit()` at `blit.c:102`. `pgraph_vk_image_blit()` has by then
already decided what the blit does to the destination surface:

```c
SurfaceBinding *surf_dest = pgraph_vk_surface_get(d, dest_addr);
if (surf_dest) {
    if (adjusted_height < surf_dest->height || row_pixels < surf_dest->width) {
        pgraph_vk_surface_download_if_dirty(d, surf_dest);
    } else {
        // The blit will completely replace the surface so any pending
        // download should be discarded.
        surf_dest->download_pending = false;   /* blit.c:570 */
        surf_dest->draw_dirty = false;         /* blit.c:571 */
    }
    surf_dest->upload_pending = true;          /* blit.c:573 */
```

and after `perform_blit()` returns it advertises the write unconditionally:

```c
memory_region_set_client_dirty(..., DIRTY_MEMORY_VGA);       /* blit.c:689 */
memory_region_set_client_dirty(..., DIRTY_MEMORY_NV2A_TEX);  /* blit.c:691 */
memory_region_set_client_dirty(..., DIRTY_MEMORY_NV2A);      /* blit.c:699 */
```

**Scenario.** A guest binds an `NV062` pair with `SET_COLOR_FORMAT = LE_R5G6B5`
(or `LE_Y8`), sets `NV09F_SET_OPERATION = BLEND_AND`, and issues a blit whose
rect covers the whole destination surface — which is the `else` branch above,
not an exotic case. `download_pending` and `draw_dirty` are cleared, so
whatever the GPU had rendered into that surface and not yet written back is
**discarded**; `upload_pending` is set, so the VkImage is reloaded from VRAM
that `perform_blit()` then declines to write; and the three
`memory_region_set_client_dirty()` calls tell the VGA client, the texture cache
and the surface tracker that a range changed when nothing did, invalidating
texture bindings and forcing a redraw for no write.

This is not the old overrun and it is **not** memory unsafety — the refusal
removes the out-of-bounds write and does not reintroduce it. It is a different
wrongness in the same path, and it is the difference between "this blit did
nothing" and "this blit reset the destination to stale VRAM and told three
subsystems it had written".

**The cited precedent does not have this problem, and the difference is
placement rather than idiom.** `pgraph_vk_solid_line()` puts its identical
`bytes_per_pixel != 4` guard at `blit.c:782`, at the **top of the entry
function**, above its own soft guards at `blit.c:795-800` and before any state is touched. `#84`
copies solid_line's warn-once shape into a leaf helper three frames down.

**Remediation.** Hoist the decision into `pgraph_vk_image_blit()` — after the
`bytes_per_pixel` switch and **before** the `surf_dest` block at `blit.c:561` —
as `if (image_blit->operation == NV09F_SET_OPERATION_BLEND_AND && bytes_per_pixel != 4) { warn once; return; }`,
and keep the leaf guard as a defensive `return` so no future caller can reach
the 32bpp indexing. That makes the refusal a genuine no-op rather than a
partially-committed one, and it is the placement the precedent already uses.
**A remediation is a claim**: if the lane prefers to keep the guard only in the
leaf, the alternative is to skip the `surf_dest` mutations and the three dirty
marks on the same condition, which is strictly more code in more places.

### M2 — `predictions/issue88-vk-same-offset-colour-wins.json` — two of nine `must_not_move` keys are in suites a per-suite arm will not contain, and `request.sh`'s gate cannot see it

The prediction's nine `must_not_move` entries include
`Color_Zeta_Disable/MaskOff_ZB` and `Null_surface/XemuBug893`. The other seven
and both `expect` keys are `Color_zeta_overlap`.

All eleven keys **do** have a capture on disk and not merely a golden, which is
the `OverlapFIFO` check and it passes: the nine `Color_zeta_overlap` captures
are all present in
`dispatch/results/z-c866527e03-016-Color_zeta_overlap/captures1/`, and the
other two in `.../z-c866527e03-013-Color_Zeta_Disable/captures1/` and
`.../z-after-048-Null_surface/captures1/`. **That is the problem**: they are
present in *three different result directories*, because the corpus sweep
requests one suite per run —
`z-c866527e03-016-Color_zeta_overlap/request.json` reads
`"suites": ["Color zeta overlap"]`.

**Scenario.** The arm is queued the way every `Color_zeta_overlap` result on
disk was queued, as a single-suite request; the prediction's own prose calls it
"a narrowed per-suite disc". `ab_compare` expands each pattern against the
captures the two arms actually scored, so `Color_Zeta_Disable/MaskOff_ZB` and
`Null_surface/XemuBug893` match nothing, cannot pass and cannot fail, and the
arm returns `PRE-REGISTERED` with 9 of 11 legs bound. Those two are not
decoration — they are the regression guard on the *other* two suites that
traverse the edited `update_surface_part()`, which is the main regression risk
the prediction names.

`request.sh`'s prediction gate does not catch this. It builds its `known` set
from `$GOLDENS` (`/home/justin/goldens/results/<suite>/*.png`, `request.sh:299-305`)
and asks only whether a golden exists, so all eleven keys bind and it queues
clean. This is AGENTS.md's inert-prediction class 1 arriving through **disc
composition** instead of through spelling, which is the only form the gate was
built for.

**Remediation.** Queue the arm over all three suites —
`--suites "Color zeta overlap" "Color Zeta Disable" "Null surface"` (index
spellings verified in `nv2a_index.json`) — or drop the two out-of-suite keys
and say in the prediction why the guard is narrower than the risk. Either is
fine; queuing one suite with eleven keys is not. Not in `hw/`, does not hold
the code fold, and **must** be settled before the arm is queued.

### M3 — `predictions/issue88-vk-same-offset-colour-wins.json` — `a_ref`/`b_ref` are not ancestors of the campaign tip, and the fold will rewrite both

`a_ref` is `12870b8fde` and `b_ref` is `e71a9952d1`. Checked at the tip:

```
merge-base --is-ancestor 12870b8fde worktree-agent-aa4f3448ff981e82f  -> yes
merge-base --is-ancestor e71a9952d1 worktree-agent-aa4f3448ff981e82f  -> yes
merge-base --is-ancestor 12870b8fde cce5eec199                        -> NO
merge-base --is-ancestor e71a9952d1 cce5eec199                        -> NO
```

Both refs are reachable from a live lane branch and neither is on the campaign
branch. That is correct *today* — the commits are held, and registering against
the lane branch is what "register last" asks for while they are unfolded.

**Scenario.** The fold cherry-picks these two commits onto `cce5eec199`. Both
shas are rewritten, and the prediction's bound refs stay valid in the one way
AGENTS.md names as the dangerous one: **reachable but not an ancestor**. The
dispatcher builds `e71a9952d1` successfully from the lane branch, produces a
complete arm B of the *pre-fold* tree, and the pair scores and reports
`PRE-REGISTERED`. Nothing errors. This project hit this trap twice in one day
on `#59`, once from exactly this cause.

**Remediation.** The orchestrator re-registers the prediction with the folded
shas immediately after the cherry-pick and before the arm is queued —
re-registering is cheap. Do **not** queue the arm against the pre-fold refs on
the grounds that they still build. Not in `hw/`.

## LOW

### L1 — `12870b8fde` commit message — "all four call sites pass it"; there are three

`perform_blit()` has exactly three call sites: `blit.c:375`, `:589`, `:612`
(`git grep -n perform_blit` at the commit, and the compiler agrees — the
signature change built clean, which is the completeness proof for the
enumeration). `perform_blit_tiled()`'s two sites at `:582` and `:603` already
carried `bytes_per_pixel` and are unchanged. GL's twin `b9d845d316` also
touches three.

No defect: every actual call site passes the right value. But the count is the
enumeration this audit was dispatched to check, and the commit message is where
this project keeps its reasoning, so a wrong count there is the kind of thing
the next reader trusts instead of re-deriving. Reviewed-and-not-fixed with the
count noted here is an acceptable outcome; the commit is held, so it can also
just be amended.

### L2 — `blit.c:375` — the tiled call site breaks `width_bytes == width * bytes_per_pixel`, which the rest of the function assumes

`perform_blit_tiled()` passes `chunk / bytes_per_pixel` as `width` and `chunk`
as `width_bytes`. When `chunk` is not a multiple of `bytes_per_pixel` the
division truncates, so the two disagree. `SRCCOPY` is unaffected (`memmove`
uses `width_bytes`). For `BLEND_AND` at 32bpp the loop then blends
`4 * (chunk / 4)` bytes while `done += chunk` advances the source by `chunk`,
so `chunk % 4` bytes per chunk are skipped and the source skews against the
destination for the remainder of the row; a leading `chunk` of 1, 2 or 3 gives
`width == 0` and blends nothing at all.

**Reachable, and only as a wrong picture.** `chunk = 16 - (offset % 16)`, and
`offset` inherits `context_surfaces->dest_offset`, which `pgraph.c:2024` stores
as `parameter & 0x07FFFFFF` with **no alignment mask** — so an unaligned guest
offset is reachable state. It additionally needs a valid GPU tile covering the
destination *and* a blit that overruns it (`clipped_dest_size < dest_size`),
which is why nothing has hit it. `width` can only shrink, so there is no
overrun and no unsafety.

Pre-existing and untouched by this commit. It is filed because the commit's
central argument is that `width` counts destination-format pixels, and this is
the one site where the byte count and the pixel count are not two views of the
same number. **Remediation:** one sentence in the new comment naming
`blit.c:375` as the exception, or align `chunk` down to a whole pixel and let
the next iteration pick up the remainder. Reviewed-and-not-fixed is acceptable.

### L3 — `surface.c:3289` — the decline is reachable on the download path, where it skips the only site that clears `pg->surface_zeta.draw_dirty`

This is the consequence of the very asymmetry Claim 2 establishes. GL's gate is
`upload && (... || no_binding)`, so GL's identical early return can only be
taken with `upload == true` and can never skip the download tail. Vulkan's is
`!current_binding || (upload && (...))`, so with `upload == false` and
`zeta_binding == NULL` the gate is satisfied by the first disjunct alone, and
the return at `surface.c:3289` skips `surface.c:3536-3549` — the only place
`pg->surface_zeta.draw_dirty` and `pg->surface_zeta.write_enabled_cache` are
cleared.

`pgraph_vk_set_surface_dirty()` sets `pg->surface_zeta.draw_dirty |= zeta`
(`draw.c:6766`) **independently of whether `r->zeta_binding` exists**, so once
zeta has declined both flags latch true for as long as the overlap persists.
`pgraph_vk_surface_update()`'s
`(zeta_write || write_enabled_cache) && draw_dirty` test is then true on every
non-upload update, and `update_surface_part(d, false, false)` is re-entered
each time to reach the same early return, paying a
`pgraph_vk_ensure_not_in_render_pass()` and a surface-hash lookup.

**Downgraded to LOW deliberately, and here is what I could not establish.** The
sharper version of this finding is that when colour finally releases the
address, the first non-upload update after zeta binds it carries a `draw_dirty`
accumulated from draws in which zeta had no image, and so issues a download of
a surface zeta never drew into. I traced it and **could not make it wrong**:
`download_surface_deferred()` guards on the *binding's own* `draw_dirty` and on
`download_generation == draw_generation` (`surface.c:1366-1372`), and the image
it would write is the one the guest did render at that address. So the failure
scenario is a per-update hash lookup, not wrong pixels — which makes the strong
form an opinion, and it is recorded as one.

**Remediation.** Clear `pg_surface->draw_dirty` and
`pg_surface->write_enabled_cache` alongside `buffer_dirty` on the decline path,
or gate the decline on `upload` so it mirrors GL exactly. The first is one
line and keeps the Vulkan gate's extra permissiveness; **the lane may
reasonably decline both** and log that the cost is a hash lookup, because there
is no measured defect behind it.

## What held up — the clean results

These are the questions the pass was sent to ask. A clean audit is a result.

### Every caller of the changed signature passes the right value, and the build proves the enumeration complete

Three `perform_blit()` sites and two `perform_blit_tiled()` sites, tabulated
under Claim 1. All three pass destination-format pixels; the tiled path already
had `bytes_per_pixel` and passes the same variable it was given. The Android
arm64 build of the fold candidate `201d158e72` completed
`BUILD SUCCESSFUL in 5m 12s`, `GRADLE_EXIT=0`, **zero** `error:` lines, on a
clean tree — which for a signature change is the structural proof that no call
site was missed, and is stronger than my reading of it.

### The M1 assert is not implied by its enclosing condition, and its boundary is exercised

The precedent that killed the previous remediation of this chain was an assert
implied by the condition it sat under. This one is not. Its enclosing condition
is `operation == NV09F_SET_OPERATION_BLEND_AND` and now `bytes_per_pixel == 4`;
neither constrains `beta->beta`, which is written in another translation unit.
Enumerated rather than assumed:

* exactly **two** write sites for `beta->beta` — `pgraph.c:1945` (`= 0`) and
  `pgraph.c:1951` (`= parameter & 0x7f800000`); `0x7f800000 >> 16 == 0x7f80`,
  which is `max_beta_mult` exactly;
* `grep -rn "beta\.beta\|beta->beta" hw/` returns those two writes and the two
  renderers' reads, nothing else;
* no `VMSTATE` entry names `BetaState`, so no savestate can inject a value.

So it is an internal invariant and not guest input turned into a DoS, which is
what `assert()` is for. Two details worth recording because they are what make
it *effective* rather than decorative:

* **Asserts are live in shipping builds here.** `android/app/src/main/cpp/CMakeLists.txt`
  applies `-UNDEBUG` for `Release`, `RelWithDebInfo` and `MinSizeRel`
  (lines 918, 1027, 1064). An assert that compiled out would have been a
  comment.
* **The boundary is reached by the corpus, so `<=` is right and `<` would
  fire.** `ImgBlt_BLENDAND_XRGB_B7FFFFFFF` masks to `0x7F800000`, i.e.
  `beta_mult == max_beta_mult` and `inv_beta_mult == 0`.

And the "wrong differently" reasoning behind it is accurate: the NEON path
narrows the value with `vdupq_n_u16((uint16_t)inv_beta_mult)` while the scalar
tail multiplies by it unmasked, so `beta_mult = 0x8000` would give the vector
body 65,408 and the scalar tail 4,294,967,168.

### M1's re-scoping is correct, and the assert is the right guard for the held fix too

`blend_and_div()` is genuinely not in this tree, so the audit's 1.76%-of-
headroom figure does describe the reciprocal trick and not the problem. With a
plain divide the dividend cannot exceed 8,339,520 (255 × 32,640 plus the
0x3FC0 rounding term) against 2³², which is the ~515× the commit states.
Checked forward as well: in the **merged** tree the same assert is what keeps
`blend_and_div()`'s operand below 2¹⁶, so the re-scoping does not leave the
held fix's precondition unguarded.

### The narrow-format class is empty in the corpus, structurally

`ls /home/justin/goldens/results/Image_blit | grep -c BLENDAND` → **20**, and
all twenty are `ImgBlt_BLENDAND_XRGB_*` or `ImgBlt_BLENDAND_ZRGB_*`, both
32bpp. There is no `ImgBlt_BLENDAND_ARGB` and no 16bpp `BLENDAND` capture. The
enumeration is complete because the capture list is fixed by the disc, so the
guard is inert on every capture that exists and an arm would show zero
movement — which is the right reason to land this without one, not an excuse.

### `#84`'s warning is visible on the platform that ships

Verified rather than accepted: `RedirectStderrToLogcat()` is the first
statement of `xemu_android_main()` (`android/app/src/main/cpp/xemu_android.cpp:1115`,
above `qemu_init()` at `:1118`), and it `dup2()`s stderr onto a pipe, sets it
unbuffered, and hands the read end to a pump thread. So the plain
`fprintf(stderr, ...)` reaches logcat under `hakuX-stderr`, and using
`__android_log_print` would have made this the only one of three sibling
narrow-format guards in these two files with a different idiom.

### The held divide fix still cherry-picks onto `#84` with zero conflicts

Rehearsed independently of the lane's rehearsal, non-destructively:

```
git merge-tree --write-tree --merge-base 24a75d6e3c^ 12870b8fde 24a75d6e3c
  -> 55b8ca27b30a7331a1401ce92759406571adac19   (exit 0, no conflict block)
```

and `blit.c` in that tree carries `blend_and_div()` at `:47`, the
narrow-format guard at `:123` and the M1 assert at `:173` together. Still
holds.

### A colour-only framebuffer is first-class, and the render pass agrees with it

This is the check that matters most for `#88`, because `#66`'s GL symptom was
`GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT` — an attachment-count
mismatch — and the Vulkan analogue would be a framebuffer whose
`attachmentCount` disagrees with its render pass's. It cannot arise:

* `create_frame_buffer()` (`draw.c:1343`) asserts only
  `r->color_binding || r->zeta_binding`, takes its dimensions from whichever is
  present, and builds `attachments[]` by counting the bindings that exist;
* `create_render_pass()` (`draw.c:1225`) derives `zeta` from
  `state->zeta_format != VK_FORMAT_UNDEFINED`, and `draw.c:1221` sets that
  field to `r->zeta_binding ? ... : VK_FORMAT_UNDEFINED`, so the render pass's
  `attachmentCount` tracks the same two pointers the framebuffer does;
* `pDepthStencilState = r->zeta_binding ? &depth_stencil : NULL` at
  `draw.c:1598`, `draw.c:2375` and `display.c:614`;
* `begin_pre_draw_inner()` (`draw.c:3545-3547`) asserts
  `color_binding || zeta_binding` and then only that each *present* binding is
  initialised.

**And the state is not newly reachable.** `pgraph_vk_surface_update()` calls
the zeta half only when `zeta_write` is true, so zeta-absent already happens
whenever `pgraph_zeta_write_enabled()` is false — which is what
`Color_Zeta_Disable` exercises. The decline reaches an existing state by a new
route rather than inventing one.

### The early return cannot leave a NULL binding to the download tail

Enumerated every way out of the gate block. On the colour side the block always
binds: either no surface is found and one is created, or the found surface is
zeta's and `unbind_surface(d, !color)` frees it first. On the zeta side the only
non-binding exit is the new `return`, which is **above** the tail. The tail's
`download_surface_deferred(d, color ? r->color_binding : r->zeta_binding)` is
therefore never reached with NULL, and when the gate is false the binding is
non-NULL by the gate's own first disjunct. `unbind_surface()` (`surface.c:1829`)
is NULL-safe in both directions anyway.

### Clearing `pg_surface->buffer_dirty` on the decline loses nothing

Traced the flag rather than trusting the comment. The comment's stated purpose —
stopping `pgraph_vk_surface_update()` from calling `unbind_surface()` on an
already-absent binding each pass — is accurate: that call is the
`if (pg->surface_zeta.buffer_dirty) unbind_surface(d, false)` in
`pgraph_vk_surface_update()`, not the one inside the block, and the block is
re-entered every pass regardless via `!current_binding`. Clearing it cannot
suppress a needed rebind, because `!current_binding` covers that, and it cannot
suppress a needed upload, because the upload decision is `upload_pending` /
`initialized` and not `buffer_dirty` — the normal path clears `buffer_dirty`
at `surface.c:3526` for exactly the same "request handled" reason.

### The prediction's structure is sound where I could check it

* All 11 keys have a **capture** on disk and not merely a golden (see M2 for
  the separate problem that they are in three different result directories).
* The two absolutes are derived arithmetically from the goldens' own
  histograms — `307200 − 175705 − 120729 = 10766` and
  `307200 − 201641 − 30592 − 3304 = 71663` — and the prediction says GL's
  measured values are a cross-check rather than the source. That is the right
  way round, and it avoids the stale-baseline class the `#67` legs fell into.
* The legs are **not** satisfiable by reverting. Reverting gives 131,495 and
  102,255, failing both absolutes; leg 3 additionally requires the
  depth-derived encodings `#87FE00` and `#FE5724` to *disappear*, which is a
  claim about a multiset that a count cannot express and that the edit does not
  force.
* The predicted movers are consistent with the mechanism rather than chosen to
  match: for each test the capture at the **shared** address moves
  (`ColorIntoZeta_ZB`, `ZetaIntoColor`) and the other stays
  (`ColorIntoZeta`, `ZetaIntoColor_ZB`). That asymmetry is the mechanism's own
  signature, and getting it backwards would have been the tell.
* `Swap_ZB` is registered as `must_not_move` rather than as a predicted fall,
  which is the correct treatment of a figure measured on a different platform
  and a different disc.

### Residual risk, named and accepted rather than filed

With zeta absent there is no depth attachment, so **every** draw while the
overlap persists runs with no depth test — not only the two captures. The
commit and the prediction both say so, and the prediction registers it as
falsifier 1. I did not file it, because it has no failure scenario relative to
any available alternative: one `VkImage` cannot be both attachments, the old
policy's zeta-wins state lost the colour writes instead, and there was never a
state with both attached. It is the cost of picking a winner, and the goldens
say pick colour. It is recorded here so the next reader does not have to
rediscover that it was considered.

## What could not be audited

* **No device arm, and none was queued.** `DEVICE TESTING IS SUSPENDED
  2026-09-18 BY THE OWNER`; `dispatch/hold/thor` and `dispatch/hold/nova` are
  both present. I queued nothing and removed no hold. `#88`'s prediction is
  bound and waiting, which is the right order.
* **The desktop build.** Known named gap on this host —
  `libcurl4-openssl-dev` is absent. **Not claimed.** The Android arm64 build is
  the only one I ran, and it passed.
* **The Khronos validation layer, which is the check this change most wants.**
  AGENTS.md requires it for any change to the Vulkan backend, and it runs on
  the desktop lane, which cannot be built here. `#88` changes which attachments
  a framebuffer has, which is precisely the class it found eight of in one
  afternoon (`#34`). I substituted reading — the framebuffer/render-pass
  attachment-count agreement above — and that is weaker than a VUID count. **A
  validation-layer run on `Color zeta overlap` should be part of pass 2 or of
  the fold, whichever gets a desktop toolchain first.**
* **The narrow-format `BLEND_AND` path is unmeasurable by construction, and
  what that means for verifiability.** The class is empty in the corpus (20/20
  `BLENDAND` captures are 32bpp), so no capture can exercise the guard on any
  fleet. `#84`'s own signal is a plain `fprintf` and does reach logcat, so a
  *title* that hits it is discoverable — but `#88`'s decline is announced only
  by `NV2A_UNIMPLEMENTED`, and `DEBUG_NV2A_FEATURES` defaults to `0`
  (`hw/xbox/nv2a/debug.h:58-59`) so that expands to `do {} while (0)` in every
  shipping build. **For `#88` the capture is the only oracle**, which is why
  M2 matters: a leg that binds to no row leaves a policy change with no
  observable at all.
* **`check_coverage.py` FAILs on `#89`, and it is a stale-checkout artefact,
  not a board defect.** Run from the detached build checkout it reported
  *"1 open issue with neither a lane nor a blocker: #89"* — and said in the same
  breath that the checkout was five commits behind. `[issue.89]` **is** present
  in `nv2a_issues.toml` at the campaign tip `cce5eec199`. Reported here rather
  than as broken infrastructure, per the rule that a gate failing in a stale
  checkout is evidence about the checkout.

## Outside my territory

I claim no files (wave 82) and edited nothing under `hw/`. Board requests are
in `$DISPATCH_DIR/board-requests/audit-blitsafe.md`; the same items are in my
final report.
