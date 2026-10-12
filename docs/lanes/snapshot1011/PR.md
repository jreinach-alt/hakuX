# snapshot1011: save states phase 0 -- a save and a load that survive a scene change (#433)

Lane: snapshot1011           Issue: #433 (0.5)
Base: master @ 6d8947bb47
State: draft
Files: android/app/src/main/cpp/CMakeLists.txt, android/app/src/main/cpp/xemu_snapshots_stub.c, ui/xemu-snapshots.c, ui/xemu-snapshots.h, hw/xbox/nv2a/nv2a.c, hw/xbox/mcpx/apu/apu.c, migration/savevm.c, docs/testing/nv2a_index.json, docs/lanes/snapshot1011/**
Prediction: none: no arm (the evidence is an env-driven test sequence's logcat and frames on the Nova)
Needs device: yes (Nova only)    Needs NDK: yes
Release note (none): the save-state engine builds on Android and is driven only by the HAKUX_SNAPSHOT_TEST test sequence; there is no player-facing control yet.

## What changes

Phase 0 of save states: internal snapshots in the HDD's qcow2, written by
`ui/xemu-snapshots.c` over QEMU's migration code, built on Android in place
of the stub, with the device state and versioning a load needs to come back
to the same scene.

The test sequence (`HAKUX_SNAPSHOT_TEST=<seconds>`) runs the five phase-0
criteria on a main-loop timer and logs one `[snap]` line per step; see
`docs/lanes/snapshot1011/NOTES.md` sections 1 and 2. Results go in section 3.
