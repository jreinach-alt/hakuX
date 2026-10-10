# perdraw1009 NOTES

## 0. Why attempt 1 didn't finish

Attempt 1 made exactly one commit (681f335fa1, the draft-claim PR.md) and then
stopped. Per `pm/lanelocal-log.md` "2026-10-09 22:50 PDT [lane.local] perdraw1009
restarted on Sonnet": the lane had been started via the board worktree's stale
copy of `lane.sh` (`docs/testing/lane.sh` under `board-wt/.boardtree`), which is
missing usagemode1009's "usage Low" cap (a 17-line diff). Usage was Low at the
time, so the stale script let the lane run on Opus anyway, printed no "usage
Low" line, and lane.local stopped the unit and restarted via the real
`/home/justin/hakuX/docs/testing/lane.sh resume perdraw1009` ("attempt 2 on
claude-sonnet-5"). Nothing about the brief or the worktree was wrong; the
infra that launched attempt 1 was reading the wrong script. This (attempt 2)
picks up the brief from scratch, below.

## 1. flush_draw_one_pass and its callees (job item 1)

Read: `hw/xbox/nv2a/pgraph/vk/draw.c` `flush_draw_one_pass` (9293),
`begin_pre_draw`/`begin_pre_draw_inner` (5995/5443), `begin_draw` (6036),
`end_draw` (6362), and `hw/xbox/nv2a/pgraph/vk/shaders.c`
`pgraph_vk_update_shader_uniforms` (1819/860) and
`pgraph_vk_update_descriptor_sets` (848).

**This path is already heavily dirty-tracked.** `begin_pre_draw_inner` is not
one path but three, tried in order, each one a superset of work:

- **SFP (super-fast path)**: ~15 generation/flag checks (pipeline unchanged,
  no FB/shader/pipeline-state dirt, no descriptor rebind needed, uniforms
  clean, texture_state_gen/non_dynamic_reg_gen/any_reg_gen all matched,
  vertex_attr_gen matched or a memcmp of the attribute/binding descriptions
  confirms the pipeline's key still fits). On a hit: pushes vertex-attr
  push-constants and returns. **No uniform upload, no descriptor write, no
  texture bind.**
- **MFP (medium-fast path)**: looser version of the same checks (allows a
  vertex_attr_gen change if the memcmp still matches, allows a push-texture
  update). On a hit: still calls `pgraph_vk_update_shader_uniforms` +
  `pgraph_vk_update_descriptor_sets` unconditionally, even though both
  functions early-out internally when their own dirty flags are clear.
- **Full path**: pipeline (re)creation, render-pass/framebuffer management,
  full descriptor-set update.

So the "uniforms 3.7 / descriptor sets 2.9 / texture bind 1.9" ms/frame in
lane.local's NFS profile is **not** three flat per-draw costs -- it's whatever
is left after SFP/MFP already filtered out the draws where nothing changed.
The profile's "pfifo_thread 0.42 core at ~1,650 draws/frame" and "renderer
14.6 ms/frame per-draw setup" numbers are each already *post*-fast-path; the
remaining cost is the draws that genuinely must touch GPU state (NFS, being a
3D racer with no static geometry reuse like a sports title's rink, likely
takes SFP/MFP misses on most draws because each object changes its transform,
texture or both every frame -- unverified, no SFP/MFP hit-rate counters were
read from this profile; `super_fast_hits`/`super_fast_misses`/`desc_rebind_skips`
/`desc_rebind_full` in `OPT_STAT_INC` would answer this on the next run and
should be read before trusting any fix's share).

**Per-step read of what each candidate does and what headroom is left:**

| step | what it does per miss | already cached? | territory |
|---|---|---|---|
| `pgraph_vk_ubosz_note_upload` | memcmp+memcpy the whole VS+PS uniform block (perflog-only counter) | N/A -- not a render cost, a measurement artifact | shaders.c (mine) |
| `pgraph_vk_update_shader_uniforms` -> `pgraph_vk_append_to_buffer` | copies the whole uniform block (up to ~3 KB) into the staging buffer at a new offset, every time `r->uniforms_changed` | Only gated on `uniforms_changed`, which is set by ANY vsh/ltctxa/ltctxb/ltc1 write or fixed-function setter (matrices, texgen, fog, eye, viewport, lights, materials) -- not on whether the resulting bytes differ. No byte-level dedup. | **buffer.c -- not in my territory** (not shaders.c/renderer.c; not listed as surfgpu1009's either -- unclaimed) |
| `pgraph_vk_update_descriptor_sets` (UBO half) | `vkUpdateDescriptorSets` for the dynamic UBO binding + ring management | Only on `need_new_ubo_set`; already skips when nothing changed via `desc_rebind_skips`/`need_descriptor_rebind` | shaders.c (mine) |
| `pgraph_vk_update_descriptor_sets` (texture half, standard path) | FNV hash of image views/samplers/layouts, `tex_desc_cache` lookup, `vkUpdateDescriptorSets` on miss | Already has a hash-keyed cache (`tex_desc_cache`, `TEX_DESC_CACHE_SIZE` slots) on top of the gen check | shaders.c (mine) |
| `pgraph_vk_bind_textures` (texture bind 1.9ms) | per-texture upload/decode decision, sampler lookup | Gated on `texture_vram_gen`/`texture_state_gen`; push-descriptor path writes directly to `push_tex_infos` with no `vkUpdateDescriptorSets` at all | **texture.c -- surfgpu1009's until fold** |
| `pgraph_vk_surface_update` (1.9ms) | surface/zeta binding refresh | not read this pass | **surface.c -- surfgpu1009's until fold** |
| vertex-RAM sync / `tlb_reset_dirty` (1.3ms) | dirty-page scan + copy of touched vertex RAM pages | Already has `OPT_SYNC_RANGE_SKIP` (sync_range_covers + has_dirty_vertex_pages) | **draw.c -- surfgpu1009's until fold** |
| `begin_draw`'s pipeline rebind block | viewport/scissor/pipeline bind, no string formatting found here | gated on `pipeline_binding_changed`/render-pass state | **draw.c -- surfgpu1009's until fold** |

**No `snprintf` was found in the shader-bind path in shaders.c or in
`begin_draw`/`begin_pre_draw_inner` in draw.c.** The only `snprintf`s in
shaders.c are inside the ubosz logger (`pgraph_vk_ubosz_log_and_reset`, once
per 60 flips, not per-draw). If the brief's "shader bind 2.4 (snprintf 0.4 of
it)" bucket is `create_pipeline`/`create_clear_pipeline` or a debug-marker
string in draw.c, it is outside today's two files read (shaders.c, and the
parts of draw.c reachable without edit rights); flagging this as unresolved
rather than guessing at a line number.

**Ranking (ms/frame x probability, not ease), everything named is CPU-side
renderer-thread cost, not GPU time -- bf2push656 already measured that halving
UBO binds on BF2 did NOT move GPU ms (GPU bind cost is ~1-4us), so a win here
is not guaranteed to generalize to GPU time; it is a renderer-thread-busy
claim only, which is what idles the guest 12.8ms/frame waiting on the
renderer in pass 2's profile:**

1. **ubosz gate (this lane, done below): ~1.2 ms/frame, P~1.0 (it is a
   measurement artifact, not a render cost -- the only uncertainty is whether
   disabling it changes anything else, and it can't: the whole block compiles
   out in release already).** Does not speed up NFS; decontaminates every
   other candidate's A/B.
2. **Byte-identical-upload skip for `pgraph_vk_update_shader_uniforms`**
   (shaders.c, mine): the bf2ubosize433 counter's own "note Z" found >=30% of
   BF2's same-binding uploads are byte-identical to the previous upload (set
   dirty by a fixed-function setter that didn't actually change the value).
   Unverified for NFS specifically -- no ubosz data exists for NFS yet, and
   with the counter now gated off by default (see #2 below) I can't read it
   without `HAKUX_UBOSZ_LOG=1` on a separate run. P 0.3-0.5 contingent on that
   read; win-if-true is a slice of the 3.7ms/frame uniforms bucket (not all of
   it -- append_to_buffer's copy is in buffer.c, out of territory, so the
   skip would need to short-circuit before the call in shaders.c, which is
   where `r->uniforms_changed` is consumed).
3. **Texture descriptor cache widening / push-descriptor coverage** (shaders.c
   texture half): already has a hash cache; before touching it, read
   `desc_rebind_skips` vs `desc_rebind_full` and the tex_desc_cache hit rate on
   an NFS run. Not attempted this session -- no device run yet (see #2, the
   route is still blocked on the gas-axis question).
4. **vertex-RAM sync, texture bind, surface_update, pfifo pusher/dispatch/spin
   split**: all outside today's territory (draw.c/texture.c/surface.c pending
   surfgpu1009's fold; pfifo.c never mine). Named here, not implemented; see
   OUTBOX for the board question on the pfifo spin.

## 2. Perflog ubosz counter (job item 2) -- done

`pgraph_vk_ubosz_note_upload`/`_note_bind`/`_log_and_reset` (shaders.c
672/774/786) are now gated by a new runtime check, `ubosz_on()`, reading
`HAKUX_UBOSZ_LOG` once (cached, default off -- any unset/empty/"0" value is
off). All three functions return immediately when off, before any
memcmp/memcpy/alloc. The call sites in draw.c (1088, 3411, 6554, 6823, 7919)
are untouched -- they are still inside `#if NV2A_PERF_LOG` (compile-time, so
release builds still carry none of this at all) but now also check the new
runtime flag via the functions they call, with no draw.c edit needed (draw.c
is still surfgpu1009's until its fold lands).

Measured size, from lane.local's 10-09 3-racer profile (pm/lanelocal-log.md,
22:30 PDT entry): ~1.2 ms/frame self, "about a third of the descriptor sets
2.9 ms/frame bucket" -- i.e. real descriptor-set cost in that profile was
closer to ~1.7 ms/frame once ubosz is subtracted. This was not independently
re-measured this session (no device run yet); it is lane.local's number,
cited rather than re-derived, per "don't re-measure what it settles".

**Behavior change, stated plainly:** this flips the DEFAULT for every
perflog build, not just this lane's A/B -- bf2ubosize433's standing
hakuX-stall `ubosz[...]` line goes silent unless `HAKUX_UBOSZ_LOG=1` is set.
The brief instructs exactly this ("env-gated, default off, or removed"); flagged
in PR.md and OUTBOX so lane.local can tell any consumer of that line.

## 3. Addendum 1 / cross-session correction: NFS gas axis

Brief originally said gas is R2 (ABS_GAS, pad.sh's RT) and asked me to verify
the SDL GAS/BRAKE swap on device before writing the route. Two updates landed
while reading code, both before any device run:

- `briefs/perdraw1009.md` "Addendum 1" (lane.local, 22:55 PDT): owner says RT
  accelerates / LT brakes in NFS MW; the old route held RT and sat in gear R
  at 0 MPH -- what holding LT looks like -- so the SUSPECT is that pad.sh's
  logical RT (ABS_GAS, raw axis 9) is arriving at the game as LT, through
  SDL's GAS/BRAKE swap.
- A cross-session message (from=hakux-0b) sharpened this further: step 0 is
  now a one-shot test -- hold `axis LT max` alone (nothing else), check in
  frames whether the speedometer rises. If yes, the swap is confirmed and
  nfs-mw.route drives on LT.

Read (not edited, per both messages) `docs/testing/perf/pad.sh`: `LOGICAL`
table maps `LT -> ABS_BRAKE ABS_Z` and `RT -> ABS_GAS ABS_RZ` (pad.sh:46-47),
so pad.sh's logical LT already resolves to the evdev axis the brief calls
BRAKE (raw 10), independent of any SDL-side swap -- the SDL swap is a
separate, later remapping on the Java side.

Read `android/app/src/main/java/org/libsdl/app/SDLControllerManager.java`
157-181: `RangeComparator` swaps `MotionEvent.AXIS_GAS`/`AXIS_BRAKE` for
SORT ORDER ONLY, with a comment naming exactly this failure mode ("some
controllers, like the Moga Pro 2, return AXIS_GAS (22) for right trigger and
AXIS_BRAKE (23) for left trigger -- swap them so they're sorted in the right
order for SDL"). This confirms the MECHANISM the addenda suspect exists and
is controller-model-dependent; it does not by itself prove the Nova's
"Retroid Pocket Controller" hits it -- that needs the on-device frame check
named in both addenda.

**Status: the on-device LT-alone investigative run has not been queued yet
this session** (no `request.sh` call made). Per Rule "never hold the device
yourself" and the pilot budget (30 min unreviewed), this is a short (<=60s)
single investigative run, well under the pilot threshold, and is the
immediate next step before writing nfs-mw.route or registering any
A/B prediction. OUTBOX names the exact request.

## 4. Status / next steps

Done this session: NOTES.md (this file), ubosz env-gate in shaders.c
(committed as a WIP-then-final commit per lane.local's request mid-session).
Not done yet: the LT investigative run, nfs-mw.route, the per-draw fix's own
HAKUX_* flag (candidate #2 above, contingent on an NFS ubosz read), the
prediction JSON, any A/B, pixel check, generalisation arm. This session is
not claiming "done" -- PR.md stays in draft/needs-device state; see OUTBOX
for the queued asks (pfifo spin lines, ubosz default-flip notice).
