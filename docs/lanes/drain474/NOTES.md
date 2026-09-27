# lane.drain474 (#474)

Branch `lane/drain474`, base master 09fdca3ba1 merged with PR #512
(`lane/slowdown462-bindtex`, the perflog-only `txw[]` probe) at 3b5c577e9c.

## The change (73a4126325)

`create_texture()` in `hw/xbox/nv2a/pgraph/vk/texture.c`, the surface-to-texture
rebind (`surface->draw_time != snode->draw_time`): the drain

    if (snode->submit_time + r->num_active_frames > r->submit_count)
        pgraph_vk_flush_all_frames(pg);

ran before `can_direct_bind` was computed, so it ran ahead of direct binds too.
It now runs only in the `!can_direct_bind` branch, ahead of
`copy_surface_to_texture`. The `txw[]` FAF/BS/CP counters are unchanged, so
`faf` in B counts only drains ahead of a copy.

Premise (lane.slowdown462, run `1-1790543757-slowdown462-3565156`, AUF, Nova,
299-420 s): `faf` 0.27 calls/flip, 4.47 ms/flip of `bt`'s 4.57; `bs` 1.00, `cp` 0,
`up` 0; 16.6 fps. The bound on the gain is about 18.0 fps: a bound, not a value.

## Why nothing in flight needs the drain on the direct path (read, not assumed)

- **What the drain guards.** Its condition is on the texture node
  (`snode->submit_time`, which `update_timestamps()` stamps on every bound node
  at submit). It waits until no in-flight frame can still sample the node's
  image. Only `copy_surface_to_texture` / `copy_zeta_surface_to_texture` write
  that image (transition to TRANSFER_DST, `vkCmdCopyImage`, back to
  SHADER_READ_ONLY, updating `texture->current_layout`).
- **The direct bind writes nothing into the node.** `bind_surface_as_texture`
  flushes the reorder window and draw queue, opens a non-draw command buffer and
  puts a COLOR_ATTACHMENT_WRITE -> SHADER_READ barrier on `surface->image`
  (GENERAL -> GENERAL). `bind_zeta_surface_as_texture` does the same for depth and
  moves `surface->image_layout` to DEPTH_STENCIL_READ_ONLY. Both set
  `texture->draw_time` and nothing else on the node. The node's `image`,
  `image_view` and `current_layout` are not touched. The barriers are on the
  surface's image and are ordered by queue submission, so an earlier frame's use
  of the surface comes first without a host wait.
- **Descriptors of in-flight frames.** With push descriptors (the fast paths in
  draw.c and `pgraph_vk_update_descriptor_sets` in shaders.c), the image infos
  are recorded into the command buffer at push time. Changing
  `tex_surface_direct_views[i]` changes what later pushes record, not what
  earlier ones did. On the standard path, a new texture descriptor set is taken
  from the ring at `descriptor_set_index`. When the ring is full, the code runs
  `pgraph_vk_finish` + `pgraph_vk_flush_all_frames` before it resets the index,
  so a set in use by a frame in flight is never rewritten. The descriptor-set
  cache (`tex_desc_cache`) is keyed on views, samplers and layouts, so a direct
  bind looks up a different key and cannot alter a cached set.
- **`tex_surface_direct_views` rotation.** Retiring a surface view is handled by
  `pgraph_vk_texture_surface_view_retired()` (#34/#274): it points a slot at the
  dummy until the slot is rebuilt. That path is separate from this drain, and its
  condition is on the node, not the surface.
- **The node's layout.** Unchanged by a direct bind. A later copy into the same
  node still goes through the copy branch, and so through the drain.
- **Natural experiment.** Two paths in `create_texture` already bind directly
  with no drain: the cache-miss bind at the end (a fresh node), and the
  same-draw_time rebind (`else if` after the draw_time test). This change makes
  the changed-draw_time direct rebind behave like them.

## Predictions (registered before any device run)

- `docs/testing/predictions/drain474-s2t-pixels.json`: pixel A/B across Texture
  render target, render update in place, Framebuffer Blit, Antialiasing, shadow
  comparator, Surface format, and Color zeta overlap. `must_not_move` on all of
  them. The arms job queues it.
- `drain474-auf-soak.json` (Nova) and `drain474-blinx-soak.json` (Thor): 420 s
  perflog survey soaks. Read with `docs/lanes/slowdown462/txwwin.py <dir> 255 411`.
  These are hand-queued (arms.sh skips soaks).

## State (2026-09-27, attempt 1)

- Preflight passed on f759e898db. CI is the build check. The code was not
  compiled locally.
- Pixel arm: the arms job queues `drain474-s2t-pixels.json` from the pushed
  registration.
- Blinx pair on the Thor, the pilot (two requests, 17 min):
  A `1790549563-drain474-2135431`, B `1790549563-drain474-2135559`. When they
  were queued, about 2.5 h of flip474 and titleroutes work was ahead of them.
- AUF pair on the Nova: **not queued yet.** Four soaks come to 34 min, over the
  30-min pilot gate. After the Blinx pair is read, write
  `pilots/drain474.ok` (with python3) and queue AUF A/B on the Nova with
  `--expect docs/testing/predictions/drain474-auf-soak.json`. The Nova is held
  for battery at the moment, so the pair will wait for it either way.
- Next lane: do not re-queue the Blinx pair. Read it with
  `python3 docs/lanes/slowdown462/txwwin.py <dir> 255 411`, and read the
  cooling devices before trusting a low fps (#507).
