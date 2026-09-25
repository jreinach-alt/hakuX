# Audit pass 1: PR #235, lane shadeflat224 (#224 family A)

Auditor: job.cloud, 2026-09-25. Head audited: `8becbfaeb0`. Read: the full
diff against `origin/master`, plus every consumer of `primitive_mode` /
`gl_primitive_mode` / `PrimAssemblyState` outside the diff that the new enum
value can reach.

**Verdict: no HIGH, no MEDIUM. Four LOWs.** Pass 2 still has one thing to
verify: the W_param must_not_move legs came back void (unreadable captures,
not measured). `shadeflat224-flatdiag-replicate.json` re-registers the same
legs, refs and disc, and its verdict is what pass 2 has to read.

## What was checked and holds

- **Index layout.** `emit_tri_adj(a,b,c,p)` emits `a p b p c p`, so slots
  0/2/4 are the triangle. The quad branch `(v0,v1,v2)/(v0,v2,v3)` and the strip
  branch `(v0,v1,v2)/(v2,v1,v3)` are the Smooth branches vertex for vertex,
  winding included. `max_output_indices()` takes `per_tri = 6` exactly when
  `emits_adjacency()` is true, and both callers (`_ranges`, `_indexed`) pass the
  same predicate the emit uses. No overrun.
- **Rewrite / shader agreement.** Flat is computed in two places and they
  agree. The rewrite side is `PrimAssemblyState.flat_shading` (CONTROL_3
  SHADEMODE == FLAT) and `.polygon_mode` (SETUPRASTER FRONTFACEMODE). The
  shader side is `GeomState.smooth_shading` (SHADEMODE == SMOOTH) and
  `polygon_front_mode` (the same field). `pgraph_glsl_gen_geom` already asserts
  front == back, so this adds no back-mode case.
- **Vulkan draw queue.** `try_enqueue_draw_indexed` truncates to multiples of
  6 via `get_draw_mode`. On replay (`vk/draw.c:5301`), `pg->primitive_mode` is
  set to the binding's mode. The replay also restores CONTROL_3 and
  SETUPRASTER from the queue (`:5326-5331`), so `get_draw_mode(ADJ, …) == ADJ`
  holds, and the flat state that produced it is the state in force. The
  merged-arrays path rewrites with the guest mode `q->primitive_mode`, so it
  emits adjacency to match.
- **The enum value reaching guest-mode code during replay.** Three places
  read it there, and all three are safe. `psh.c:3972` (`>= PRIM_TYPE_TRIANGLES`)
  keeps polygon offset on for ADJ, which is correct for a filled quad.
  `pgraph_draw_rasterises_lines()` falls to `default: false`, also correct.
  The vk early-exit comparisons (`:2086/2106/3899/4089`) compare
  guest-vs-binding exactly as they did with TRIANGLES. No table is indexed by
  `primitive_mode`.
- **The vk cached-state fast path** (`vk/shaders.c:1406`) now re-derives the
  draw mode from the cached `smooth_shading` and `polygon_front_mode`. The
  full path does the same, so the two cannot disagree.
- **GL.** Every GL draw call in `pgraph_gl_flush_draw` goes through
  `gl_draw_mode()`. `gl_geometry_stage_available()` is the same predicate
  `gl/shaders.c:372` uses to drop the geometry stage: always on desktop,
  `geometry_shaders_supported` on Android. So "no geometry stage" always
  pairs `no_adjacency` in the rewrite with a `GL_TRIANGLES` draw.
- **Geometry shader.** `need_geom()` is true for ADJ. `calc_triz(0,2,4)`
  takes arbitrary indices. Flat D0/D1/B0/B1 and vtxFogSpecial are read from
  slot 1 (v3), and the non-flat varyings from 0/2/4. vtxFogSpecial matches
  the old path: the old path's first-provoking output vertex was v3. On the
  Android GL build (last-vertex default), the old path handed the rasteriser
  v1's vtxFogSpecial. The new path pins v3 on every output vertex, so it is
  convention-proof. The cylWrap reference `v_vtxT[0]` is slot 0, a real
  triangle vertex.
- **Predictions.** The two files differ only in `prediction` prose and
  `registered_utc`. `b_ref 3ce8778094` is an ancestor of the head. The head
  differs from b_ref in `hw/` only by master's `pmc.c` (+41), which a_ref
  (`a6bb4a13d4`, on master) also lacks, so the A/B pair is consistent.

**Not verified here.** The claim that the adjacency shader compiles under
glslc (vulkan1.0) and GL/GLES 3.20. `geom-dump` builds cleanly on this host,
but this session could not execute it. The lane's arm (all 12 must_move
legs better and within bound) is on-device evidence that the Vulkan shader
compiles.

## Findings

### L1 (LOW). The GL half of the change is unexercised by any arm
`gl/draw.c:785-808`, `gl/shaders.c:44`, `gl/renderer.h:42-47`. Every device
arm is Vulkan, and the prediction says so. Failure scenario: desktop GL or
GLES 3.2 rejects the `triangles_adjacency` geometry shader, or the GLES
fallback pairing breaks. Either way, flat textured quads draw nothing (or the
old diagonal) on the GL renderer, and nothing registered would see it. The
code reads correct, so this is a coverage gap, not a defect.

### L2 (LOW). `get_draw_mode()` maps ADJ to ADJ regardless of shade and polygon mode
`prim_rewrite.c:109-119`. If `pg->primitive_mode` were ever ADJ while
CONTROL_3 read SMOOTH (or FRONTFACEMODE read LINE), `set_geom_state` would
produce `{ADJ, smooth}` and trip the new assert in `gen_geom` (`geom.c:104`).
No path found that does this: replay restores CONTROL_3 and SETUPRASTER from
the queue entry. So there is no failure scenario today. It is a trap for the
next person who adds a replay path.

### L3 (LOW). Degenerate QUADS draws on the raw-vertex fallback now use the adjacency topology
When every range has fewer than 4 vertices, the rewrite returns 0 indices.
GL's `glMultiDrawArrays` and vk's indirect or plain draw then submit the raw
vertices with the binding's topology, which for a flat filled quad is now
ADJ. A 3-vertex flat QUADS range used to draw a stray triangle, and now
draws nothing. Silicon draws nothing for an incomplete quad, so this is a
behaviour change in the right direction. It is recorded so nobody reads it
as a regression.

### L4 (LOW). The regenerated `nv2a_index.json` points `tests_root` at the live tree
Provenance changed from a pinned scratch copy to `/home/justin/nxdk_pgraph_tests`
and `/home/justin/pbkitplusplus`. `tests_commit` is unchanged, and the rest
of the diff is `line`/`loc` moves only (816 changed lines, none a count). So
the index content is right. The provenance path just names a mutable tree
rather than a dated one.

## For pass 2

- The replicate arm's `[job.arms]` verdict. It must show the W_param
  must_not_move legs **readable** on both arms (check the `[status]` tags and
  B's `run1.log` coverage line, not the pixel delta), and unmoved. A void leg
  is not a pass.
- Family A's 12 must_move legs held on the first arm. Pass 2 should confirm
  the replicate did not contradict them.
