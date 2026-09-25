# #34 -- package the Khronos validation layer in the Android build and count VUIDs on Adreno

Issue: #34 (Vulkan validation layer: four open findings from the desktop lane)
Lane: lane.vklayer34 (board wave 150, 2026-09-25)
Base: current origin/master (ec1b67a92d at dispatch) -- fetch before building.
Files: android/app/build.gradle.kts, docs/lanes/vklayer34/**,
       docs/testing/vk_validation_android.md

## State

All eight desktop findings measure zero (fixes e7998e7fdd, 83a47188f7,
0a428d5b62, 8f49518936, 9e39ca431a, 136b15a40d, 4b42532466 are ancestors of
HEAD). What is open is the Adreno confirmation: nothing in android/ packages
libVkLayer_khronos_validation.so, so vk/instance.c:111 finds no layer and all
266 device logcats under dispatch/results carry no VUID.

## Goal

A debug-only way to ship VK_LAYER_KHRONOS_validation in the apk (a gradle
property, off by default; the layer .so is fetched into the build dir, never
committed), then one device run with `validation_layers = true` and a VUID count
from logcat tag `xemu-vk-validation`. Report the count per VUID on #34.

## Falsifier

If Adreno confirms the desktop result, the device VUID count over one Clear
run is 0. Any VUID that appears is a finding the desktop lane could not see;
list it. Positive control: the layer must be provably loaded (logcat shows the
layer found) -- a count of 0 from an unloaded layer is the state we are in now.
A default build (property unset) must produce a byte-identical apk manifest and
no layer in lib/.

## Done when

Default apk unchanged; property-on apk loads the layer on the device; the VUID
table is on #34 with the run's apk_sha; the tracker row is updated by the board,
not by you (report on the issue). Build needs JDK 21 via JAVA_HOME and the
desktop build too (AGENTS.md). Device: use the dispatcher, not raw adb input.
