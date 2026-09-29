# lane.gpl569 (#569 P5: Vulkan graphics pipeline libraries)

Issue #569, PR #594. Branched from master at 1922ce1cad.

## Step 0: does the fleet's Turnip support it? Yes (posted on #569)

- **The fleet driver.** Every handheld loads `vulkan.purple.so`, which reports
  `PurpleVK-public Adreno (TM) 740 (git-62ac221a33)`. That is T30, a fork of
  Mesa 26.3.0-devel.
- **The T30 binary** (`~/hakux-work/drv/T30/vulkan.purple.so`, unstripped)
  contains `tu_pipeline_builder_parse_libraries`, Turnip's library-link path.
- **Upstream Turnip at `4c18636110f0`**, the tree `tools/turnip/build.sh`
  pins, sets all four in `tu_device.cc` unconditionally:
  `EXT_graphics_pipeline_library`, `graphicsPipelineLibrary`,
  `graphicsPipelineLibraryFastLinking` and
  `graphicsPipelineLibraryIndependentInterpolationDecoration`.
- **hakuX's own extension dump could not answer this,** because it lists only
  the extensions hakuX enables. `instance.c` now logs
  `[gpl569] ext= lib= fast= interp= requested= mode=` (tag `hakuX-build`) on
  every start, whatever the switch says.

## The change (6aaa1142ad; default flipped on in a84fda7ed4)

- **Switch:** `HAKUX_GPL` in the environment, or `HAKUX_GPL_DEFAULT` at build
  time.
  - 0 is the monolithic path, unchanged.
  - 1 fast-links from libraries.
  - 2 does the same, then links the same libraries again with LTO on the
    compile worker and swaps that pipeline in.
  - The extension and feature are requested only when the mode is non-zero.
- **Four libraries,** each cached in a `GHashTable` keyed by the bytes of a
  zeroed struct (`vk/compile_worker.c`):

  | Library | Key |
  |---|---|
  | VI | bindings, attributes, topology |
  | PR | vs id, gs id, rasterizer fields, attachment formats |
  | FS | fs id, depth/stencil state (whole struct from `flags` on), formats |
  | FO | blend attachment, formats; blend constants only when they are not dynamic |

  Every key also carries the dynamic-state list.
- **Module id** is a hash of the module's SPIR-V plus its length
  (`ShaderModuleInfo::gpl_id`), not the `VkShaderModule` handle, which can be
  reused after a module is freed.
- **Render pass for the libraries:** one per (color format, zeta format),
  obtained through `get_render_pass()` with the load ops zeroed. Every hakuX
  render pass with the same formats is identically defined, because
  `create_render_pass()` reads only the formats.
- **One fixed pipeline layout** (`pgraph_vk_gpl_layout`) carries the full
  16-attribute vertex push range. `push_template_index()` returns 16 for a
  binding under it, so descriptors are pushed with the template built from an
  identically defined layout.
  - **No `INDEPENDENT_SETS`.** Every library gets the same whole layout, which
    is the case the flag exists to relax. This departs from the plan's R6
    wording, deliberately.
- **Fallback:** a failed library or link falls back to a monolithic create
  under the same layout, and is counted as `fb=`.
- **LTO swap (mode 2):** the fast-linked pipeline is kept alive in
  `gpl_retired_pipeline` until the entry is evicted, since a command buffer
  in flight may use it. `pre_evict` refuses an entry whose LTO job is pending,
  and `finalize_pipeline_cache` waits for LTO jobs first.
- **Async compile on:** the worker builds the libraries and the link (the same
  `PipelineCreateParams`, with `gpl` set).
- **The fragment slot, for lane.uberspike569:** FS is its own library, so a
  prebuilt fragment ubershader library can be linked against any PR library.
  To do that, create it with `r->gpl.layout` and the per-format-pair render
  pass, and insert it in `r->gpl.libs[GPL_FS]` under its own key.
- **Instrument:** `[gpl569] mode= links= link_ms= link_fail= fb= new=vi/pr/fs/fo
  hit= fail= lib_ms= libs= flush= lto=done/fail/swapped lto_ms= heap_mb=`
  (tag `hakuX-perf`), with running totals.
  - It prints on every link that created a library, and on every 32nd link.
  - Library and link creates go through
    `pgraph_vk_create_graphics_pipeline_fb()`, so `[shd413]` dpc_ms is still
    the render thread's whole create time.
  - LTO creates bypass that wrapper, because they are not a stall.

## Checks done without a device

- All four changed files type-check with the NDK clang line from
  `compile_commands.json` (`-Wall`). They add no new warnings.
- `check_android_guards.py`: ok.
- **Desktop build: not run.** This host has no desktop build tree (AGENTS.md,
  "Building").

## Legs (registered before any run)

- **`gpl569-pixels-inert.json`** (arms job, 2 runs per arm): the full 27-suite
  sweep, A 6aaa1142ad against B a84fda7ed4, every capture inside its measured
  band. B's logcat must show mode=1 and links > 0.
- **`gpl569-doa-soak.json`**, hand-queued: cold DOA perflog soaks on the
  Nova, in the order A, B, then B2 (b_ref with `HAKUX_GPL=2`). The judge is
  `gpljudge.py`.

  | Leg | Registered |
  |---|---|
  | S1 | create ms per miss, B/A <= 0.70 (flagged if below 0.23, GPL's bound) |
  | S2 | first load after play, B/A <= 0.70 |
  | S3 | PR library hit share >= 0.50 |
  | D1 | GPU Tot ms B/A <= 1.10 and gfps >= 0.90 |
  | D2 | B2 GPU ms / A <= 1.03, with swaps > 0 |
  | MEM | a reading: library counts and device-local heap |

- **`gpl569-blinx-soak.json`**: the same three arms on Blinx, for D1 and D2.

## Runs

- **Queued 2026-09-28 17:37 PDT**, all on the Nova, which is on hostops' charge
  hold until about 18:00-19:00 PDT. All three are `--perflog`, survey route,
  440 s, `HAKUX_RELEASE_PRIO=1`:
  - `1-1790642263-gpl569-834655`: DOA A (6aaa1142ad, off), cold.
  - `1-1790642270-gpl569-837983`: DOA B (a84fda7ed4, mode 1), cold.
  - `1-1790642271-gpl569-838619`: DOA B2 (a84fda7ed4, `--env HAKUX_GPL=2`),
    warm.
  - These are the pilot, about 26.5 min of device time. They must be reviewed,
    and `pilots/gpl569.ok` written, before the Blinx trio goes in.
  - A plain-priority duplicate of A (`1790642249-gpl569-828024`) was queued
    first by mistake and removed from the queue unclaimed. To get release
    priority on an issue without the 0.5 label, pass `HAKUX_RELEASE_PRIO=1`.
- **Pixel arm:** `gpl569-pixels-inert.json`, pushed at 6dd14f86f6; the arms
  job queues it.
- **Preflight** (`--allow-tracker`): passed at 6dd14f86f6.

## Do not repeat

- Do not read the Turnip `.so` string table for extension support. It is
  Mesa's whole generated registry. The symbol `tu_pipeline_builder_parse_libraries`
  and upstream `tu_device.cc` are the evidence; the `[gpl569]` init line is
  the proof.
- `git log -S` on `~/hakux-work/mesa-turnipfork` is a blobless clone, so it
  fetches from the network and runs for minutes. Grep the checked-out tree
  instead.
