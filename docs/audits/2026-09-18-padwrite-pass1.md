# Audit pass 1 — #59's dual-source pad write

**Lane** `lane.audit-padwrite` (territory wave 73, claims no files).
**Subject** `lane.padwrite59`, branch `claude/padwrite59-dualsrc-tip`, tip
`775389f537`, five commits, 424 lines of compiled code across
`glsl/psh.c` (+121), `vk/draw.c` (+143), `vk/instance.c` (+89),
`glsl/psh.h` (+38), `vk/texture.c` (+33).
**Date** 2026-09-18. **Records** `2026-09-18-padwrite-pass1.json` (flat array,
schema as `2026-09-14-remote-pass1.json`).

**3 HIGH, 2 MEDIUM, 3 LOW.** Not a clean audit. Two of the three HIGHs are one
bit collision seen from two sides; the third is independent and is the one that
falsifies the change's central plumbing claim.

## Why this is an audit and not an arm

Both handhelds are out of service — `$DISPATCH_DIR/hold/thor` is placed and the
Nova has been held since 2026-09-13 — so the two registered arms are bound and
will not be claimed. This code does not fold without a read.

It is also the right instrument independently of the hold. The highest-risk
path here is one **no arm on this fleet could exercise**: the Adreno part
advertises `dualSrcBlend`, so every code path taken when the feature is ABSENT
is unreachable on the only hardware available. H2 lives on exactly that path.
H1 and H3 live on the static pipeline path, which the change's own comment
(`draw.c:4466-4468`) says is dead on Adreno because EDS3 blend is supported
there. **None of the three findings could have been produced by a device run on
this fleet, whatever the hold.**

## The four load-bearing claims

| claim | verdict |
|---|---|
| 1. The blend cannot be fixed by reordering: `result.a = As*Fs + Ad*Fd` is linear in two alphas, so a constant 0 is expressible and a constant 1 is not. | **HOLDS.** Checked against the factor vocabulary in `nv2a_regs.h:381-412`. A constant 1 in `result.a` requires a factor pair summing to exactly 1 independent of both alphas, and no `(Fs, Fd)` from that list does it; `ZERO/ZERO` gives the constant 0. Dual-source separation is the route. |
| 2. The synthetic blend-reg field is necessary, and it reaches every one of the three blend paths the function keys. | **FAILS, twice.** The field is placed on top of `NV_PGRAPH_BLEND_LOGICOP_ENABLE` and half of it is stripped before the pipeline key is compared (**H1**), and on the static path `init_pipeline_key()` is never reached on a colour-format change at all, so the key is irrelevant there (**H3**). The two dynamic paths — EDS3 at `draw.c:4469` and the reorder snapshot at `draw.c:5403` — do carry it correctly, and the claim that `q->dyn_blend` is raw and never sees the synthetic value is TRUE (`draw.c:4845/4955/6255/6312` read `pgraph_reg_r`, and `draw.c:5121` restores that raw value). |
| 3. `pgraph_glsl_dual_src_pad_supported()` is a device constant set once after `vkCreateDevice` succeeds, so it cannot go stale in the shader cache. | **HOLDS.** The setter is at `instance.c:1267-1268`, after `vkCreateDevice` at 1232 and after its failure return at 1236, and reads back off `enabled_physical_device_features` — the same struct `pEnabledFeatures` is populated from at 1217. The enable decision at 987-1009 runs after the `desired_features` loop writes `*enabled` at 883, so it is not overwritten, and `r->device_props` is filled in `select_physical_device` at 610, before this function. The gate is read only at shader generation and at blend-state derivation, both after init. `775389f537` was the right fix and it is complete. |
| 4. The GLES hazard is prevented: glslang needs ES 310 or `EXT_blend_func_extended` for the `index` qualifier and our GLES path emits `#version 300 es`, so emitting the second output there would fail to compile every draw. | **HOLDS.** Both emission sites are gated on `ps->opts.vulkan` as well as the device flag — the declaration at `psh.c:1998-2016` and the stamp at `psh.c:3503` — and `psh_convert` is the only place either string is produced. The GL/GLES fragment output string is byte-identical to the pre-patch one. One correction: the GL shader TEXT is not byte-identical to pre-patch overall, because `padAlphaMode` joins `PSH_UNIFORM_DECL_X` and `psh.c:2022-2024` emits every uniform unconditionally for both renderers (**L3**). Harmless — `locs[]` returns -1 and staging is skipped — but the claim should be stated as "unchanged in behaviour", not "byte-identical". |

## Findings

### H1 — the synthetic field sits on the guest's logic-op enable, and the pipeline key strips it

