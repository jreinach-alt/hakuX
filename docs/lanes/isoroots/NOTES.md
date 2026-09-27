# lane.isoroots -- a handheld's titles may live under more than one root

Issue #397 (tracking #433). PR #457.

## What changed

- `docs/testing/devices.sh`
  - `device_env` sets `DEVICE_ISO_ROOTS` (colon-separated, searched in order).
    Thor: `/storage/388C-68F7/ROMS/xbox:/storage/emulated/0/ROMS/xbox` (SD card
    first, then internal). Nova: `/storage/E6C6-D7AA/Games/XBox` only, as before.
  - `DEVICE_ISO_ROOT` is still exported and is the first root, so run_disc.sh's
    test-disc push and `devices.sh <serial>` are unchanged.
  - `device_iso_roots`: one root per line (falls back to `DEVICE_ISO_ROOT` when a
    caller set only that).
  - `device_title_path <title>`: ONE `adb_call` running a loop in the device's
    shell; prints the first `<root>/<title>` that is a file, non-zero if none.
    Paths are single-quoted with the quote escaped, so apostrophes work (master's
    `[ -f '$tpath' ]` broke on any title containing `'`).
  - `device_title_miss <title>`: `title not on device: <title> -- searched <r1>, <r2>`.
  - `devices.sh titles` lists every root, each under its own `===` header.
- `docs/testing/dispatcher.sh` (soak path, ~line 752, one 5-line hunk):
  `tpath=$(device_title_path "$title")`; on a miss the ERROR is
  `device_title_miss`. The xemu-surf region (~1376, PR #440) is untouched.
- `soak_title.sh`: not changed. It takes the full path as `$1` and derives no
  root anywhere (grepped: its only use is `ISO="$1"`).
- `docs/testing/jobs/selftest.d/99-iso-roots.sh`: new.

## The selftest and how each leg was shown to fail

The fragment cuts the soak's title check out of dispatcher.sh verbatim (from
`local tpath` to the first `fi`) and runs it with dispatcher.sh's own functions
against a fake adb whose `shell` runs the command under `sh` with every
`/storage/` path moved into a scratch directory. `IR_TESTING=<docs/testing tree>`
points it at another tree; that is how master was run (`git archive
origin/master docs/testing` at deb0903b51).

| leg | branch | master | mutant that fails it |
|---|---|---|---|
| root 2: title only in Thor internal is found | ok | FAIL | first-root-only lookup |
| none: ERROR names the title and both roots | ok | FAIL | first-root-only, reversed order |
| quote: title with `'` is found | ok | FAIL | (master's quoting) |
| root 1: title under both roots plays from SD | ok | ok (control) | reversed order |
| one root: Nova finds its title | ok | ok (control) | -- |
| one root: Nova miss names exactly its one root | ok | FAIL | Nova given a second root |
| unchanged: `devices.sh bdc158a5` prints the SD root | ok | ok (no-regression) | -- |
| titles: `devices.sh titles thor` lists both roots | ok | FAIL | first-root-only, reversed order |

Mutants were one-line edits of this branch's devices.sh (append `| tac` to the
root list; replace the split with `cut -d: -f1`; add internal storage to the
Nova's roots). Branch: 9/9 ok. Master: 4 ok, 5 FAIL. Each mutant: the rows named.

## Live proof (read-only, Thor bdc158a5, 2026-09-27T01:43Z)

No title was copied, moved or deleted; no hold was taken.

- `devices.sh titles thor`: 36 names under the SD root; the internal root
  `/storage/emulated/0/ROMS/xbox` exists and is empty (lane.xbox had not pushed
  there yet).
- `device_title_path 4D530003-Project_Gotham_Racing.xiso.iso` ->
  `/storage/388C-68F7/ROMS/xbox/4D530003-Project_Gotham_Racing.xiso.iso`, rc 0.
- `device_title_path "No_Such_Title (USA).iso"` -> rc 1, `title not on device:
  No_Such_Title (USA).iso -- searched /storage/388C-68F7/ROMS/xbox,
  /storage/emulated/0/ROMS/xbox`.
- Second-root branch in the device's own (toybox) shell, roots overridden to
  `SD:/storage/emulated/0/Download`: `"Dark Cloud.iso"` (spaces, only in
  Download) -> `/storage/emulated/0/Download/Dark Cloud.iso`; the PGR name still
  resolves to the SD root first.

Still owed: one real titlebench soak of a title that exists ONLY on Thor
internal, once lane.xbox pushes one there. Asked for in
`$DISPATCH_DIR/board-requests/isoroots.md`.

## What the host runs after the fold

The dispatcher reads devices.sh and dispatcher.sh at start, so the change is
live only after the dispatcher restarts on the folded master:

    host-tools/dispatcher_update_window.sh

then, once `git -C <dispatcher tree> log -1 --format=%h -- docs/testing/devices.sh`
shows this fold:

    touch ~/hakux-work/hardware/titlepush/thor-internal.on

(the file lane.xbox waits for before pushing Thor titles to internal storage).

## Do not repeat

- Do not test the soak lookup by grepping dispatcher.sh for `device_title_path`:
  the fragment runs the real block, which is the only form that fails on master.
- The fake adb runs host `sh`, not toybox; the live Download leg above is what
  covers the device's shell.
