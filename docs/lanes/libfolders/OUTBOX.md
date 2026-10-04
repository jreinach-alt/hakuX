## #433 -- 2026-10-04

[lane.libfolders] The game library now takes several games folders (ordered set, migrated from the single pref).
Code is on `lane/libfolders` at `dfa6d4c044`; build and Thor install queued as request
`1-1791142964-lane.libfolders-796796`. Not yet compiled or looked at on the device. The screenshot pair (add internal
`ROMS/xbox` beside the SD folder) and the migration check need an adb session on the Thor, which a lane may not open;
the steps are in `docs/lanes/libfolders/NOTES.md`.

## #433 -- 2026-10-04 (attempt 2)

[lane.libfolders] The build for `dfa6d4c044` succeeded and the Thor took the apk (the soak was refused for a
foreign dual-screen overlay, unrelated). Nothing has been looked at on the device: the migration test and the
screenshot pair need adb under the playtest hold rules, steps in `docs/lanes/libfolders/NOTES.md` (Status). PR.md is
now `State: ready`.
