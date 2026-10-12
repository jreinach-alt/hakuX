# savestate1011 OUTBOX (#433)

## #433 -- 2026-10-11 21:56 PDT

Step 1, save states as files.

- **Where they live.** A state is one file,
  `<app files>/x1box/states/<title_id>/slot<N>.hxs`, written to a `.tmp`,
  fsynced and renamed. Settings can move the folder to any picked folder
  (a persistable grant) and reset it.
- **The hard disk.** Each state takes a disk-only qcow2 snapshot of the
  hard disk at the same instant. A load goes to that snapshot first, so a
  load also rolls back game saves made after the state.
- **Non-qcow2 disks.** A hard disk that is not qcow2 is refused, with the
  reason shown.
- **Compatibility.** A state is refused on the schema fingerprint, title,
  disc and controller layout, never on the build.

Nova pilot (1-1791778805-savestate1011-904197, 187: Ride or Die): all 11
functional steps pass.

| What | Measured |
|---|---|
| Raw state | 41.6 MB |
| Disk snapshot | 18-29 ms, inside the pause |
| Raw save pause | 66-89 ms |
| Load pause | 119-145 ms |
| Whole load | 155-191 ms |

Compatibility, both directions:

- A state with one schema field changed is refused before the machine
  stops.
- A state from another build with the same schema loads.
- Title, disc and controller-layout mismatches are each refused.

The run deleted its scratch folder and all 10 disk snapshots, and left
none.

## #433 -- 2026-10-11 21:56 PDT

Steps 3 and 4, slots, undo, auto-save, auto-load and the UI. All are built
and committed.

- **Pause menu:**
  - Save state, Load state, Undo load and Undo save. The undo items are
    disabled when there is nothing to undo.
  - Save and Load open a 10-slot list. Each slot shows its date and time or
    "Empty". A slot that cannot load is greyed, with the reason.
  - It takes the gamepad (D-pad, A, B) as well as touch. Nobody has used
    it by hand on the Nova yet; that is in the owner checks.
  - A toast gives the slot and ms.
- **Settings, a "Save states" section:**
  - the folder (picker, path shown, reset);
  - compression Off/On;
  - Auto-load last state (off by default);
  - Auto-save on quit (off by default).
- **Undo load** keeps the running machine in memory, with a disk snapshot.
  In the pilot that adds 52-72 ms to every load, about 40% of a load's
  pause.
- **Undo save** puts the replaced file and its disk snapshot back. Doing it
  again is redo. It costs 4.6-6.5 ms.
- **Auto-save on quit** writes only the `auto` slot, synchronously, before
  the process exits. It also tries a best-effort save when Android stops the
  app without an Exit.
- **Auto-load** picks the newest loadable state among `auto` and 0-9, about
  1-2 s after the game starts. A refusal shows as a toast.

## #433 -- 2026-10-11 22:41 PDT

Step 1, the hard-disk rewind test on the Nova (1-1791781810-savestate1011-1461488,
187: Ride or Die, no input). It passes.

187 writes 73.5 MB to its cache partition (Z) at t=16-18 s of every boot. The
test saved at t=8, let the game write, and loaded at t=40:

| Partition | At the save | Before the load | After the load |
|---|---|---|---|
| Z (cache) | 24 KB of data | 73.5 MB, new hash | the save's hash |
| E (game saves) | hash A | A | A |
| X, Y, C | unchanged | unchanged | unchanged |

- Every partition kept its FATX magic.
- The game ran on after the load. It replayed its boot from t=8 (Xbox logo,
  Ubisoft, ESRB, title).
- E: was untouched: 187's save file is the same before and after the run.
- An undo load 20 s later put the disk back exactly as it was before the
  load.

The check that the game runs after the undo load is being re-run. The game
was on its title screen, which does not move, and a single 5 s look read it
as stopped. The frames show it running.

## #433 -- 2026-10-11 23:27 PDT

Step 2, compression: what each option costs. Measured on the Nova in
1-1791781811-savestate1011-1461611.

- **Scene:** 20 save/load cycles per option on 187: Ride or Die's attract
  race, 60 fps.
- **Volume:** 160 saves and 160 loads, all ok.

| Option | Pause, median / p95 | File safe on disk | Size | CPU |
|---|---|---|---|---|
| Off (raw) | 67 / 75 ms | 202 ms | 41.6 MB | 0 |
| **On: zstd 1, 4 threads, inside the pause** | **76 / 86 ms** | **127 ms** | **10.1 MB** | 59 ms |
| LZ4, 1 thread, inside the pause | 89 / 94 ms | 154 ms | 14.1 MB | 32 ms |
| zstd 3, 1 thread, inside the pause | 139 / 148 ms | 186 ms | 9.5 MB | 82 ms |
| Save raw, compress on an idle core, then swap (zstd 3) | 69 / 77 ms | raw 202 ms, compressed 844 ms | 9.5 MB | 598 ms |
| Dolphin's: copy in the pause, write after (zstd 3) | 59 / 63 ms | 714 ms | 9.5 MB | 585 ms |

