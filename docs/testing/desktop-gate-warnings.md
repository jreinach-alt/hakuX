# Desktop build gate: warning inventory

The desktop (lavapipe) build is the only gate that catches a desktop link
error: the Android build cannot, and CI is a finite monthly budget reserved
for release builds, never a self-check. Three defects have reached the tree
that way -- an unguarded `__android_log_print` in `vp.c`, `XEMU_OPT_TB_CACHE_HINTS=0`
dropping two counter definitions that `profile.c` declares `extern`, and the
implicit `qemu_log` recorded below.

Regenerate with `docs/testing/gate.sh <ref> [base]` for a fold, or a full clean
build for the inventory (see **Scope**); this file is the snapshot, not the
source of truth.

## Scope: what a gate's warning count actually covers

**Read this before quoting a number out of this file or a gate report.**

ninja only recompiles what is out of date, so an incremental gate emits
warnings **only for the files that run rebuilt**. A typical fold gate compiles
**79 of 1,377** C objects -- 5.7%. Its warning count is a census over those 79,
not a property of the tree.

Every warning total in this file before 2026-09-14 was that kind of slice
presented as the whole. The snapshot below is different: it is a **full clean
build** (`ninja -t clean` then build, 1,812 edges, 1,377 C objects and 81 C++),
so it is the real inventory.

Three traps, all of them paid for, all of them mine:

1. **The count is scoped to the compile set.** "The tree carries 57 warning
   sites", recorded here at `c4594bdf`, was 57 over 62 of 1,377 objects. The
   true figure at `c4594bdf` was never measured and is not recoverable now; the
   figure for the current tree, measured properly, is 78. `gate.sh` now prints
   `N of M objects compiled` on every report so the denominator travels with
   the number.

2. **The site regex dropped headers.** `\.\./[a-z0-9_/-]+\.c:` excludes `.h`
   and any path containing a dot. On one run that read 67 against 71 actual --
   the four missing were `accel/tcg/tb-cache-hints.h` and
   `vk/stb_image_write.h`. Widened to `[A-Za-z0-9_/.-]+\.[ch]`.

3. **Trends keyed on `file:line` count drift as churn.** A function inserted
   upstream shifts every later line, so the same warning reads as one removal
   plus one addition. `ac829cd8` -> `08b4219a` scored 30 gone / 27 new that
   way. Compare by file + message, never by line.

4. **A delta is only meaningful over files compiled in BOTH runs**, and this
   one bit hardest because it hides inside the fix for (3). Keyed by
   file+message, `ac829cd8` -> `08b4219a` reads as 3 removals -- and 2 of them
   are false. `target/i386/tcg/fpu_helper.c` was not recompiled in the second
   run, so its two `xemu_*_fp_safe` warnings were not *removed*, they were
   **not observed**; the full clean build still carries both, at lines 365 and
   370. Restricted to the 21 warning-carrying files compiled in both runs the
   honest answer is **1 removal, 0 additions** -- `vk/draw.c`'s unused
   `requested`. `gate.sh` now computes the intersection and reports the delta
   only over it. Same trap as (1), one level deeper: absence of a warning is
   evidence of nothing unless the file was compiled.

The irony is the point: this file was written because an earlier report quoted
ten warnings that had survived a grep and asked a question about them. It then
recorded a slice and called it the inventory, one level up. A measurement is
not trustworthy because it is bigger than the last one.

## Snapshot at `0103d4fa` (full clean build)

`ninja -C build -t clean && ninja -C build qemu-system-i386`, unfiltered, exit
status taken directly from ninja: **NINJA_EXIT=0, 1,812 edges, links clean.**

**78 distinct warning sites**, of which 1 is in vendored `subprojects/` and 77
are ours; 63 sit in `hw/xbox/**` or `ui/**`.

