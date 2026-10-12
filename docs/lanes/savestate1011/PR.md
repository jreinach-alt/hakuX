# savestate1011: save states as files -- slots 0-9, compression, undo, auto-save and auto-load (#433)

Lane: savestate1011           Issue: #433 (0.5)
Base: master @ 5326de78b2 (merged at 382ed38ed4; contains lane/snapshot1011)
State: draft
Files: ui/xemu-snapshots.c, ui/xemu-snapshots.h, migration/savevm.c, android/app/src/main/cpp/CMakeLists.txt, android/app/src/main/cpp/xemu_android.cpp, android/app/src/main/cpp/savestate/**, android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PauseMenuOverlay.kt, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsManager.kt, android/app/src/main/java/com/rfandango/haku_x/SaveState*.kt, android/app/src/main/res/values/strings.xml, android/app/src/main/res/layout/savestate_*, docs/lanes/savestate1011/**, docs/testing/nv2a_index.json
Prediction: none: no arm (the evidence is an env-driven test sequence's logcat and frames on the Nova)
Needs device: yes (Nova only)    Needs NDK: yes
Release note (other): save states in the pause menu: ten slots per game stored as files on the device, optional compression, undo save and undo load, auto-save on quit and auto-load at boot.

Save states move out of the hard-disk image into one file per slot, with a
disk-only snapshot that keeps the hard disk consistent with the loaded RAM.

Details: `docs/lanes/savestate1011/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