`NV2A_VK_BLEND_PAD_ALPHA` is `0x00030000`, "bits 16..17", justified by
"`NV_PGRAPH_BLEND` defines bits 0..11". It defines more than that:
`nv2a_regs.h:413` is `NV_PGRAPH_BLEND_LOGICOP_ENABLE (1 << 16)` and
`nv2a_regs.h:414` is `NV_PGRAPH_BLEND_LOGICOP 0x0000F000`.

`init_pipeline_key()` assigns the effective register at `draw.c:1815` and then,
twelve lines later, strips that bit:

```c
key->regs[0] &= ~(NV_PGRAPH_BLEND_LOGICOP_ENABLE |
                   NV_PGRAPH_BLEND_LOGICOP);
```

`PSH_PAD_ALPHA_ZERO` is 1, so it lives entirely in bit 16 and is erased.
`PSH_PAD_ALPHA_NONE` is 0. **The pipeline key cannot tell a `_Z` pad format
from a format with no pad bits at all** — which is exactly the aliasing the
field was introduced to prevent, on exactly the surface (`Blend surface`, one
address, 32 cases, `SET_SURFACE_FORMAT` the only change) the comment cites.
`PSH_PAD_ALPHA_ONE` is 2, bit 17, and survives: the bug is silent on the `_O`
half, which is the shape that survives a partial reading of a score table.

### H2 — the same collision on the feature-absent path, and it is a crash

When the gate is false the `SET_MASK` is skipped, so bits 16..17 hold whatever
the raw register holds — and bit 16 is the guest's own
`NV097_SET_LOGIC_OP_ENABLE` (`pgraph.c:3951-3955`). `pgraph_vk_reg_r()` does
not mask it: the dynamic-mask table gates generation counters inside
`pgraph_reg_w` only (`pgraph.h:458-478`). So on a device with **no**
`dualSrcBlend`, a guest that enables a colour logic op makes
`pgraph_vk_blend_stamps_pad_alpha()` return true, and the renderer programs
`VK_BLEND_FACTOR_SRC1_ALPHA` with the feature disabled and a shader that
declares one output. `vkCreateGraphicsPipelines` is called under `VK_CHECK`
(`draw.c:1702`) — **an abort at pipeline creation**, on the device class this
fleet does not own. This is audit pass 1's original HIGH by shape and by
mechanism.

The brief asked whether the feature-absent path is a refusal to enable or a
failure to start. `instance.c:987-1009` gets the *enable decision* exactly
right — both preconditions, together, with the limit checked and a named
verdict — and `instance.c:972-985` documents the consequences correctly. The
refusal then leaks, not in `instance.c` but two files away, because the
predicate that consumes the refusal is keyed on bits the guest can set.

### H3 — the field reaches the key; the key is not reached

`create_pipeline()` early-returns at `draw.c:1869-1881` *before*
`init_pipeline_key()` is ever called, when the generation counters and
`check_render_pass_dirty()` are unchanged. A colour-format-only change moves
none of them:

- `pg->surface_shape.color_format` is a plain `PGRAPHState` field, not a pgraph
  register, so `pgraph_reg_w()`'s generation machinery never runs for it;
- `DEF_METHOD(NV097, SET_SURFACE_FORMAT)` bumps `shader_state_gen`,
  `non_dynamic_reg_gen` and `any_reg_gen` **only when the zeta format changes**
  (`pgraph.c:2467-2474`). Nothing bumps `pipeline_state_gen`;
- `init_render_pass_state()` carries only the host `VkFormat`
  (`draw.c:1312-1317`), and A8R8G8B8 and X8R8G8B8_Z8R8G8B8 share
  `B8G8R8A8_UNORM`;
- `bind_surface()` does set `pipeline_state_dirty` (`surface.c:1826`) but is not
  reached when the wanted binding is already bound, which is the whole reuse
  case.

The uniform, by contrast, *is* staged every draw from the live register
(`psh.c:3772-3795`). So the shader's decision to stamp and the pipeline's
decision to substitute can disagree, in both directions, and one direction is
arm 1's measured defect reintroduced.

This hole predates #59 — the destination-alpha fold sits in it too, and the
comment at `draw.c:1807-1814` claims keying on the effective register closes
it. That claim was already only true of the paths that rebuild the key. #59
widens the consequence from two blend factors to the whole alpha equation plus
a SRC1 substitution, so the remediation belongs with this change even though
the defect is inherited.

### M1 — the read-side withdrawal is unconditional; the write-side stamp is not