| count | family |
|---:|---|
| 33 | `-Wmissing-prototypes` |
| 11 | `-Wunused-variable` |
| 11 | `-Wnested-externs` |
| 4 | `-Wunused-function` |
| 4 | `-Wsuggest-attribute=format` |
| 4 | `-Wshadow=compatible-local` |
| 3 | `-Wunused-but-set-variable` |
| 3 | `-Wtype-limits` |
| 2 | `-Wformat-truncation=` |
| 1 | `-Wshadow=local` |
| 1 | `-Wredundant-decls` |
| 1 | `-Wimplicit-function-declaration` |

By directory, outside `subprojects/`:

| count | directory |
|---:|---|
| 44 | `hw/xbox/nv2a/pgraph/vk` |
| 9 | `hw/xbox/nv2a/pgraph/gl` |
| 8 | `accel/tcg` |
| 4 | `system` |
| 3 | `ui` |
| 2 | `target/i386/tcg` |
| 2 | `hw/xbox/nv2a/pgraph` |
| 2 | `hw/xbox` |
| 4 | one each: `hw/xbox/nv2a`, `ui/thirdparty/stb_image`, `ui/thirdparty/fpng`, `subprojects/` |

### The one that is not noise: `-Wimplicit-function-declaration`

    hw/xbox/game-compat.c:20:5  implicit declaration of function 'qemu_log'

**This is a real defect and no incremental gate could ever have shown it**, because
`game-compat.c` is not in the compile set of any fold touching `pgraph`. It took
the full build to surface.

`game-compat.c` includes `qemu/osdep.h`, `hw/xbox/game-compat.h` and
`xemu-xbe.h`, and **not** `qemu/log.h`. Its non-Android `COMPAT_LOG` calls
`qemu_log`, which is declared in `include/qemu/log-for-trace.h:33` as

    void G_GNUC_PRINTF(1, 2) qemu_log(const char *fmt, ...);

Two consequences:

- **Format checking is silently off.** `G_GNUC_PRINTF(1, 2)` never applies to
  these calls, so a mismatch between a `COMPAT_LOG` format string and its
  arguments is not diagnosed at the one place it would be.
- **Calling a variadic function with no prototype in scope is undefined.** The
  compiler assumes `int qemu_log()` and does not know the call is variadic. On
  x86-64 SysV a variadic call must set `%al` to the number of vector registers
  used; it works today because every argument is an integer or a pointer.

It is **desktop-only**. Under `__ANDROID__`, `COMPAT_LOG` expands to
`__android_log_print`, which `<android/log.h>` declares properly -- so the
Android build is clean and cannot see this. That is the exact mirror of the
`vp.c` defect this gate was created for, with the arms swapped.

Fix is one line, `#include "qemu/log.h"`. **`hw/xbox/game-compat.c` is not in
`[lane.remote]`'s file list**, so this lane reports it rather than taking it.
`ui/xemu.c:1869` declaring `game_compat_check` as a nested extern is the same
feature's other half.

The remaining 77 are pre-existing tree noise, not a priority against accuracy
work, and none is in a file the current fold touched.

