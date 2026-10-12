# savestate1011 NOTES (#433)

Dolphin-style save states. They are files on the device, not in the Xbox
drive image. Each title has ten numbered slots (0-9) and an auto slot.
Compression is optional. There is one level each of undo save and undo load,
plus auto-save on quit and auto-load at boot. This builds on
`docs/lanes/snapshot1011/NOTES.md`, the phase-0 engine: the v2 identity
header and the schema fingerprint.

## Attempt 1: why it did not finish

Attempt 1 built the native side (commit 121cde1e09) and queued a pilot run on
the Nova (1-1791778805-savestate1011-904197, 600 s). The session ended at
about 21:31 PDT, as the pilot finished. At that point:

- the pilot result had not been read;
- the Kotlin frontend (pause menu, slot list, SAF store) was uncommitted;
- this file did not exist.

The first pilot request (727262) had been refused by the profile gate.
`187-ride-or-die` is a first-run route and 55530036 already has a kept
profile. The second request named the title only, with no route, so the
game booted to its attract race on the kept profile. That pilot ran.

Attempt 2 read the pilot (all 11 functional steps pass; numbers below). It
queued the 20-cycle measurement, merged origin/master, and finished the
frontend.

The 20-cycle measurement (1240876) stopped about 150 s into its 2600 s.
lane.local put a hold on the Nova at 04:42:41Z (21:42:41 PDT) for the
owner's hands-on test (`lane.local-ownerplay`), and the logcat ends at
21:42:49 with the game running normally at 59 fps. It recorded only 6 saves
of cycle 0, so it measures nothing. It was queued again on the final ref,
to run after the hold.

## Attempt 2: why it did not finish

Attempt 2 ran out of turns: the session hit its 300-turn cap at 23:27:58
PDT. By then it had:

- finished the frontend and the per-game switches;
- queued and read the 20-cycle measurement (1461611);
- run the disk test twice (1461488, then 1797227).

The write-up of 1797227 and the step 2 OUTBOX entry were still uncommitted.
The PR was still a draft. Attempt 3 committed them, added the image-growth
numbers, merged origin/master, ran the selftest and marked the PR ready.

## Design

### Where states live

- **Default folder:** `<app external files dir>/x1box/states/<title_id>/`,
  for example
  `/storage/emulated/0/Android/data/com.jreinach.hakux/files/x1box/states/4d530004/`.
  Android deletes it when the app is uninstalled. The setting says so.
- **Picked folder:** chosen with `ACTION_OPEN_DOCUMENT_TREE`, with a
  persistable grant held the same way as `hddUri`. The native code reaches
  it through `SaveStateStore.kt`, which returns file descriptors. "Reset to
  default" clears it. If the grant is gone, the native side logs it and
  falls back to the default folder.
- **Files:** `slot0.hxs` ... `slot9.hxs`, `auto.hxs`, and `undo-save.hxs`
  (the state a save replaced). There is also `sessions.log` at the root: one
  line per boot, `unix_time<TAB>title_id`. It lets the slot list say
  "another game ran since".

### File format (`hxs.c`)

- A 48-byte header: magic `HXS1`, codec, level, stream length, payload
  length, metadata length, chunk size and flags.
- The payload: either the raw migration stream or 1 MiB chunks, each
  compressed independently with LZ4 or zstd.
- A metadata block of key=value lines: title_id, title_name, disc,
  controllers, schema, build, slot, saved_at, disk_snap, region.
- A trailer, `HXSE`.

A file counts as complete only when its size is exactly header + payload +
metadata + trailer and the trailer matches. The header is written last, so a
file cut short anywhere is never taken for a state.

**Atomic writes.** Each write goes `<name>.tmp`, then fsync, then rename. A
background compression writes `<name>.z.tmp`, fsyncs it, renames it over the
raw file, and only then is the raw file gone.

**Startup cleanup**, before anything else runs:

