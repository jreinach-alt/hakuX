# savestate1011: save states as files -- slots 0-9, compression, undo, auto-save and auto-load (#433)

Lane: savestate1011           Issue: #433 (0.5)
Base: master @ 00fde8afb3 (merged at 399f819d82; contains lane/snapshot1011)
State: ready
Files: ui/xemu-snapshots.c, ui/xemu-snapshots.h, migration/savevm.c, android/app/src/main/cpp/CMakeLists.txt, android/app/src/main/cpp/xemu_android.cpp, android/app/src/main/cpp/savestate/**, android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PauseMenuOverlay.kt, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsManager.kt, android/app/src/main/java/com/rfandango/haku_x/SaveState*.kt, android/app/src/main/res/values/strings.xml, android/app/src/main/res/layout/savestate_*, docs/lanes/savestate1011/**, docs/testing/nv2a_index.json
Prediction: none: no arm (the evidence is an env-driven test sequence's logcat and frames on the Nova)
Needs device: yes (Nova only)    Needs NDK: yes
Release note (other): save states in the pause menu: ten slots per game stored as files on the device, optional compression, undo save and undo load, auto-save on quit and auto-load at boot.

Save states move out of the hard-disk image into one file per slot. Each
state also takes a disk-only snapshot of the HDD, so a load always puts the
hard disk back to match the RAM it loads.

## What a player gets

- **Pause menu:** Save state, Load state, Undo load and Undo save.
  - Save and Load open a list of slots 0-9. Each slot shows its date and
    time, or "Empty".
  - A slot that cannot be loaded is greyed out with the reason.
  - The list works with the gamepad and with touch.
  - A toast after each save or load gives the slot and the ms.
- **Settings, Save states:**
  - the folder: the path is shown, with a picker and Reset to default;
  - compression, Off / On;
  - Auto-load last state;
  - Auto-save on quit.
- The three switches can be overridden per game (the folder cannot).

## Disk design

- Every state takes a disk-only internal qcow2 snapshot of the HDD at the
  same instant (`hxs-<root8>-<title>-s<N>-<uuid8>`). The state file names it.
- A load goes to that snapshot first, then loads RAM from the file. Game
  saves written to E: after the state are rolled back; the setting says so.
- A slot's snapshot is deleted when the slot is overwritten or deleted. A
  startup pass deletes snapshots that no file names.
- A non-qcow2 HDD is refused for both save and load (`hdd-not-qcow2`).
- **Cost:**
  - 18-29 ms inside the pause;
  - +64 KB of image the first time;
  - +0.38 MB over 34 min of play with 160 saves and 160 loads (1461611).
- Where a game rewrites data while a snapshot holds the old copy, the
  image keeps one old copy per live snapshot. The case seen was 187's
  73.5 MB boot cache, rewritten after a load (1797227).
- **The disk test (1797227):**
  - the save was at t=8, then 187 wrote 73.5 MB to Z;
  - after the load at t=40, every partition hashes as at the save, with
    FATX intact, and the game runs;
  - after Undo load, the disk is as it was before the load;
  - E: is unchanged across the run.

## Compatibility

- **Refused** on the schema fingerprint, title, disc, controller layout or a
  missing disk snapshot, before anything stops.
- **Recorded but never refused on:** the build. A state from another build
  with the same schema loads (F7). A one-field schema mutant is refused
  (F6).

## Compression: what it costs, and the recommendation

1-1791781811-savestate1011-1461611: 187: Ride or Die's attract race on the
Nova, 20 cycles per option, 160 saves and 160 loads, all ok.

| Option | Pause, median / p95 | File safe on disk | Size | CPU | Hitches |
|---|---|---|---|---|---|
| Off (raw) | 67 / 75 ms | 202 ms | 41.6 MB | 0 | 0 |
| **On: zstd 1, 4 threads, inside the pause** | **76 / 86 ms** | **127 ms** | **10.1 MB** | 59 ms | 0 |
| LZ4, 1 thread, inside the pause | 89 / 94 ms | 154 ms | 14.1 MB | 32 ms | 0 |
| zstd 3, 1 thread, inside the pause | 139 / 148 ms | 186 ms | 9.5 MB | 82 ms | 0 |
| raw, then compress on an idle core (zstd 3) | 69 / 77 ms | raw 202 ms, compressed 844 ms | 9.5 MB | 598 ms | 0 |
| raw, then compress on an idle core (LZ4) | 69 / 73 ms | raw 204 ms, compressed 405 ms | 14.1 MB | 185 ms | 0 |
| Dolphin's: copy in the pause, write after (zstd 3) | 59 / 63 ms | 714 ms | 9.5 MB | 585 ms | 0 |

- A hitch is a frame of 100 ms or more in the 10 s after a save. The worst
  frame was 33-47 ms in every row, against 32 ms with no save.
- Loads take the same in every row: 127-129 ms paused, 174-178 ms in all.
  Keeping the undo-load state is 60 ms of that pause.

**On = zstd level 1 on four threads, inside the pause. On is the default.**
Against Off, On pauses 9 ms longer (under one frame). In exchange:

- the file is safe 75 ms sooner;
- it is a quarter of the size;
- nothing runs after the game resumes.

**The idea of compressing on an idle core** saves 7 ms of pause against On.
It leaves the 42 MB file in place for most of a second, writes 51 MB of
flash per save, and takes ten times the CPU on a little core. It is not
recommended.

**Dolphin's way** pauses 17 ms less than On, but its file is not safe until
714 ms.

**No third setting:** the options pause within about a frame of each other.

## Runs (Nova)

| Result id | What | Outcome |
|---|---|---|
| 1-1791778805-savestate1011-904197 | pilot: functional + 2 measure cycles | F1-F11 pass |
| 1-1791781811-savestate1011-1461611 | measure, 20 cycles x 8 options | 160 saves, 160 loads ok; the table above |
| 1-1791781810-savestate1011-1461488 | disk + functional | disk checks pass; 4 checks read a still title screen as stopped; fixed in a7d713effe |
| 1-1791783647-savestate1011-1797227 | disk + functional, a7d713effe | every step passes (D1, D2, F1-F11, F5b) |

Every run used a scratch state folder and deleted every `hxs-` snapshot
before it ended (0 left), and E: was unchanged.

## Owner checks

The harness cannot prove these. The dispatcher rebuilds the title disk on
every run, so a disk snapshot never survives into the next run. The harness
also has no hands on the pause menu.

1. Pause menu with the gamepad: save to slot 0, play, load slot 0. B closes
   the list.
2. The same with touch.
3. Undo load, Undo save, Undo save again (redo). Each is greyed out when
   there is nothing to undo.
4. Settings folder: the default path is shown, Change folder puts new saves
   there, and Reset to default goes back.
5. Auto-save on quit, then auto-load: Exit writes `auto.hxs`. The next start
   of the same title jumps there within about 2 s. Undo load goes back to the
   fresh boot.
6. Swipe-away with auto-save on: best effort only (`onStop` starts the save;
   Android may end the process first).
7. With On a slot file is about 10 MB, with Off about 42 MB (187).

## What is left

- **Per-game save-state section:** not reachable yet. It needs an entry in
  `SettingsIndexActivity.kt`, outside this lane's files. `WAITING` asks for
  the grant.
- **Loading during background compression:** untested on the device. Both
  runs' compression finished before the test's load at 1 s. Background mode
  is reachable only from the test driver, because On is inline.
- **Thumbnails** and **"start without auto-load"** in the game list are not
  done. After an auto-load, Undo load returns to the fresh boot.
- **A setting to skip the undo-load copy:** not done. The copy is 60 ms of
  the 128 ms load pause.

## Checks

- `docs/testing/preflight.sh --allow-tracker`: passed on 3cd2bec334.
- `docs/testing/jobs/selftest.sh`, four shards, on 3cd2bec334: 137 of 137
  fragments, 3430 passed, 0 failed.

Details: `docs/lanes/savestate1011/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