### Sites

    accel/tcg/cpu-exec.c:169  no previous prototype for 'tier1_clear_all_requests' [-Wmissing-prototypes]
    accel/tcg/cpu-exec.c:71  no previous prototype for 'xemu_set_tier1_threshold' [-Wmissing-prototypes]
    accel/tcg/cpu-exec.c:83  no previous prototype for 'xemu_get_tier1_threshold' [-Wmissing-prototypes]
    accel/tcg/cpu-exec.c:89  no previous prototype for 'xemu_get_tier1_stats' [-Wmissing-prototypes]
    accel/tcg/tb-maint.c:1223  nested extern declaration of 'hakux_tb_invalidated' [-Wnested-externs]
    accel/tcg/tb-maint.c:812  nested extern declaration of 'tier1_clear_all_requests' [-Wnested-externs]
    accel/tcg/translate-all.c:1021  no previous prototype for 'tb_gen_superblock' [-Wmissing-prototypes]
    accel/tcg/translate-all.c:1031  unused variable 'ti' [-Wunused-variable]
    hw/xbox/game-compat.c:20  implicit declaration of function 'qemu_log' [-Wimplicit-function-declaration]
    hw/xbox/game-compat.c:20  nested extern declaration of 'qemu_log' [-Wnested-externs]
    hw/xbox/nv2a/nv2a.c:60  no previous prototype for 'xemu_get_xbox_ram_ptr' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/gl/blit.c:346  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/gl/blit.c:396  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/gl/display.c:581  unused variable 'pg' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/gl/renderer.c:348  no previous prototype for 'pgraph_gl_force_register' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/gl/surface.c:1250  comparison of unsigned expression in '>= 0' is always true [-Wtype-limits]
    hw/xbox/nv2a/pgraph/gl/surface.c:1253  comparison of unsigned expression in '>= 0' is always true [-Wtype-limits]
    hw/xbox/nv2a/pgraph/gl/surface.c:922  'android_log_and_drain_gl_errors' defined but not used [-Wunused-function]
    hw/xbox/nv2a/pgraph/gl/texture.c:1031  unused variable 'row_pitch' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/gl/texture.c:1244  unused variable 'upload_slice_pitch' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/pgraph.c:214  no previous prototype for 'pgraph_method_histogram_log_and_reset' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/profile.c:458  unused variable 'idle_pct' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/blit.c:315  nested extern declaration of 'xemu_get_frame_skip' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/blit.c:494  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/vk/blit.c:544  declaration of 'dest' shadows a previous local [-Wshadow=compatible-local]
    hw/xbox/nv2a/pgraph/vk/buffer.c:28  no previous prototype for 'xemu_set_texture_cache_size' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/buffer.c:336  nested extern declaration of 'xemu_get_submit_frames' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/buffer.c:33  no previous prototype for 'xemu_get_texture_cache_size' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/buffer.c:57  unused variable 'gib' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/command.c:58  nested extern declaration of 'xemu_get_submit_frames' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/draw.c:2434  declaration of 'cmd' shadows a previous local [-Wshadow=local]
    hw/xbox/nv2a/pgraph/vk/draw.c:245  no previous prototype for 'xemu_set_fast_fences' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:250  no previous prototype for 'xemu_get_fast_fences' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:255  no previous prototype for 'xemu_set_skip_occlusion_queries' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:260  no previous prototype for 'xemu_get_skip_occlusion_queries' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:265  no previous prototype for 'xemu_set_draw_reorder' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:270  no previous prototype for 'xemu_get_draw_reorder' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:275  no previous prototype for 'xemu_set_draw_merge' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:280  no previous prototype for 'xemu_get_draw_merge' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:285  no previous prototype for 'xemu_set_async_compile' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:290  no previous prototype for 'xemu_get_async_compile' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:295  no previous prototype for 'xemu_set_frame_skip' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:300  no previous prototype for 'xemu_get_frame_skip' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:305  no previous prototype for 'xemu_set_submit_frames' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:3125  unused variable 'requested' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/draw.c:312  no previous prototype for 'xemu_get_submit_frames' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/draw.c:3517  unused variable 'r' [-Wunused-variable]
    hw/xbox/nv2a/pgraph/vk/draw.c:825  'destroy_framebuffers' defined but not used [-Wunused-function]
    hw/xbox/nv2a/pgraph/vk/instance.c:664  ' (' directive output may be truncated writing 2 bytes into a region of size between 1 and 256 [-Wformat-truncation=]
    hw/xbox/nv2a/pgraph/vk/instance.c:689  ' (v' directive output may be truncated writing 3 bytes into a region of size between 1 and 256 [-Wformat-truncation=]
    hw/xbox/nv2a/pgraph/vk/renderer.c:1416  nested extern declaration of 'xbox_ram_fp_active_ptr' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/renderer.c:1417  nested extern declaration of 'xbox_ram_fp_vram_base_ptr' [-Wnested-externs]
    hw/xbox/nv2a/pgraph/vk/renderer.c:1776  no previous prototype for 'pgraph_vk_force_register' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/renderer.c:599  function 'diag_json_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/renderer.c:603  function 'diag_json_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/renderer.c:628  function 'diag_diff_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/renderer.c:632  function 'diag_diff_append' might be a candidate for 'gnu_printf' format attribute [-Wsuggest-attribute=format]
    hw/xbox/nv2a/pgraph/vk/shaders.c:1127  no previous prototype for 'pgraph_vk_set_shader_warmup_progress_cb' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/shaders.c:322  'grow_descriptor_ring' defined but not used [-Wunused-function]
    hw/xbox/nv2a/pgraph/vk/shaders.c:937  no previous prototype for 'shader_module_key_persist' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/stb_image.h:4958  no previous prototype for 'stbi__unpremultiply_on_load_thread' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/stb_image_write.h:1128  no previous prototype for 'stbi_write_png_to_mem' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/stb_image_write.h:895  no previous prototype for 'stbi_zlib_compress' [-Wmissing-prototypes]
    hw/xbox/nv2a/pgraph/vk/texture.c:1680  variable 'did_s2t_copy' set but not used [-Wunused-but-set-variable]
    hw/xbox/nv2a/pgraph/vk/texture.c:1681  variable 'did_upload' set but not used [-Wunused-but-set-variable]
    hw/xbox/nv2a/pgraph/vk/texture.c:632  variable 'replaced' set but not used [-Wunused-but-set-variable]
    subprojects/VulkanMemoryAllocator/include/vk_mem_alloc.h:6840  unused variable 'name' [-Wunused-variable]
    system/main.c:46  'g_qemu_exit_status' defined but not used [-Wunused-variable]
    system/physmem.c:896  nested extern declaration of 'xbox_ram_fp_cb_count_ptr' [-Wnested-externs]
    system/physmem.c:928  nested extern declaration of 'xbox_ram_fp_cb_count_ptr' [-Wnested-externs]
    system/physmem.c:928  redundant redeclaration of 'xbox_ram_fp_cb_count_ptr' [-Wredundant-decls]
    target/i386/tcg/fpu_helper.c:365  no previous prototype for 'xemu_set_fp_safe' [-Wmissing-prototypes]
    target/i386/tcg/fpu_helper.c:370  no previous prototype for 'xemu_get_fp_safe' [-Wmissing-prototypes]
    ui/thirdparty/fpng/fpng.cpp:564  comparison of unsigned expression in '>= 0' is always true [-Wtype-limits]
    ui/thirdparty/stb_image/stb_image.h:4958  no previous prototype for 'stbi__unpremultiply_on_load_thread' [-Wmissing-prototypes]
    ui/xemu.c:130  'sdl_render_thread_id' defined but not used [-Wunused-variable]
    ui/xemu.c:1869  nested extern declaration of 'game_compat_check' [-Wnested-externs]
    ui/xemu.c:2375  'sleep_ns' defined but not used [-Wunused-function]

