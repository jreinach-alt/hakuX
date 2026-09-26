# A hakuX Adreno driver: what a menu-loaded driver can reach

Gate 0 of lane.turnipfork (#68), written 2026-09-25. It answers the owner's
question: *"What's preventing us from doing our own Hakux drivers,
specifically geared to do what NV2A does but better?"*, and the condition
attached to it: to say up front if anything needs deeper hardware access than
loading a driver through the hakuX menu.

**The short answer.** Nothing on the list needs root to *try*. But no
candidate has a measured gain that only our own driver can deliver. The large
costs we have measured sit in our own code and in plain-Vulkan choices, not
in the driver. A driver fork is worth building as an instrument: a
reproducible build we can symbolize, patch and bisect. It is not yet worth
building as a product. Gate 1 (below) measured the two remaining
candidates, (f) and (g), and neither changes that.

Sources: Mesa `main` pinned at `4c18636110f0ef2e1d4cecdbfbf4b7126c1d22cc`
(26.3.0-devel, the same series as T30; cloned outside the repo at
`~/hakux-work/mesa-turnipfork`). The fleet driver is T30,
`PurpleVK 26.3.0-devel (git-62ac221a33)`. That sha is the packager's fork and
not an upstream commit. Paths below are relative to the Mesa tree unless they
start with `hw/` or `docs/`.

## The limits, stated as limits

1. **Silicon (T3).** The Adreno 740 has no NV2A register combiners, no
   W-buffer, no Morton-swizzled texture or render-target layout (its layouts
   are linear, tiled and UBWC, `src/freedreno/fdl/`), no palette formats, no
   24-bit float depth format, and no NV2A clip or raster rules as fixed
   function. Those remain shader or geometry emulation whoever writes the
   driver. A driver can make them cheaper to compile, bind and run. It
   cannot add silicon.
2. **Access (T2, out of scope).** A driver loaded through the hakuX menu runs
   as the app, in userspace, on the stock kernel. It cannot change GPU or CPU
   clocks or governors, the CP's protected register ranges, or SQE/GMU
   firmware. Those need root or an unlocked bootloader, and users will not do
   that.
3. **Reach.** Snapdragon only (Adreno 6xx/7xx; A8xx is in Mesa too). Mali and
   Xclipse keep the generic Vulkan path, so every driver-side feature needs a
   plain-Vulkan fallback. Every T1 item below therefore has to be written
   twice: once in the driver, once as the fallback.

What an app's command stream *can* write is decided per register range, not
per bit. `CP_PROTECT[32]` entries are address ranges (`a6xx.xml:293-295`).
Any register Turnip already writes from userspace is therefore writable with
any bit pattern.

## Tiers

- **T0**: plain Vulkan on any driver (or on any Turnip, with no build of ours)
- **T1**: needs our own Turnip build, loaded through the hakuX menu or bundled in the APK, no root
- **T2**: needs root, a custom kernel or an unlocked bootloader. Out of scope.
- **T3**: impossible: silicon or signed firmware

Evidence grades: **measured** (a device run or profile on disk),
**bounded** (an upper limit derived from a measurement), **hypothesis**
(reasoned, not yet measured).

## The report

| # | candidate | tier | evidence | user delivery | expected gain (grade) |
|---|---|---|---|---|---|
| a | Hardware clip / viewport controls (`GRAS_CL_CNTL`) | **T1** to set. The one NV2A divergence it could fix is a **T3** precision limit that is already solved at **T0** | Writable: Turnip writes `GRAS_CL_CNTL` on every pipeline (`tu_pipeline.cc:3524-3531`, `vp_clip_code_ignore=1`), and sets `clip_disable`, `vp_xform_disable` and `persp_division_disable` itself in its 3D blit path (`tu_clear_blit.cc:1114-1119`). Fields: `a6xx.xml:1422-1436`; `VP_CLIP_CODE_IGNORE` is marked as a guess there. Semantics: Adreno's clipper already produces NV2A's external wedge except at \|w\| ratios >= 2^120, where it draws nothing (`hw/xbox/nv2a/pgraph/glsl/geom.c:87-95`). PR #250 fixed exactly those rows at T0, in the geometry shader (+560,741 px on W_param, 451/451). | Would have to be bundled and default-on to matter | **About zero.** Bounded above by the cost of #250's wedge path. That cost is itself unmeasured (hypothesis: the GS output grew from 3 to 8 vertices, `geom.c:413-416`), and is measurable at T0 by a frame-time A/B of `a8691063e6` against `537ffb91ed`. The GS stays either way: every filled triangle needs it for `calc_triz` (`geom.c:409-422`). What `clip_disable` does to a mixed-sign triangle on the a740 is **unmeasured**. |
| b1 | GPU-visible guest RAM (the mapping) | **T0** on Turnip. Host-pointer import is **T1** | Turnip exposes `VK_EXT_map_memory_placed` (`tu_device.cc:367`) and cached, I/O-coherent memory when KGSL reports it (`tu_knl_kgsl.cc:303-311`, `1921-1923`). Guest RAM can *be* a Vulkan allocation placed where QEMU wants it, so nothing needs importing. `VK_EXT_external_memory_host` is **not** in Turnip's extension table (`get_device_extensions`, `tu_device.cc:205-439`). Adding it would use `IOCTL_KGSL_MAP_USER_MEM` / `KGSL_MEMFLAGS_USERMEM_ADDR` (`msm_kgsl.h:209-224,689`). Whether the production kernel lets an app do that is **unmeasured**. The stock Qualcomm driver's support for `map_memory_placed` is unknown. | T0: no driver needed on Turnip | Enabling only; no gain on its own |
| b2 | Zero-copy surfaces and textures (render and sample in guest layout) | **T0** for linear colour surfaces and DXT textures. **T3** for swizzled surfaces, Z24S8 and palettes | Linear images with an explicit row pitch: `VK_EXT_image_drm_format_modifier` (`tu_device.cc:358`). BC1-3 sample natively (`textureCompressionBC`, landscape doc). NV2A Morton swizzle is not an Adreno layout. Z24S8 is kept as D32F+S8, 8 bytes, because Adreno's float-to-unorm24 quantiser rounds differently from the NV2A (`hw/.../vk/surface.c:3946-3968`); guest memory cannot hold that. Rendering to linear memory gives up UBWC. | T0, emulator-side | **Hypothesis.** It removes the stale-copy class only for linear, natively formatted colour surfaces. Each of #184, #262 and #303 has to be classified by format and swizzle before this is worth anything. It is a large `hw/` rewrite, not a driver feature. |
| c | Depth formats and precision (Z16, Z24, float Z, #266) | **T0** (already done) / **T3** for native NV2A float depth | Z16 maps to D16 (`surface.c:3961`). Z24 is exact through D32F plus shader quantisation (`hw/.../glsl/psh.c:3642-3697`). No format carries NV2A F16/F24 depth. `RB_DEPTH_CNTL` has no rounding control (`a6xx.xml:2461-2474`). Varyings are fp32 in silicon, so a driver cannot change the slope interpolation #266 points at. Cost side: a shader that writes depth turns LRZ/early-Z off unless it declares a depth layout (`tu_lrz.cc:1238-1260`, `tu_shader.cc:3741-3752`). | none | **None from a driver.** A T0 `DepthGreater`/`DepthLess` layout where our depth is monotone might restore LRZ (hypothesis). |
| d | Register-combiner compile stutter and bind cost | **T0** | Measured: ir3/NIR compile is **3 of 11,129** samples on the renderer thread in 20 s of Crimson Skies gameplay (profile below). In steady play, compiling is invisible. Stutter is episodic, and this profile did not capture a first encounter. Emulator: async compile exists but **defaults off** (`hw/.../vk/draw.c:33`, `SettingsActivity.kt:69`). The VkPipelineCache is saved to disk (`draw.c:1356-1373`), and Turnip serialises ir3 binaries into it. Turnip implements GPL with fast-link (`tu_device.cc:349`, `tu_pipeline.cc:1752-2133`). **Pipeline derivatives do nothing on Turnip**: `src/freedreno/vulkan` never reads `DERIVATIVE` or `basePipeline` (0 hits). | T0, settings or emulator | Ranked: (1) async compile on by default, (2) GPL for the combiner FS, (3) ubershader (costs FS ALU on every fragment). A driver adds nothing Turnip lacks. **Stutter is unmeasured**: needs a cold-cache trace. |
| e | Driver CPU cost | **T1** to make leaner, and **not worth it** | **Measured**, below: Turnip is **7.2%** (inclusive) of the renderer thread, about **2 ms per emulator-bound frame**. Our own `fast_hash` (22.3%) and `tlb_reset_dirty` (21.6%) on the same thread are each 3x the whole driver. | n/a | **Bounded: at most about 2 ms per frame** of renderer time, and the renderer is not the critical path. The guest is blocked on the renderer 8.7 ms per frame (`frame-pacing-and-parallelism.md`, "Step 1"). |
| f | GMEM / tiling control | **T0** partly (load/store ops, pass boundaries). A hakuX autotune policy is **T1** | Turnip picks sysmem or GMEM per render pass through `tu_autotune` (in the profile: `process_entries`, `on_submit`, `find_rp_history`). Driconf `tu_autotune_algorithm` exists, and DXVK is pinned to `prefer_sysmem` (`00-turnip-defaults.conf:36-40`). `TU_DEBUG=sysmem` / `gmem` are parsed by T30 (strings present). The app sets `env_vars` before the driver loads (`xemu_android.cpp:796-809`, called at `:1239`, driver at `:1784`). **So this A/B needs no build**: `request.sh --env TU_DEBUG=sysmem`. | T0 measurement now; T1 policy only if it pays | **Measured, flat** (Gate 1 results below): autotune, forced sysmem and forced GMEM all run Crimson Skies at a median 29 gfps, guest frame 33.3 ms, 2 replicates each. The title sits at its 30 Hz cap, so this rules out a cost and cannot show a gain. |
| g *(added)* | Texel-coordinate rounding mode (`TPL1_MODE_CNTL.TEXCOORDROUNDMODE`: truncate or round-to-nearest-even) | **T0 on Turnip** (driconf through env). A per-draw choice is **T1** | `tu_cmd_buffer.cc:2290-2296` programs it from driconf `tu_use_tex_coord_round_nearest_even_mode`, default truncate ("Vulkan requires truncation, D3D rounds to nearest even", `00-turnip-defaults.conf:19-24`). Driconf defaults are overridden by the environment (`util/xmlconfig.c:424-439`), which Android reads with `getenv` first (`util/os_misc.c:238`). T30 has the option (string present). `NEARESTMIPSNAP` is next to it (`a6xx.xml:4474-4493`). | T0 today; bundled per-draw only if texture suites split | **Measured** (Gate 1 results below): device-wide RNE is worse (127 rows worse, 21 better). A 3D-only policy would gain 8,140 of 1,408,643 differing pixels. The register is written once per device (`tu6_init_static_regs`, `tu_cmd_buffer.cc:2166,2290`), so per-texture needs a patch: **T1, not worth building**. |
| h *(added)* | GPU power constraint (a clock *request*, not control) | **T1**, and a **hypothesis** that the kernel honours it | KGSL has per-context and per-submission `PWR_CONSTRAINT` (`msm_kgsl.h:51,103,336,1234-1252`). Turnip never sets it (`tu_knl_kgsl.cc:54-56`). The governor may ignore it. Clock or governor *control* is **T2**. | bundled | **Hypothesis**; low value unless the GPU is shown to be the bound. |
| i *(added)* | Native combiners, W-buffer, swizzle, palette, float depth, NV2A clip and raster rules | **T3** | Limit 1 above | none | none |
| j *(added)* | Clocks, governors, protected registers, SQE/GMU firmware | **T2 / T3** | Limit 2 above | none | none |

**Dropped as T2 or T3:** (i) native NV2A fixed function (combiners,
W-buffer, Morton layouts, palettes, float depth, bit-exact unorm24
quantisation); (j) clocks, governors, CP-protected registers, SQE/GMU
firmware; and (a)'s only real target, the clipper's precision failure at
\|w\| ratios >= 2^120, which is silicon. (a) survives only as a T1
curiosity with a near-zero ceiling. No candidate needs root to be *tried*,
and nothing here will be proposed that does.

## (e) in detail: the driver share, measured

The 09-11 Crimson Skies profile (`~/hakux-work/perf/perf.data`, 20 s of
gameplay, 44,637 `cpu-clock` samples at 1 kHz, `--call-graph dwarf`) was
recorded while T30 was installed. It "could not attribute" the driver only
because nobody symbolized it. T30 ships unstripped (`.symtab` 701 KB,
`.debug_info` 783 KB). Its build-id
`dd183c112c83ecf192de025d70c80d66e2cceb10` matches the recorded mapping
`files/gpu_driver/vulkan.purple.so` exactly, so the NDK's host simpleperf
symbolizes it with `--symfs`. Script: `tools/turnip/driver_share.py`.

| thread (role) | samples | driver self | driver inclusive | kernel under driver |
|---|---:|---:|---:|---:|
| `qemu_main` (guest CPU) | 28,679 | 0 | 0 | 0 |
| `Thread-6` (pfifo: all Vulkan translation) | 11,129 | 545 (4.9%) | **799 (7.2%)** | 159 |
| `Thread-7` (render: submit, fences) | 830 | 248 | 611 | 291 |
| `SDLThread` | 2,687 | 0 | 17 | 17 |

- The pfifo thread's top self symbols are ours: `fast_hash` 2,480 and
  `tlb_reset_dirty` 2,399, against 799 for the whole driver.
- Inside the driver, cost is spread across state emission and descriptors
  (`vk_dynamic_graphics_state_copy`, `tu_emit_draw_state`, `tu6_draw_common`,
  descriptor updates, `tu_CmdBindPipeline`). No single hotspot exists to
  patch.
- 94 pfifo samples unwind to `tu_GetPhysicalDeviceMemoryProperties2`, which
  is plausibly VMA's budget query run per frame. The caller frame is
  unresolved, so this attribution is a **hypothesis**. It would be a cheap
  T0 fix if real.
- `Thread-7`'s driver time is `kgsl_queue_submit` into the kernel. That runs
  in parallel with the pfifo thread, not on the guest's critical path.

**Date:** a 09-11 build (`33557e82ab`..`9edf95861d` era), before the #223
wedge and every renderer change since. The ratio (ours about 6x the driver)
is large enough that a fresh profile is unlikely to invert it, but it has not
been re-measured. `tools/turnip/driver_share.py` re-runs on any new
`perf.data`.

## What this means for Gate 1

1. **Build the fork anyway, as an instrument.** It gives a reproducible,
   symbolized and patchable driver, a control identical to T30, and the
   only way to bench (a)'s `clip_disable` semantics or (h)'s power
   constraint.
2. **Run the two no-build A/Bs first,** because they decide whether any T1
   policy is worth writing:
   - (g) `tu_use_tex_coord_round_nearest_even_mode=true`: pixel arms on the
     texture suites.
   - (f) `TU_DEBUG=sysmem` against `gmem`: frame time on the four reference
     titles.

   Both go through `request.sh --env` on T30, with no driver swap and no
   device hold.
3. **If neither moves anything, there is no T1 candidate worth building**,
   and the NOTES will say so. The performance program's measured levers are
   ours: `fast_hash` and `tlb_reset_dirty` on the renderer thread, and TCG on
   the guest thread.

## Gate 1 results (2026-09-26): no T1 candidate is worth building

**Control: passed.** Our unmodified build (`turnip_hakux_4c18636110f0_none`,
`vulkan.hakux.so` sha256 `f94a1acc…`) renders the 12 texture suites
pixel-identical to T30: 220 of 220 captures, and every scores row matches.
The run was made by the host (#68 comment 5843130427). adrenotools loads it
by path, so the soname difference does not matter.

**(g) texel-coordinate rounding, measured.** Both runs were on the Nova,
with T30, ref `a7f7c8bda9`, apk `9395b70d7cf1`, and the same 220 captures.
The base run is `1790370789-turnipfork-3702404`. The RNE run is
`1790370791-turnipfork-3706030`, with
`tu_use_tex_coord_round_nearest_even_mode=true` set through the environment.
That the RNE run moved pixels proves the variable reached T30's driconf.

| suite | rows | base differing px | RNE differing px | rows better / worse |
|---|---:|---:|---:|---|
| Volume_texture | 20 | 144,715 | 139,612 | 16 / 1 |
| Texture_3D_as_2D | 2 | 3,037 | **0** | 2 / 0 |
| Bump_map | 40 | 365,126 | 371,745 | 3 / 35 |
| Texture_cubemap | 72 | 2,287 | 15,993 | 0 / 72 |
| Texture_Matrix | 11 | 326 | 3,133 | 0 / 7 |
| Texture_border | 18 | 4,600 | 7,087 | 0 / 6 |
| Texgen, Texture_perspective(+enable) | 15 | 746,764 | 747,279 | 0 / 6 |
| Texture_format, LOD_Bias, WrapMode | 42 | 141,788 | 141,788 | 0 / 0 |
| **total** | 220 | 1,408,643 | 1,426,637 | 21 / 127 |

Truncation, which is Vulkan's rule and T30's default, is the better
device-wide choice. Only 3D textures prefer RNE. A driver policy of "RNE when
a 3D view is bound" would move at most 8,140 differing pixels (0.58% of these
suites), and would take 2 rows to exact. That is the ceiling. Several things
would sit against it:
- A patched `tu6_init_static_regs`, plus per-draw state tracking.
- A 13 MB driver bundled in the APK.
- A plain-Vulkan fallback for Mali and Xclipse.

**Hypothesis, unmeasured:** the same rows might be reachable at T0 with a
half-subtexel bias on 3D coordinates in our shader. That would differ from
RNE only at exact ties. It is an `hw/` change for a pgraph lane, not a driver
change.

**(f) GMEM policy, measured flat.** All runs were on the Nova, T30, Crimson
Skies, 240 s hands-off, 2 replicates per arm, with the first 10 s dropped.

| arm | runs | median gfps | mean gfps | median guest frame (ms) |
|---|---|---:|---:|---:|
| autotune (default) | `…3734492`, `…3734624` | 29.0, 29.0 | 29.01, 29.05 | 33.3, 33.3 |
| `TU_DEBUG=sysmem` | `…3734531`, `…3734656` | 29.0, 29.0 | 29.18, 29.27 | 33.3, 33.3 |
| `TU_DEBUG=gmem` | `…3734588`, `…3734707` | 29.0, 29.0 | 29.07, 29.04 | 33.3, 33.3 |

The game frame is two vblanks in every arm. What this can see is a cost:
neither forced mode costs a frame. What it cannot see is a gain: at the cap,
GPU time saved does not show in gfps. Nothing we have measured puts GPU time
on the critical path. So a hakuX autotune policy has no measured target.

**Conclusion.** Each T1 item, and what stands against building it:

| item | what stands against it |
|---|---|
| (a) | a near-zero ceiling after PR #250 |
| (e) | at most about 2 ms per frame of a thread that is not the critical path |
| (f) | flat |
| (g) | 0.58% of one suite family's pixels, with a T0 route |
| (h) | the GPU is not shown to be the bound |

None is worth prototyping, so the lane ends without a prototype. The fork
remains as an instrument:
- `tools/turnip/build.sh` gives a pinned, symbolized build.
- The control shows it is interchangeable with T30.
- `host-tools/turnip_control.sh` is the path to run it.

It is worth reopening if a profile shows the GPU, or the driver, on the
critical path.

User delivery, for any T1 item that survives: bundle it in the APK and
select it by default on Adreno 6xx/7xx only, with the menu as the override
and the system driver as the fallback everywhere else. T30's `.so` is 18.9 MB
unstripped; a stripped build is about 13 MB (`.text` 3.9 MB plus `.rodata`
9.2 MB).
