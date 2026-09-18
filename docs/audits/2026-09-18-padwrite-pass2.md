# Audit pass 2 — #59's dual-source pad write, over the remediation of pass 1

**Lane** `lane.audit2-padwrite` (territory wave 80, claims no files).
**Subject** `lane.padwrite59`, branch `claude/padwrite59-dualsrc-tip`, tip
**`f0f4ab0c39`**, five commits over base `0e919fe51e`, ~600 lines of compiled
code across `glsl/psh.c` (+121), `glsl/psh.h` (+38), `vk/draw.c` (+212),
`vk/instance.c` (+115), `vk/texture.c` (+78) and `pgraph/pgraph.c` (+36).
The remediation itself is one commit, **`832557813c`**, plus `f0f4ab0c39` which
re-registers the prediction.
**Pass 1's record** `docs/audits/2026-09-18-padwrite-pass1.{md,json}`.
**Date** 2026-09-18. **Records** `2026-09-18-padwrite-pass2.json` (flat array,
schema as `2026-09-18-remote-pass2.json`: `pass1_id` or `pass2_id`, `severity`,
`file`, `line`, `verdict`, `summary`, `scenario`, `remediation`, `evidence`,
optional `decision`).

**3 HIGH CLOSED. 1 MEDIUM DECIDED and accepted. 1 MEDIUM OPEN. 2 LOW CLOSED,
1 LOW DECIDED. 5 new LOW, all of them opinions or observations with no failure
scenario in shipped code, and all five say so.**

**The code is clean.** All three HIGHs are closed, and closed for reasons I
established rather than inherited. No new HIGH and no new MEDIUM in the
compiled code — which is worth saying plainly, because 600 lines fixing three
HIGHs is exactly where a new defect enters and pass 1's own HIGH in another
lane was introduced by an otherwise-correct fix.

**The plumbing is not clean.** M2 — the prediction's arm B ref — is OPEN, and
it has recurred a **third** time on this one issue, by a third distinct
mechanism. That is the one thing on this branch that still bites.

**A clean pass 2 does not imply the fold.** What it still needs is at the end.

## The three HIGHs

### H1 — CLOSED, by the relocation alone

The field is `0x000C0000`, bits 18..19 (`draw.c:612`). `init_pipeline_key()`'s
strip at `draw.c:1896-1897` masks `NV_PGRAPH_BLEND_LOGICOP_ENABLE |
NV_PGRAPH_BLEND_LOGICOP` = `0x0001F000`, and `0x000C0000 & 0x0001F000 == 0`, so
`PSH_PAD_ALPHA_ZERO` now lives in bit 18 and survives into the key. `_Z` and
`NONE` are distinguishable. Closed independently of the second fix, which is
what pass 1 asked be verified separately.

**I computed the field extent myself**, because the original defect came from a
`grep | head -30` that truncated four lines before the contradiction — a
negative read from an instrument that could not see the thing. The
mask-shaped `NV_PGRAPH_BLEND_*` defines are exactly six: `EQN 0x00000007`
(`:364`), `EN (1<<3)` (`:380`), `SFACTOR 0x000000F0` (`:381`),
`DFACTOR 0x00000F00` (`:397`), `LOGICOP_ENABLE (1<<16)` (`:413`),
`LOGICOP 0x0000F000` (`:414`). Everything between those is an enum *value*, and
the next define, at `:415`, is `NV_PGRAPH_BLENDCOLOR` — a different register.
Their union is **`0x0001FFFF`**, confirming the lane's figure. `0x000C0000` is
clear of it.

### H2 — CLOSED, by the unconditional write, and that fix is load-bearing

`SET_MASK` clears before OR-ing (`nv2a_regs.h:27-32`), so writing
`PSH_PAD_ALPHA_NONE` when the gate is off forces the field to 0 whatever the raw
register held. The write is now unconditional on both arms of the gate
(`draw.c:639-642`).

