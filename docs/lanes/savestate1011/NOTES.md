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
- In the pilot, the disk snapshot took 18-29 ms inside the pause.
- Image growth: the qcow2 file only grows by clusters the guest rewrites
  while a snapshot holds the old copy. Without a disk write, a snapshot
  costs only its L1 table and refcount updates (hdd file_bytes are in the
  `[savestate] hdd` lines).

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
- On the Nova that is cpu0, 84% idle. The emulator's threads have
  `mask=ff` and the vCPU runs on cpu5/7.
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
| 1-1791781810-savestate1011-1461488 | `disk+func` (`HAKUX_SAVESTATE_DISK=8,40,60`), 200 s, ref fefe83e884 | queued |
| 1-1791781811-savestate1011-1461611 | `measure`, 20 cycles x 8 options (no d-none), 2600 s, frames every 10 s, ref fefe83e884 | queued |

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
| F5b | `auto_load_run()`, the function a boot with auto-load on runs, picks and loads auto (added after the pilot) | in 1461488 |
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

## Measurement

Pending: queued on the Nova behind the owner's hold.

The code sets "On" to b-zstd1x4: inline zstd level 1, four threads over the
1 MiB chunks (`HXS_ON_*` in `hxs.c`). That was the best option in the
pilot's 2 cycles:

- its pause was 77 ms, against 66-89 ms for raw;
- the file was durable at 128 ms, against about 205 ms for raw;
- the file was 10.5 MB, against 41.6 MB;
- no work is left to run after the game resumes.

The 20-cycle run decides it.

## Disk test

Pending.

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
     jumps to where you quit, with the toast "Loaded the auto slot (N ms)".
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
  t=17-19 s) are the dashboard/title cache and the profile load, not a game
  save.
