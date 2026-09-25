# A hakuX-built Adreno driver (a Turnip fork): first prove what a menu-loaded driver can reach, then build only that

Lane: turnipfork            Issue: #68 (context: the performance program), plus the issues named per candidate
Base: origin/master
Files: tools/turnip/**, docs/investigations/adreno-driver-feasibility.md, docs/lanes/turnipfork/**,
docs/testing/predictions/turnipfork-*.json. The Mesa tree lives OUTSIDE the repo: clone it into
`/home/justin/hakux-work/mesa-turnipfork/` and pin a commit. **No emulator (`hw/`, `android/`) edits in
this lane before Gate 1 passes.** Ask the board when you get there.
Needs device: yes, for the Gate 0 probes and later A/Bs, in bounded holds (Nova now; the Thor after the
0.5 sweeps). Needs NDK: yes (Mesa cross-build for Android arm64). Prediction: one per prototype.

## Who you are on this lane

You are a **principal GPU driver engineer**. You know Mesa's freedreno stack (Turnip, the ir3
compiler, and the a6xx/a7xx register database in `src/freedreno/registers/`), the KGSL kernel
interface (`/dev/kgsl-3d0`), how Adreno command streams are built (PM4, CP packets), and how
libadrenotools loads a replacement Vulkan driver into an unrooted app. You separate what the
**silicon** can do, what the **kernel** lets an app do, and what the **Vulkan API** exposes. Every
claim cites a source file and line, a register definition, or an on-device probe. If you cannot
cite it, it is a hypothesis and you label it so.

## Why (the owner, 2026-09-25)

"We're using off the shelf or generic-ish drivers from a third party, not designed for Hakux.
What's preventing us from doing our own Hakux drivers, specifically geared to do what NV2A does but
better?"

And the condition, verbatim: **"I don't want you to downplay or hand wave those hardware limits you
mentioned. If this requires deeper hardware access than just loading a custom driver through the
Hakux menus as we do today, I want to know that up front before we burn tokens on something no one
will want to do on their device."**

## What exists today

- hakuX links **libadrenotools** (`android/app/src/main/cpp/CMakeLists.txt:187-194`), and it has
  a GPU-driver picker (`GpuDriverHelper`, `PerGameSettingsActivity.kt:62-66`; pref
  `runtime_override_gpu_driver`).
- The fleet runs a third-party community Turnip build, `turnip_mrpurple_T30-toasted`. It is packaged
  as `meta.json` plus `vulkan.purple.so` (`/home/justin/hakux-work/turnip_mrpurple_T30-toasted.adpkg.zip`).
- The harness already A/Bs drivers: `docs/testing/_set_driver_pref.py`, `_driver_ab_verdict.py`,
  and #77's T30/T26/stock A/B.

## The hard limits (state them in your report as limits, not as obstacles to argue away)

1. **Silicon.** The Adreno 740 has no NV2A register combiners, no W-buffering, no NV2A texture
   swizzle or palette formats, and none of the NV2A's exact clip or raster rules as fixed-function
   hardware. Those stay shader (or geometry) emulation whoever writes the driver. A driver can make
   them cheaper to compile, bind and run. It cannot add silicon.
2. **Access.** A driver loaded through the hakuX menu runs as the app, in userspace, on the stock
   kernel.
   - It can build any command stream the kernel accepts from an app, compile shaders, and allocate
     and map memory through KGSL.
   - It cannot change GPU or CPU clocks or governors, kernel protections (the CP's protected
     register ranges), or firmware (SQE/GMU).
   - Those need root or an unlocked bootloader, and **they are out of scope. Users will not do that.**
3. **Reach.** Snapdragon (Adreno 6xx/7xx) only. Mali and Xclipse devices keep the generic Vulkan
   path, so every hakuX-driver feature needs a fallback. Adreno generations differ (a740, a750,
   A8xx), so the fork must track them.

## Gate 0: the access report (FIRST; no build work before it is posted)

For each candidate below, classify it with evidence into one of four tiers:
- **T0**, plain Vulkan on any driver;
- **T1**, needs our own Turnip build, loaded through the hakuX menu or bundled in the APK, no root;
- **T2**, needs root, a custom kernel, or an unlocked bootloader;
- **T3**, impossible: silicon or signed firmware.

For each T1 item, also say how the user gets it: bundled in the APK and selected by default, or a
menu choice.

**Candidates** (add your own, and classify them the same way):
- **(a) Hardware clip and viewport controls.** Mesa's register database names controls such as
  perspective-division, viewport-transform and clip disables (check `GRAS_CL_CNTL` and friends on
  a7xx). Could one of them give NV2A's clipping semantics natively?
  - That would replace the geometry-shader "external wedge" for one-negative-w triangles
    (`hw/xbox/nv2a/pgraph/glsl/geom.c`, #223, PR #250), which is slow on Adreno.
  - Say whether the registers are writable from an app's command stream (kernel protect lists on
    this kernel), and what they actually do: bench it, don't infer it from names.
- **(b) Zero-copy guest memory.** Map the emulator's guest RAM (an app allocation) into the GPU
  address space, so surfaces and textures read and write it directly as the NV2A did. That would
  remove the stale-copy bug class (#184, #262, maybe #303).
  - Is `VK_EXT_external_memory_host`, or KGSL user-memory import, available on these devices'
    kernels? Which caching modes can be mapped, and what coherence do they give?
  - What do NV2A swizzle and format differences leave uncovered?
- **(c) Depth formats and precision** that match NV2A Z16/Z24 fixed and float depth exactly, given
  how #266 arises (Z24S8 stored as D32_SFLOAT; a saturated fragment fails LEQUAL).
- **(d) Register-combiner compile stutter and bind cost.** Measure shader-compile time in our frames
  (the ir3 compile is inside the driver). Rank the options: `VK_EXT_graphics_pipeline_library`,
  driver-side caches, and combiner "ubershaders". Pipeline derivatives give no benefit on modern
  drivers; say whether that holds for Turnip.
- **(e) Driver CPU cost.** How much of the render thread's time is inside the driver versus our
  pgraph code? Take a simpleperf run with Turnip symbols. The 09-11 profile could not attribute it.
  This number decides whether a leaner submission path is worth anything.
- **(f) GMEM/tiling control:** tile-memory use for NV2A-style frames (clears, blits,
  surface-as-texture).

**Post the report on #68** as a table: candidate, tier, evidence (file:line or probe),
user-facing delivery, and the expected gain with its evidence grade (measured, bounded,
hypothesis). Then say plainly which candidates are dropped because they are T2 or T3.

**The host relays the report to the owner before Gate 1.** You continue into Gate 1 on T0/T1 items
only.

## Gate 1: build a hakuX Turnip and prototype the best T1 item

1. **Reproducible build.** Build Turnip from a pinned Mesa commit for Android arm64 (meson plus an
   NDK cross file) under `tools/turnip/`. Package it in the same shape as the T30 package
   (`meta.json` + `vulkan.<name>.so`). Show that our unmodified build renders the pgraph smoke
   suites identically to T30 before you change anything. That is your control.
2. **Prototype the top T1 candidate** as a private Vulkan extension or a driver-side behaviour
   behind an env var or build flag. The emulator side (a small consumer in `hw/`) needs a board
   grant, so ask on #68.
3. **Register a prediction, then A/B on one device:**
   - the pixels it should move and must not move (pgraph arms);
   - frame time on the reference titles.

   Report it win or lose.

## Device rules

- **Driver changes are device config.** Set them with `docs/testing/_set_driver_pref.py`, under a
  hold of at most 60 minutes.
- **Restore T30** afterwards and verify by read-back. A driver left selected changes every other
  lane's measurements. Host toolsmith defect 14 exists because of exactly that kind of leftover.
- **Never** leave a custom driver installed or selected on a device when your hold ends.

## Do not

- **Propose anything T2 or T3 for users.** A probe that needs root is out; say what it would have
  measured.
- **Edit `hw/` or `android/` before Gate 1**, or without a board grant.
- **Touch `tcg/**`, `util/cacheflush.c`** (lane.perfarch's) or **`accel/tcg/*`** (lane.tcgchurn's).
- **Trigger CI as a self-check.**

## Done when

- The Gate 0 report is on #68 and in `docs/investigations/adreno-driver-feasibility.md`.
- The reproducible build exists, and its control matches T30.
- One T1 prototype has an arm verdict, or NOTES say why no T1 candidate is worth building.