It is **sufficient at every consumption site**, which is what makes it
equivalent to the consumer-side gate pass 1 suggested instead:
`pgraph_vk_effective_blend_reg()` is the only producer of a value carrying the
field, and all three callers of `pgraph_vk_blend_stamps_pad_alpha()` consume its
output — `draw.c:2314` (static), `4563` (eds3), `6009` (reorder, via
`e->dyn_blend` set at `5472`). No consumer reads the raw register.

**One correction to the lane's framing, in the direction that makes fix (2)
more important than it claims.** The commit calls the relocation "defence in
depth rather than the only thing between a guest register and a crash". That is
right, and the reason is stronger than stated: **fix (1) alone would not have
closed H2.** PGRAPH MMIO is an unmasked passthrough — `pgraph_write()`'s
`default:` arm at `pgraph.c:1015-1020` calls `pgraph_reg_w(pg, addr, val)` with
the guest's raw 32-bit value — so a guest can write arbitrary bits into
`pg->regs_[NV_PGRAPH_BLEND]`, bits 18..19 included. Relocation moves the field
off the guest's *named* field; it does not move it out of guest reach. Only the
unconditional write makes the bits "always ours".

The two fixes also **compose without interaction**, which is worth one line
because the pair was chosen in a specific order: with the field at 18..19 the
unconditional write clobbers nothing guest-visible, because bit 16
`LOGICOP_ENABLE` is preserved in the effective register. An unconditional write
at the *old* bits 16..17 would have closed H2 while silently erasing the guest's
logic-op enable from every effective value.

### The build assertions are not tautologies

I re-ran the negative control rather than take it on report, building it from
the macros lifted verbatim out of `nv2a_regs.h:364-414` and `psh.h:144-148`,
with `QEMU_BUILD_BUG_ON` expanded as `include/qemu/compiler.h:73-78` defines it
(`static_assert(!(x), ...)`, so it fires when the condition is true), and
compiling each leg separately with `gcc -std=gnu11`:

| candidate | overlap | key-strip | width | |
|---|---|---|---|---|
| `0x000C0000` | accept | accept | accept | the new field |
| `0x00030000` | **REJECT** | **REJECT** | accept | **the shipped bug** |
| `0x00020000` | accept | accept | **REJECT** | bit 17, one bit wide |
| `0x00040000` | accept | accept | **REJECT** | bit 18, one bit wide |
| `0x00018000` | **REJECT** | **REJECT** | accept | straddles LOGICOP + ENABLE |
| `0x0000C000` | **REJECT** | **REJECT** | accept | inside LOGICOP |
| `0x00300000` | accept | accept | accept | pass 1's suggestion |
| `0xC0000000` | accept | accept | accept | top of the word |

The lane's three claims reproduce exactly. **Every leg has both an accepting
and a rejecting candidate**, so none of the three is implied by the others or by
the values around it — which is the check pass 1's precedent asks for. Two blind
spots remain and are filed as **N1**, LOW, with no current failure scenario.

### H3 — CLOSED

`SET_SURFACE_FORMAT` captures `old_color_format` before the assignment and bumps
`pipeline_state_gen` and `any_reg_gen` when it changes (`pgraph.c:2496-2502`).
Pass 1 asked pass 2 to check two things specifically and both hold:

- the bump is on the **colour** arm, in its own `if` with its own saved value,
  not folded into the zeta comparison three lines below;
- the transition now reaches `init_pipeline_key`, because **both** early-outs
  pass 1 named compare `pipeline_state_gen` — `create_pipeline()`'s at
  `draw.c:1943-1947` and `check_pipeline_dirty()`'s at `draw.c:1810`. That is
  why pass 1 rejected a condition-list widening and asked for a counter: one
  counter satisfies both exits; a condition added to one exit does not.

**The bump covers every write of the field.** `pg->surface_shape.color_format`
is assigned in exactly one place in the whole tree (`pgraph.c:2497`). It is also
in vmstate (`nv2a.c:1563`), which would bypass the bump, but
`nv2a_post_load()` sets `pgraph.flush_pending` (`nv2a.c:1500-1506`), so that
path invalidates renderer state anyway.