- A `.z.tmp` that is complete and names the same disk snapshot as its raw
  file is promoted.
- A `.tmp` that is complete and newer than the slot it would replace is
  promoted.
- Any other stray file is deleted.
- Raw files that "On" would have compressed are queued again.

### Hard disk: rewind by default

- Every state takes a disk-only internal qcow2 snapshot of the HDD at the
  same instant: `hxs-<root8>-<title>-s<N>-<uuid8>`. The file names it.
- A load goes to that snapshot first, then loads the stream. So the HDD
  always matches the RAM being loaded. Game saves written to E: after the
  state are rolled back.
- When a slot is overwritten or deleted, its snapshot is deleted. A startup
  pass also deletes snapshots that no file names.
- In the pilot, the disk snapshot took 18-29 ms inside the pause. In
  1797227 it took 18-27 ms.
- **Image growth.** The qcow2 file grows only by the clusters the guest
  rewrites while a snapshot still holds the old copy. The rest is a small
  amount of metadata. The `file_bytes` in the `[savestate] hdd` lines, once a
  second, show it:

| Run | What happened | hdd.img growth |
|---|---|---|
| 1797227 | the first disk snapshot (L1 copy, refcounts, snapshot table) | +64 KB (19,202,048 to 19,267,682) |
| 1797227 | 187 writes 73.5 MB to Z, which was empty at the save (new clusters, no copy) | +73.9 MB, as without a snapshot |
| 1797227 | a load, which goes to the save's snapshot and keeps an undo-load snapshot | +64 KB |
| 1797227 | the replayed boot writes Z's 73.5 MB again while the undo-load snapshot holds the first copy | +73.8 MB |
| 1461611 | 34 min of the attract race with 160 saves, 160 loads and their disk snapshots (t=76 to 2121 s) | +0.38 MB (92,798,976 to 93,192,723) |

- So during play that does not rewrite the disk, the snapshots cost about
  0.4 MB in 34 min. Where a game rewrites data, each live snapshot can hold
  one old copy of what was rewritten. 187's boot cache is the case seen
  here: one copy is 73.5 MB.
- There are at most 13 live snapshots: 0-9, auto, undo-save and undo-load.
- A qcow2 file never shrinks. Clusters freed when a snapshot is deleted are
  reused by later writes, so the file stays at its high-water mark (167 MB
  at the end of 1797227, after all 8 snapshots were deleted).

**Non-qcow2 HDD: refused.** Save and load both refuse with
`hdd-not-qcow2`, and the pause menu shows why. With a raw image, a loaded
RAM state could not be matched to its disk, and loading RAM over a diverged
disk corrupts the FATX partitions. That is the case the brief rules out.

### Compatibility

A load is refused, before anything stops, when the state's value differs
from the running one for any of:

- **schema:** the fingerprint from snapshot1011;
- **title** and **disc;**
- **controller layout;**
- **disk snapshot:** the snapshot is missing.

The build is recorded but never refused on. The pilot proves both
directions:

- F6 mutates one schema field. The load is refused and the game keeps
  running.
- F7 records a different build with the same schema. The load is accepted.
- F8 covers layout, title and disc.

### Modes (what "compression" can mean)

| Option | What happens |
|---|---|
| a | raw stream straight to the file inside the pause |
| b | inline: serialize to memory, compress inside the pause (LZ4, zstd 1, zstd 3; "x4" = four threads over the 1 MiB chunks), write |
| c | the owner's idea: raw file first (as a), then the `hxs-worker` thread compresses on an idle core to `.z.tmp`, fsync, rename over the raw file |
| d | Dolphin's way: serialize to memory inside the pause; the worker compresses and writes after the machine restarts |

**The worker thread (`hxs-worker`).**

- At startup it reads `/proc/stat` for one second, then pins itself to the
  core the emulator uses least.
