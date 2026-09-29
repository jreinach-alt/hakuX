# lane.hddsplit: title runs on titles.qcow2, disc runs on hdd.img

Issue #397 (harness defect found under #474). PR #622. Base `2dd92568b5`.

## Why

Every soak and every nxdk disc run shared the one `files/x1box/hdd.img` on
each handheld. On 2026-09-29 the Thor's was 6.9 GB (Nova 6.5 GB) of an 8 GiB
qcow2, and a Crimson Skies soak's "gameplay" frames were the title's "not
enough free blocks to save games" dialog. The real saves on it were a few MB.
hostops rebuilt both disks by hand that afternoon (saves.py list/pull/build/
verify, originals kept as `hdd.img.bak-20260929`); nothing stopped it
recurring. `titlestate.py` already described the split; nothing called it.

## What is wired, and where

`docs/testing/dispatcher.sh`, all in `serve_one` plus new functions after
`apply_env_pref`:

| step | where | what |
|---|---|---|
| every request | after `apply_env_pref` | `restore_hdd_pref`: if `$D/.hdd_pref.<dev>` exists (a title run did not finish), put `hddPath` back. No marker: no adb call. |
| title run, before | soak branch, before `soak_title.sh` | `titles_disk_prepare`: loop on `titlestate.py plan` until `keep`; then `hddPath` = `.../files/x1box/titles.qcow2`, read back, the old value in the marker. Writes `<rdir>/hdd.json`. |
| title run, after | after `stop_frame_capture` | `titles_disk_after`: if the device file's sha256 moved, pull it (sha-checked) and `titlestate.py after-run` harvests every title on it; then `restore_hdd_pref`. |
| disc run, before | before the runs loop | `hdd_img_guard`: past `HAKUX_HDD_RESET_BYTES` (1 GiB) hdd.img is pulled, `saves.py reset` (list, pull every title, build, verify each), the old file copied to `hdd.img.bak-auto` on the device, the new one pushed via `.new` + rename, sha-checked. Any failure leaves hdd.img alone and records `alert`. |
| results | soak `result.json` `hdd`; disc `result.json` `hdd_guard` | path, `sha256_at_start`, the plans, the post-run harvest. |

`titlestate.py plan` (new) decides, given the device file's size and sha256:

- `seed`: no titles disk yet and hdd.img never harvested. The dispatcher pulls
  hdd.img once and `seed` harvests every title on it, so no profile made on
  the shared disk is lost by the move.
- `harvest`: the device file's sha256 is not the one last harvested or pushed.
- `build`: no disk / not on the device / the store's saves differ from what
  it was built from / grown past `TITLES_DISK_CAP_BYTES` (512 MiB).
  `rebuild` builds into `titlestate/images/<dev>-<sha12>.qcow2`, verifies
  every save on it, keeps the newest five; the dispatcher pushes, then
  `pushed` records it (and now keeps `save_na`, which status_html reads).
- `keep`: otherwise.
- **Never `build` over a disk whose last harvest failed**, unless it is past
  `TITLES_DISK_CEILING_BYTES` (4 GiB); the result says `alert`.

`saves.py`: `reset` subcommand (the whole list/pull/build/verify flow; the
output is removed if any title fails to verify), and `MAKE_XBOX_HDD` to find
`tools/make_xbox_hdd.py` from the dispatcher snapshot (`$D/bin/titles/`),
where `../../../tools` is not the repo. `titles/titlestate.py` and
`titles/saves.py` are added to `SCRIPT_DEPS` and `snapshot_scripts`.
`harvest` now uses a per-device, per-process scratch dir: both workers
harvest, and `.incoming` was shared.

Kill switch: `HAKUX_TITLES_DISK=0` in a worker's environment; title runs
then boot hdd.img as before, and `hdd.json` says `split: off`.

## How it was tested

- `selftest.d/99-hdd-split.sh`, 32 legs, on a fake adb whose device is a
  directory. Asserts the written `hddPath`, the pushed file's sha256 against
  the registry, `sha256_at_start` in hdd.json, that the seeded saves verify
  on the pushed disk, that a restore leaves `x1box_prefs.xml` byte-identical,
  that a new save written by the "run" is harvested and the next run
  rebuilds with it, plan()'s guards (a failed harvest is kept, the ceiling
  overrides), the kill switch, the hdd.img guard, and the call order in
  `serve_one`. **Against master's three files: 24 of 32 red** (the 8 green
  are "nothing changed" legs that master also satisfies).
- 97-dispatch-deploy, 97-dispatch-snapshot-rename, 99-title-state and
  `titlestate_selftest.py`: green. 51-dispatch-hardening E/E2 fail
  standalone on master too (they need fragment 50's fixture).
- On a real image: the Thor's 09-27 pull (4,487,249,920 B) through
  `saves.py reset` -> 10,289,152 B, 34 titles, every one verified, 0.6 s.
  `seed` + `rebuild` + `pushed` + `plan` on a scratch registry: 34 titles,
  0 errors, then `keep`; the save ids match the ones lane.titlestate
  harvested (Crimson Skies `42b0f68410a3`, Alien Hominid `c50c0ad5b571`).

**Not yet shown on a device.** The workers run the dispatcher from their
snapshot of the host's master checkout, so this code reaches a device only
after the fold and a worker re-exec. The proof is the first title soak after
that on each handheld: `result.json` `hdd.path` ends in `titles.qcow2`,
`hdd.plans` reads `seed, build, keep`, and the logcat has
`HDD from pref: .../titles.qcow2  size=` (xemu_android.cpp:1032). The first
soak on each device pays the seed: one pull of hdd.img, ~11 MB since the
09-29 mitigation.

## For the next lane

- Held interactive sessions (`nav.py`) do not go through the dispatcher: they
  boot whatever `hddPath` says, which between requests is hdd.img. A held
  title session that should see the titles disk sets it itself.
- A route that saves must still end with `flush`: the soak's force-stop
  loses unflushed qcow2 metadata, and the post-run harvest reads only what
  reached the file.
- `hdd.img.bak-auto` is overwritten by each guard reset; the 09-29 manual
  backups have their own names and are untouched.
