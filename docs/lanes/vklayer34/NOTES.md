# lane.vklayer34 -- #34 validation layer on Adreno

Started 2026-09-24 from master @ ec1b67a92d. PR #217. Device doc: docs/testing/vk_validation_android.md.

## The brief's premise was false: the layer is already in every debug apk

The brief says "nothing in android/ packages libVkLayer_khronos_validation.so"
and asks for a gradle property to ship it. But
`android/app/src/debug/jniLibs/arm64-v8a/libVkLayer_khronos_validation.so` is
tracked on master, where `0ae07ee5fa` (2026-09-07) moved it from main/ to debug/.
It is byte-identical to the Khronos `android-binaries-1.4.341.0` release
(sha256 `a11e2d33f8473fdc50cde07d50c330c23de88223a2c5f566ccabe62f0ffe2308`).
The dispatcher's three most recent builds, including `ec1b67a92d.apk`,
all carry `lib/arm64-v8a/libVkLayer_khronos_validation.so`.

The gradle property I wrote first (fetch 1.4.357.0 into build/, pinned
sha256) failed `mergeDebugJniLibFolders` with "Duplicate resources" against
that file, which is how this came to light. I reverted it. **Do not re-add a
packaging property**: the packaging already works. The brief's other
falsifier, "a default build must have no layer in lib/", is the opposite of
master's deliberate state since 09-07, so I did not act on it either.

## Why 266 (now 1152) device logcats show no VUID: four independent blocks

`survey_logcats.py` over all 973 result dirs / 1152 logcat files, 2026-09-24:

| block | evidence |
|---|---|
| 1. Logcat allow-list drops the tag | `dispatcher.sh:1089` LOGCAT_SPEC ends in `*:S` and has no `xemu-vk-validation` (nor `hakuX-stderr`, nor `MainActivity`). No run could ever show a VUID or the layer list, whatever the device did. 0 of 1152 logcats contain "Available instance layers". |
| 2. Custom driver bypasses the loader | 857/1152 logcats show `Loading custom Vulkan driver: vulkan.purple.so` (hakuX tag). adrenotools -> `volkInitializeCustom` (instance.c) calls the driver's own vkGetInstanceProcAddr, so no loader and no layers. The other 295 carry no driver line at all. |
| 3. Validation is off by default | `validation_layers` pref defaults false (xemu_android.cpp:919). No request field can set it: `--env` writes `env_vars`, a different key. |
| 4. debug_utils is looked for in the wrong list | `add_optional_instance_extension_names` queries `pLayerName = NULL` only. The Android loader lists driver extensions there, so VK_EXT_debug_utils may exist only in the layer's own list. Then no messenger gets installed. Unverified; the instrumentation ref logs which case applies. |

So "0 VUIDs on device" has so far been a count by an instrument that could not
see a VUID ([[what-the-instrument-cannot-see]]).

## The device run: one instrumentation ref, reverted immediately

This is the skew44 "one ref per mode" pattern. Commit C1 on this branch:
- MainActivity: always use the system driver (fixes block 2)
- xemu_android.cpp: `validation_layers = true` (block 3)
- instance.c: all validation logging to `hakuX-lane`, which is captured (block 1),
  with `pMessageIdName` so VUIDs count by id; debug_utils taken from the
  layer's extension list when the NULL list lacks it (block 4)

C2 reverts C1, so the PR's net diff is this directory only. Type-checked both
TUs with the dispatcher build tree's NDK clang lines (`typecheck_tu.py`): exit 0.

Request: suites `Clear`, ref C1, `--no-expect` (a survey, not an arm).

Positive control (all must appear in logcat1.txt, tag hakuX-lane):
`vkval GPU driver: forced system driver`, `vkval validation_layers forced on`,
`layer[..]: VK_LAYER_KHRONOS_validation`, `Validation layers ENABLED`,
`vkval debug_utils enabled = 1`. If any is missing the count is VOID, not 0.

## Results

Request `1790317606-vklayer34-4071708`: Thor (serial bdc158a5, Adreno 740,
**system** driver), ref e2c9fef860, apk_sha `6b99875f661e`, Clear 32/32
captures (26 exact). The logcat covers process start (23:27:23) to clean exit
(`qemu_main returned 0`, 23:27:45). `count_vuids.py`: all 5 control lines OK.

| n | sev | VUID |
|---|---|---|
| 1 | E | `VUID-VkShaderModuleCreateInfo-pCode-08740`: GeometryPointSize capability without `shaderTessellationAndGeometryPointSize` |

**So the falsifier ("Adreno count = 0") is refuted by one VUID the desktop could
not see.** Source: `glsl/geom.c:413` and `:508` write `gl_PointSize` in the GS
when `!opts.gles`. `vk/instance.c:846` requests the feature as optional, so it
is off on a device that lacks it. The fix is to gate those writes on the
enabled feature, and it belongs to whoever takes #34's finding; it is not in
this lane's Files. Spec consequence: without the feature a GS-emitted point
has size 1.0.

Not resolved: whether block 4 bites on its own. The `debug_utils enabled = 1`
line does not say which extension list supplied it. Also, the layer caps each
id at 10 reports by default, so a count above 10 would be a floor.

Caveat that limits the result: this is the system Qualcomm driver. The fleet's
normal configuration (adrenotools custom driver) bypasses the loader, so no
layer can validate it.

## Do not repeat

- Don't write a gradle property to package the layer. It is already in
  `src/debug/jniLibs` and a second copy fails the merge as a duplicate.
- Don't read a zero VUID count from any pre-09-24 device logcat as evidence:
  block 1 alone makes it structurally zero.

## For toolsmith (instrument owner), not done here

- Add `xemu-vk-validation:V` (and `hakuX-stderr:E`) to LOGCAT_SPEC.
- A request field for a bool pref / the driver override would make a
  validation run queueable without a code ref.