`surface_sampled_pad_alpha()` returns IDENTITY for every pad-format surface
once the gate is true (`texture.c:1362`), but the stamp only writes the pad byte
where the raster drew **with alpha writes enabled**. Surface upload from guest
RAM, an NV062 image blit (which patches guest memory, `blit.c:513-557`, not the
image), and any draw with `NV_PGRAPH_CONTROL_0_ALPHA_WRITE_ENABLE` clear all
leave non-stamped bytes in the image. On those pixels the sampled alpha
regresses from the format's measured constant to a stale or guest-supplied
byte. `psh.h:180` states the qualifier itself — "exact on every pixel the
raster drew" — and then the withdrawal drops it.

The gating rather than deletion is right, and the reason given (arm 1's 26,417
px were uninterpretable because two changes moved one quantity) is correct.
The gap is that the stated motive for withdrawing at all is a measurement one:
"leaving it in would make the write side INVISIBLE". That is a reason to run
the arm with the swizzle out. It is not by itself a reason to fold with it out.

### M2 — the prediction's arm B ref is not on the branch

`b_ref` is `fab34eb3ea`, which is **not** an ancestor of `775389f537`. Its
patch-id equals `3519f4fc9e`'s (`7803c8d8c21a…`), so it is the same patch on an
abandoned sha, still reachable from the older branch
`origin/claude/padwrite59-dualsrc`. The dispatcher can therefore build it
**successfully** and produce an arm B that excludes `c3d4e121df` and, crucially,
`775389f537` — the gate-ordering fix. The arm as bound measures the version the
lane itself decided must not ship, and nothing fails to announce it.

`a_ref` `2445a6ff46` is a valid ancestor and needs no change. The validity
gate in the prediction (arm A must read `Clear/SFC_X1R5G5B5_Z1R5G5B5` = 49,152
and `Blend_surface/*DstAlpha*` = 0 on all 16) is the good part of that document
and should survive re-registration.

### L1 / L2 / L3

`L1` — the old query-only `dualSrcBlend` block still executes below the new one,
calling `vkGetPhysicalDeviceFeatures` twice and printing a second, contradictory
log line. The prediction's FAILS IF clause makes that line the arm's evidence.
`L2` — the `SRC_ALPHA_SATURATE` paragraph is wrong in the direction it claims:
under the stamp `min(As, 1-Ad)` evaluates to 0 for both pad variants, which is
the hardware answer; the code is right and the justification is not.
`L3` — `padAlphaMode` adds one unused uniform to the GL/GLES shader text.

`L2` and `L3` have **no failure scenario**, so they are opinions and are
recorded as such. Both are about a sentence, not a behaviour.

## Things checked that HOLD, recorded so pass 2 does not re-derive them

- **Every consumer of `fragColor.a` on the Vulkan path.** The alpha test
  (`psh.c:3390-3411`) and #43's signed fold (`psh.c:3413-3470`) both precede the
  stamp (`psh.c:3503-3511`), and nothing after it touches `fragColor` — the only
  later append to `ps->code` is `gl_FragDepth` (`psh.c:3524-3622`). There is no
  alpha-to-coverage anywhere in the vk renderer (`sampleShadingEnable` is
  `VK_FALSE` at `draw.c:1518`, `2035`, `compile_worker.c:90`,
  `display.c:556`, and no `alphaToCoverage` appears at all).
- **The fixed-function readers of source alpha are exhaustively covered.** From
  the NV2A factor list, the only colour-half readers of `As` are `SRC_ALPHA`,
  `ONE_MINUS_SRC_ALPHA` (substituted) and `SRC_ALPHA_SATURATE` (L2).
  `SRC_COLOR`/`DST_COLOR` and their complements contribute only RGB to the
  colour half; `CONSTANT_*` read the blend constant. Nothing else reads it.
- **Destination alpha never reads the stamp.** All four stamping formats are in
  `surface_color_format_dst_alpha_is_one()` (`draw.c:288-302`), so
  `DST_ALPHA`/`ONE_MINUS_DST_ALPHA` are folded to `ONE`/`ZERO` before the pad
  field is added. The signed-equation early return at `draw.c:470-499` skips
  that fold but forces `ONE/ONE`, so neither factor reads `Ad` there either.
- **MIN/MAX blend equations.** Vulkan ignores factors for MIN/MAX, so forcing
  `srcAlpha=ONE/dstAlpha=ZERO` alone would not land the stamp — but
  `alphaBlendOp` is forced to `VK_BLEND_OP_ADD` at all three sites, which
  covers it.
- **MRT.** `create_render_pass` sets `colorAttachmentCount = color ? 1 : 0`
  (`draw.c:1397`) and there is no second colour attachment anywhere, so the
  dual-source/MRT exclusion cannot bite. The `instance.c` comment asserting
  this is accurate.
