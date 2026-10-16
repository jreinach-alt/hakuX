# icon1016: hakuX CE app icon (#433)

State: draft

Lane: icon1016            Issue: #433
Base: master @ 37ba9bd8bf
Files: android/app/src/main/res/drawable/ic_launcher_fg.xml, android/app/src/main/res/drawable/ic_launcher_mono.xml, android/app/src/main/res/values/ic_launcher_background.xml, android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml, android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml, docs/lanes/icon1016/**
Prediction: none: analysis-only (resource-only Android change; no perf/pixel claim to predict, see NOTES.md for the geometry check instead)
Needs device: yes (Thor, bdc158a5)
Needs NDK: no
Release note (other): New app icon.

This is resource-only Android code (adaptive-icon drawables + one colour
value), so the fold runs the device-run gate.

Replaces the adaptive icon's foreground, monochrome and background layers
with the owner's new mark (`hakux-work/svg/hakux-svg-master.svg` and
`hakux-svg-monochrome.svg`), expressed as Android vector drawables since no
SVG rasterizer is installed on this machine and installing one was ruled
out. Vector drawables have no stroke-dasharray, so the 270-degree dashed
ring is drawn as a single explicit arc path (`M 0,-39 A 39,39 0 1 1 -39,0`);
the inner subtle ring and the lowercase-h glyph are reused with minimal
syntax changes. minSdk is 33, so the legacy PNG mipmaps are already dead
weight and stay untouched (listed in NOTES.md).

Background colour changes from `#000000` to `#0B1110` (the banner's
background) — the owner's two source files carry no background layer, so
this is a design choice made here rather than a direct transcription; flagged
for the owner in NOTES.md.

Status: implementation and XML-parse verification done. Still to do in this
session: Gradle `assembleDebug` build check, `aapt dump badging` on the
resulting APK, and a Thor visual check per AGENTS.md's device-lease and
fan-temperature rules. Will update this PR and NOTES.md with results before
marking ready.
