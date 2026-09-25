# Running the Khronos validation layer on a handheld

The desktop lane runs validation routinely (`AGENTS.md`, "The Khronos validation
layer runs on the lane"). On Android the layer is already packaged, yet four
separate things keep it off in an ordinary dispatcher run. Every device logcat
from before 2026-09-24 is blind to VUIDs because of them. Measured by
lane.vklayer34 (#34, `docs/lanes/vklayer34/NOTES.md`).

## Packaging: already done

Debug apks ship `lib/arm64-v8a/libVkLayer_khronos_validation.so` from
`android/app/src/debug/jniLibs/` (moved there from main/ by `0ae07ee5fa`,
2026-09-07). It is Khronos `android-binaries-1.4.341.0`, sha256
`a11e2d33f8473fdc50cde07d50c330c23de88223a2c5f566ccabe62f0ffe2308`. Release
apks do not carry it. The Android loader finds layers in the app's native
library directory, so no adb push and no setprop are needed.

## The four blocks

| # | block | where | what gets past it |
|---|---|---|---|
| 1 | The dispatcher's logcat allow-list ends `*:S` and does not name `xemu-vk-validation` | `docs/testing/dispatcher.sh` LOGCAT_SPEC | log under `hakuX-lane`, or have toolsmith add `xemu-vk-validation:V` |
| 2 | An adrenotools custom driver (the fleet normally loads `vulkan.purple.so`) is entered through `volkInitializeCustom`. That skips the loader, and with it every layer | `vk/instance.c` create_instance, `MainActivity.initializeGpuDriver` | the system driver: `runtime_override_gpu_driver=system`, or force it in a ref |
| 3 | The `validation_layers` pref defaults false, and `request.sh --env` writes `env_vars`, a different key | `xemu_android.cpp` (`GetPrefBool(... "validation_layers" ...)`) | force it in a ref, or set the pref on the device |
| 4 | `VK_EXT_debug_utils` is looked for only with `pLayerName = NULL` | `add_optional_instance_extension_names` | also query the layer's own list, as the ref does. On Thor the messenger was installed (`debug_utils enabled = 1`), but the ref's log line does not say which list supplied the extension, so whether this block bites on its own is still open |

A consequence: **validation cannot see the custom-driver configuration the
fleet normally runs.** A validation result is about the system Qualcomm driver.

## How the first run was done

Measurement ref `e2c9fef860` (reverted by the next commit on lane/vklayer34)
forces the system driver and `validation_layers = true`. It logs everything
under `hakuX-lane` as `vkval id=<pMessageIdName> | <message>`. Queue it as a
suites request with `--ref` and `--no-expect`. Then run:

    python3 docs/lanes/vklayer34/count_vuids.py <dispatch result dir>

This prints the positive-control lines and a count per VUID. **If any control
line is missing the count is VOID, not 0**: a zero from a layer that never
loaded is what every earlier logcat shows.

The layer caps each message id at 10 reports by default, so a count above 10
is a floor.

## Result, 2026-09-24 (Thor, Adreno 740 system driver, apk_sha 6b99875f661e)

Clear, 32/32 captures, logcat covers process start to clean exit, control PASS:

| n | severity | VUID |
|---|---|---|
| 1 | error | `VUID-VkShaderModuleCreateInfo-pCode-08740`: SPIR-V capability GeometryPointSize declared without `shaderTessellationAndGeometryPointSize` |

Source: `glsl/geom.c` writes `gl_PointSize` in the geometry shader whenever
`!opts.gles`. `vk/instance.c` asks for `shaderTessellationAndGeometryPointSize`
as optional, so the feature is not enabled on a device that lacks it. The
Adreno 740 system driver evidently lacks it and lavapipe evidently has it,
which is why the desktop lane could not see this.
