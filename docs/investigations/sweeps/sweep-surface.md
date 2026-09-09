> **Machine-generated inventory. NOT verified.**
>
> This is the raw output of a read-only sweep agent, preserved because the
> container it ran in is ephemeral. It is a lead list, not documentation.
> Citations are mostly accurate and at least two claims across this set were
> wrong — see the Corrections section of
> [`../nv2a-sweep-2026-09.md`](../nv2a-sweep-2026-09.md), which holds the
> subset re-checked by hand.
>
> Check any claim here against the code before acting on it.

# NV2A surface / framebuffer / render-target inventory

Read-only sweep of `/home/user/hakuX` at commit `5b4f577`. No files under the repo were
modified. All paths below are relative to `/home/user/hakuX/`.

Conventions used in this document:

- **VERIFIED** — I read the cited line(s) and the claim is a direct restatement of the code.
- **INFERRED** — I read the cited lines but the claim requires reasoning across them
  (e.g. "this flag is lost"); flagged inline as `[INFERRED]`.
- Everything I could not settle is in **Uncertainties**, not asserted above.

Two structs share the name `SurfaceFormatInfo` (one per backend, different fields); two
share the name `SurfaceBinding` (one per backend, different fields). Both are cited with
their backend path to disambiguate.

---

## Concepts owned

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Surface clip rect, horizontal | method | `NV097_SET_SURFACE_CLIP_HORIZONTAL` (0x200) | `hw/xbox/nv2a/nv2a_regs.h:863` |
| — clip X / clip width subfields | regfield | `NV097_SET_SURFACE_CLIP_HORIZONTAL_X`, `_WIDTH` | `hw/xbox/nv2a/nv2a_regs.h:864`, `:865` |
| Surface clip rect, vertical | method | `NV097_SET_SURFACE_CLIP_VERTICAL` (0x204) | `hw/xbox/nv2a/nv2a_regs.h:866` |
| — clip Y / clip height subfields | regfield | `NV097_SET_SURFACE_CLIP_VERTICAL_Y`, `_HEIGHT` | `hw/xbox/nv2a/nv2a_regs.h:867`, `:868` |
| Surface format word | method | `NV097_SET_SURFACE_FORMAT` (0x208) | `hw/xbox/nv2a/nv2a_regs.h:869` |
| Colour surface format selector | regfield | `NV097_SET_SURFACE_FORMAT_COLOR` (mask 0x0F) | `hw/xbox/nv2a/nv2a_regs.h:870` |
| Colour surface format values (9 of them: `LE_X1R5G5B5_Z1R5G5B5` 0x01 … `LE_G8B8` 0x0A) | format-enum | `NV097_SET_SURFACE_FORMAT_COLOR_LE_*` | `hw/xbox/nv2a/nv2a_regs.h:871-880` |
| Zeta (depth) surface format selector | regfield | `NV097_SET_SURFACE_FORMAT_ZETA` (mask 0xF0) | `hw/xbox/nv2a/nv2a_regs.h:881` |
| Zeta format values Z16 / Z24S8 | format-enum | `NV097_SET_SURFACE_FORMAT_ZETA_Z16` = 1, `_Z24S8` = 2 | `hw/xbox/nv2a/nv2a_regs.h:882`, `:883` |
| Surface memory layout selector | regfield | `NV097_SET_SURFACE_FORMAT_TYPE` (mask 0xF00) | `hw/xbox/nv2a/nv2a_regs.h:884` |
| Layout values PITCH / SWIZZLE | format-enum | `NV097_SET_SURFACE_FORMAT_TYPE_PITCH` = 1, `_SWIZZLE` = 2 | `hw/xbox/nv2a/nv2a_regs.h:885`, `:886` |
| Anti-aliasing mode selector | regfield | `NV097_SET_SURFACE_FORMAT_ANTI_ALIASING` (mask 0xF000) | `hw/xbox/nv2a/nv2a_regs.h:887` |
| AA mode values (CENTER_1 / CENTER_CORNER_2 / SQUARE_OFFSET_4) | format-enum | `NV097_SET_SURFACE_FORMAT_ANTI_ALIASING_*` = 0,1,2 | `hw/xbox/nv2a/nv2a_regs.h:888-890` |
| Swizzled surface log2 dimensions | regfield | `NV097_SET_SURFACE_FORMAT_WIDTH`, `_HEIGHT` | `hw/xbox/nv2a/nv2a_regs.h:891`, `:892` |
| Surface pitch word | method | `NV097_SET_SURFACE_PITCH` (0x20C) | `hw/xbox/nv2a/nv2a_regs.h:893` |
| — colour / zeta pitch halves | regfield | `NV097_SET_SURFACE_PITCH_COLOR`, `_ZETA` | `hw/xbox/nv2a/nv2a_regs.h:894`, `:895` |
| Colour surface base offset | method | `NV097_SET_SURFACE_COLOR_OFFSET` (0x210) | `hw/xbox/nv2a/nv2a_regs.h:896` |
| Zeta surface base offset | method | `NV097_SET_SURFACE_ZETA_OFFSET` (0x214) | `hw/xbox/nv2a/nv2a_regs.h:897` |
| Surface clear trigger | method | `NV097_CLEAR_SURFACE` (0x1D94) | `hw/xbox/nv2a/nv2a_regs.h:1278` |
| — Z / stencil / RGBA clear-enable bits | state-bit | `NV097_CLEAR_SURFACE_Z`, `_STENCIL`, `_COLOR`, `_R/_G/_B/_A` | `hw/xbox/nv2a/nv2a_regs.h:1279-1285` |
| Clear rectangle registers | regfield | `NV_PGRAPH_CLEARRECTX` / `Y` + `_XMIN/_XMAX/_YMIN/_YMAX` | `hw/xbox/nv2a/nv2a_regs.h:407-412` |
| Clear colour value | regfield | `NV_PGRAPH_COLORCLEARVALUE` | `hw/xbox/nv2a/nv2a_regs.h:413` |
| Clear depth/stencil value | regfield | `NV_PGRAPH_ZSTENCILCLEARVALUE` | `hw/xbox/nv2a/nv2a_regs.h:642` |
| Front/back 3D surface index + modulo (flip chain) | regfield | `NV_PGRAPH_SURFACE` + `_READ_3D`, `_WRITE_3D`, `_MODULO_3D` | `hw/xbox/nv2a/nv2a_regs.h:265-268` |
| Depth encoding select (fixed vs float) | state-bit | `NV_PGRAPH_SETUPRASTER_Z_FORMAT` (bit 29) | `hw/xbox/nv2a/nv2a_regs.h:517` |
| Depth encoding select, guest-facing | state-bit | `NV097_SET_CONTROL0_Z_FORMAT` (bit 12) | `hw/xbox/nv2a/nv2a_regs.h:903` |
| Colour write enables (per-channel) | state-bit | `NV_PGRAPH_CONTROL_0_{ALPHA,RED,GREEN,BLUE}_WRITE_ENABLE` | `hw/xbox/nv2a/nv2a_regs.h:445-448` |
| Depth / stencil write enables | state-bit | `NV_PGRAPH_CONTROL_0_ZWRITEENABLE`, `_STENCIL_WRITE_ENABLE` | `hw/xbox/nv2a/nv2a_regs.h:443`, `:444` |
| Z clamp / cull behaviour at near-far | state-bit | `NV097_SET_ZMIN_MAX_CONTROL_ZCLAMP_EN` (+ `_CULL`, `_CLAMP`) | `hw/xbox/nv2a/nv2a_regs.h:1271-1273` |
| Occlusion (zpass) counting enable | method | `NV097_SET_ZPASS_PIXEL_COUNT_ENABLE` (0x17CC) | `hw/xbox/nv2a/nv2a_regs.h:1152` |
| 2D blit surface descriptor class | method | `NV_CONTEXT_SURFACES_2D` (class 0x62) | `hw/xbox/nv2a/nv2a_regs.h:818` |
| Blit → 2D-surface binding | method | `NV09F_SET_CONTEXT_SURFACES` | `hw/xbox/nv2a/nv2a_regs.h:835` |
| **Guest-visible surface shape** (the memcmp'd cache key half) | struct | `SurfaceShape` — `z_format, color_format, zeta_format, log_width, log_height, clip_x, clip_y, clip_width, clip_height, anti_aliasing` | `hw/xbox/nv2a/pgraph/surface.h:25-33` |
| **Per-target pending state** (colour and zeta) | struct | `Surface` — `draw_dirty, buffer_dirty, write_enabled_cache, pitch, offset` | `hw/xbox/nv2a/pgraph/pgraph.h:64-71` |
| Live colour/zeta target state in PGRAPH | state-bit | `PGRAPHState::{dma_color, dma_zeta, surface_color, surface_zeta, surface_type, surface_shape, last_surface_shape}` | `hw/xbox/nv2a/pgraph/pgraph.h:145-149` |
| Bound-surface dimensions echoed back for viewport/clear | struct | `PGRAPHState::surface_binding_dim` (marked `// FIXME: Refactor`) | `hw/xbox/nv2a/pgraph/pgraph.h:151-158` |
| Internal-resolution multiplier | state-bit | `PGRAPHState::surface_scale_factor`, `scale_buf` | `hw/xbox/nv2a/pgraph/pgraph.h:277-278` |
| AA → pixel-count expansion | function | `pgraph_apply_anti_aliasing_factor()` | `hw/xbox/nv2a/pgraph/pgraph.h:446-464` |
| Scale-factor expansion | function | `pgraph_apply_scaling_factor()` | `hw/xbox/nv2a/pgraph/pgraph.h:466-472` |
| Colour-write predicate | function | `pgraph_color_write_enabled()` | `hw/xbox/nv2a/pgraph/pgraph.h:430-437` |
| Zeta-write predicate | function | `pgraph_zeta_write_enabled()` | `hw/xbox/nv2a/pgraph/pgraph.h:439-444` |
| GL host surface descriptor | struct | `SurfaceBinding` (GL) | `hw/xbox/nv2a/pgraph/gl/renderer.h:42-68` |
| GL host format table entry | struct | `SurfaceFormatInfo` (GL): `bytes_per_pixel, gl_internal_format, gl_format, gl_type, gl_attachment` | `hw/xbox/nv2a/pgraph/gl/constants.h:332-338` |
| GL colour surface format map | format-enum table | `kelvin_surface_color_format_gl_map[]` | `hw/xbox/nv2a/pgraph/gl/constants.h:340-355` |
| GL zeta format maps (float / fixed) | format-enum table | `kelvin_surface_zeta_float_format_gl_map[]`, `kelvin_surface_zeta_fixed_format_gl_map[]` | `hw/xbox/nv2a/pgraph/gl/constants.h:357-366`, `:368-373` |
| VK host surface descriptor | struct | `SurfaceBinding` (VK) | `hw/xbox/nv2a/pgraph/vk/renderer.h:276-321` |
| VK guest bpp table entry | struct | `BasicSurfaceFormatInfo` | `hw/xbox/nv2a/pgraph/vk/constants.h:321-323` |
| VK host format table entry | struct | `SurfaceFormatInfo` (VK): `host_bytes_per_pixel, vk_format, usage, aspect` | `hw/xbox/nv2a/pgraph/vk/constants.h:325-330` |
| VK colour surface format maps | format-enum table | `kelvin_surface_color_format_map[]`, `kelvin_surface_color_format_vk_map[]` | `hw/xbox/nv2a/pgraph/vk/constants.h:332-339`, `:341-388` |
| VK zeta format entries | format-enum table | `kelvin_surface_zeta_format_map[]`, `zeta_d16`, `zeta_d32_sfloat_s8_uint`, `zeta_d24_unorm_s8_uint` | `hw/xbox/nv2a/pgraph/vk/constants.h:390-393`, `:397-416` |
| VK per-device zeta map (runtime-selected) | state-bit | `PGRAPHVkState::kelvin_surface_zeta_vk_map[3]` | `hw/xbox/nv2a/pgraph/vk/renderer.h:1320` |
| Deferred (batched) surface readback record | struct | `DeferredSurfaceDownload` | `hw/xbox/nv2a/pgraph/vk/renderer.h:325-339` |
| VK recycled-image pool entry | struct | `SurfaceImageConfig`, `PooledSurfaceImage` | `hw/xbox/nv2a/pgraph/vk/renderer.h:709-722` |

Note on the colour format enum: nine values are defined in `nv2a_regs.h:871-880`, but only
six ever reach a host format — `LE_X1R5G5B5_Z1R5G5B5`, `LE_R5G6B5`, `LE_X8R8G8B8_Z8R8G8B8`,
`LE_A8R8G8B8`, `LE_B8`, `LE_G8B8` (`gl/constants.h:340-355`, `vk/constants.h:332-339`).
The `_O*` ("overwrite alpha") variants 0x02/0x05/0x07 and the `_Z1A7R8G8B8`/`_O1A7R8G8B8`
pair 0x06/0x07 are absent from both host tables (VERIFIED by the sparse designated
initialisers in both tables), i.e. they land on a zero entry.

---

## Sites

### Method decode / PGRAPH-side state (`pgraph/pgraph.c`)

| concept | file:line | role | notes |
|---|---|---|---|
| `SET_SURFACE_CLIP_HORIZONTAL` handler | `hw/xbox/nv2a/pgraph/pgraph.c:2026-2034` | DISPATCH / WRITE | calls `surface_update(d,false,true,true)` first, then writes `surface_shape.clip_x/clip_width` |
| `SET_SURFACE_CLIP_VERTICAL` handler | `hw/xbox/nv2a/pgraph/pgraph.c:2036-2044` | DISPATCH / WRITE | same pattern for `clip_y/clip_height` |
| `SET_SURFACE_FORMAT` handler | `hw/xbox/nv2a/pgraph/pgraph.c:2046-2073` | DISPATCH / WRITE | writes `color_format`, `zeta_format`, `anti_aliasing`, `log_width`, `log_height`; bumps `shader_state_gen`/`non_dynamic_reg_gen`/`any_reg_gen` only when `zeta_format` changed (`:2055-2059`); sets both `buffer_dirty` flags when `surface_type` changed (`:2067-2072`) |
| `SET_SURFACE_PITCH` handler | `hw/xbox/nv2a/pgraph/pgraph.c:2075-2086` | WRITE | `buffer_dirty |=` on pitch change, colour and zeta independently |
| `SET_SURFACE_COLOR_OFFSET` handler | `hw/xbox/nv2a/pgraph/pgraph.c:2088-2093` | WRITE | `buffer_dirty |=` on offset change |
| `SET_SURFACE_ZETA_OFFSET` handler | `hw/xbox/nv2a/pgraph/pgraph.c:2095-2100` | WRITE | same |
| `SET_CONTEXT_DMA_COLOR` | `hw/xbox/nv2a/pgraph/pgraph.c:1989-1996` | WRITE | flushes via `surface_update` then forces `surface_color.buffer_dirty = true` |
| `SET_CONTEXT_DMA_ZETA` | `hw/xbox/nv2a/pgraph/pgraph.c:1998-2002` | WRITE | forces `surface_zeta.buffer_dirty = true` but does **not** call `surface_update` — asymmetric with the colour case above |
| `SET_CONTROL0` (z_format, stencil write enable, z perspective) | `hw/xbox/nv2a/pgraph/pgraph.c:2124-2143` | DISPATCH / WRITE | `surface_update` then `NV_PGRAPH_SETUPRASTER_Z_FORMAT` (`:2134-2136`) |
| `SET_COLOR_MASK` | `hw/xbox/nv2a/pgraph/pgraph.c:2485-2501` | WRITE | latches `surface_color.write_enabled_cache |= pgraph_color_write_enabled(pg)` **before** applying the new mask (`:2487`) |
| `SET_DEPTH_MASK` | `hw/xbox/nv2a/pgraph/pgraph.c:2503-2509` | WRITE | same pattern for `surface_zeta.write_enabled_cache` (`:2505`) |
| `CLEAR_SURFACE` | `hw/xbox/nv2a/pgraph/pgraph.c:4029-4032` | DISPATCH | thin forward to `renderer->ops.clear_surface` |
| `SET_ZSTENCIL_CLEAR_VALUE` / `SET_COLOR_CLEAR_VALUE` | `hw/xbox/nv2a/pgraph/pgraph.c:4018-4027` | WRITE | into `NV_PGRAPH_ZSTENCILCLEARVALUE` / `NV_PGRAPH_COLORCLEARVALUE` |
| `SET_CLEAR_RECT_HORIZONTAL` / `_VERTICAL` | `hw/xbox/nv2a/pgraph/pgraph.c:4034-4042` | WRITE | into `NV_PGRAPH_CLEARRECTX/Y` |
| `pgraph_get_clear_color()` | `hw/xbox/nv2a/pgraph/pgraph.c:4199-4259` | CONVERT | unpacks `NV_PGRAPH_COLORCLEARVALUE` per `surface_shape.color_format` into float RGBA |
| `pgraph_get_clear_depth_stencil_value()` | `hw/xbox/nv2a/pgraph/pgraph.c:4261-4296` | CONVERT | Z16/Z24S8 → float depth + int stencil, honouring `surface_shape.z_format` (f16/f24 via `convert_f16_to_float`/`convert_f24_to_float`) |
| `SET_FLIP_READ/WRITE/MODULO`, `FLIP_INCREMENT_WRITE` | `hw/xbox/nv2a/pgraph/pgraph.c:1881-1927` | WRITE | maintain `NV_PGRAPH_SURFACE_{READ,WRITE,MODULO}_3D`; `FLIP_INCREMENT_WRITE` bumps `pg->frame_time` (`:1915`) — the surface eviction clock |
| `NV_PGRAPH_INCREMENT` MMIO → `READ_3D` | `hw/xbox/nv2a/pgraph/pgraph.c:913-923` | WRITE | modulo-increment of the read index |
| Fast-path method table entries for `SET_FLIP_*` | `hw/xbox/nv2a/pgraph/pgraph.c:476-481` | TABLE-ENTRY | `MF_MASKED(NV_PGRAPH_SURFACE, 1..3)`, masks in `mask_lut` at `:281-285` |
| `WAIT_FOR_IDLE`, `FLIP_STALL`, `BACK_END_WRITE_SEMAPHORE_RELEASE` | `hw/xbox/nv2a/pgraph/pgraph.c:1876-1879`, `:1929-1934`, `:3971-3973` | DISPATCH | each forces `surface_update(d, false, true, true)` (download side) |
| `ContextSurfaces2DState` decode (2D blit surfaces) | `hw/xbox/nv2a/pgraph/pgraph.c:1714-1740` | WRITE | colour format, source/dest pitch, source/dest offset, source/dest DMA objects |
| `nv2a_get_framebuffer_surface` / `nv2a_release_framebuffer_surface` | `hw/xbox/nv2a/pgraph/pgraph.c:1273-1298` | DISPATCH | UI-side entry; `assert(!pg->framebuffer_in_use)` at `:1280` |
| `nv2a_set/get_surface_scale_factor` | `hw/xbox/nv2a/pgraph/pgraph.c:1300-1327` | DISPATCH | drops the BQL around the renderer call |
| `SET_ZMIN_MAX_CONTROL` | `hw/xbox/nv2a/pgraph/pgraph.c:3992-4010` | WRITE | only `ZCLAMP_EN` is decoded, into `NV_PGRAPH_ZCOMPRESSOCCLUDE`; `CULL_NEAR_FAR_EN` and `CULL_IGNORE_W` are not read |
| `SET_ZPASS_PIXEL_COUNT_ENABLE` | `hw/xbox/nv2a/pgraph/pgraph.c:3589-3592` | WRITE | into `pg->zpass_pixel_count_enable` |
| `pgraph_write_zpass_pixel_cnt_report` | `hw/xbox/nv2a/pgraph/pgraph.c:4298+` | WRITE | writes the report into guest memory via `dma_report` |

### GL backend

| concept | file:line | role | notes |
|---|---|---|---|
| `pgraph_gl_surface_update` (entry point) | `hw/xbox/nv2a/pgraph/gl/surface.c:2938-3018` | DISPATCH | refreshes `surface_shape.z_format` from `NV_PGRAPH_SETUPRASTER` (`:2944-2946`); upload vs download branch; `pg->draw_time++` on upload (`:2988`); final colour/zeta dimension `assert` (`:3012-3015`); `surface_evict_old()` (`:3017`) |
| `update_surface_part` | `hw/xbox/nv2a/pgraph/gl/surface.c:2702-2911` | READ / WRITE | the whole bind/create/evict decision |
| `memory_region_test_and_clear_dirty(..., DIRTY_MEMORY_NV2A)` | `hw/xbox/nv2a/pgraph/gl/surface.c:2712-2714` | READ | **page-granular test-and-clear over `[entry.vram_addr, +entry.size)`**; guarded `!tcg_enabled()` |
| `populate_surface_binding_entry_sized` | `hw/xbox/nv2a/pgraph/gl/surface.c:2603-2673` | TABLE-ENTRY / CONVERT | picks `kelvin_surface_color_format_gl_map` or the float/fixed zeta map (`:2621`, `:2633-2636`); computes `vram_addr = dma.address + surface->offset` (`:2660`) and `size = height * MAX(pitch, width*bpp)` (`:2664`) |
| `populate_surface_binding_entry` | `hw/xbox/nv2a/pgraph/gl/surface.c:2675-2700` | CONVERT | dimensions from clip rect or log2 shape, AA-expanded, `clip_x/clip_y` added for pitch (non-swizzle) surfaces |
| `surface_get_dimensions` | `hw/xbox/nv2a/pgraph/gl/surface.c:3021-3032` | CONVERT | swizzle → `1<<log_width/height`, else clip width/height |
| `check_surface_compatibility` | `hw/xbox/nv2a/pgraph/gl/surface.c:1640-1657` | READ | colour-ness, `gl_attachment`, `gl_internal_format`, `pitch` must match; strict mode compares dims exactly |
| `surface_put` / `pgraph_gl_surface_get` / `_get_within` | `hw/xbox/nv2a/pgraph/gl/surface.c:1546-1596` | WRITE / READ | **key = exact `vram_addr`**; linear `QTAILQ` scan |
| `pgraph_gl_surface_invalidate` | `hw/xbox/nv2a/pgraph/gl/surface.c:1598-1620` | WRITE | deletes the GL texture and frees the node |
| `surface_evict_old` | `hw/xbox/nv2a/pgraph/gl/surface.c:1622-1638` | WRITE | age limit 5 `frame_time` ticks (`:1627`) |
| `invalidate_overlapping_surfaces` | `hw/xbox/nv2a/pgraph/gl/surface.c:1529-1544` | WRITE | downloads then invalidates every overlapping surface |
| `surface_access_callback` (guest CPU touches surface VRAM) | `hw/xbox/nv2a/pgraph/gl/surface.c:1456-1499` | READ / WRITE | TCG-only; sets `download_pending` on any access to a `draw_dirty` surface, `upload_pending` on writes; blocks the vCPU on `downloads_complete` |
| `register/unregister_cpu_access_callback` | `hw/xbox/nv2a/pgraph/gl/surface.c:1501-1520` | WRITE | `tcg_enabled()`-gated; skipped for zero-size surfaces |
| `surface_download` | `hw/xbox/nv2a/pgraph/gl/surface.c:2336-2359` | CONVERT | readback into `d->vram_ptr + vram_addr`, then `memory_region_set_client_dirty` for `DIRTY_MEMORY_VGA` and `DIRTY_MEMORY_NV2A_TEX` (`:2350-2355`); clears `download_pending`, `draw_dirty` |
| `surface_download_to_buffer` | `hw/xbox/nv2a/pgraph/gl/surface.c:2133-2334` | CONVERT | `glo_readpixels`, optional downscale via `surface_copy_shrink_row` (`:2295-2306`), optional `swizzle_rect` (`:2308-2312`) |
| `surface_copy_shrink_row` | `hw/xbox/nv2a/pgraph/gl/surface.c:1741-1781` | CONVERT | CPU downscale for `surface_scale_factor > 1` |
| `pgraph_gl_upload_surface_data` | `hw/xbox/nv2a/pgraph/gl/surface.c:2440-2571` | CONVERT | `unswizzle_rect` (`:2481`), pitch→tight repack (`:2494-2505`), `surface_copy_expand` upscale (`:2510-2519`), `glTexImage2D` |
| `surface_copy_expand` / `_row` | `hw/xbox/nv2a/pgraph/gl/surface.c:2389-2438` | CONVERT | integer upscale on upload |
| `pgraph_gl_set_surface_dirty` | `hw/xbox/nv2a/pgraph/gl/surface.c:950-976` | WRITE | ANDs the requested dirty flags with the write-enable predicates; sets `draw_dirty`, refreshes `frame_time`, clears `cleared` |
| `framebuffer_dirty` | `hw/xbox/nv2a/pgraph/gl/surface.c:939-948` | READ | `memcmp(surface_shape, last_surface_shape)` — the whole struct including `z_format` |
| `pgraph_gl_check_surface_to_texture_compatibility` | `hw/xbox/nv2a/pgraph/gl/surface.c:1377-1446` | READ | the aliasing rule set; see Coupling points |
| `surface_to_texture_can_fastpath` | `hw/xbox/nv2a/pgraph/gl/surface.c:1073-1124` | READ | a *second*, near-duplicate rule set with fewer preconditions |
| `pgraph_gl_render_surface_to_texture` | `hw/xbox/nv2a/pgraph/gl/surface.c:1327-1375` | CONVERT | fast path (`render_surface_to`) or `render_surface_to_texture_slow` |
| `render_surface_to_texture_slow` | `hw/xbox/nv2a/pgraph/gl/surface.c:1243-1321` | CONVERT | readback to CPU + `glTexImage2D` in the texture's format |
| `pgraph_gl_process_pending_downloads` | `hw/xbox/nv2a/pgraph/gl/surface.c:2361-2373` | DISPATCH | drains `download_pending` across all surfaces |
| `pgraph_gl_download_dirty_surfaces` | `hw/xbox/nv2a/pgraph/gl/surface.c:2375-2387` | DISPATCH | drains `draw_dirty` across all surfaces |
| `flush_surfaces` / `pgraph_gl_surface_flush` | `hw/xbox/nv2a/pgraph/gl/surface.c:3057-3076`, `:3104-3118` | WRITE | zeroes `last_surface_shape`, unbinds, invalidates **without** downloading (`:3071-3073`, FIXME) |
| `pgraph_gl_init_surfaces` / `_finalize_surfaces` | `hw/xbox/nv2a/pgraph/gl/surface.c:3034-3055`, `:3078-3102` | WRITE | FBO + surface list lifecycle |
| `pgraph_gl_set_surface_scale_factor` | `hw/xbox/nv2a/pgraph/gl/surface.c:892-925` | DISPATCH | halts PFIFO, forces a dirty-surface download and a flush, resumes |
| `pgraph_gl_clear_surface` | `hw/xbox/nv2a/pgraph/gl/draw.c:47-152` | DISPATCH / WRITE | sets `pg->clearing` (`:53`), computes `full_clear` against `surface_binding_dim` (`:119-121`), sets `binding->cleared` (`:144-149`) |
| `pgraph_gl_draw_begin` / `_draw_end` | `hw/xbox/nv2a/pgraph/gl/draw.c:154-372`, `:374-427` | DISPATCH | `surface_update(d,true,true,depth_test||stencil_test)` (`:172`); `assert(color_binding || zeta_binding)` (`:178`); `draw_time++` and `set_surface_dirty` at end (`:415-425`) |
| GL viewport from `surface_binding_dim` | `hw/xbox/nv2a/pgraph/gl/draw.c:331-332` | READ | render-target dims feed the viewport |
| `pgraph_gl_image_blit` | `hw/xbox/nv2a/pgraph/gl/blit.c:72-223` | CONVERT | CPU memmove/blend blit; downloads a dirty source surface (`:118-121`); on a full-cover dest surface *discards* pending download and `draw_dirty` (`:159-163`); marks VGA + NV2A_TEX dirty (`:219-222`) |
| GL display path | `hw/xbox/nv2a/pgraph/gl/display.c:575-632` | READ / CONVERT | finds the scanout surface with `pgraph_gl_surface_get_within`, force-uploads under KVM (`:600`), renders |
| `pgraph_gl_get_framebuffer_surface` | `hw/xbox/nv2a/pgraph/gl/display.c:634-675` | READ | asserts colour attachment and a known GL format (`:659-665`) |
| GL texture ⇄ surface aliasing | `hw/xbox/nv2a/pgraph/gl/texture.c:763-840`, `:912-923` | READ / CONVERT | surface lookup by texture VRAM offset, compat check, overlap writeback, render-to-texture |
| `check_texture_dirty` (page-granular) | `hw/xbox/nv2a/pgraph/gl/texture.c:512-519` | READ | `memory_region_test_and_clear_dirty(..., DIRTY_MEMORY_NV2A_TEX)` over a page-aligned range |
| `pgraph_gl_mark_textures_possibly_dirty` | `hw/xbox/nv2a/pgraph/gl/texture.c:492-510` | WRITE | page-aligns the range, then marks every overlapping cache node |
| Vertex RAM dirty consume (same bit as surfaces) | `hw/xbox/nv2a/pgraph/gl/vertex.c:55-71` | READ | `memory_region_test_and_clear_dirty(..., DIRTY_MEMORY_NV2A)` over a page-aligned range |
| `pgraph_gl_process_pending` | `hw/xbox/nv2a/pgraph/gl/renderer.c:249-279` | DISPATCH | pumps `downloads_pending` / `download_dirty_surfaces_pending` from the PFIFO thread |
| GL renderer op table | `hw/xbox/nv2a/pgraph/gl/renderer.c:323-339` | TABLE-ENTRY | `clear_surface`, `image_blit`, `surface_update`, `set_surface_scale_factor`, `get_framebuffer_surface` |

### Vulkan backend

| concept | file:line | role | notes |
|---|---|---|---|
| `pgraph_vk_surface_update` | `hw/xbox/nv2a/pgraph/vk/surface.c:3018-3119` | DISPATCH | same skeleton as GL, plus `flush_reorder_window`/`flush_draw_queue` on the download branch (`:3061-3062`) and `download_surface_complete_deferred` (`:3073`) before uploads; `expire_old_surfaces` + `prune_invalid_surfaces` (`:3113-3114`) |
| `update_surface_part` | `hw/xbox/nv2a/pgraph/vk/surface.c:2756-3015` | READ / WRITE | shelving/unshelving variant of the GL logic |
| Inline `DIRTY_MEMORY_NV2A` test-and-clear | `hw/xbox/nv2a/pgraph/vk/surface.c:2774-2793` | READ | open-coded page loop over `ram_list.dirty_memory[DIRTY_MEMORY_NV2A]` using `bitmap_test_and_clear_atomic`; **does not** go through `memory_region_test_and_clear_dirty` |
| `populate_surface_binding_target_sized` | `hw/xbox/nv2a/pgraph/vk/surface.c:2658-2728` | TABLE-ENTRY / CONVERT | picks `kelvin_surface_color_format_map` + `_vk_map`, or `r->kelvin_surface_zeta_vk_map` (`:2677-2691`) |
| `get_surface_dimensions` | `hw/xbox/nv2a/pgraph/vk/surface.c:100-111` | CONVERT | byte-for-byte duplicate of the GL version |
| `framebuffer_dirty` | `hw/xbox/nv2a/pgraph/vk/surface.c:114-123` | READ | duplicate of the GL version |
| `check_surface_compatibility` | `hw/xbox/nv2a/pgraph/vk/surface.c:2155-2171` | READ | colour-ness, `host_fmt.vk_format`, `pitch`; **no attachment/aspect field to compare** unlike GL |
| `surface_put` / `pgraph_vk_surface_get` | `hw/xbox/nv2a/pgraph/vk/surface.c:1750-1769` | WRITE / READ | **key = exact `vram_addr`**, stored in a `GHashTable` (`surface_addr_map`) |
| `pgraph_vk_surface_get_within` | `hw/xbox/nv2a/pgraph/vk/surface.c:1771-1784` | READ | linear scan for containment (display + blit use this) |
| `bind_surface` / `unbind_surface` | `hw/xbox/nv2a/pgraph/vk/surface.c:1569-1603` | WRITE | sets `framebuffer_dirty`, `pipeline_state_dirty` |
| `invalidate_surface` | `hw/xbox/nv2a/pgraph/vk/surface.c:1605-1634` | WRITE | moves the node to `invalid_surfaces` keeping its `VkImage`; records `invalidation_frame` |
| `shelve_surface` / `get_shelved_surface` | `hw/xbox/nv2a/pgraph/vk/surface.c:1645-1663`, `:1671-1688` | WRITE / READ | shelf key = `vram_addr` **and** `vk_format`, `color`, `width`, `height`, `pitch` |
| `invalidate_overlapping_surfaces` | `hw/xbox/nv2a/pgraph/vk/surface.c:1697-1748` | WRITE | *lazy*: overlapping active surfaces are invalidated **without** downloading (`:1716-1726`) |
| `expire_old_surfaces` | `hw/xbox/nv2a/pgraph/vk/surface.c:2106-2153` | WRITE | age limit `max_surface_frame_time_delta` = 5 (`:45`); shelf capped at `max_shelved_surfaces` = 20 (`:2104`) |
| `prune_invalid_surfaces` | `hw/xbox/nv2a/pgraph/vk/surface.c:2085-2102` | WRITE | keeps `num_invalid_surfaces_to_keep` = 10 (`:44`); skips in-flight images |
| `surface_image_pool_acquire` / `_release` / `_drain` | `hw/xbox/nv2a/pgraph/vk/surface.c:1837-1899` | READ / WRITE | recycles `VkImage`s keyed on `{format,width,height,usage}` (`:1828-1835`) |
| `create_surface_image` | `hw/xbox/nv2a/pgraph/vk/surface.c:1901-2001` | WRITE | pool hit or fresh `vmaCreateImage`; transitions from `UNDEFINED` to GENERAL (colour) / DEPTH_STENCIL_ATTACHMENT (zeta) (`:1991-1995`) |
| `migrate_surface_image` | `hw/xbox/nv2a/pgraph/vk/surface.c:2003-2020` | WRITE | hands image + view + layout from one binding to another |
| `download_surface` | `hw/xbox/nv2a/pgraph/vk/surface.c:1157-1188` | CONVERT | generation-guarded (`:1168-1171`); marks VGA + NV2A_TEX dirty (`:1177-1182`) |
| `download_surface_deferred` | `hw/xbox/nv2a/pgraph/vk/surface.c:1195-1224` | CONVERT | batched record → fall back to sync |
| `download_surface_record_deferred` | `hw/xbox/nv2a/pgraph/vk/surface.c:216-556` | CONVERT | records the copy (and depth/stencil compute pack) into the non-draw CB; supports partial row ranges (`:233-241`) |
| `pgraph_vk_complete_staged_downloads` | `hw/xbox/nv2a/pgraph/vk/surface.c:571-615` | CONVERT | CPU `memcpy_image` / `swizzle_rect` out of staging, then per-surface flag cleanup (`:596-609`) |
| `pgraph_vk_download_surface_complete_deferred` | `hw/xbox/nv2a/pgraph/vk/surface.c:617-677` | DISPATCH | fence wait / finish then completion |
| `pgraph_vk_download_surfaces_in_range_if_dirty` | `hw/xbox/nv2a/pgraph/vk/surface.c:153-213` | READ / CONVERT | scans active, **shelved**, and **invalid** lists for overlap |
| `download_surface_to_buffer` | `hw/xbox/nv2a/pgraph/vk/surface.c:679-1155` | CONVERT | compute-based Z24S8 pack, compute swizzle, CPU `memcpy_image`/`swizzle_rect` (`:1140-1154`) |
| `pgraph_vk_upload_surface_data` | `hw/xbox/nv2a/pgraph/vk/surface.c:2181-2630` | CONVERT | CPU `unswizzle_rect` (`:2242-2246`) or compute unswizzle; staging buffer + `vkCmdCopyBufferToImage` regions (`:2310-2329`) |
| `pgraph_vk_prerecord_display_download` | `hw/xbox/nv2a/pgraph/vk/surface.c:1226-1282` | CONVERT | piggybacks all dirty-surface downloads onto the flip-stall submit |
| `pgraph_vk_wait_for_surface_download` | `hw/xbox/nv2a/pgraph/vk/surface.c:1284-1309` | DISPATCH | Android forces a download when the VK display is not using external memory (`:1289-1297`) |
| `surface_access_callback` | `hw/xbox/nv2a/pgraph/vk/surface.c:1467-1546` | READ / WRITE | TCG-only; computes a **partial row range** from the touched byte range (`:1493-1527`) and coalesces with an existing pending range |
| `pgraph_vk_set_surface_dirty` | `hw/xbox/nv2a/pgraph/vk/draw.c:5445-5479` | WRITE | as GL, plus `r->surface_draw_gen++` and per-binding `draw_generation++` |
| `pgraph_vk_clear_surface` | `hw/xbox/nv2a/pgraph/vk/draw.c:5140-5384` | DISPATCH / WRITE | `pg->clearing = true` (`:5165`), `surface_update` (`:5169`), inline `vkCmdClearAttachments` fast path (`:5206-5289`), pipeline-draw fallback for partial-channel clears (`:5328-5349`) |
| VK draw begin | `hw/xbox/nv2a/pgraph/vk/draw.c:338` | DISPATCH | `pgraph_vk_surface_update(d, true, true, depth_test || stencil_test)` |
| `pgraph_vk_image_blit` | `hw/xbox/nv2a/pgraph/vk/blit.c:155-329` | CONVERT | NEON-accelerated CPU blit; same discard-on-full-cover rule (`:256-261`); marks VGA + NV2A_TEX **and NV2A** dirty (`:317-328`) |
| `pgraph_vk_transition_image_layout` | `hw/xbox/nv2a/pgraph/vk/image.c:35-316` | DISPATCH | hand-enumerated layout transition matrix; unlisted pairs hit `assert(!"unsupported layout transition!")` (`:311`) |
| Depth/stencil pack/unpack compute shaders | `hw/xbox/nv2a/pgraph/vk/surface-compute.c:28-115` | CONVERT | GLSL for D24S8 ⇄ Z24S8 and D32S8 ⇄ Z24S8 |
| Swizzle/unswizzle compute shaders | `hw/xbox/nv2a/pgraph/vk/surface-compute.c:139-166` | CONVERT | 32-bit-only address swizzle |
| Direct depth pack (samples the image) | `hw/xbox/nv2a/pgraph/vk/surface-compute.c:120-137` | CONVERT | used by the zeta→texture path |
| `pgraph_vk_pack_depth_stencil` / `_unpack_depth_stencil` / `_pack_depth_stencil_direct` / `_compute_swizzle` | `hw/xbox/nv2a/pgraph/vk/surface-compute.c:446`, `:526`, `:600`, `:708` | CONVERT | dispatch wrappers |
| VK display path | `hw/xbox/nv2a/pgraph/vk/display.c:1694-1744` | READ | `pgraph_vk_surface_get_within(d, pcrtc.start + line_offset)` (`:1711`) |
| `render_display` | `hw/xbox/nv2a/pgraph/vk/display.c:1461-1634` | CONVERT | force-uploads under KVM (`:1488`), transitions the surface image for sampling (`:1513`, `:1560`) |
| VK texture ⇄ surface aliasing | `hw/xbox/nv2a/pgraph/vk/texture.c:1337-1427` | READ / CONVERT | surface lookup, compat check, shelf fallback (`:1389-1402`), range download with a memoised skip (`:1404-1427`) |
| `check_surface_to_texture_compatiblity` (VK) | `hw/xbox/nv2a/pgraph/vk/texture.c:1102-1119` | READ | dims + `!cubemap` + `levels == 1`; zeta always compatible; colour compares **byte size only** |
| `copy_surface_to_texture` / `copy_zeta_surface_to_texture` | `hw/xbox/nv2a/pgraph/vk/texture.c:1006-1082`, `:707-899` | CONVERT | `vkCmdCopyImage` / compute depth pack |
| `bind_surface_as_texture` / `bind_zeta_surface_as_texture` | `hw/xbox/nv2a/pgraph/vk/texture.c:905-948`, `:955-1003` | WRITE | zero-copy direct sampling of the surface image |
| `check_texture_dirty` (VK) | `hw/xbox/nv2a/pgraph/vk/texture.c:475-482` | READ | identical page-granular `DIRTY_MEMORY_NV2A_TEX` test-and-clear |
| `pgraph_vk_process_pending` | `hw/xbox/nv2a/pgraph/vk/renderer.c:291-323` | DISPATCH | batches downloads/sync/flush into a single render-thread command |
| VK renderer op table | `hw/xbox/nv2a/pgraph/vk/renderer.c:1686-1702` | TABLE-ENTRY | |
| Null renderer surface ops (all empty) | `hw/xbox/nv2a/pgraph/null/renderer.c:60-62`, `:109-112`, `:126-139` | TABLE-ENTRY | `clear_surface` and `surface_update` are no-ops |

### VRAM dirty-logging setup

| concept | file:line | role | notes |
|---|---|---|---|
| Enable NV2A + NV2A_TEX dirty logging on VRAM; seed everything dirty | `hw/xbox/nv2a/nv2a.c:469-471` | WRITE | `memory_region_set_log(...)` ×2 then `memory_region_set_dirty(vram, 0, size)` |
| Dirty client numbering | `include/exec/ramlist.h:11-16` | TABLE-ENTRY | `VGA=0`, `NV2A=3`, `NV2A_TEX=4` |
| `memory_region_test_and_clear_dirty` | `system/memory.c:2359-2371` | READ | syncs the MR bitmap first, then delegates |
| `physical_memory_test_and_clear_dirty` | `system/physmem.c:1236-1282` | READ | **page-granular**: `end = TARGET_PAGE_ALIGN(start+length) >> TARGET_PAGE_BITS`, `start_page = start >> TARGET_PAGE_BITS`; clears every bit in that page span |
| `TARGET_PAGE_BITS` for i386 | `target/i386/cpu-param.h:23` | TABLE-ENTRY | 12 → 4 KiB pages |

---

## Surface lifecycle

Nobody has written this down, so here it is end to end. The two backends implement the
same skeleton; where they differ I say so. Function names are the real ones.

### 0. The clock

Two counters drive everything: `pg->frame_time`, bumped once per `FLIP_INCREMENT_WRITE`
(`hw/xbox/nv2a/pgraph/pgraph.c:1915`), and `pg->draw_time`, bumped on every upload-side
`surface_update` (`gl/surface.c:2988`, `vk/surface.c:3076`) and at the end of every draw
(`gl/draw.c:415`). `frame_time` is the eviction clock; `draw_time` is the
surface-newer-than-texture clock.

### 1. Guest describes a target (no host object yet)

The guest writes `NV097_SET_SURFACE_FORMAT`, `_PITCH`, `_COLOR_OFFSET`, `_ZETA_OFFSET`,
`_CLIP_HORIZONTAL/_VERTICAL`, `SET_CONTEXT_DMA_COLOR/ZETA`. Each handler
(`pgraph.c:1989-2100`) does two things: it first calls
`renderer->ops.surface_update(d, false, true, true)` to flush whatever is currently bound
(this is the "get any straggling draws in before the surface's changed" comment at
`pgraph.c:1991`), then updates `pg->surface_shape` / `pg->surface_color` /
`pg->surface_zeta` and raises `buffer_dirty` if the new value differs.

At this point nothing host-side exists. `SurfaceShape` (`surface.h:25-33`) holds the guest
description; `Surface` (`pgraph.h:64-71`) holds pitch, offset and the three dirty bits.

### 2. Binding — `surface_update(upload=true)`

Triggered from draw begin (`gl/draw.c:172`, `vk/draw.c:338`) and clear
(`gl/draw.c:94`, `vk/draw.c:5169`).

`pgraph_gl_surface_update` / `pgraph_vk_surface_update`
(`gl/surface.c:2938`, `vk/surface.c:3018`):

1. Refresh `surface_shape.z_format` from `NV_PGRAPH_SETUPRASTER_Z_FORMAT`
   (`gl/surface.c:2944-2946`).
2. Mask the requested writes by the write-enable predicates unless clearing
   (`gl/surface.c:2948-2950`).
3. `framebuffer_dirty()` — `memcmp` of `surface_shape` against `last_surface_shape`
   (`gl/surface.c:939-948`). On a change, copy shape forward and set **both**
   `buffer_dirty` flags (`gl/surface.c:2954-2959`).
4. Unbind whichever target has `buffer_dirty`, then call `update_surface_part()` for each
   enabled target (`gl/surface.c:2961-2975`).

`update_surface_part` (`gl/surface.c:2702`, `vk/surface.c:2756`) is the core:

- `populate_surface_binding_entry` (`gl/surface.c:2675`) builds a candidate binding:
  dimensions from `surface_get_dimensions` (swizzle → `1 << log_width/height`, otherwise
  clip width/height — `gl/surface.c:3021-3032`), AA-expanded via
  `pgraph_apply_anti_aliasing_factor`, plus `clip_x`/`clip_y` for non-swizzled surfaces
  (`gl/surface.c:2690-2693`). `populate_surface_binding_entry_sized`
  (`gl/surface.c:2603`) then resolves the host format from the format tables, loads the
  DMA object (`nv_dma_load`, `:2639`) and asserts it, and computes
  `vram_addr = dma.address + surface->offset` (`:2660`) and
  `size = height * MAX(pitch, width * bpp)` (`:2664`). It sets `upload_pending = true`,
  `download_pending = false`, `draw_dirty = false`, `cleared = false`.
- The dirty check: GL uses `memory_region_test_and_clear_dirty(d->vram, entry.vram_addr,
  entry.size, DIRTY_MEMORY_NV2A)` (`gl/surface.c:2712-2714`); VK open-codes the same
  test-and-clear directly on `ram_list.dirty_memory[DIRTY_MEMORY_NV2A]`
  (`vk/surface.c:2774-2793`). Both are skipped under TCG (there the CPU access callback
  does the job instead).
- Rebind decision: GL enters the create/bind block when `upload && (buffer_dirty ||
  mem_dirty)` (`gl/surface.c:2716`); VK additionally enters whenever nothing is currently
  bound (`vk/surface.c:2799-2800`).
- Cache lookup by **exact `vram_addr`** (`pgraph_gl_surface_get`, `gl/surface.c:1567`;
  `pgraph_vk_surface_get`, `vk/surface.c:1765`). A hit is validated by
  `check_surface_compatibility` (`gl/surface.c:1640`, `vk/surface.c:2155`) plus three
  extra rules: the swizzle-vs-linear migration allowance (`gl/surface.c:2760-2774`), a
  colour/zeta non-overlap check when the found surface is larger than the target
  (`gl/surface.c:2776-2785`), and a "zeta must match the bound colour dims" check
  (`gl/surface.c:2787-2790`).
- On a compatible hit: publish dims into `pg->surface_binding_dim`, OR `mem_dirty` into
  `upload_pending`, force `surface_zeta.buffer_dirty` when the colour target rebound
  (`gl/surface.c:2792-2802`).
- On an incompatible hit: GL downloads then invalidates
  (`pgraph_gl_surface_download_if_dirty` + `pgraph_gl_surface_invalidate`,
  `gl/surface.c:2807-2808`). VK instead **shelves**: it records
  `surface->shelved_dirty = surface->draw_dirty` and calls `shelve_surface()` with no
  download (`vk/surface.c:2908-2912`).
- On a miss: GL `glGenTextures` + `glTexImage2D` + `surface_put()`
  (`gl/surface.c:2812-2844`). VK first tries the shelf (`get_shelved_surface`,
  `vk/surface.c:2923`), then the invalid list
  (`get_any_compatible_invalid_surface`, `:2928`), then the image pool inside
  `create_surface_image` (`:2933` → `:1928`), before allocating.
  A shelf hit sets `upload_pending = false; initialized = true` (`vk/surface.c:2948-2949`)
  because the `VkImage` already holds the right pixels.
- `surface_put` (`gl/surface.c:1546`, `vk/surface.c:1750`) asserts the address is not
  already present, invalidates every **overlapping** surface, and registers the CPU access
  callback.
- Finally the surface is attached to the framebuffer (GL `glFramebufferTexture2D`,
  `gl/surface.c:2882`) or recorded as the binding (VK `bind_surface`,
  `vk/surface.c:2986`), and `buffer_dirty` is cleared (`gl/surface.c:2896`).

### 3. Upload (guest VRAM → host image)

Back in `surface_update`, for each live binding, `pgraph_gl_upload_surface_data` /
`pgraph_vk_upload_surface_data` runs if `upload_pending` (`gl/surface.c:2996`,
`vk/surface.c:3086`). GL: optional `unswizzle_rect`, pitch→tight repack,
`surface_copy_expand` upscale, `glTexImage2D` (`gl/surface.c:2479-2557`). VK: CPU
`unswizzle_rect` or compute unswizzle, staging-buffer `memcpy`, then
`vkCmdCopyBufferToImage` with separate depth and stencil regions
(`vk/surface.c:2239-2329`). Both then set `draw_time = pg->draw_time`
(`gl/surface.c:2458`, `vk/surface.c:2213`).

### 4. Marking dirty

Every draw and clear ends with `pgraph_{gl,vk}_set_surface_dirty`
(`gl/surface.c:950`, `vk/draw.c:5445`). It ANDs the caller's request with
`pgraph_color_write_enabled` / `pgraph_zeta_write_enabled`, sets `draw_dirty` on both the
`PGRAPHState::surface_{color,zeta}` record and the bound `SurfaceBinding`, refreshes
`frame_time`, and clears `cleared`. VK additionally increments
`r->surface_draw_gen` and the per-binding `draw_generation`
(`vk/draw.c:5458-5478`).

### 5. Download (host image → guest VRAM)

Four triggers:

1. **Guest CPU touches the range.** Only under TCG: `surface_access_callback`
   (`gl/surface.c:1456`, `vk/surface.c:1467`) is invoked by the memory-access callback
   registered in `register_cpu_access_callback` (`gl/surface.c:1501`). It sets
   `download_pending` on any `draw_dirty` surface overlapping the touched range,
   `upload_pending` on writes, then blocks the vCPU on `r->downloads_complete` while the
   PFIFO thread drains via `process_pending_downloads`
   (`gl/surface.c:2361`, `vk/surface.c:1311`). VK narrows the download to the touched row
   range (`vk/surface.c:1493-1527`).
2. **A texture reads the range.** GL walks the whole surface list and downloads
   overlapping dirty surfaces (`gl/texture.c:826-839`). VK calls
   `pgraph_vk_download_surfaces_in_range_if_dirty` (`vk/surface.c:153`), which also scans
   the shelved and invalid lists, memoised by
   `tex_surf_range_cache` (`vk/texture.c:1404-1427`).
3. **Something else needs VRAM coherent**: `WAIT_FOR_IDLE`, `FLIP_STALL`,
   `BACK_END_WRITE_SEMAPHORE_RELEASE`, blits, and the scale-factor change path all funnel
   through `surface_update(upload=false)`, whose non-upload branch calls
   `update_surface_part(d, false, color)` → download and clear
   `write_enabled_cache` + `draw_dirty` (`gl/surface.c:2899-2910`,
   `vk/surface.c:2999-3014`). Note the non-upload branch runs only when
   `(color_write || write_enabled_cache) && draw_dirty` (`gl/surface.c:2977-2984`) — this
   is what `write_enabled_cache` exists for: it remembers that the target *was* writable
   before a `SET_COLOR_MASK`/`SET_DEPTH_MASK` turned writes off.
4. **Save-state / renderer switch**: `pre_savevm_trigger` raises
   `download_dirty_surfaces_pending` (`gl/renderer.c:286`, `vk/renderer.c:1597`).

The download itself (`surface_download`, `gl/surface.c:2336`; `download_surface`,
`vk/surface.c:1157`) writes straight into `d->vram_ptr + surface->vram_addr`, then marks
the written bytes dirty for `DIRTY_MEMORY_VGA` and `DIRTY_MEMORY_NV2A_TEX`
(`gl/surface.c:2350-2355`, `vk/surface.c:1177-1182`) — deliberately *not*
`DIRTY_MEMORY_NV2A`, so the surface does not immediately re-upload its own readback.
Then `download_pending = false; draw_dirty = false`.

VK adds a deferred pipeline: `download_surface_record_deferred`
(`vk/surface.c:216`) records the copy into the non-draw command buffer and returns; the
CPU-side `memcpy` and flag clearing happen later in
`pgraph_vk_complete_staged_downloads` (`vk/surface.c:571`), driven by
`pgraph_vk_download_surface_complete_deferred` (`vk/surface.c:617`). Up to
`MAX_DEFERRED_DOWNLOADS` = 64 (`vk/renderer.h:323`) are batched behind one fence.
`pgraph_vk_prerecord_display_download` (`vk/surface.c:1226`) piggybacks the whole dirty
set onto the flip-stall submission.

### 6. Aliasing as a texture

In `pgraph_gl_bind_textures` (`gl/texture.c:763`), a surface is looked up by the
texture's VRAM offset. If found and
`pgraph_gl_check_surface_to_texture_compatibility` (`gl/surface.c:1377`) passes, the
surface's `upload_pending` is resolved and the texture is *rendered from* the surface via
`pgraph_gl_render_surface_to_texture` (`gl/surface.c:1327`) whenever
`binding->draw_time < surface->draw_time` (`gl/texture.c:912`). Otherwise the texture
falls back to VRAM, and every overlapping dirty surface is downloaded first
(`gl/texture.c:826-839`).

VK does the same lookup (`vk/texture.c:1340`) but has three outcomes instead of two:
`copy_surface_to_texture` (`vk/texture.c:1006`, a `vkCmdCopyImage`),
`copy_zeta_surface_to_texture` (`vk/texture.c:707`, a compute depth pack), or the
zero-copy `bind_surface_as_texture` / `bind_zeta_surface_as_texture`
(`vk/texture.c:905`, `:955`) which sample the surface image in place. VK will also alias a
**shelved** surface's image if the active list misses (`vk/texture.c:1389-1402`).

### 7. Eviction

- **Overlap**: `surface_put` calls `invalidate_overlapping_surfaces` before insertion
  (`gl/surface.c:1554`, `vk/surface.c:1756`). GL downloads then frees; VK invalidates
  lazily without downloading (`vk/surface.c:1716-1726`).
- **Age**: `surface_evict_old` (`gl/surface.c:1622`) / `expire_old_surfaces`
  (`vk/surface.c:2106`) drop anything unused for ≥ 5 `frame_time` ticks
  (`gl/surface.c:1627`, `vk/surface.c:45`). Called at the tail of every `surface_update`.
- **Incompatible rebind**: as in step 2.
- **Flush** (renderer switch, scale-factor change, shutdown): `flush_surfaces`
  (`gl/surface.c:3057`) / `pgraph_vk_surface_flush` (`vk/surface.c:3214`) zero
  `last_surface_shape`, unbind both targets and invalidate everything. GL deliberately
  **skips** the download here — the call is commented out with
  "We should download all surfaces to ram, but need to investigate corruption issue"
  (`gl/surface.c:3071-3073`). VK does download (`vk/surface.c:3231`).

GL frees the node immediately (`pgraph_gl_surface_invalidate`, `gl/surface.c:1598`). VK
has a three-tier afterlife: active list → `shelved_surfaces` (image kept, address key
dropped, `shelved_dirty` recorded) or `invalid_surfaces` (image kept for reuse) →
`surface_image_pool` (image recycled by `{format,w,h,usage}`) → destroyed
(`vk/surface.c:1645`, `:1605`, `:2022`, `:1888`).

---

## Cache and dirty-tracking state

This is the section relevant to issue 19 (cross-test contamination traced toward
texture/surface dirty tracking).

### Which structs hold surface cache state

| container | file:line | contents |
|---|---|---|
| `PGRAPHGLState::surfaces` | `hw/xbox/nv2a/pgraph/gl/renderer.h:189` | `QTAILQ` of all live GL `SurfaceBinding`s |
| `PGRAPHGLState::color_binding`, `zeta_binding` | `hw/xbox/nv2a/pgraph/gl/renderer.h:190` | currently attached targets |
| `PGRAPHVkState::surfaces` | `hw/xbox/nv2a/pgraph/vk/renderer.h:1184` | live list |
| `PGRAPHVkState::invalid_surfaces` | `hw/xbox/nv2a/pgraph/vk/renderer.h:1185` | evicted-but-image-retained |
| `PGRAPHVkState::shelved_surfaces` | `hw/xbox/nv2a/pgraph/vk/renderer.h:1186` | evicted-but-fully-retained, re-attachable by address |
| `PGRAPHVkState::surface_addr_map` | `hw/xbox/nv2a/pgraph/vk/renderer.h:1187` | `GHashTable` address → binding, active list only |
| `PGRAPHVkState::surface_image_pool` | `hw/xbox/nv2a/pgraph/vk/renderer.h:1215-1216` | free `VkImage`s keyed on `{format,w,h,usage}` |
| `PGRAPHState::surface_color`, `surface_zeta` | `hw/xbox/nv2a/pgraph/pgraph.h:146` | the *guest-side* pending state, backend-independent |
| `PGRAPHState::last_surface_shape` | `hw/xbox/nv2a/pgraph/pgraph.h:149` | the shape memcmp'd against by `framebuffer_dirty` |

### What the cache KEY is

**The key is the byte address `vram_addr = dma.address + surface->offset`, and nothing
else.** VERIFIED:

- `pgraph_gl_surface_get` compares only `surface->vram_addr == addr`
  (`hw/xbox/nv2a/pgraph/gl/surface.c:1573-1577`).
- `pgraph_vk_surface_get` is a `g_hash_table_lookup` on the address alone
  (`hw/xbox/nv2a/pgraph/vk/surface.c:1765-1769`).
- The address is computed at `gl/surface.c:2660` / `vk/surface.c:2713`.

Format, dimensions, pitch and swizzle are **not** part of the key; they are validated
*after* the lookup by `check_surface_compatibility`
(`gl/surface.c:1640-1657`, `vk/surface.c:2155-2171`) and a mismatch causes eviction
rather than a miss. The VK shelf is the one place where a wider key is used —
`get_shelved_surface` requires address + `vk_format` + `color` + `width` + `height` +
`pitch` to all match (`vk/surface.c:1677-1682`).

There is no key entry for `anti_aliasing`, `z_format` or `clip_x/clip_y`. Those live in
`SurfaceBinding::shape` and are only compared indirectly, via the global
`framebuffer_dirty()` memcmp of `pg->surface_shape` vs `pg->last_surface_shape`
(`gl/surface.c:941-942`), which is a *global* signal, not per-surface.

### Fields that track dirtiness

| field | declared | set by | cleared by | granularity |
|---|---|---|---|---|
| `Surface::buffer_dirty` | `pgraph.h:66` | `SET_SURFACE_PITCH/COLOR_OFFSET/ZETA_OFFSET` on change (`pgraph.c:2081`, `:2091`, `:2098`), `SET_CONTEXT_DMA_COLOR/ZETA` (`pgraph.c:1995`, `:2001`), `SET_SURFACE_FORMAT` type change (`pgraph.c:2070-2071`), `framebuffer_dirty` (`gl/surface.c:2957-2958`), colour rebind forcing zeta (`gl/surface.c:2801`, `:2855`) | `update_surface_part` after a successful bind (`gl/surface.c:2896`, `vk/surface.c:2989`) | per target (colour / zeta), not per surface |
| `Surface::draw_dirty` | `pgraph.h:65` | `set_surface_dirty` (`gl/surface.c:960-961`, `vk/draw.c:5455-5456`) | `update_surface_part` download branch (`gl/surface.c:2909`, `vk/surface.c:3011`), `flush_surfaces` (`gl/surface.c:3063-3064`, `vk/surface.c:3220-3221`) | per target |
| `Surface::write_enabled_cache` | `pgraph.h:67` | `SET_COLOR_MASK` / `SET_DEPTH_MASK` **before** applying the new mask (`pgraph.c:2487`, `:2505`) | download branch of `update_surface_part` (`gl/surface.c:2908`, `vk/surface.c:3010`) | per target |
| `SurfaceBinding::draw_dirty` | `gl/renderer.h:62`, `vk/renderer.h:296` | `set_surface_dirty` (`gl/surface.c:964`, `:971`; `vk/draw.c:5463`, `:5472`) | `surface_download` (`gl/surface.c:2358`), `download_surface` (`vk/surface.c:1186`), staged completion (`vk/surface.c:607`, `:666`), bulk paths (`vk/surface.c:1381`, `:1459`), full-cover blit discard (`gl/blit.c:162`, `vk/blit.c:260`), fresh-binding init (`gl/surface.c:2667`, `vk/surface.c:2720`) | **per surface, whole surface** |
| `SurfaceBinding::download_pending` | `gl/renderer.h:63`, `vk/renderer.h:298` | `surface_access_callback` (`gl/surface.c:1480`, `vk/surface.c:1526`), `pgraph_vk_wait_for_surface_download` (`vk/surface.c:1303`) | on download (`gl/surface.c:2357`, `vk/surface.c:1184`) | per surface (VK: plus a row range) |
| `SurfaceBinding::upload_pending` | `gl/renderer.h:64`, `vk/renderer.h:299` | fresh binding (`gl/surface.c:2665`, `vk/surface.c:2718`), `mem_dirty` on a cache hit (`gl/surface.c:2800`, `vk/surface.c:2892`), CPU write callback (`gl/surface.c:1485`, `vk/surface.c:1532`), blit into the surface (`gl/blit.c:164`, `vk/blit.c:262`) | on upload (`gl/surface.c:2457`, `vk/surface.c:2212`); forced false on a VK shelf hit (`vk/surface.c:2948`) | per surface |
| `SurfaceBinding::shelved_dirty` (VK only) | `vk/renderer.h:297` | `update_surface_part` at shelve time (`vk/surface.c:2908`) | `pgraph_vk_download_surfaces_in_range_if_dirty` (`vk/surface.c:190`) | per surface |
| `SurfaceBinding::draw_generation` / `download_generation` (VK only) | `vk/renderer.h:303-304` | `draw_generation++` in `set_surface_dirty` (`vk/draw.c:5465`, `:5474`); `download_generation = draw_generation` at every download completion (`vk/surface.c:608`, `:667`, `:1187`, `:1382`, `:1460`) | — | per surface; used to skip redundant downloads (`vk/surface.c:1168-1171`, `:1201-1203`, `:1491`) |
| `SurfaceBinding::cleared` | `gl/renderer.h:59`, `vk/renderer.h:293` | GL only: `pgraph_gl_clear_surface` (`gl/draw.c:145`, `:148`) | `set_surface_dirty` (`gl/surface.c:966`, `:973`; `vk/draw.c:5468`, `:5477`), fresh binding (`gl/surface.c:2672`, `vk/surface.c:2725`) | per surface |
| `SurfaceBinding::frame_time` | `gl/renderer.h:60`, `vk/renderer.h:294` | `set_surface_dirty`, `surface_update`, display fetch (`gl/display.c:667`) | — | per surface; drives age eviction |
| `SurfaceBinding::draw_time` | `gl/renderer.h:61`, `vk/renderer.h:295` | upload (`gl/surface.c:2458`), `surface_update` (`gl/surface.c:2997`), draw end (`gl/draw.c:419`, `:422`) | — | per surface; compared against `TextureBinding::draw_time` |
| `TextureLruNode::possibly_dirty` (GL) | `gl/renderer.h:160` | `pgraph_gl_mark_textures_possibly_dirty` (`gl/texture.c:492-510`) | after a rebuild (`gl/texture.c:908`) | per cache node, page-aligned range |
| `PGRAPHState::texture_dirty[]` | `pgraph.h:161` | method handlers | `gl/texture.c:756` | per texture unit |
| `DIRTY_MEMORY_NV2A` VRAM bitmap | `include/exec/ramlist.h:14` | QEMU on guest writes; `vk/blit.c:327-328` explicitly | `gl/surface.c:2712`, `vk/surface.c:2789`, `gl/vertex.c:66`, `vk/draw.c:5119` | **per 4 KiB page** |
| `DIRTY_MEMORY_NV2A_TEX` VRAM bitmap | `include/exec/ramlist.h:15` | QEMU on guest writes; surface downloads (`gl/surface.c:2353`, `vk/surface.c:1180`), blits (`gl/blit.c:221`, `vk/blit.c:319`) | `gl/texture.c:517`, `vk/texture.c:480` | **per 4 KiB page** |

### The page-granularity problem, precisely

`memory_region_test_and_clear_dirty` → `physical_memory_test_and_clear_dirty`
(`system/memory.c:2359-2371` → `system/physmem.c:1236-1282`) rounds the requested range
**outward to whole target pages** (`system/physmem.c:1250-1251`) and then clears every
bit in that span (`:1261-1270`). `TARGET_PAGE_BITS` is 12 for i386
(`target/i386/cpu-param.h:23`), so the unit is 4 KiB.

Four distinct consumers clear bits in these two bitmaps, and none of them coordinates:

| consumer | bitmap | range it clears |
|---|---|---|
| `update_surface_part` (GL) | `DIRTY_MEMORY_NV2A` | `[entry.vram_addr, +entry.size)` page-aligned outward — `gl/surface.c:2712-2714` |
| `update_surface_part` (VK) | `DIRTY_MEMORY_NV2A` | same span, open-coded — `vk/surface.c:2775-2792` |
| vertex RAM sync (GL) | `DIRTY_MEMORY_NV2A` | `gl/vertex.c:55-71`, explicitly page-aligned at `:55` |
| vertex RAM sync (VK) | `DIRTY_MEMORY_NV2A` | `vk/draw.c:5109-5122` |
| texture dirty check (GL) | `DIRTY_MEMORY_NV2A_TEX` | `gl/texture.c:512-519`, `TARGET_PAGE_ALIGN` at `:514-515` |
| texture dirty check (VK) | `DIRTY_MEMORY_NV2A_TEX` | `vk/texture.c:475-482`, identical |

**[INFERRED]** Consequences that follow directly from those citations:

1. **Surface eats texture/vertex dirty bits and vice versa.** A surface at
   `vram_addr = 0x3F000`, size 0x2000, page-aligns to `[0x3F000, 0x41000)`. Any texture,
   palette or vertex array living in those pages loses its `DIRTY_MEMORY_NV2A` bit the
   moment `update_surface_part` runs — for `DIRTY_MEMORY_NV2A_TEX` the symmetric loss
   happens through `check_texture_dirty`. The two bitmaps are separate
   (`include/exec/ramlist.h:14-15`), which limits the blast radius to *within* each
   client, but surfaces and vertex buffers share `NV2A`, and every texture and palette
   shares `NV2A_TEX`.
2. **A surface eats its own neighbour's bits.** Two surfaces whose `[vram_addr, +size)`
   ranges land in the same page — small render targets, a colour and zeta pair packed
   tightly, or a scratch target near a framebuffer — will clear each other's upload
   signal. Whichever `update_surface_part` runs first consumes `mem_dirty` for the shared
   page; the second sees `mem_dirty == false` and skips the re-upload.
3. **The clear is unconditional even on a cache hit.** `mem_dirty` is computed *before*
   the `if (upload && ...)` branch in both backends (`gl/surface.c:2712` precedes `:2716`;
   `vk/surface.c:2773` precedes `:2799`), so the bits are consumed on every
   `update_surface_part` call — including calls that end up doing nothing. Any other
   consumer of those pages that was going to look later has already lost the signal.
4. **A cross-run/cross-test carrier.** `flush_surfaces` (`gl/surface.c:3057-3076`)
   invalidates surfaces **without downloading**, and the accompanying comment says so
   explicitly. The `DIRTY_MEMORY_NV2A` state is *not* reset by any surface path — only
   `nv2a.c:471` seeds the whole VRAM dirty, once, at device realize. So a test that leaves
   a page's NV2A bit cleared leaves it cleared for whatever runs next at that address.
5. **VK's inline test-and-clear bypasses the memory-region layer.** `vk/surface.c:2780-2792`
   reads `ram_list.dirty_memory[DIRTY_MEMORY_NV2A]` directly, so it skips both
   `memory_region_sync_dirty_bitmap(mr, false)` (`system/memory.c:2368`) and
   `memory_region_clear_dirty_bitmap()` (`system/physmem.c:1274`) that the GL path gets
   for free. It also skips `physical_memory_dirty_bits_cleared()`
   (`system/physmem.c:1277-1279`), though that one is TCG-only
   (`system/physmem.c:1030-1032`) and the whole VK block is `!tcg_enabled()`-gated
   (`vk/surface.c:2774`), so that particular omission is harmless. The two skipped
   listener calls are not obviously harmless — see Uncertainties.

### Two more candidate contamination carriers (VK-only)

**[INFERRED]** In `update_surface_part`, `target` is `memset` to zero at
`vk/surface.c:2765`, `populate_surface_binding_target_sized` sets `draw_dirty = false`
(`:2720`), and then the whole struct is assigned over the recovered binding:
`*surface = target;` (`vk/surface.c:2938`). On the unshelve path (`:2923-2926`) the
recovered surface's `draw_dirty` and `shelved_dirty` are therefore both reset to false,
while `migrate_surface_image` has just handed the `VkImage` (which still holds unwritten
GPU content) to the new binding. The display and texture paths still read correct pixels
from that image, but any later *VRAM* reader — `pgraph_vk_download_surfaces_in_range_if_dirty`
(`vk/surface.c:176`), `expire_old_surfaces` (`:2120`), `surface_access_callback`
(`:1490`) — will see `draw_dirty == false` and skip the writeback.

**[INFERRED]** The same assignment drops the `mem_dirty` signal on the unshelve path. The
sequence is: `mem_dirty` is test-and-cleared at `vk/surface.c:2789`; the branch is entered;
`pgraph_vk_surface_get` misses because `shelve_surface` removed the address from
`surface_addr_map` (`:1658-1659`); `get_shelved_surface` hits; and
`surface->upload_pending` is then forced to `false` (`:2948`). A guest write to that VRAM
while the surface sat on the shelf is therefore observed and then discarded. Under TCG the
write would not even be observed, because `shelve_surface` unregisters the CPU access
callback (`:1656`).

**[INFERRED]** `surface_image_pool_acquire` (`vk/surface.c:1837-1858`) hands back a
`VkImage` whose contents belong to a previously destroyed surface, keyed only on
`{format,width,height,usage}` (`:1828-1835`). `create_surface_image` then transitions it
from `VK_IMAGE_LAYOUT_UNDEFINED` (`:1993-1995`), which by the Vulkan spec permits the
implementation to discard the contents but does not require it. A newly created surface
normally has `upload_pending = true` (`:2718`) so this is covered — unless the upload is
skipped, which is exactly what the unshelve path does. I did not find a path that combines
a pool hit with `upload_pending = false`, so I am not claiming one exists; see
Uncertainties.

---

## Coupling points (must-agree, unenforced)

1. **Two GL surface→texture rule sets that must stay identical, and don't.**
   `pgraph_gl_check_surface_to_texture_compatibility` (`gl/surface.c:1377-1446`) is the
   gate; `surface_to_texture_can_fastpath` (`gl/surface.c:1073-1124`) decides whether the
   render uses the blit path or the readback path. Their `switch` bodies over
   `surface_fmt`/`texture_fmt` are textually identical (`:1092-1119` vs `:1413-1441`), but
   only the gate checks pitch/width/height (`:1383-1387`), `cubemap` (`:1397`) and
   `levels > 1` (`:1402`). Nothing enforces that the two lists stay in sync; they are
   maintained by copy-paste.

2. **The aliasing rule set is a hand-written allow-list, and it is not symmetric with
   VK's.** GL enumerates exact `(surface_format, texture_format)` pairs
   (`gl/surface.c:1413-1441`); VK's `check_surface_to_texture_compatiblity`
   (`vk/texture.c:1102-1119`) compares only `host_bytes_per_pixel ==
   vk_format_texel_size(tex_vkf.vk_format)` for colour, and returns unconditionally
   `true` for zeta (`:1112-1114`). VK will therefore alias combinations GL refuses (any
   same-size format pair) and will alias zeta→texture at all, which GL explicitly refuses
   (`gl/surface.c:1392-1395`, `// FIXME: Support zeta to color`). Same guest program, two
   different rendering decisions, no shared test.

3. **`SurfaceBinding::cleared` is written in GL and never written in VK.** GL sets it in
   `pgraph_gl_clear_surface` (`gl/draw.c:144-149`) using a `full_clear` computed against
   `surface_binding_dim` (`gl/draw.c:119-121`). In VK the only assignments are
   `cleared = false` (`vk/draw.c:5468`, `:5477`; `vk/surface.c:2725`) — VERIFIED by
   grep over `pgraph/vk/`. Both backends then *read* it in the identical
   swizzle↔linear migration rule (`gl/surface.c:2768`, `vk/surface.c:2860`). So the
   clause `(pg->clearing || surface->cleared)` can only ever be satisfied through
   `pg->clearing` on VK, and the "a fully cleared linear surface may be re-marked
   swizzled" allowance is dead code there. The two backends diverge in whether a surface
   is reused or evicted, silently.

4. **Blit dirty marking differs.** `pgraph_vk_image_blit` marks the destination
   `DIRTY_MEMORY_NV2A` in addition to VGA and NV2A_TEX, with a comment explaining that
   without it "the surface's VkImage retains stale GPU-rendered content while VRAM has
   fresh blit data" (`vk/blit.c:321-328`). `pgraph_gl_image_blit` marks only VGA and
   NV2A_TEX (`gl/blit.c:219-222`). The GL path partially compensates by setting
   `surf_dest->upload_pending = true` directly (`gl/blit.c:164`) — but only when a surface
   is bound at the *exact* destination address, whereas the dirty bit would also catch a
   surface created later. Fix applied to one backend only.

5. **Colour and zeta must have equal dimensions, asserted only at the end.**
   `assert(color_binding->width == zeta_binding->width && ...heights)` at
   `gl/surface.c:3012-3015` and `vk/surface.c:3106-3109`. The invariant is *maintained* in
   three separate places — `populate_surface_binding_entry` forcing the zeta size from the
   colour binding (`gl/surface.c:2694-2697`), the zeta-vs-colour compat clause
   (`gl/surface.c:2787-2790`), and the "colour rebound at a different size" forcing
   `surface_zeta.buffer_dirty` (`gl/surface.c:2854-2856`) — with no single owner.

6. **Colour and zeta at the same address is unimplemented and silent.** Both backends
   detect it and call `NV2A_UNIMPLEMENTED("Same color & zeta surface offset")` then
   unbind the other target (`gl/surface.c:2727-2728`, `vk/surface.c:2818-2819`). With
   `DEBUG_NV2A_FEATURES == 0` (`hw/xbox/nv2a/debug.h:48-49`) the macro expands to nothing
   (`debug.h:67`), so this produces no output at all in a normal build.

7. **`surface_binding_dim` is a global side channel.** `update_surface_part` publishes the
   bound surface's dims into `pg->surface_binding_dim`
   (`gl/surface.c:2794-2799`, `:2847-2852`; `vk/surface.c:2886-2891`, `:2958-2963`), and
   the clear path (`gl/draw.c:119-121`) and viewport setup (`gl/draw.c:331-332`) read it.
   It is written only inside the *rebind* block, so on a `surface_update` that takes the
   `else` path it retains the previous surface's values. The struct carries a
   `// FIXME: Refactor` (`pgraph.h:158`).

8. **`framebuffer_dirty` is a whole-struct `memcmp`.** `gl/surface.c:941-942` and
   `vk/surface.c:116-117` memcmp `SurfaceShape` (`surface.h:25-33`). Any field added to
   `SurfaceShape` silently becomes part of the framebuffer-invalidation trigger, including
   `z_format`, which is not a guest-written shape field at all but is back-filled from
   `NV_PGRAPH_SETUPRASTER` at the top of `surface_update` (`gl/surface.c:2944-2946`). The
   struct has no padding declaration and is compared as raw bytes.

9. **Two independent copies of `surface_get_dimensions` and `framebuffer_dirty`.** Both
   carry `// FIXME: Move to common` (`gl/surface.c:938`, `:3020`; `vk/surface.c:99`,
   `:113`) and are currently byte-identical. They must agree; nothing checks that.

10. **Texture-overlap tests use two different interval conventions.**
    `check_surface_overlaps_range` uses exclusive ends
    (`gl/surface.c:1448-1454`, `vk/surface.c:145-151`), while the GL texture writeback
    loop open-codes the test with inclusive ends
    (`gl/texture.c:827-831`: `tex_vram_end = texture_vram_offset + length - 1`,
    `surf_vram_end = surface->vram_addr + surface->size - 1`, then
    `!(surface->vram_addr >= tex_vram_end || texture_vram_offset >= surf_vram_end)`).
    **[INFERRED]** The inclusive form misses an exactly-adjacent-by-one-byte case that the
    exclusive form catches, and vice versa at the touching boundary.

11. **Zeta host format is chosen per-device on VK and per-`z_format` on GL.** GL indexes
    `kelvin_surface_zeta_float_format_gl_map` or `..._fixed_format_gl_map` on
    `surface_shape.z_format` (`gl/surface.c:2633-2636`), and the float Z24S8 entry is
    explicitly a lie — the comment says GL cannot pack floating-point Z24S8 so it "just
    emulate[s] this with fixed-point Z24S8" (`gl/constants.h:361-365`). VK ignores
    `z_format` entirely for format selection (`vk/surface.c:2690-2691`, with
    `// FIXME: Support float 16,24b float format surface` at `:2692`) and instead picks
    D24S8 or D32S8 based on device support at init (`vk/surface.c:3168-3185`). The two
    backends will disagree on depth precision for the same guest state, and the VK choice
    additionally varies per GPU.

12. **`num_deferred_downloads` bookkeeping vs surface lifetime (VK).**
    `deferred_downloads_clear_surface` (`vk/surface.c:561-569`) nulls the back-pointer for
    a surface about to be freed, and the comment at `:558-560` says the staged data is
    still copied but the flags are not updated. Callers must therefore free surfaces only
    via paths that call it — `invalidate_overlapping_surfaces` (`:1743`),
    `prune_invalid_surfaces` (`:2097`), `expire_old_surfaces` (`:2146`),
    `pgraph_vk_surface_flush` (`:3239`). `invalidate_surface` does **not** call it, which
    is correct only because it keeps the node alive on `invalid_surfaces`. Unenforced.

---

## Stubs and gaps

`NV2A_UNIMPLEMENTED` is a no-op unless `DEBUG_NV2A_FEATURES` is on
(`hw/xbox/nv2a/debug.h:48-49, 60-62, 66-68`); the default is 0 (`debug.h:49`).
`assert()` is always live — QEMU refuses to build with `NDEBUG`
(`include/qemu/osdep.h:311-312`), so every `assert` below aborts the process on failure.

| symbol | file:line | kind | what behaviour it gates | ABORTS? |
|---|---|---|---|---|
| `NV2A_UNIMPLEMENTED("Same color & zeta surface offset")` | `hw/xbox/nv2a/pgraph/gl/surface.c:2727` | NV2A_UNIMPLEMENTED | colour and zeta pointing at the same VRAM address; the other target is silently unbound | No (no-op in default build) |
| same, VK | `hw/xbox/nv2a/pgraph/vk/surface.c:2818` | NV2A_UNIMPLEMENTED | same | No |
| `abort()` on unmapped colour surface format | `hw/xbox/nv2a/pgraph/gl/surface.c:2623-2625` | explicit abort | any `SET_SURFACE_FORMAT_COLOR` whose table entry has `bytes_per_pixel == 0` — i.e. the `_O*`/`X1A7R8G8B8` variants | **Yes** |
| same, VK (`host_bytes_per_pixel == 0`) | `hw/xbox/nv2a/pgraph/vk/surface.c:2679-2683` | explicit abort | same | **Yes** |
| `assert(pg->surface_shape.color_format != 0)` | `hw/xbox/nv2a/pgraph/gl/surface.c:2618`; `vk/surface.c:2674` | assert | binding a colour target before `SET_SURFACE_FORMAT` | **Yes** |
| `assert(pg->surface_shape.zeta_format != 0)` | `hw/xbox/nv2a/pgraph/gl/surface.c:2630`; `vk/surface.c:2687` | assert | binding a zeta target before format is set | **Yes** |
| `assert(surface->pitch % fmt.bytes_per_pixel == 0)` | `hw/xbox/nv2a/pgraph/gl/surface.c:2647`; `vk/surface.c:2703` | assert | non-pixel-aligned pitch | **Yes** |
| `assert(surface->offset + surface->pitch*height <= dma.limit + 1)` | `hw/xbox/nv2a/pgraph/gl/surface.c:2646`; `vk/surface.c:2702` | assert | a surface that overruns its DMA object | **Yes** |
| `assert(dma.dma_class == NV_DMA_IN_MEMORY_CLASS)` | `hw/xbox/nv2a/pgraph/gl/surface.c:2643`; `vk/surface.c:2699` | assert | stale/bogus DMA object; the comment above it admits this fires from unrelated bugs | **Yes** |
| `assert(!(entry.swizzle && pg->clearing))` | `hw/xbox/nv2a/pgraph/gl/surface.c:2758`; `vk/surface.c:2851` | assert | a `CLEAR_SURFACE` targeting a swizzled surface | **Yes** |
| `assert(color_binding->width == zeta_binding->width && ...)` | `hw/xbox/nv2a/pgraph/gl/surface.c:3013-3014`; `vk/surface.c:3107-3108` | assert | mismatched colour/zeta dimensions surviving all the maintenance rules | **Yes** |
| `assert(d->pgraph.surface_color.buffer_dirty)` in invalidate | `hw/xbox/nv2a/pgraph/gl/surface.c:1606`, `:1610`; `vk/surface.c:1619`, `:1623` | assert | invalidating a still-bound surface without having marked it dirty | **Yes** |
| `assert(pgraph_gl_surface_get(d, addr) == NULL)` in `surface_put` | `hw/xbox/nv2a/pgraph/gl/surface.c:1552`; `vk/surface.c:1754` | assert | duplicate address insertion | **Yes** |
| `assert(status == GL_FRAMEBUFFER_COMPLETE)` after attach | `hw/xbox/nv2a/pgraph/gl/surface.c:2891` | assert | incomplete FBO; **suppressed on Android**, which prints to stderr and continues (`:2887-2892`) | Yes off-Android |
| `assert(status == GL_FRAMEBUFFER_COMPLETE)` in `bind_current_surface` | `hw/xbox/nv2a/pgraph/gl/surface.c:1735` | assert | same, `#ifndef __ANDROID__` guarded (`:1734-1736`) | Yes off-Android |
| `assert(pg->surface_scale_factor == 1 \|\| downscale)` | `hw/xbox/nv2a/pgraph/gl/surface.c:2270`; `vk/surface.c:761` | assert | swizzled readback at internal resolution without a downscale step | **Yes** |
| `assert(!"CLEAR_SURFACE not supported for selected surface format")` | `hw/xbox/nv2a/pgraph/pgraph.c:4236` | assert | `CLEAR_SURFACE` on `LE_B8`, `LE_G8B8` or any unmapped format | **Yes** |
| `assert(!"CLEAR_SURFACE handling for LE_X1A7R8G8B8_* is untested")` | `hw/xbox/nv2a/pgraph/pgraph.c:4250` | assert | alpha extraction for the X1A7R8G8B8 formats; deliberately trips on first use | **Yes** |
| `assert(false)` on unknown zeta format in clear-value decode | `hw/xbox/nv2a/pgraph/pgraph.c:4293` | assert | `zeta_format` outside {Z16, Z24S8} | **Yes** |
| `assert(false)` in `pgraph_apply_anti_aliasing_factor` default | `hw/xbox/nv2a/pgraph/pgraph.h:461` | assert | `anti_aliasing` ≥ 3 (the field is 4 bits wide, `nv2a_regs.h:887`) | **Yes** |
| `assert(!"Invalid zclamp value")` | `hw/xbox/nv2a/pgraph/pgraph.c:4007` | assert / FIXME | `SET_ZMIN_MAX_CONTROL` `ZCLAMP_EN` other than 0/1; the FIXME above says HW should raise `NV_PGRAPH_NSOURCE_DATA_ERROR_PENDING` instead | **Yes** |
| `assert(false)` on unknown blit surface format | `hw/xbox/nv2a/pgraph/gl/blit.c:100`; `vk/blit.c:196` | assert | `NV062_SET_COLOR_FORMAT_*` outside the five handled values | **Yes** |
| `assert(false && "Unknown blit operation")` | `hw/xbox/nv2a/pgraph/gl/blit.c:56`; `vk/blit.c:127` | assert | blit ops other than `SRCCOPY` and `BLEND_AND` | **Yes** |
| `assert(!"unsupported layout transition!")` | `hw/xbox/nv2a/pgraph/vk/image.c:311` | assert | any `(oldLayout,newLayout)` pair outside the hand-written matrix at `:72-309` | **Yes** |
| `assert(!"Unsupported host fmt")` in compute shader selection | `hw/xbox/nv2a/pgraph/vk/surface-compute.c:193` | assert | depth pack/unpack for a host format other than D24S8/D32S8 | **Yes** |
| `assert(no_conversion_necessary)` (download) | `hw/xbox/nv2a/pgraph/vk/surface.c:710` | assert | any zeta surface that is neither D16 nor a compute-convertible D*S8 | **Yes** |
| `assert(no_conversion_necessary)` (upload) | `hw/xbox/nv2a/pgraph/vk/surface.c:2234` | assert | same on the upload side | **Yes** |
| `assert(surface->color)` / attachment / GL format asserts in display | `hw/xbox/nv2a/pgraph/gl/display.c:659-665` | assert | scanning out from a non-colour or unexpected-format surface | **Yes** |
| `assert(!pg->framebuffer_in_use)` | `hw/xbox/nv2a/pgraph/pgraph.c:1280` | assert | re-entrant `nv2a_get_framebuffer_surface` | **Yes** |
| `flush_surfaces` does not download | `hw/xbox/nv2a/pgraph/gl/surface.c:3071-3073` | FIXME (commented-out call) | on renderer switch / scale change, GL discards all un-downloaded surface content | No |
| `// FIXME: Support zeta to color` | `hw/xbox/nv2a/pgraph/gl/surface.c:1082`, `:1393` | FIXME | GL cannot alias a depth surface as a texture at all | No |
| `// FIXME: Support rendering surface to cubemap face` | `hw/xbox/nv2a/pgraph/gl/surface.c:1398` | FIXME | cubemap render targets fall back to VRAM | No |
| `// FIXME: Support rendering surface to mip levels` | `hw/xbox/nv2a/pgraph/gl/surface.c:1403` | FIXME | mipmapped render targets fall back to VRAM | No |
| `// FIXME: Better checks/handling on formats and surface-texture compat` | `hw/xbox/nv2a/pgraph/gl/surface.c:1076`, `:1381` | FIXME | the aliasing allow-list is acknowledged incomplete | No |
| `// FIXME: Force alpha to zero` on `X1R5G5B5_Z1R5G5B5` and `X8R8G8B8_Z8R8G8B8` | `hw/xbox/nv2a/pgraph/vk/constants.h:344`, `:359` | FIXME | the `Z` (zero-alpha) semantics of those surface formats are not implemented on VK | No |
| `// FIXME: Map channel color` on `LE_B8` / `LE_G8B8` | `hw/xbox/nv2a/pgraph/gl/constants.h:350`; `vk/constants.h:374`, `:382` | FIXME | single/dual-channel surfaces map to R8/RG8 with no swizzle | No |
| `// FIXME: Respect write enable at last TOU?` | `hw/xbox/nv2a/pgraph/gl/surface.c:2343`; `vk/surface.c:1173` | FIXME | downloads write all channels regardless of the write mask in force when the pixels were produced | No |
| `// FIXME: Cannot monitor for reads/writes; flush now` | `hw/xbox/nv2a/pgraph/gl/surface.c:2901`; `vk/surface.c:3002` | FIXME | under KVM every download-side `surface_update` forces an unconditional readback | No |
| `// FIXME: Verify output of depth stencil conversion` | `hw/xbox/nv2a/pgraph/vk/surface.c:931` | FIXME | the compute Z24S8 pack result is unvalidated | No |
| `// TODO: Float depth format` | `hw/xbox/nv2a/pgraph/vk/surface-compute.c:26` | TODO | float Z16/Z24 never reaches the compute converters | No |
| `// FIXME: What does hardware do when min >= max? / min >= surface size?` | `hw/xbox/nv2a/pgraph/vk/draw.c:5300-5301` | FIXME | degenerate clear rectangles are clamped by guesswork (`:5302-5305`) | No |
| `/* FIXME: Needs confirmation */` on the clear rect decode | `hw/xbox/nv2a/pgraph/gl/draw.c:96` | FIXME | `CLEARRECTX/Y` interpretation | No |
| `/* FIXME: Respect window clip?!?! */` | `hw/xbox/nv2a/pgraph/gl/draw.c:126` | FIXME | window clip is ignored during clears | No |
| `// FIXME: Make automatic` (invalid-surface retention = 10) | `hw/xbox/nv2a/pgraph/vk/surface.c:44` | FIXME | fixed-size image recycling pool | No |
| `// FIXME: Possible race condition with pgraph, consider lock` | `hw/xbox/nv2a/pgraph/gl/display.c:640` | FIXME | `pgraph_gl_get_framebuffer_surface` reads pgraph state under only the PFIFO lock | No |
| `/* FIXME: Sanity check surface dimensions */` | `hw/xbox/nv2a/pgraph/gl/display.c:594` | FIXME | scanout surface dimensions are not validated against VGA params | No |
| Null renderer: `clear_surface` and `surface_update` are empty | `hw/xbox/nv2a/pgraph/null/renderer.c:60-62`, `:109-112` | stub | with the null renderer no surface state is maintained at all; `get_report` always returns 0 (`:80-83`) | No |

---

## Suites plausibly exercised

Mapping is against the suite→symbol index the repo already ships,
`docs/testing/nv2a_index.json` (provenance `emulator_commit 5b4f5778…`, matching HEAD;
`tests_commit 33e7c6b0…`). I re-derived the symbol lists from that file and then located
each symbol in the tree myself. The suite names below are the `results_name` values.

| suite | primary code sites | confidence | reasoning |
|---|---|---|---|
| **Surface_format** (`src/tests/surface_format_tests.cpp`) | `pgraph.c:2046-2073` (format decode); `gl/constants.h:340-355` / `vk/constants.h:341-388` (format tables); `gl/surface.c:2603-2673` / `vk/surface.c:2658-2728` (format resolution); `gl/surface.c:2623-2625` / `vk/surface.c:2679-2683` (**abort** on unmapped format); `pgraph.c:4199-4259` (clear-colour unpack) | **High** | Index symbols for this suite are `SET_CONTEXT_DMA_A`, `SET_CONTEXT_DMA_COLOR`, `SET_SURFACE_COLOR_OFFSET`, `SET_SURFACE_PITCH{,_COLOR,_ZETA}`, `SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8` — exactly the binding path. Any test that selects one of the unmapped colour formats (`_O8R8G8B8`, `_X1A7R8G8B8_*`) hits the `abort()` or the `assert` at `pgraph.c:4236/4250`. |
| **Blend_surface** (`src/tests/blend_surface_tests.cpp`) | `pgraph.c:2046-2073`; `gl/draw.c:187-210` (blend state); `gl/surface.c:2440-2571` / `vk/surface.c:2181-2630` (upload); the `_O*`/`_Z*` alpha semantics FIXMEs at `vk/constants.h:344`, `:359`; `pgraph.c:4241-4258` (alpha from clear value) | **High** | Index symbols include `SET_SURFACE_FORMAT_COLOR_LE_X1A7R8G8B8_{Z,O}1A7R8G8B8`, `_X1R5G5B5_{Z,O}1R5G5B5`, `_X8R8G8B8_{Z,O}8R8G8B8` — i.e. it deliberately exercises precisely the formats missing from both host tables. The `Z` vs `O` distinction (preserve vs overwrite alpha) has no implementation anywhere in the surface path. |
| **Texture_render_target** (`src/tests/texture_render_target_tests.cpp`) | `gl/surface.c:1377-1446` (compat gate), `:1073-1124` (fastpath), `:1327-1375` (render-to-texture), `:1243-1321` (slow path); `vk/texture.c:1102-1119`, `:1006-1082`, `:707-899`, `:905-1003`; `gl/texture.c:763-840`, `:912-923` | **High** | Index symbols are `SET_SURFACE_COLOR_OFFSET`, `SET_SURFACE_PITCH*`, `SET_TEXTURE_OFFSET`, plus `SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_DEPTH_{X8_Y24,Y16}_{FIXED,FLOAT}` and DXT/palette formats. The depth-as-texture formats hit GL's `// FIXME: Support zeta to color` refusal (`gl/surface.c:1392-1395`) while VK accepts them unconditionally (`vk/texture.c:1112-1114`) — coupling point 2. |
| **Image_blit** (`src/tests/image_blit_tests.cpp`) | `pgraph.c:1714-1740` (2D surface decode), `:1748-1749` (`SET_CONTEXT_SURFACES`); `gl/blit.c:72-223`; `vk/blit.c:155-329`; `nv2a.c:97` (`nv_clip_gpu_tile_blit`) | **High** | The index lists no symbols for this suite (its source uses the pbkit 0x62/0x9F classes rather than NV097 defines), but the class handling is unambiguous. Both backends' full-cover discard (`gl/blit.c:159-163`, `vk/blit.c:256-261`) and the NV2A-dirty divergence (coupling point 4) are directly in play. |
| **Depth_buffer** (`src/tests/depth_format_tests.cpp`) | `pgraph.c:2046-2073` (zeta format), `:2124-2143` (`SET_CONTROL0` z_format), `:4261-4296` (clear value decode); `gl/constants.h:357-373`; `vk/surface.c:3168-3185` (device-dependent zeta format); `vk/surface-compute.c:28-115` (Z24S8 pack/unpack) | **High** | Index symbols: `SET_SURFACE_FORMAT_ZETA_Z16`, `_Z24S8`, `SET_DEPTH_{FUNC,MASK,TEST_ENABLE}`, `SET_STENCIL_*`, `SET_COMPRESS_ZBUFFER_EN`. Note `SET_COMPRESS_ZBUFFER_EN` — I found no handler for it in the surface path; see Uncertainties. GL's admitted fixed-point substitution for float Z24S8 (`gl/constants.h:361-365`) is squarely what this suite measures. |
| **Depth_buffer_fixed_function** (`src/tests/depth_format_fixed_function_tests.cpp`) | same sites as above, plus the fixed-function vertex path | **High** | Identical symbol list to `Depth_buffer` in the index — same surface-side code, different upstream vertex pipeline. |
| **ZMinMaxControl** (`src/tests/z_min_max_control_tests.cpp`) | `pgraph.c:3992-4010` (only `ZCLAMP_EN` decoded, `assert` on other values at `:4007`); `pgraph/glsl/psh.c:115-116` (consumes `NV_PGRAPH_ZCOMPRESSOCCLUDE_ZCLAMP_EN`) | **Medium-High** | Index symbols include `..._CULL_NEAR_FAR_EN_{TRUE,FALSE}` and `..._CULL_IGNORE_W_{TRUE,FALSE}`, which have **no** corresponding `#define` in `nv2a_regs.h:1270-1273` and no decode in `pgraph.c:3992-4010`. Confidence is on the *mapping*; the behaviour for those two sub-fields is simply absent. |
| **ZPass_pixel_count** (`src/tests/zpass_pixel_count_tests.cpp`) | `pgraph.c:3589-3592` (`zpass_pixel_count_enable`), `:4298+` (`pgraph_write_zpass_pixel_cnt_report`), `:3971-3973` (semaphore release forces `surface_update`); `gl/draw.c:352-369`, `:404-413` (GL occlusion queries); `vk/draw.c:3058`, `:4813`; `gl/reports.c`, `vk/reports.c`; `null/renderer.c:80-83` (always reports 0) | **Medium-High** | Index symbols: `SET_ZPASS_PIXEL_COUNT_ENABLE`, `CLEAR_REPORT_VALUE*`, `GET_REPORT*`, `SET_CONTEXT_DMA_{REPORT,SEMAPHORE}`, `SET_LINE_WIDTH`, `SET_POINT_SIZE`. Surface relevance is indirect but real: the count depends on the depth surface being bound and correctly sized, and on Android GL the query is silently disabled without `occlusion_query_boolean` (`gl/draw.c:354-357`, `:406-409`). Confidence is Medium-High rather than High because I did not read `reports.c` in either backend. |

Two additional suites in the index bear directly on this sweep even though they were not
in the brief: **Antialiasing_tests** (index symbols include all three
`SET_SURFACE_FORMAT_ANTI_ALIASING_*` values plus `SET_SURFACE_{COLOR,ZETA}_OFFSET` and
`SET_SURFACE_PITCH*`) maps onto `pgraph_apply_anti_aliasing_factor`
(`pgraph.h:446-464`), which merely multiplies the surface dimensions — no actual
multisampling exists anywhere in either backend. **Confidence: High** on the mapping.

---

## Uncertainties

Things I could not settle from a read-only pass. I would rather list them than guess.

1. **Issue 19 itself.** I could not find the issue text. The repo has `KNOWN_ISSUES.md`,
   `ROADMAP.md`, `.github/ISSUE_TEMPLATE/`, `.gitlab/issue_templates/` and
   `docs/testing/nv2a_index.json` (whose `issues` key is an empty dict), and none mentions
   issue 19, "contamination" or "cross-test". Everything I wrote about contamination is
   derived from the code, not from the bug report, so I may be describing a different
   mechanism than the one that was traced.
2. **Whether hakuX runs the pgraph suite under TCG or KVM.** This decides which dirty
   mechanism is live: TCG uses `mem_access_callback_insert` and skips the bitmap entirely
   (`gl/surface.c:1503`, `:2712`), KVM uses the bitmap and skips the callbacks. The
   page-granularity contamination analysis above applies **only** to the KVM/bitmap side.
   Under TCG the equivalent risk is the callback ranges, which are byte-exact
   (`gl/surface.c:1505-1507`) and therefore not page-contaminated — but the callback is
   only registered for surfaces with non-zero `width` *and* `height`
   (`gl/surface.c:1504`), so zero-size surfaces are untracked in both modes.
3. **Whether the VK inline dirty scan's skipped listener calls matter.**
   `vk/surface.c:2780-2792` bypasses `memory_region_sync_dirty_bitmap()`
   (`system/memory.c:2368`) and `memory_region_clear_dirty_bitmap()`
   (`system/physmem.c:1274`). Under KVM the first pulls the kernel's dirty log into the
   userspace bitmap and the second notifies `log_clear` listeners. If the NV2A VRAM region
   has no such listener, the omission is inert; I did not trace the listener set for
   `d->vram`.
4. **Whether the pooled-`VkImage` recycle can ever surface stale pixels.** I showed the
   pool is content-blind (`vk/surface.c:1837-1858`) and that the only `upload_pending =
   false` path is the *shelf* path (`:2948`), which does not go through the pool. I did not
   exhaustively prove no path combines them.
5. **Whether the lost `draw_dirty` on VK unshelve is reachable in practice.** The
   `*surface = target` assignment at `vk/surface.c:2938` provably resets it; whether a
   guest sequence exists that shelves a dirty surface, unshelves it, and then reads the
   VRAM I did not establish.
6. **`NV097_SET_COMPRESS_ZBUFFER_EN`.** The index lists it for both `Depth_buffer` suites.
   I did not locate a handler; I did not grep exhaustively enough to assert it is absent.
7. **`NV097_SET_SURFACE_FORMAT_TYPE` values above 2.** `nv2a_regs.h:884` gives a 4-bit
   field but only PITCH and SWIZZLE are named (`:885-886`). Code treats "not SWIZZLE" as
   linear (`gl/surface.c:2658-2659`, `:3024`), so an out-of-range value silently means
   linear. Whether hardware has a third mode, I do not know.
8. **`Surface::write_enabled_cache` semantics.** I described the mechanism from
   `pgraph.c:2487`/`:2505` and `gl/surface.c:2977-2984`, but I did not find any comment or
   test that pins down the intended rule, and the latch is a `|=` that is only ever
   cleared inside the download branch — so it can stay set across a target rebind.
9. **`SurfaceShape` `memcmp` and struct padding.** `surface.h:25-33` is nine `unsigned
   int`s, so on every ABI I know of it has no interior padding — but the code relies on
   that without a `static_assert`, and `framebuffer_dirty` compares raw bytes
   (`gl/surface.c:941-942`).
10. **The Android-specific GL surface code.** `gl/surface.c:37-884` is roughly 850 lines
    of `__ANDROID__`-only format conversion, NEON row kernels and RGBA8 transfer paths
    that this fork adds on top of upstream xemu. I read the entry points and the
    compatibility predicates (`:155-185`, `:588-613`, `:830-883`) but did not audit the
    NEON kernels for correctness. `android_surface_to_texture_rgba8_compatible`
    (`:830-883`) admits format pairs that the non-Android list refuses (e.g. surface
    `X1R5G5B5` → texture `A1R5G5B5`, `:844-845`), so **the Android build has a third,
    wider aliasing rule set** on top of the two in coupling point 1. Its interaction with
    `android_surface_to_texture_needs_guest_reinterpretation` (`:588-613`) I did not fully
    trace.
11. **`gl/reports.c` and `vk/reports.c`.** Not read; the ZPass mapping above is therefore
    Medium-High rather than High.
12. **`vk/display.c` beyond the surface lookup.** I read `render_display`'s surface
    interaction (`:1461-1634`) and `pgraph_vk_render_display` (`:1694-1744`) but not the
    swapchain/external-memory machinery, so I cannot say whether the Android forced
    download at `vk/surface.c:1289-1297` has surface-state side effects beyond the flags.
13. **Whether `pgraph_vk_get_framebuffer_surface` (`vk/renderer.c:1617`) has the same
    format assertions as GL's.** Not read.
14. **Relative severity.** I have listed several plausible contamination mechanisms
    (page-granular dirty clearing, VK unshelve flag reset, GL flush-without-download). I
    have no runtime evidence ranking them, and did not build or run anything.