**I confirmed H3 was a real defect rather than inheriting the derivation**,
because `SET_SURFACE_FORMAT` calls `surface_update(d, false, true, true)`, whose
`upload=false` branch flushes the reorder window and the draw queue
(`surface.c:3538-3539`). Had that flush reset the pipeline binding, H3 would
never have bitten. It does not: it submits pending draws and clears
`draw_queue.active`, and touches neither `r->pipeline_binding` nor
`r->last_pipeline_state_gen`. `bind_surface` (`surface.c:1811-1827`) is the only
`pipeline_state_dirty` setter on the surface path and is not reached on
compatible reuse.

**`shader_state_gen` deliberately not bumped is correct**, and I verified the
reasoning rather than accepting it. Nothing in `pgraph/glsl/` reads
`surface_shape.color_format` at shader-generation time — every `color_format` in
`psh.c` is a *texture* format from `NV_PGRAPH_TEXFMT0_COLOR`. `PshState` carries
no surface colour format. The stamp at `psh.c:3503` is gated only on
`ps->opts.vulkan && g_dual_src_pad_supported`, neither of which depends on the
format. And `padAlphaMode` is staged from `upload_draw_uniforms()`
(`draw.c:4770`) on every draw, as well as from the `create_pipeline`
fall-through at `draw.c:1977`. So the shader text does not depend on this field
and a recompile would be cost with no correctness behind it.

**Nothing broken by the `any_reg_gen` bump either**, which was worth checking
because it has wider reach than `pipeline_state_gen`. Its two consumers are the
method fast path's `sfp_ok` (`draw.c:3829`) and `try_enqueue_draw_arrays`'
`uniforms_changed` (`draw.c:4869`), and both fail conservative — bail to the
slow path, or re-upload the uniforms. The draw queue is empty when the bump
lands anyway, since the flush precedes it, and
`flush_draw_queue_internal`'s generation save/restore bracket
(`draw.c:5144-5147`, `5397-5401`) runs entirely before the bump and cannot
clobber it. The GL renderer reads neither counter — a grep over
`pgraph/gl/` returns nothing — so the bump is inert there.

### H3's second claim: the #48 repair

**Verified, and it needs a scope the claim does not carry.**
`pgraph_vk_blend_reg_dst_alpha_folded` (`draw.c:455-540`) branches on
`surface_color_format_dst_alpha_is_one(pg->surface_shape.color_format)` at
`draw.c:530`, so the fold's output varies with the guest colour format, entered
`key->regs[0]`, and went stale with the key. The bump repairs it, and the
comment at `draw.c:1877-1883` that claimed keying on the effective register had
closed it was indeed only ever true of the paths that rebuild the key.

But on an eds3 device the fold is recomputed every draw at `draw.c:4538` and
compared against `r->dyn_state.blend`, so **it was never stale there**. The #48
repair, like H1 and H3 themselves, lands only on the non-eds3 static path. See
**N5**.

## M1 — DECIDED, and I accept the decline

The four parts are separated at the site (`texture.c:1361-1406`), three as
not-regressions and one declined.

**The three hold, and I checked them against the format table *and* the upload
code rather than against the argument** — which is a stronger result than the
lane claimed for itself. `kelvin_surface_color_format_vk_map`
(`vk/constants.h:497-600`) gives all four stamping formats guest
bytes-per-pixel == host bytes-per-pixel: the 1555 pair at
`VK_FORMAT_A1R5G5B5_UNORM_PACK16` (2 and 2), the 8888 pair at
`VK_FORMAT_B8G8R8A8_UNORM` (4 and 4). Both host layouts put the guest's pad bit
exactly where the guest's X bit is — `A1R5G5B5_UNORM_PACK16`'s A is bit 15,
which is `X1R5G5B5`'s X; `B8G8R8A8_UNORM` little-endian is ARGB8888, whose A
byte is `X8R8G8B8`'s X byte. And the upload is unconditionally a copy for colour
surfaces: `surface.c:2576-2580` computes
`no_conversion_necessary = surface->color || ...` and **asserts** it, and the
transfer is `memcpy`/`memcpy_image` (`surface.c:2625-2630`) with an unswizzle
that permutes pixel positions, not channels. No alpha is synthesised anywhere on
that path. So the guest's pad byte *is* our image's pad byte, and #48's constant
was overriding correct data. The NV062 blit patches guest memory and inherits
this.

