# The Adreno driver landscape, and what this emulator needs from it

Written 2026-09-11, before evaluating drivers, so that the evaluation tests
the right things. Device in hand: Retroid Pocket Nova, QCS8550 (Snapdragon
8 Gen 2 class), **Adreno 740**, Android 13.

Every accuracy number this project has was measured on exactly one driver,
and the build users install defaults to a different one. That is the reason
this survey exists.

## What hakuX actually requires

From the code, not from folklore. `hw/xbox/nv2a/pgraph/vk/instance.c`.

**Hard gate.** A device is rejected outright only if it reports Vulkan below
**1.1** or lacks a queue family with graphics and compute
(`is_device_suitable`). Vulkan 1.3 is *not* required: below it the renderer
asks for `VK_EXT_extended_dynamic_state` instead of relying on the core
feature.

**Required device extensions (Android).** All four, or the device is not
used:

| extension | why |
|---|---|
| `VK_ANDROID_external_memory_android_hardware_buffer` | presentation goes through AHardwareBuffer |
| `VK_KHR_external_memory` | same |
| `VK_EXT_queue_family_foreign` | same |
| `VK_KHR_external_semaphore_fd` | same |

The desktop build deliberately does not require the FD interop pair, because
its display path has a download fallback; Android has none.

**Required feature.** `geometryShader`, and it is not a formality: the
generator emits a geometry stage for every `LINES` and `TRIANGLES` primitive,
and quads are rewritten to triangles, so essentially every draw goes through
one.

**Optional features**, each used if present: `depthClamp`,
`fillModeNonSolid`, `occlusionQueryPrecise`, `samplerAnisotropy`,
`shaderClipDistance`, `shaderTessellationAndGeometryPointSize`, `wideLines`,
`textureCompressionBC`.

**Optional extensions**: `VK_EXT_custom_border_color`, `VK_EXT_memory_budget`,
`VK_EXT_extended_dynamic_state3`, and `VK_EXT_extended_dynamic_state` below
Vulkan 1.3.

## The landscape: two implementations, many packagers

There are only two real Vulkan implementations for Adreno. Everything else is
packaging.

**Qualcomm proprietary.** Ships in the vendor image
(`/vendor/lib64/egl/`). Qualcomm also publishes updatable drivers through the
Play Store on some devices; this one does not support that path, which the
emulator logs as *"Updatable production driver is not supported on the
device"*. So on the Nova the stock driver is whatever the OEM shipped: build
dated 27 Dec 2023, driver version 0676.53.

**Mesa Turnip.** The open-source Vulkan driver for Adreno, part of Mesa,
maintained by the Freedreno community. Vulkan 1.3 on Adreno 6xx and 7xx.
There is no central Turnip download: community maintainers build from Mesa,
apply their own patches, and package as adrenotools `.adpkg.zip` archives
with a `meta.json`. The ones that come up repeatedly:

| packager | character |
|---|---|
| MrPurple666 / purple-turnip | tracks upstream Mesa, aims at stability and standards compliance |
| K11MCH1 (Kimchi) / AdrenoToolsDrivers | performance patches and device hacks, the de facto aggregator others link to |
| StevenMXZ, The412Banner, WinNative-Emu | scheduled or per-commit CI builds from Mesa main, newest hardware first |
| v3kt0r-87, nihui, zoerakk | further build scripts and mirrors |

Naming is a maintainer's own scheme, not Mesa's. This device carries
**"Turnip Adreno Driver T30 (@Mr_Purple_666)", Mesa 26.3.0-T30-1.4.359**.
The Retro Tech Dad video used **Turnip v23.3.0-R5**, a Mesa nearly three
years older. A `turnip_mrpurple_T26-toasted.adpkg.zip` also sits in the
device's Downloads, unused. Three different drivers across three
observations of the same emulator.

Software implementations (lavapipe, SwiftShader) exist and the desktop lane
uses lavapipe, but they are not an option on the handheld.

## Measured coverage on this device

Both from the emulator's own startup log, same device, same build.