- It probes and re-pins again after any two minutes with no job.
- On the Nova it picks a 2.0 GHz little core, about 80-87% idle:
  - in 1461611 it picked cpu0 at startup and cpu2 two minutes later;
  - the emulator's threads have `mask=ff`;
  - the vCPU thread sits on cpu7 (cpu5 in 1461488) at 91-92%.
- It runs at `SCHED_IDLE`.
- A `[savestate] cpu` line logs the topology, each core's idle share, every
  emulator thread's core and mask, and the pick.

**Cancellation and reads.**

- A new save to a slot cancels that slot's pending job: it is dropped if
  queued, and stopped if running.
- A load first waits for the title's deferred (d) writes. It does not stop
  a background (c) job. It opens whichever complete file is in place, raw
  or compressed. The rename is atomic, so an open descriptor stays valid
  either way.

### Undo

- **Undo load.** Before a load, the running machine is kept in memory,
  with a disk snapshot named `-undo-load-`. Undo load puts both back.
- **Undo save.** The file a save replaced moves to `undo-save.hxs`, with its
  disk snapshot. Undo save swaps it back into its slot. Doing it twice is
  redo.
- There is one level of each. The menu disables each item when there is
  nothing to undo.

### Auto-save and auto-load

**Auto-save on quit** (off by default) writes only the `auto` slot.

- It is a synchronous save with the setting's own mode: raw under Off,
  inline zstd under On. Nothing is left to a worker that the exit would
  kill.
- It runs before `nativeExitEmulation`/`killProcess` on the pause menu's
  Exit and Back-to-library paths.
- A swipe-away from recents gives the app `onStop`, but no time is promised
  after it. The code does a best-effort save there; see "Owner checks".

**Auto-load last state** (off by default) picks the newest loadable state
among auto and 0-9. It skips any state saved before another title ran.

- It runs on the save-state thread once the machine starts and the
  controller layout has held for 1 s. That is within about 1-2 s, at most
  8 s.
- The load replaces the RAM and goes to the disk snapshot, so nothing the
  guest did in those seconds survives.
- It never uses `-loadvm`.
- A refusal shows as a toast with the reason.
- **Boot without auto-load (stretch).** Every load keeps the machine it
  replaced as the undo-load state, so after an auto-load, Undo load in the
  pause menu goes back to the fresh boot, about 1-2 s in. The success toast
  says so. A "start without auto-load" entry in the game list would need
  `GameLibraryActivity.kt`, outside this lane's files; it is not done.

### Per-game settings (stretch, half done)

- Compression, auto-load and auto-save on quit are per-game overridable
  (`PerGameSettingsManager.overridablePreferenceKeys`). MainActivity and
  `xemu_android.cpp` already read them through the runtime override first.
- The folder stays global. Settings opened per game shows the card without
  the folder controls, under the section key `savestates`.
- Not reachable yet. The per-game settings index lists only graphics, audio
  and debug. It needs a "Save States" entry that opens `savestates`, and
  `sectionHasOverrides` needs the three keys. That is
  `SettingsIndexActivity.kt`, outside this lane's files, so `WAITING` asks
  for the grant.
- Thumbnails are not done.

## Runs

