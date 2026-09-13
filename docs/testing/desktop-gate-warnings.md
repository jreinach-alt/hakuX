# Desktop build gate: warning inventory

The desktop (lavapipe) build is the only gate that catches a desktop link
error: the Android build cannot, and CI is a finite monthly budget reserved
for release builds, never a self-check. Two defects reached the tree that way
-- an unguarded `__android_log_print` in `vp.c`, and `XEMU_OPT_TB_CACHE_HINTS=0`
dropping two counter definitions that `profile.c` declares `extern`.

Regenerate with `docs/testing/gate.sh <ref> [base]` (see below); this file is the
snapshot, not the source of truth.

## Why this file exists

An earlier gate report quoted ten warnings and asked whose job three of them
were. That list was an artefact: the log had been filtered to the `unused*`
families, so the question was posed about whatever survived a grep. The tree
carries far more than ten, and none of them is special. Recording the whole
inventory once is cheaper than re-deriving a slice of it per fold.

## Snapshot at `c4594bdf`

`ninja -C build qemu-system-i386`, unfiltered, exit status taken directly from
ninja: **0 errors, 62 compile steps, links clean.** 57 distinct warning sites
in 11 families:

| count | family |
|---:|---|
| 24 | `-Wmissing-prototypes` |
| 8 | `-Wunused-variable` |
| 7 | `-Wnested-externs` |
| 4 | `-Wunused-function` |
| 4 | `-Wsuggest-attribute=format` |
| 4 | `-Wshadow=compatible-local` |
| 3 | `-Wunused-but-set-variable` |
| 3 | `-Wredundant-decls` |
| 2 | `-Wtype-limits` |
| 2 | `-Wformat-truncation=` |
| 1 | `-Wshadow=local` |

**None of the 57 is in a file that fold touched** (`psh.c`, `vsh.c`,
`vsh-ff.c`). They are pre-existing tree noise, not introduced by the work
being gated, and they are not a priority against accuracy work.

### Sites

    hw/xbox/nv2a/nv2a.c:60  no previous prototype for 'xemu_get_xbox_ram_ptr' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/gl/blit.c:328  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/gl/blit.c:378  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/gl/display.c:581  unused variable 'pg' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/gl/renderer.c:349  no previous prototype for 'pgraph_gl_force_register' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/gl/surface.c:1222  comparison of unsigned expression in '>= 0' is always true [-Wtype-limits]
    hw/xbox/nv2a/pgraph/gl/surface.c:1225  comparison of unsigned expression in '>= 0' is always true [-Wtype-limits]
    hw/xbox/nv2a/pgraph/gl/surface.c:894  'android_log_and_drain_gl_errors' defined but not used [-Wunused-function]
    hw/xbox/nv2a/pgraph/gl/texture.c:1028  unused variable 'row_pitch' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/gl/texture.c:1241  unused variable 'upload_slice_pitch' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/pgraph.c:214  no previous prototype for 'pgraph_method_histogram_log_and_reset' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/profile.c:485  unused variable 'idle_pct' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/blit.c:315  nested extern declaration of 'xemu_get_frame_skip' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/blit.c:494  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/vk/blit.c:544  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/vk/blit.c:633  nested extern declaration of 'xemu_get_frame_skip' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/blit.c:633  redundant redeclaration of 'xemu_get_frame_skip' [-Wredundant-decls]
    hw/xbox/nv2a/pgraph/vk/buffer.c:28  no previous prototype for 'xemu_set_texture_cache_size' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/buffer.c:33  no previous prototype for 'xemu_get_texture_cache_size' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/buffer.c:336  nested extern declaration of 'xemu_get_submit_frames' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/buffer.c:57  unused variable 'gib' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/command.c:58  nested extern declaration of 'xemu_get_submit_frames' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/draw.c:1030  'destroy_framebuffers' defined but not used [-Wunused-function]
    hw/xbox/nv2a/pgraph/vk/draw.c:2706  declaration of 'cmd' shadows a previous local [-Wshadow=local]
    hw/xbox/nv2a/pgraph/vk/draw.c:3397  unused variable 'requested' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/draw.c:3792  unused variable 'r' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/draw.c:450  no previous prototype for 'xemu_set_fast_fences' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:455  no previous prototype for 'xemu_get_fast_fences' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:460  no previous prototype for 'xemu_set_skip_occlusion_queries' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:465  no previous prototype for 'xemu_get_skip_occlusion_queries' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:470  no previous prototype for 'xemu_set_draw_reorder' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:475  no previous prototype for 'xemu_get_draw_reorder' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:480  no previous prototype for 'xemu_set_draw_merge' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:485  no previous prototype for 'xemu_get_draw_merge' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:490  no previous prototype for 'xemu_set_async_compile' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:495  no previous prototype for 'xemu_get_async_compile' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:500  no previous prototype for 'xemu_set_frame_skip' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:505  no previous prototype for 'xemu_get_frame_skip' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:510  no previous prototype for 'xemu_set_submit_frames' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:517  no previous prototype for 'xemu_get_submit_frames' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/instance.c:664  ' (' directive output may be truncated writing 2 bytes into a region of size between 1 and 256 [-Wformat-truncation=]
    hw/xbox/nv2a/pgraph/vk/instance.c:689  ' (v' directive output may be truncated writing 3 bytes into a region of size between 1 and 256 [-Wformat-truncation=]
    hw/xbox/nv2a/pgraph/vk/renderer.c:1416  nested extern declaration of 'xbox_ram_fp_active_ptr' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/renderer.c:1417  nested extern declaration of 'xbox_ram_fp_vram_base_ptr' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/renderer.c:1777  no previous prototype for 'pgraph_vk_force_register' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/renderer.c:599  function 'diag_json_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/renderer.c:603  function 'diag_json_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/renderer.c:628  function 'diag_diff_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/renderer.c:632  function 'diag_diff_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/shaders.c:1127  no previous prototype for 'pgraph_vk_set_shader_warmup_progress_cb' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/shaders.c:322  'grow_descriptor_ring' defined but not used [-Wunused-function]
    hw/xbox/nv2a/pgraph/vk/shaders.c:937  no previous prototype for 'shader_module_key_persist' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/texture.c:1753  variable 'did_s2t_copy' set but not used [-Wunused-but-set-variable]
    hw/xbox/nv2a/pgraph/vk/texture.c:1754  variable 'did_upload' set but not used [-Wunused-but-set-variable]
    hw/xbox/nv2a/pgraph/vk/texture.c:632  variable 'replaced' set but not used [-Wunused-but-set-variable]
    ui/xemu.c:130  'sdl_render_thread_id' defined but not used [-Wunused-variable]
    ui/xemu.c:1869  nested extern declaration of 'game_compat_check' [-Wnested-externs]
    ui/xemu.c:2375  'sleep_ns' defined but not used [-Wunused-function]

## Reading a gate log

Two traps, both paid for:

- **`NINJA_EXIT` must come from ninja, not from the end of a pipeline.** Never
  pipe ninja through a filter and then read `$?`.
- **`[65/65] Linking target` is printed when ninja *starts* the edge.** On its
  own it is not evidence the link finished. A log showing neither compile
  steps nor `ninja: no work to do.` has been filtered, and its exit status
  cannot be attributed -- treat that as UNSOUND and re-run, do not report PASS.
