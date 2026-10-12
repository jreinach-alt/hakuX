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
