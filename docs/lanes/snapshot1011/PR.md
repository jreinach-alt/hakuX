# snapshot1011: save states phase 0 -- a save and a load that survive a scene change (#433)

Lane: snapshot1011           Issue: #433 (0.5)
Base: master @ 6d8947bb47 (origin/master merged at ff47c466c1)
State: ready
Files: android/app/src/main/cpp/CMakeLists.txt, android/app/src/main/cpp/xemu_snapshots_stub.c, ui/xemu-snapshots.c, ui/xemu-snapshots.h, hw/xbox/nv2a/nv2a.c, hw/xbox/mcpx/apu/apu.c, migration/savevm.c, docs/testing/nv2a_index.json, docs/lanes/snapshot1011/**
Prediction: none: no arm (the evidence is an env-driven test sequence's logcat and frames on the Nova)
Needs device: yes (Nova only)    Needs NDK: yes
Release note (none): the save-state engine builds on Android and is driven only by the HAKUX_SNAPSHOT_TEST test sequence; there is no player-facing control yet.

## What changes

Phase 0 of save states: internal snapshots in the HDD's qcow2, written by
`ui/xemu-snapshots.c` over QEMU's migration code, built on Android in place
of the stub, with the device state and versioning a load needs to come back
to the same scene.

- `ui/xemu-snapshots.c` is built on Android; its GL thumbnail code is compiled
  only off Android, and the stub keeps only the thumbnail stand-ins.
- Save and load start a paused machine first and pause it again after, so the
  GPU and APU state handlers always run; a load restarts the machine itself, so
  the frontend's resume path does not clear the loaded GPU waits.
- Saved now: vertex-attribute state, the lighting ring and fog state, and the
  other pgraph and PRAMDAC state no section carried. After a load every
  renderer generation counter moves and every dirty map is set, so the first
  draw rebuilds from the loaded state. The APU monitor FIFO is emptied on load.
- `XEMU_SNAPSHOT_DATA_VERSION` 2: the header adds the schema fingerprint, the
  build, the title ID, a disc hash and the controller layout. The header is
  read with `bdrv_snapshot_load_tmp` and a mismatch is refused before
  `load_snapshot` resets the machine. The pmc-enable subsection has `.needed`.
- `HAKUX_SNAPSHOT_TEST=<seconds>` runs the five phase-0 criteria on a main-loop
  timer and logs one `[snap]` line per step.

## Results on the Nova (187: Ride or Die)

| Run | Ref | Result |
|---|---|---|
| 1-1791753422-snapshot1011-2350466 | a8c3031263 | criteria 2-5 pass; c1 hashes match, but A and B are the same spot on the start line |
| 1-1791764800-snapshot1011-813455 | 4c4e5f98a9 | all five pass; A = pre-race cutscene, B = race, first frame after the load = the cutscene |

| | save_ms | load_ms | header check | state size |
|---|---|---|---|---|
| c1 (save A, load A from B) | 263, 338 | 116, 123 | 3 ms | 59.02, 58.39 MB |
| c3 (20 cycles per run, 40/40 ok each) | median 307, 291; max 489 | median 107, 98; max 116 | 2-12 ms | 58.4-59.1 MB |
| c4 (requested while paused) | 296, 261 | 107, 98 | 10, 2 ms | 59.09, 58.85 MB |
| c5 (different controller layout) | 294, 466 | refused before reset | 5 ms | 59.08, 58.83 MB |

60 s after the c1 load: six distinct region hashes in both runs, frames moving,
no crash line; run 2's frames continue 94 s past the sequence's end at 59.94 Hz
VBLANK. No black screen after any load. Both slots are deleted at the end
(snapshots=0), and the disk harvest is identical across both runs and matches
the title's previous run (55530036 `fa079adf42d5`).

## Left for phase 1

- `build` (commit plus native build ID) is refused on mismatch, so a state loads
  only into the APK that made it.
- On a title run the state lives in `titles.qcow2`, which is rebuilt from the
  goldens before every run; nothing carries over between runs.
- The controller layout must match between save and load.
- The inline vertex buffer between BEGIN and END is not saved; Android states
  have no thumbnail.
- A load rewinds the game but not `route.sh`; a route verb that loads a state
  and resumes from the mark is phase 1's.

Checks: `docs/testing/preflight.sh --allow-tracker` passes; `docs/testing/jobs/selftest.sh`
3377 passed, 0 failed, all 136 fragments.

Details: `docs/lanes/snapshot1011/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