- **No hitches.** No option caused a frame of 100 ms or more in the 10 s
  after a save. The worst frame was 33-47 ms, against 32 ms with no save.
- **Loads cost the same with or without compression:** 127-129 ms paused,
  about 176 ms in all.
  - Of that, undo load's copy of the running machine is 60 ms.
  - Decompressing is 8-13 ms; reading a compressed file saves 11-13 ms.

**Recommendation: On = zstd 1 on four threads, inside the pause. On is the
default.** Against Off it:

- pauses 9 ms longer (under one frame);
- has the file safe on disk sooner;
- uses a quarter of the space;
- leaves no work behind after the game resumes.

**Saving raw, then compressing on an idle core** saves 7 ms of pause
against On. The cost:

- the 42 MB file stays for most of a second;
- each save writes 51 MB of flash instead of 10;
- it takes ten times the CPU, on a little core.

It is not recommended.

**Dolphin's way** pauses 17 ms less than On. A quit in the 0.7 s before its
file is written loses the save.

**No third setting.** The options pause within about one frame of each
other; size and safety decide, and On wins both.

**Where it runs.** The compression worker pins itself to the least-used
core (a 2.0 GHz little core on the Nova) at the lowest scheduling priority.
The game's CPU thread is on the 3.2 GHz core.

## #433 -- 2026-10-11 23:27 PDT

Step 1, the hard-disk rewind test, re-run
(1-1791783647-savestate1011-1797227). Every check passes.

- **The game wrote, and the load rolled it back.** As before, the game
  wrote 73.5 MB to Z between the save and the load. After the load every
  partition matched the save, with FATX intact.
- **The game ran after the load.** The scene moved 1 s later, and the
  frames show the boot replaying: Ubisoft, ESRB, then the title screen.
- **The undo load put the disk back** as it was before the load. The game
  ran on into its attract race 12 s later.
- **E: (game saves) was untouched.**
- **Every other check passed:** save/load, undo load, undo save, the auto
  slot, auto-load, the four refusals (schema, title, disc, controller
  layout), a state from another build loading, delete and the slot list.
- **Clean-up:** all 8 disk snapshots were deleted and the scratch folder
  is gone.

## #433 -- 2026-10-12 01:37 PDT

What the hard-disk rewind costs in image size, and where the lane stands.

**Image growth** (`hdd.img` size, logged once a second):

- One disk snapshot adds 64 KB.
- 34 min of the 187 attract race with 160 saves, 160 loads and their
  snapshots added 0.38 MB (1-1791781811-savestate1011-1461611).
- A game that rewrites data while a state holds the old copy keeps one old
  copy per live state. In the disk test, 187's boot cache is 73.5 MB, and it
  was rewritten after a load, so the image grew by 73.8 MB
  (1-1791783647-savestate1011-1797227). There are at most 13 live states
  (0-9, auto, undo-save, undo-load).
- The image file never shrinks. Space freed by a deleted state is reused by
  later writes.

**Done:** files in internal storage or a picked folder; slots 0-9 and auto;
compression Off / On (On by default); undo load and undo save; auto-save on
quit; auto-load at boot; the pause menu and Settings. Every functional and
disk check passes on the Nova.

**For you to check by hand:** the list under "Owner checks" in `PR.md`. It
covers the pause menu with the gamepad and with touch, the folder picker,
and auto-save then auto-load across two starts of a title. The harness
cannot test across two starts, because it rebuilds the title disk every
run.

**Not done:**

- The per-game save-state page needs one entry in the per-game settings
  index, a file outside this lane.
- Thumbnails.
- "Start without auto-load" in the game list. Undo load after an auto-load
  goes back to the fresh boot.

## #433 -- 2026-10-12 02:18 PDT

The per-game save-state settings can now be reached, and a load during
background compression has been tested on the Nova.

**Per game.** Long-press a game in the library and open Game settings. The
list now ends with Save States: compression, auto-load and auto-save on quit
for that game alone. The folder stays global. The entry is marked when the
game overrides any of the three.

**A load while a compression job runs**
(1-1791795179-savestate1011-996104, 187: Ride or Die, this head's code):

- The save wrote the raw 41.6 MB file in its 72 ms pause; the file was safe
  at 210 ms.
- A load started at once, while zstd 3 ran on an idle little core. It read
  the raw file (read 18 ms, pause 135 ms) and brought the scene back.
- The job finished at 945 ms (626 ms of CPU) and put the 9.5 MB file in the
  raw file's place. The next load read it (decompress 18 ms, pause 139 ms).
- Every other functional step passed as well. E: was unchanged, and every
  test snapshot and the test folder were removed.

This mode is still reachable only from the test driver. On compresses inside
the pause.

**Still not done:** thumbnails; "start without auto-load" in the game list
(Undo load after an auto-load goes back to the fresh boot); a switch to skip
the undo-load copy (60 ms of a load's 128 ms pause).
