# release05: v0.5.0 release notes (#433, 0.5)

State: ready

Lane: release05          Issue: none (#433 umbrella)
Base: master @ c6e0a63852
Files: docs/releases/v0.5.0.md, docs/lanes/release05/PR.md
Prediction: none (release notes only)
Needs device: no    Needs NDK: no

`docs/releases/v0.5.0.md`, in the v0.4.0-j1 / v0.4.1-j1 format, covering
v0.4.1-j1..master:

- Three install notes: the Android 10 / ARMv8.2 LSE floor (#427, minSdk
  26 -> 29, the "Unsupported CPU" gate), alongside-install, ES-DE files.
- New: save states, several games folders, ubershader, pipeline pre-build,
  Fast renderer paths, GPU surface reuse, the Thor bottom screen.
- Fixed: NFS Most Wanted audio and race start, GTA San Andreas sky,
  RalliSport Challenge's rival cars (#804), Forza's in-race slowdown (#414),
  the per-title sysmem render mode (AUF, DOA Ultimate), VBLANK rate (#65)
  and HD-mode PAL detection, three crashes, FRNDINT.
- Speed and Rendering: default-on changes only, each checked present at
  cf628f179f; figures only where the commit body carries them.
- Reporting a bug: the issue forms, Debug Capture off in this release and
  how to switch it on, the About links (contrib1012, pubdocs1012,
  debugcap1012).

Left out: opt-in switches that stay off (`HAKUX_IDLE_HALT`,
`HAKUX_PFIFOWAIT`, `HAKUX_ZETA_D24` and the rest), instrumentation, harness
and status-page work, the #44 skew bound (reset to a per-title override
before cf628f179f), the OpenGL ES renderer's parity work (Vulkan is the
Android default), and two audio changes not yet confirmed by ear. #311 is
not re-announced; v0.4.1-j1 carried it.

Release note (none): this is the release note.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