| Result id | What | Outcome |
|---|---|---|
| 1-1791778350-savestate1011-727262 | pilot, route `187-ride-or-die` | refused by the profile gate (first-run route, kept profile) |
| 1-1791778805-savestate1011-904197 | pilot: `func+measure`, 2 cycles, 187 attract race, ref 121cde1e09 | F1-F11 pass; done ok=1, 10 snapshots deleted, 0 left, scratch dir gone |
| 1-1791779971-savestate1011-1240876 | `measure`, 20 cycles x 9 options, ref 121cde1e09 | stopped at ~150 s by the owner's hold on the Nova; 6 saves, not used |
| 1-1791781810-savestate1011-1461488 | `disk+func` (`HAKUX_SAVESTATE_DISK=8,40,60`), 200 s, ref fefe83e884 | D1 pass. D2: disk pass, `game_runs=0`. F1, F3, F4 fail. All three ran on the still title screen (see "Disk test"). F2, F5-F11 and F5b pass. 8 snapshots deleted, 0 left, scratch dir gone |
| 1-1791781811-savestate1011-1461611 | `measure`, 20 cycles x 8 options (no d-none), 2600 s, frames every 10 s, ref fefe83e884 | done ok=1: 160 saves and 160 loads ok, 3 snapshots deleted, 0 left, scratch dir gone. Table in "Measurement" |
| 1-1791783647-savestate1011-1797227 | `disk+func` again, same request, ref a7d713effe (waits for a moving scene) | D1, D2 (`game_runs=1`), F1-F11 and F5b pass; E: untouched; 8 snapshots deleted, 0 left, scratch dir gone (see "Disk test") |

All runs:

- use `HAKUX_STATE_DIR=<app files>/hxs-test-<tag>`;
- refuse to start unless the HDD path is a titles image;
- delete every `hxs-` snapshot and the scratch folder at the end.

`hdd.json` and `hdd.after.json` are harvested.

## Pilot (904197): functional

| Step | What | Result |
|---|---|---|
| F1 | save slot 0, load: region back to the save's | pass; scene moved between |
| F2 | background zstd 3: raw first, compressed 886 ms after the stop; load reads zstd | pass |
| F3 | undo load returns to the kept state | pass; undo kept in 55.6 ms |
| F4 | undo save puts the replaced state back; again = redo | pass |
| F5 | auto slot: save 198.6 ms, picked as newest | pass |
| F5b | `auto_load_run()`, the function a boot with auto-load on runs, picks and loads auto (added after the pilot) | pass in 1461488 and 1797227 |
| F6 | schema mutant (nv2a.parent_obj): refused, machine never stopped | pass |
| F7 | build "build-A-test", same schema: loads | pass |
| F8 | controller layout, title, disc: each refused | pass |
| F9 | delete removes file and disk snapshot | pass |
| F10 | slot list | pass |
| F11 | save and load from paused: save leaves paused, load leaves running | pass |

**Load breakdown** (pilot, 30 loads):

- pause 119-145 ms; total 155-191 ms;
- read 3-17 ms;
- decompress 7-14 ms;
- **keeping the undo-load state 52-72 ms;**
- going to the disk snapshot 36-44 ms;
- the rest is reset and restore.

**Undo load adds about 55 ms to every load.** That is about 40% of the
load's pause.

## Measurement (1461611)

- **Scene:** 187: Ride or Die's attract race at 60 fps (frames
  f00009-f00240), ref fefe83e884.
- **Volume:** 20 cycles of each option; 160 saves and 160 loads, all ok.
- **One cycle:** load a base state, save to the option's slot, watch 10 s,
  load that save back.