The cross-table invariant also holds: exactly four rows carry a
`sampled_pad_alpha` override (`constants.h:517`, `543`, `571`, `597`) and
exactly four cases return non-`NONE` in `pgraph_glsl_surface_pad_alpha_mode`
(`psh.c:236-248`), the same four, with `X1A7R8G8B8_{Z,O}` correctly in neither.
So the KEEP IN SYNC note at `psh.c:205-211` is satisfied.

### The declined part: accepted

Quoting the decline:

> Whether silicon masks the pad bits with the ALPHA write mask at all is
> UNMEASURED — the pad bits are not an alpha channel, so there is a real
> question there and no golden in the corpus separates the two answers. Forcing
> the mask on for pad formats would make the stamp unconditional and is
> deliberately NOT done, because it would be an unmeasured behaviour change
> riding along with a measured one.

**Accepted**, for three reasons, and I tested the premise rather than accept it
— "no golden separates the answers" is a claim of the same kind as a blocker,
and this project has had three "unmeasurable" blockers proved false in one day.

1. **The premise holds to the resolution my instrument has.** The corpus's two
   write-mask suites are `Color_mask_blend` (one test,
   `C00010101_O32774_S772_D0`) and `Color_Zeta_Disable` (one test, `MaskOff_ZB`),
   neither naming a surface format; while every pad-format capture —
   `Clear`'s `SCF_`/`SFC_` rows, `Surface_format`'s `Fmt_` rows,
   `Blend_surface`'s 32 — masks no alpha writes. No capture combines
   pad-format surface × alpha-write-masked draw × sample-back.
2. **The alternative overrides the write mask the guest asked for**, on a path
   with no oracle. That is strictly worse than a written-down bound if silicon
   honours the mask, and no better than a coin flip otherwise.
3. **It is recorded as a bound at the site**, not as silence, which is what
   AGENTS.md asks of a declined finding.

**What my instrument cannot see**, stated so the acceptance is not read as more
than it is: this is a survey of test *names* and score rows, not of the
`nxdk_pgraph_tests` sources. It cannot see a test that masks alpha writes
without saying so in its name. If the decline is ever to become a measurement,
the cheap route is to read `Color_mask_blend`'s source for the surface format it
targets, and — if it is `A8R8G8B8` — to ask for one new disc test rather than to
guess. One capture rendering to `X8R8G8B8_Z8R8G8B8` with the alpha write mask
clear and sampling back separates the two answers outright, and the fix then
follows the measurement instead of preceding it.

## M2 — OPEN. Third occurrence, third mechanism

**At the fold candidate the re-registration is correct.** At `f0f4ab0c39`,
`merge-base --is-ancestor 0e919fe51e f0f4ab0c39` and
`--is-ancestor 832557813c f0f4ab0c39` both succeed. The brief asked whether it
still holds at the current tip; on the branch, yes.

**At the integration tip `52600e6417` it does not.**
`merge-base --is-ancestor 832557813c 52600e6417` **fails**. The prediction's own
commit has already been landed on `claude/es-de-launcher-disc-error-ojnl14` as
**`fb43bf4bdc`** — one file, `issue59-dual-source-pad-write-v2.json`, +36 lines,
docs only, the same subject as `f0f4ab0c39` — while the five code commits have
not. The mainline therefore carries a bound registration whose `b_ref` names
code the mainline does not contain.

This is M2's shape for the third time on one issue: first an abandoned branch,
then a routine rebase, now a docs commit folded ahead of its code.

The scenario: the base `0e919fe51e` is three commits behind `52600e6417`, so the
fold must rebase or merge, and a rebase rewrites `832557813c`. Concretely — the
hold lifts, someone reads the board (`52600e6417`'s own subject says the HIGHs
are remediated), queues an arm from the mainline's prediction, and the
dispatcher resolves `b_ref` from `origin/claude/padwrite59-dualsrc-tip`, which
still reaches it. *Today* that builds the right code, which is why this is
MEDIUM and not HIGH. After the fold's rebase it either fails to build — loud,
fine — or produces a verdict for a tree that is not the fold.

