Lane: async413            Issue: #413
Base: master @ 01e62d8d1c
Files: android/app/src/main/cpp/xemu_android.cpp, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, docs/lanes/async413/NOTES.md, docs/lanes/async413/asyncwin.py, docs/lanes/async413/pr-body.md, docs/testing/predictions/async413-blinx.json, docs/testing/predictions/async413-doa.json
Prediction: registering (legs S, V, F on DOA Ultimate, Nova, cold, two builds)
Needs device: yes    Needs NDK: no

Measures whether async shader compilation (the existing `async_compile` setting, off by default) removes DOA Ultimate's cold-cache compile stalls (13.8 s title-stage load, 14.8 s fight load, 15.2 s mid-fight hitch; lane.pipeline413), and at what visual cost.

Fix commit d1e5278311 flips the native default (`xemu_android.cpp:959`) and the two UI defaults (`SettingsActivity.kt:69`, `:543`). Nothing else.

In progress: legs and results go here.

Release note (performance): shader compiles no longer freeze the game; a new effect may appear a moment late the first time it is seen.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
