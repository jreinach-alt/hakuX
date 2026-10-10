# surfgpudefault1009: the surfgpu switch as a Graphics toggle, on by default (#433, 0.5)

State: in progress (device proof pending)

Lane: surfgpudefault1009          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 39379dafdd
Files: docs/lanes/surfgpudefault1009/NOTES.md, docs/lanes/surfgpudefault1009/PR.md,
  android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt,
  android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt,
  android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsManager.kt,
  android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt,
  android/app/src/main/res/layout/activity_settings.xml,
  android/app/src/main/res/values/strings.xml
Prediction: none: settings plumbing; the performance evidence is lane.surfgpu1009's
Needs device: yes (Nova only)    Needs NDK: no

Release note (performance): TBD -- "GPU surface reuse" graphics setting, on by default; measured gain TBD.

## What changed

Copies the shape of `d4a02e2060` (#569, the Ubershader setting) for lane.surfgpu1009's `HAKUX_SURFGPU` switch
(`hw/xbox/nv2a/pgraph/vk/surface.c`'s `surfgpu_enabled()`, merged from `origin/lane/surfgpu1009` first):

- A "GPU surface reuse" switch in Graphics settings, on by default, with a per-game override.
- `MainActivity.kt` sets `HAKUX_SURFGPU=1`/`0` from the switch at the same point it sets `HAKUX_GPL`. An
  `HAKUX_SURFGPU` line in the `env_vars` pref still wins (applied after, by `xemu_android.cpp`), so
  `request.sh --env` can pick either path regardless of the switch.
- No startup banner, no native change: `surface.c`'s own default stays off for anything that doesn't set the env
  var (non-app builds, bare `request.sh` runs with no `--env`).

## Device proof (Nova, NBA Live 07, `nbalive07.route`, 480 s, `--perflog`)

TBD -- see NOTES.md section 4.
