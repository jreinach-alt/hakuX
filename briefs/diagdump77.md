# lane.diagdump77 -- a marker-file-armed frame dump for #77

Issue: #77 (Galleon deck/ground stipple, visible in a commercial title)
Base: master @ ab471cc80f902b2a4060842d78f55249a5ef83d1
Files: hw/xbox/nv2a/debug.h, hw/xbox/nv2a/pgraph/vk/renderer.c,
       android/app/src/main/cpp/xemu_android.cpp,
       android/app/src/main/java/com/rfandango/haku_x/LauncherActivity.kt

## What's already done

#77's investigation is extensive and is NOT asking you to find the mechanism.
Read nv2a_issues.toml's issue.77 entry first. Stipple fires 10-14 frames per
100 on the deck and ground; format, dimensions, level count, pitch, swizzle
flag, texture-matrix enable and texgen mode are all ruled out by measurement
(115 addresses, 22,493 binds, zero variation while the artifact is present).
Two instrument errors upstream of this were already found and corrected (a
2.25x capture upscale, a USB dialog dimming frames) -- do not re-derive those.

The investigation is now blocked on one capability gap, in the issue's own
words: "a marker-file-armed frame dump, the way apu.c arms the PCM capture.
There is none today -- nv2a_dbg_trigger_diag_frames is reachable only from
the Debug Capture button and LauncherActivity reads only rom_path. It must
dump WITHOUT the per-draw pgraph_vk_finish or it inherits the diag capture
blindness to merging and barriers."

## Goal

Give the harness a way to arm a per-draw frame dump from a marker file (no
button press, no LauncherActivity involvement beyond reading the marker),
that does NOT force pgraph_vk_finish() per draw the way the existing Debug
Capture path does -- that finish is what makes the current path blind to
merging and barrier behaviour, which is exactly what a stipple artifact this
subtle needs visible.

## Falsifier

A soak run armed via the marker file produces per-draw frame dumps for a
title that stipples (Galleon), and a diff against a dump taken with the
existing Debug Capture button shows the new path does NOT serialize with
pgraph_vk_finish per draw (no forced finish in the trace/log around each
dumped draw). If the new path still forces a finish, it has reproduced the
existing capability under a different trigger and answered nothing new.

## Done when

The marker-file arm exists, is documented (a line in AGENTS.md's device
table or equivalent), and one frame-dump run against Galleon is on disk with
its path posted to #77 -- along with confirmation (from the trace/log, not
assumption) that no per-draw finish was forced. Do not attempt to diagnose
the stipple mechanism itself from that dump; that is the next issue, not
this one.

## Out of scope

gl/renderer.c and gl/debug.c are lane.remote's -- this issue's dump path is
Vulkan-only (vk/renderer.c) and does not need the GL renderer touched.