- **The clear's third derivation of the same fact.** `pgraph_vk_get_clear_color`
  keys on `pgraph_vk_surface_drawn_format(r->color_binding)`
  (`draw.c:693-701`) while the stamp and the blend field key on the live
  register — two different sources for one per-format fact, which is the M3/P4
  shape the lane cites twice. It holds anyway: `drawn_format` is refreshed from
  `pg->surface_shape.color_format` on both the create path
  (`surface.c:3120`) and the compatible-reuse path (`surface.c:3340`), and
  `surface_update` runs ahead of both the clear and the draw. Recorded because
  the claim of "one derivation read twice" is true of the psh.c/draw.c pair and
  not of the clear, and because nothing makes the two stay in sync by
  construction.
- **No `assert` implied by its own condition.** The change adds none. The
  pre-existing `assert(sf < ARRAY_SIZE(...))` at `draw.c:4481-4483` is still
  reached before the substitution, and the substitution's output is not
  re-indexed into those tables.
- **No model hard-coded as an invariant.** The pad-mode table
  (`psh.c:236-248`) and the `dst_alpha_is_one` table (`draw.c:288-302`) both
  enumerate guest format enums with a `default` arm, and both take the guest
  enum rather than a host `VkFormat` — which is the right call, since five guest
  formats share `B8G8R8A8_UNORM`.
- **Snapshot divergence is not live.** `pgraph_vk_effective_blend_reg` reads
  registers through the snapshot-aware `pgraph_vk_reg_r` but the surface format
  from live `PGRAPHState`, which would be an asymmetry — except that
  `r->active_snap` is never assigned anywhere outside its declaration and read
  in `vk/renderer.h`, so the snapshot path is dead. Worth knowing if it is ever
  turned on: `RenderCommandSnapshot` already carries `surface_shape`
  (`renderer.h:528`) and this code does not consult it.

## What could not be audited, and why

- **The desktop build.** A **known named gap** on this host:
  `libcurl4-openssl-dev` is not installed (`pkg-config --exists libcurl` fails,
  `/usr/include/curl/curl.h` absent). **I could not build; I am not claiming
  I did.** Nothing in this record rests on a compiler — all of it is read from
  source and from `nv2a_regs.h`. The include chain that makes
  `pgraph_glsl_dual_src_pad_supported()` visible in `vk/draw.c` and
  `vk/texture.c` was traced by hand: `renderer.h` → `glsl/shaders.h:25` →
  `psh.h`.
- **Any runtime behaviour.** No device, by policy and by fact: both handhelds
  are held and the owner is troubleshooting a screen fault. No run was queued,
  no hold touched. H2's abort, H1's and H3's stale pipelines and M1's stale
  sampled alpha are all derived, not observed.
- **Whether the `_O`-format `SRC_ALPHA_SATURATE` residual in L2 is reachable in
  the corpus.** It depends on how a pad-format destination's alpha got there,
  which is M1's question, and answering it needs either the upload path
  instrumented or a capture. Stated as a bound, not a value.
- **`maxFragmentDualSrcAttachments` on any real part except by inference.** The
  code's handling of a self-contradictory driver (feature true, limit 0) is
  correct by reading; no device in the fleet reports that combination and none
  ever will be available to check it. That is the reason the audit exists, not
  a defect in it.

## Dispatch notes

- H1 and H2 are one collision and one relocation closes both — but they must be
  **verified separately in pass 2**, because a fix that only widens the mask at
  `draw.c:1827` closes H1 and leaves H2 live.
- H3's remediation (a `pipeline_state_gen` bump on the colour-format arm of
  `SET_SURFACE_FORMAT`) also repairs the pre-existing destination-alpha hole, so
  it is worth more than #59 alone and should be scoped as such.
- M2 should be actioned **after** H1–H3 land, so the re-registration happens
  once against the real fold candidate rather than twice.
- **A remediation is a claim.** Each of the above is a suggestion from someone
  who did not have to make it work. A lane that disagrees should decline with a
  reason rather than implement it, and say so in its report.

## Territory

`lane.audit-padwrite` claims no files. The only files written are this record
and its JSON, both under `docs/audits/`, which no lane claims in
`docs/testing/territory.toml`. Everything this audit asks for is in
`lane.padwrite59`'s territory (`glsl/psh.c`, `glsl/psh.h`, `vk/draw.c`,
`vk/instance.c`, `vk/texture.c`) or in the prediction file, plus one bump in
`hw/xbox/nv2a/pgraph/pgraph.c` for H3 — which is in `[free]`, so it is
unclaimed rather than walled, and a remediating lane needs it granted on the
board rather than taken. Filed to
`$DISPATCH_DIR/board-requests/audit-padwrite.md`. No CI was triggered; no PR
exists and none was opened.