**Nothing enforces the rule.** `check_cited_commits.py` scans
`nv2a_issues.toml`, not `docs/testing/predictions/*.json`, and no other script
reads a prediction's refs for ancestry. `AGENTS.md:2124-2128` asks for exactly
the queue-time gate that would catch this and it does not exist. Three
occurrences is the point at which the discipline has been shown not to hold, and
the project's own note applies: **the record is not the delivery.**

Mitigating: no v2 request is queued. `dispatch/queue/` holds six `skew44`
requests and both `padwrite59` arms are in `dispatch/queue/withdrawn/` with a
README, so nothing resolves the ref today. No hold was touched and no work
queued.

**The legs themselves are sound**, and I checked the one that is easiest to make
inert. The FAILS IF clause names the literal string `vk dualSrcBlend: enabled`.
`instance.c:998-1007` sets `verdict` to exactly `"enabled"` on success, so the
logcat line reads `vk dualSrcBlend: enabled (maxFragmentDualSrcAttachments=N,
#59)` and the substring matches. The two failure verdicts — `available but limit
0, NOT enabled` and `missing, NOT enabled` — do **not** contain it, because they
differ immediately after the colon. So the check discriminates rather than
passing on any outcome. That is a live leg, not a matched-nothing one.

## L1, L2, L3

**L1 — CLOSED.** The block's code is deleted and its comment kept and rewritten
in place. Exactly one dualSrcBlend log line remains (`instance.c:1002-1007`) and
the second `vkGetPhysicalDeviceFeatures` call is gone. Verified as a side effect
that the edit did **not** break pass 1's claim 3, which is the collateral pass 1
warned about: the ordering is still enable-decision (`995`) →
`pEnabledFeatures` (`1201`) → `vkCreateDevice` (`1216`) → failure return
(`1220`) → `pgraph_glsl_set_dual_src_pad_supported` (`1251-1252`).

**L2 — CLOSED.** The paragraph is rewritten, the code unchanged, and the rewrite
goes further than asked: it notes Vulkan has no `SRC1_ALPHA_SATURATE` to
substitute, and that the class is empty in the corpus so the paragraph is
"unmeasured as well as derived". That last sentence was not requested and is the
right instinct. One clause of the new text is still wrong and one sentence pass
1 asked for is missing — **N2**, LOW.

**L3 — DECIDED, accepted.** Not changed, which is what pass 1 recommended:
keying a uniform declaration on the renderer would split the one macro that
keeps the shader text and the host-side offsets in agreement, a worse trade than
an unused `int`. The accompanying ask is honoured — the commit says the GL path
"generates exactly the GLSL it generates today" rather than claiming
byte-identity.

## The limitation, evaluated

The lane wrote into its own FAILS IF that **this fleet is a poor detector of H1
and H3**. I verified it, and then found the attribution is wrong in a way that
matters more than the verification.

**The claim is true as stated.** With eds3 blend enabled, H1 and H3 are
structurally unobservable. `init_pipeline_key` sets `key->regs[0] = 0` under
`if (r->eds3_blend_supported)` (`draw.c:1900-1907`), so the whole blend register
including the pad field leaves the pipeline key. And `create_pipeline`'s
`use_eds3_blend` (`draw.c:2065-2067`) skips the entire static blend branch at
`draw.c:2261-2330` — the only place the static path reads the effective register
or applies the pad substitution. Blend enable, equation and write mask become
dynamic states set per draw. So an arm on an eds3 part can confirm the accuracy
claim and cannot confirm H1's remediation, H3's, or H3's #48 repair.