## Reading a gate log

Traps, all paid for:

- **`NINJA_EXIT` must come from ninja, not from the end of a pipeline.** Never
  pipe ninja through a filter and then read `$?`.
- **`[65/65] Linking target` is printed when ninja *starts* the edge.** On its
  own it is not evidence the link finished. A log showing neither compile
  steps nor `ninja: no work to do.` has been filtered, and its exit status
  cannot be attributed -- treat that as UNSOUND and re-run, do not report PASS.
- **`pgrep -x qemu-system-i386` can never match.** The name is 16 characters and
  the kernel caps `/proc/N/comm` at 15, which is what `pgrep -x` compares
  against. Measured against a live 16-character process: `pgrep -x
  qemu-system-i386` -> rc=1, `pgrep -x qemu-system-i38` -> rc=0. `gate.sh` used
  this as its "one emulator at a time" interlock and the guard was inert for its
  whole life -- the rule was held by hand, not by the script. pgrep does warn
  about this on stderr; the script discarded it with `2>&1`. It now compares the
  basename of `/proc/N/exe`, which is untruncated, and which cannot match the
  caller the way `pgrep -f` would. It caught a stale process on its first run.

  The general form, and the reason it is worth a paragraph: **a guard that never
  fires is indistinguishable from a guard that always passes.** Same family as
  the `pgrep -f` trap in `CLAUDE.md`. Give every interlock a positive control.