| requirement | Qualcomm 0676.53 | Turnip T30 (Mesa 26.3.0) |
|---|---|---|
| `geometryShader` (required) | available | available |
| `depthClamp` | available | available |
| `fillModeNonSolid` | available | available |
| `occlusionQueryPrecise` | available | available |
| `samplerAnisotropy` | available | available |
| `shaderClipDistance` | available | available |
| `wideLines` | available | available |
| `textureCompressionBC` | available | available |
| `shaderTessellationAndGeometryPointSize` | **missing** | available |
| `VK_EXT_custom_border_color` | enabled | enabled |
| `VK_KHR_external_semaphore_fd` | enabled | enabled |
| `VK_EXT_memory_budget` | **not available** | enabled |
| `VK_EXT_extended_dynamic_state3` | **not available** | enabled |

Three gaps, all on the stock driver, none on Turnip.

`shaderTessellationAndGeometryPointSize` is the one that matters most,
because the geometry shader the emulator puts in front of every draw writes
`gl_PointSize`. Mesa enabled that feature in Turnip in 22.2.0 (September
2022), so every Turnip build in circulation has it.

One further difference worth recording: the two drivers report different
memory heaps for the same phone, 11,265 MB on stock against 8,448 MB on
Turnip. The renderer buckets that figure to pick its budget, and both land in
the same 1,536 MB tier here, but a device near a tier boundary would be
sized differently depending only on which driver is loaded.

## Assessment

**The working hypothesis, that non-stock drivers all have full coverage and
differ only at the margins, is right about Turnip and wrong about the stock
driver.** Every Turnip build inherits Mesa's feature set, so a packager's
choices are patches, performance tuning and GMEM strategy, not coverage. The
gaps are on the vendor driver, and that is precisely the one the release
build falls back to, because a custom driver is installed per application
package and the freshly installed `com.jreinach.hakux` has none.

That has two consequences worth separating:

1. **A correctness question.** Every golden comparison either lane has ever
   run was on Turnip. Which residuals are ours and which are Mesa's is
   unknown, and the remote lane is fitting rules to those numbers.
2. **A user question.** Whatever the emulator does on the stock driver is
   what someone sees on first launch, and nobody has measured it.

## What to evaluate, and how

The evaluation should answer, in order:

1. **Does the stock driver change the golden numbers?** Same build, same
   discs, driver switched. Any suite that moves is driver-dependent and
   should be excluded from accuracy work until it is understood.
2. **Does Turnip version matter?** T30 against the older T26 already on the
   device, and ideally against something near the video's 23.3.0. If the
   numbers are stable across three years of Mesa, the accuracy lane can stop
   worrying about driver drift.
3. **What does each cost in frame time and memory?** Not covered anywhere in
   the tracker.

Method note: a driver can be installed without the app's UI. The loader reads
`files/gpu_driver/meta.json` for a `libraryName` and loads that `.so` from
the same directory, so on a debuggable build a driver can be placed, swapped
or disabled over adb, which makes an automated sweep across drivers possible.
Moving `meta.json` aside is enough to fall back to the system driver.

## Sources

- [PPSSPP, Custom Adreno graphics drivers](https://www.ppsspp.org/docs/reference/custom-drivers/)
- [K11MCH1/AdrenoToolsDrivers](https://github.com/K11MCH1/AdrenoToolsDrivers)
- [Mesa 22.2.0 release notes](https://docs.mesa3d.org/relnotes/22.2.0.html)
- [Mesa freedreno driver documentation](https://docs.mesa3d.org/drivers/freedreno.html)
- [The Definitive Guide to Android Turnip Drivers & Hardware Compatibility (2026)](https://pocket-gaming.org/2026/06/15/the-definitive-guide-to-android-turnip-drivers-hardware-compatibility-2026/)
- [The412Banner/Banners-Turnip](https://github.com/The412Banner/Banners-Turnip)
- [StevenMXZ/Adreno-Tools-Drivers](https://github.com/StevenMXZ/Adreno-Tools-Drivers)
- Device measurements: this repository's own startup logs, 2026-09-10 and 2026-09-11.