**But the cause is a build flag, not the hardware.** `OPT_DYNAMIC_BLEND` is
`#define`d to `1` at `vk/renderer.h:50`, and every one of the four things that
makes the static path dead is inside `#if OPT_DYNAMIC_BLEND`: the eds3
feature-enable (`instance.c:915-943`), the key zeroing (`draw.c:1899-1908`), the
eds3 draw path (`draw.c:4533-4589`) and the reorder path's copy
(`draw.c:5982-6032`). `use_eds3_blend` has an explicit
`#else bool use_eds3_blend = false;` arm, and `instance.c:1187` already guards
the dynamic-state registration with `OPT_DYNAMIC_BLEND && r->eds3_blend_supported`.
No `vkCmdSetColorBlend*EXT` or `vkCmdSetColorWriteMaskEXT` call exists outside
the guard.

**So flipping that one line to 0 makes the static pipeline path live on the
fleet's own Adreno part.** "This fleet is a poor detector of H1 and H3" is true
of the *default build*, not of the fleet. That is the blocker-is-a-claim shape:
an "unverifiable" accepted without being tested.

**What would detect them.** An arm whose only difference from arm B is
`OPT_DYNAMIC_BLEND 0`, bound to the captures H1 and H3 actually reach — the
pad-format rows of `Blend_surface` (one surface, one address, only
`SET_SURFACE_FORMAT` changing, which is H1's and H3's exact shape) and
`Surface_format`'s `Fmt_X*` rows. Its arm A is the same build at the
pre-remediation code, where H1 and H3 are live, so it is a falsifier whose A
side is *expected to fail* — which is the shape a falsifier should have, rather
than one its own patch forces true.

Two caveats, stated rather than glossed. **`OPT_DYNAMIC_BLEND 0` is a build
configuration nobody in this campaign has run**; it needs a smoke boot before it
is an arm. My check is structural — all four eds3 sites and the feature-enable
are inside the guard — which establishes self-consistency, not that it boots.
And it cannot run while the fleet is held, and nothing here asks for it to:
register it and leave it bound, which is what the hold's own offline order says.

Separately: `r->eds3_blend_supported` being true on the Adreno part is asserted
by a code comment (`draw.c:4535-4537`) and by `instance.c:497` plus the
three-feature check at `927-941`. Unlike `dualSrcBlend`, **no logged boot line in
this tree names it.** Worth one log line next to the dualSrcBlend one, for the
same reason that one existed.

## Things checked that HOLD, recorded so nobody re-derives them

- **Pass 1's claim 2 still holds at this tip.** `q->dyn_blend` remains raw —
  set from `pgraph_reg_r` at `draw.c:4914`, `5024`, `6324`, `6381` — and is the
  only one of the two restored into `pg->regs_` (`draw.c:5190`), while
  `e->dyn_blend` is effective and is never restored. So no synthetic value leaks
  back into a register and is re-read.
- **One derivation read twice, verified textually.** `psh.c:3793-3797` stages the
  uniform from `g_dual_src_pad_supported ? pgraph_glsl_surface_pad_alpha_mode(
  pg->surface_shape.color_format) : PSH_PAD_ALPHA_NONE`, character-for-character
  the expression `draw.c:639-642` folds into the synthetic field. The shader and
  the blend state cannot disagree about which draws stamp.
- **The include chain the asserts need is present**: `draw.c:23` → `renderer.h:29`
  (`nv2a_regs.h`) and `renderer.h:33` (`glsl/shaders.h` → `psh.h`), with
  `QEMU_BUILD_BUG_ON` via `qemu/osdep.h` → `compiler.h:78`. All three symbols the
  asserts reference are in scope.
- **The remediation's `draw.c` change is minimal.** Stripped of comments it is
  the field move, the three asserts, and the gate turned into a ternary feeding
  one unconditional `SET_MASK`. Nothing else.
- **Territory is clean.** `pgraph/pgraph.c` is granted to `lane.padwrite59` at
  wave 77 in `docs/testing/territory.toml:66`, so the H3 fix was made on a
  granted file rather than a taken one. This lane claims no files.
- **The `nv2a_index.json` content is correct**, checked without rebuilding it:
  the index stores each site's source line text beside its `file:line`, and all
  **2,914** recorded locations match the fold candidate's own sources exactly —
  including 1,194 in `pgraph/pgraph.c` and 408 in `vk/draw.c`, the two files
  whose line numbers the remediation shifted. Zero mismatches across 31 files.
  Its *provenance stamp* is another matter — **N4**.