- **Order:** the options take turns cycle by cycle, so drift (heat, the
  race's scene) falls on all of them alike.
- **Run end:** `done ok=1`, all disk snapshots deleted, 0 left, the scratch
  folder gone.

Report: `docs/lanes/savestate1011/measure_report.py <result dir>`.

| Option | Pause med / p95 ms | File safe med / p95 ms | MB | Compress CPU ms | Load pause / whole ms | Lag in the next 10 s, med / p95 ms | Hitches |
|---|---|---|---|---|---|---|---|
| a, raw (Off) | 67.0 / 75.3 | 202 / 212 | 41.6 | 0 | 127 / 176 | 21 / 35 | 0 |
| b, LZ4 | 88.5 / 93.7 | 154 / 340 | 14.1 | 32 | 129 / 175 | 26 / 48 | 0 |
| b, zstd 1 | 104.7 / 111.6 | 159 / 166 | 10.1 | 47 | 128 / 177 | 7 / 58 | 0 |
| b, zstd 3 | 139.0 / 147.8 | 186 / 195 | 9.5 | 82 | 128 / 177 | 32 / 54 | 0 |
| **b, zstd 1 on 4 threads (On)** | **76.1 / 85.7** | **127 / 139** | **10.1** | 59 | 127 / 176 | 31 / 51 | 0 |
| c, zstd 3 (the owner's idea) | 68.7 / 77.2 | raw 202; compressed 844 / 1027 | 9.5 | 598 | 128 / 178 | 22 / 39 | 0 |
| c, LZ4 | 68.5 / 73.4 | raw 204; compressed 405 / 607 | 14.1 | 185 | 128 / 174 | 25 / 50 | 0 |
| d, zstd 3 (Dolphin's) | 59.3 / 63.0 | 714 / 736 | 9.5 | 585 | 128 / 177 | 12 / 33 | 0 |
| no save (3 windows) | | | | | | 11 / 27 | 0 |

**What the columns mean:**

- **Pause:** the time the machine is stopped.
- **File safe:** from the stop until the final file is fsynced and renamed
  into place.
- **Lag:** frame time lost in the 10 s after the save beyond 60 fps, not
  counting the save's own pause. It is 7-32 ms at the median in every row,
  with no pattern by mode: inline zstd 1 shows 7 and inline zstd 1 x4 shows
  31, and neither leaves anything running after the resume. That is noise:
  well under two frames over 10 s.
- **Hitches:** a flip of 100 ms or more (`hitch_report.HITCH_MS`) in
  those windows. There were none. The worst flip in any window was 33-47 ms;
  with no save it was 32 ms.

**CPU.**

- The Nova has 8 cores: cpu0-2 at 2.0 GHz, cpu3-6 at 2.8 GHz and cpu7 at
  3.2 GHz.
- The vCPU thread runs on cpu7, which is 97-99% busy.
- The worker pinned itself to cpu0 or cpu2 at `SCHED_IDLE` (`worker_cpu=2
  idle=1` on the jobs).
- c and d compress there, on a little core, which is why their CPU is ten
  times b's.

**Loads** are the same in every row: 127-129 ms paused and 174-178 ms in
all. The medians break down as:

- reading the file: 17 ms raw, 4-6 ms compressed;
- decompressing: 8-13 ms;
- keeping the undo-load state: 59-60 ms;
- going to the disk snapshot: 40 ms;
- restoring the machine: 23 ms.

Compression does not slow a load.

**Undo load costs 60 ms of every load's 128 ms pause.** Without it a load
would pause about 68 ms. It is always on now; a setting to turn it off is
the obvious next step if loads should be faster.

### Recommendation: On = inline zstd 1 on four threads

This is `HXS_ON_*` in `hxs.c`, the code's setting since e7be0b7c4f. Against
Off it:

- pauses 9 ms longer at the median (76 vs 67) and 10 ms longer at p95. That
  is less than one frame at 60 fps.
- has the file safe 75 ms sooner (127 vs 202 ms), because it writes 10 MB
  instead of 42.
- is a quarter of the size: 10.1 MB instead of 41.6 MB.
- leaves nothing to run after the game resumes. A quit right after a save
  loses nothing, and auto-save on quit waits only for the save itself
  (F5 in 1461488: 199 ms).

**The owner's idea (c): save raw, compress on an idle core, then swap.** It
works:

- the pause is the raw pause (68.7 ms);
- no frame cost shows in the 10 s after (0 hitches; lag inside the no-save
  spread);
- the raw file is safe at 202 ms, as with Off.

Against On, though, it:

- saves 7 ms of pause (68.7 vs 76.1 at the median), under half a frame;
- leaves the 42 MB raw file in place for 0.8-1.0 s with zstd 3, or
  0.4-0.6 s with LZ4;
- writes 51 MB of flash per save instead of 10: the raw file, then the
  compressed one;
- spends ten times the CPU (598 vs 59 ms), on a 2.0 GHz core.

It is not recommended. On gets the size and the early safe file for 7 ms
more pause.

**Dolphin's way (d)** has the shortest pause, 59 ms, because the pause only
copies the state into memory. The file is not safe until 714 ms, and a kill
in that window loses the save. Its pause is 17 ms (one frame) shorter than
On's.

**No third choice.** The reasonable options (a, b x4, c, d) all pause
59-76 ms, about one frame apart. Size and safety are the only real
differences, and On wins both.

## Disk test

The title is 187: Ride or Die (55530036), on the dispatcher's titles disk
(qcow2), with no input.

**How I know the game writes the hard disk:** the test hashes each partition
(X, Y, Z, C, E and the rest) at the save, before the load and after it. It
also counts the guest's write ops. 187 writes the hard disk at boot:

- about 30 ops at t=3 s;
- 670 ops (73.5 MB) between t=16 and t=18 s, which take partition Z (a
  cache) from 24 KB to 73.5 MB of data.

A state saved at t=8 is from before that burst.

**1461488** (ref fefe83e884): save at t=8, load at t=40, undo load at t=60.

| Hash | When | wr_ops | Z | E | Other partitions |
|---|---|---|---|---|---|
| H0 | the save, t=8 | 30 | `954c6cb5…`, 24 KB | `4c00bcd6…` | - |
| H1 | before the load, t=40 | 700 | `7da57b0d…`, 73.5 MB | same | same |
| H2 | after the load, t=40.2 | 700 | `954c6cb5…` = H0 | same | same |
| H3 | after the undo load, t=60.2 | 1370 | `7da57b0d…` = H1 | same | same |

- **D1 passes.** The game wrote Z between the save and the load
  (670 ops). After the load, every partition hashes as at the save, and
  every partition still has its FATX magic.
- **The game ran after the load.** It replays its boot from t=8: the frames
  show the Xbox logo, Ubisoft and the ESRB notice (f00021-f00026). The
  replay wrote Z again, so wr_ops went from 700 to 1370 by t=60.
- **E: is untouched.** The game save is the same file before and after
  the run (`hdd.json` save `fa079adf42d5`, harvested `fa079adf42d5`). The
  harvest read all 94 titles' saves with no errors.
- **D2's disk check passes:** after the undo load the disk is H1 again,
  and every partition has its FATX magic.
- **D2's `game_runs` failed, and so did F1, F3 and F4.** They ran on 187's
  title screen, "Please press START to begin" (f00027-f00036). That screen
  is still in the 32 rows the region hash reads: only the prompt lower
  down blinks. The game was running all along:
  - the pace lines hold 60 flips/s;
  - the prompt blinks (f00031, f00035, f00036 without it);
  - the attract sequence starts at 22:35:37 (f00037-f00042).
- **The fix (a7d713effe):**
  - D1 and D2 wait up to 30 s and 60 s for the region to change, instead
    of one 5 s look.
  - After the disk test, func waits for its start time and a moving
    scene.

**1797227** (ref a7d713effe, the same request): every step passes.

| Hash | When | wr_ops | Z | E | Other partitions |
|---|---|---|---|---|---|
| H0 | the save, t=8 | 30 | `2bf281d7…`, 24 KB | `e0b69c86…` | - |
| H1 | before the load, t=40 | 700 | `ea19a5bb…`, 73.5 MB | same | same |
| H2 | after the load, t=40.2 | 700 | `2bf281d7…` = H0 | same | same |
| H3 | after the undo load, t=60.2 | 1370 | `ea19a5bb…` = H1 | same | same |

- **D1 passes:**
  - the game wrote Z (670 ops) between the save and the load;
  - after the load every partition hashes as at the save and has its FATX
    magic;
  - the scene moved 1.0 s after the load (`game_runs=1 moved_ms=1002`).
- **The frames show the replay after the load at 23:23:28:**
  - the title screen at f00022 (23:23:27);
  - then Ubisoft (f00024) and the ESRB notice (f00026);
  - then the title screen again at f00028 (23:23:42).
- **D2 passes:**
  - after the undo load the disk is H1 again, with every partition's FATX
    magic;
  - the scene moved 12.0 s later (`game_runs=1 moved_ms=12016`): the undo
    load put the game back on the title screen it had left at t=40, and
    the attract race started at 23:24:00 (f00034 title, f00036 race).
- **F1-F11 and F5b pass,** after `func waits for a moving scene
  moved_ms=1002`. They ran during the attract race (f00036-f00048).
- **E: is untouched.** `hdd.json` save `fa079adf42d5`, harvested
  `fa079adf42d5`; no harvest errors.
- **Clean-up:** `done ok=1`, 8 snapshots deleted, 0 left, scratch folder
  gone.

**What F2 does not cover.** F2 saves in background mode, waits 1 s, then
loads, expecting a load during compression to read the complete raw file.
In both runs the job had already finished:

- the compressed file was in place 790 ms (1461488) and 856 ms (1797227)
  after the stop;
- so the first load read zstd (`first_load_codec=zstd job_running=0`).

A load during the job is therefore untested on the device. Background mode
is reachable only from the test driver (On is inline). If On ever becomes
background, shorten F2's wait to about 200 ms first.

## Owner checks

The harness cannot prove these. The dispatcher rebuilds the title disk on
every run, so a state's disk snapshot never survives into the next run (the
state is then refused as `disk-snapshot-missing`). The harness also has no
hands on the pause menu.

1. **Pause menu, gamepad.** Open the pause menu during play.
   - Save state: the slot list opens. D-pad to slot 0 and press A.
   - The toast says "Saved to slot 0 (paused N ms)" and the game resumes.
   - Play on, then Load state, slot 0: the game is back at that moment.
   - B closes the slot list without doing anything.
2. **Pause menu, touch.** The same, with taps.
3. **Undo.**
   - Undo load returns to the moment before the load.
   - Undo save after saving over slot 0 puts its previous state back.
     Undo save again redoes the save.
   - Each item is greyed when there is nothing to undo.
4. **Folder.**
   - Settings, Save states: the folder shows
     `/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box/states`
     on the debug build (`com.jreinach.hakux` on release).
   - Change folder: pick a folder. The path is shown, and a new save
     appears there as `<title_id>/slot0.hxs`.
   - Reset to default goes back.
5. **Auto-save on quit, then auto-load.**
   - Turn both on and play a title.
   - Pause menu, Exit. This writes `auto.hxs`.
   - Start the same title again. Within about 2 s of the game appearing, it
     jumps to where you quit, with the toast "Loaded the auto slot (N ms).
     Undo load in the pause menu goes back to a fresh boot."
   - Pause menu, Undo load: the game is back at the start of the boot.
6. **Swipe-away.**
   - With auto-save on, swipe the app away from recents during play.
   - On the next start, auto-load restores that moment if Android gave the
     save time to finish. That is best effort: `onStop` starts the save, and
     Android may end the process first.
7. **Compression.** With On, a slot file is about 10 MB. With Off it is
   about 42 MB (187: Ride or Die).

## Do not repeat

- Do not queue a save-state run with route `187-ride-or-die`. It is
  first-run and the profile gate refuses it. The title alone, with no input,
  boots to the attract race on the kept profile. That scene moves, and it is
  enough for save/load. Do not use `--find-route` to get past the gate.
- No harvest so far shows the game writing E: during unattended play.
  `hdd.json` vs `hdd.after.json` changed in no run searched. The HDD writes
  in a 187 boot (the `[savestate] hdd` lines: about 700 ops, 74 MB at
  t=16-18 s) are the dashboard/title cache and the profile load, not a game
  save.
