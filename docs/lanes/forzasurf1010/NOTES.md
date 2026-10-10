# lane.forzasurf1010 -- Forza's surfupd wait vs. default-on surfgpu (#433, 0.5)

Brief: does lane.surfgpudefault1009's shipped default (`HAKUX_SURFGPU=1`) remove the per-frame
`surfupd` wait lane.frametrace named on Forza (12.2 ms/frame, `vk/draw.c:4319` behind the render
thread's fence), given frametrace's own capture was invalid (car stalled against the wall, 8th of
8)? surfgpu targets `surfupd`/`reuse`; surfdl1008 found a different caller on Midnight Club 2
(`range`, `texture.c`'s `pgraph_vk_download_surfaces_in_range_if_dirty`), which surfgpu does not
touch. Measure, don't infer.

## 1. Setup

- Base: master @ `510dacff37` (this branch's root).
- Nova serial `ee317437`, root `/storage/E6C6-D7AA/Games/XBox` (docs/testing/devices.sh).
- **Forza's ISO is already on the Nova**, confirmed read-only (`adb -s ee317437 shell ls -la
  '/storage/E6C6-D7AA/Games/XBox/' | grep -i forza`): `4D53006E-Forza_Motorsport.xiso.iso`,
  3270705152 bytes, same size as the Thor's copy. `docs/testing/titles/targets.toml` only lists
  the Thor for this title -- that doc is stale, not mine to fix here (not in this lane's
  territory). No push needed; step 1 of the brief is done by reading, not by acting.
- The switch: `HAKUX_SURFGPU`, read once by `surfgpu_enabled()` in `hw/xbox/nv2a/pgraph/vk/surface.c`
  (line ~558). Default off at the native level; the app's Graphics toggle sets it on by default
  via `MainActivity.kt`'s `nativeSetenv`, but a queued request's `--env HAKUX_SURFGPU=0/1` is
  applied later by `xemu_android.cpp` from the `env_vars` pref and wins (confirmed by
  lane.surfgpudefault1009, NOTES section 4: `surfgpu: ON (#433)` then `env: HAKUX_SURFGPU=0`, 48 ms
  apart, same PID). So both arms here use `request.sh --env HAKUX_SURFGPU=1` / `=0` directly,
  independent of the app's Settings default, and the ON arm's log must show `[surfgpu] on`
  (it is logged once, from `surfgpu_enabled()`'s first call) while the OFF arm's must not.
- Route: `docs/testing/titles/routes/forza.drive.route` (`drive forza 420 find`), state `any`.
  This is lane.routedriver's screen-driven route (`drive.py`, RT held in the race, A only on
  menus, never START) -- proven on both handhelds to reach confirmed play (20 s of `find`), unlike
  the frametrace capture's blind route that left the car stalled. This is what the brief names in
  item 2 and is used unmodified (no local copy needed under routes/).
- Reader: `docs/lanes/surfgpu1009/sg_judge.py` is title-agnostic (`--expect`, `--a`, `--b`,
  optional `--floor`): it reads every `[sdcall]` caller's wait by name (not just `reuse`/`surfupd`)
  from post-mark logcat, `[surfgpu]` counters, and gfps/ph_* from
  `docs/lanes/near30/decompose.py`. Read-only, writes nothing -- used as-is rather than copied,
  per territory (this lane's territory is `docs/lanes/forzasurf1010/**` and its own prediction
  files; `sg_judge.py` is surfgpu1009's file, called, not edited).
