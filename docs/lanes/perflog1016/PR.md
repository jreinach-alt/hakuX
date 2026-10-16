# perflog1016: a pause-menu switch for the perflog telemetry tier, and a "Mark this moment" button (#433)

State: draft

Lane: perflog1016            Issue: #433 (motivating defect #998)
Base: master @ 15a72e10dc
Files: docs/lanes/perflog1016/PR.md, docs/lanes/perflog1016/NOTES.md, docs/lanes/perflog1016/OUTBOX.md, hw/xbox/nv2a/debug.h, android/app/src/main/java/com/rfandango/haku_x/PauseMenuOverlay.kt
Prediction: pending (default-path A/B, registered before any device run)
Needs device: yes    Needs NDK: yes

Work in progress: inventory of the `NV2A_PERF_LOG` hooks first, then the
run-time switch for the ones that can carry a flag read at no cost while off.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