## What could not be audited, and why

- **The desktop build. A known named gap on this host**, confirmed:
  `pkg-config --exists libcurl` fails and `/usr/include/curl/curl.h` is absent.
  **I did not build and I am not claiming I did.** This matters more for pass 2
  than for pass 1, because the three `QEMU_BUILD_BUG_ON`s are the one part of
  this change for which a compiler, not a reader, is the right instrument. I
  compiled them, but in a reconstructed translation unit with the macros lifted
  verbatim — same arithmetic, not the same preprocessor. The include chain is
  traced by hand above.
- **The Android build.** Not run. The lane reports it clean with no new
  warnings; I did not reproduce that, and building would have meant working
  outside my (empty) territory on a long-running job for a claim that the
  reconstructed asserts already cover.
- **The `nv2a index` preflight gate** (`preflight.sh:115-127`). Not run: it needs
  the `nxdk_pgraph_tests` checkout against the *branch's* tree, and this worktree
  is at the integration tip, which does not contain the code commits. I checked
  the index a different way (above) that needs no tests checkout.
- **Any runtime behaviour.** No device, by policy and by fact. Both handhelds are
  out of service, `dispatch/hold/thor` is placed, and the Nova has been held
  since 2026-09-13. No run was queued, no hold touched, no request re-queued. H1's
  key aliasing, H2's abort, H3's stale pipeline and M1's sampled alpha are all
  derived — as they were in pass 1, and as, per the limitation above, they will
  remain under the default build.
- **Whether silicon masks pad bits with the ALPHA write mask.** Unmeasured, and
  I accepted the decline rather than resolving it. Stated as a bound.
- **`Color_mask_blend`'s surface format.** I read its name and its score row, not
  its source, so my support for "no golden separates the answers" is at
  name resolution. Said plainly in M1 rather than left to be inferred.

## What the fold still needs

A clean pass 2 does not imply the fold, and three things are outstanding.

1. **Re-register the prediction as part of the fold, not before it (M2).** The
   registration is already on the mainline ahead of its code, so folding the
   code as-is leaves a `b_ref` that is an ancestor of nothing. Recompute both
   refs against the folded shas and commit the updated prediction in the same
   fold. And build the queue-time gate `AGENTS.md:2124-2128` already specifies —
   three occurrences on one issue is enough.
2. **A decision about H1's and H3's evidence.** Under the default build they fold
   on a reading alone, with pass 1 and pass 2 as their only evidence — exactly as
   the original findings had. Either register the `OPT_DYNAMIC_BLEND 0` arm
   described above and leave it bound, or record explicitly that the owner is
   folding two HIGH remediations on two readings. Both are defensible; the
   silent version is not.
3. **A desktop or Android build by someone who can run one.** The asserts are
   compile-time and the whole point of them is that the compiler is the checker.
   Nothing in this record rests on a compiler having seen the real file.

The five new findings are all LOW, all opinions or observations, and **none of
them should hold the fold** — N1 and N2 belong with whoever next touches the
field and the paragraph, N3 is a citation to reword, N4 is pre-existing index
tooling, and N5 is an evidence gap rather than a defect.

## Territory

`lane.audit2-padwrite` claims no files (territory wave 80,
`docs/testing/territory.toml:85`). The only files written are this record and
its JSON, both under `docs/audits/`, which no lane claims. **Nothing in `hw/`
was edited** — this is an audit. The one thing this audit asks for outside its
own files is the queue-time prediction gate in M2's remediation, which is
tooling nobody currently holds; filed to
`$DISPATCH_DIR/board-requests/audit2-padwrite.md` along with the M2 recurrence
and the `OPT_DYNAMIC_BLEND 0` arm proposal, and named here as the brief
requires. **No CI was triggered: no PR exists, none was opened, nothing was
pushed, and every commit subject carries `[skip ci]`.** No device work was
queued and no hold was removed.
