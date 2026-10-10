# surfgpudefault1009: the surfgpu switch as a Graphics toggle, on by default (#433, 0.5)

State: ready

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

Note: `git diff --stat origin/master...HEAD` also carries lane.surfgpu1009's own files (`surface.c`, `draw.c`,
`sg_judge.py`, its predictions, its route, its NOTES.md) -- that lane has not folded to master yet, and step 1 of
this lane's brief merges it in by name so the device proof below runs against real `HAKUX_SURFGPU` code. Those
files are lane.surfgpu1009's row, not this lane's; the `Files:` list above is what this lane itself wrote.

Release note (performance): new "GPU surface reuse" graphics setting, on by default, with a per-game override;
measured +24 gfps (22.3 -> 46.8, NBA Live 07, from lane.surfgpu1009) when it reuses rather than recreates GPU
surfaces across frames.

## What changed

Copies the shape of `d4a02e2060` (#569, the Ubershader setting) for lane.surfgpu1009's `HAKUX_SURFGPU` switch
(`hw/xbox/nv2a/pgraph/vk/surface.c`'s `surfgpu_enabled()`, merged from `origin/lane/surfgpu1009` first):

- A "GPU surface reuse" switch in Graphics settings, on by default, with a per-game override.
- `MainActivity.kt` sets `HAKUX_SURFGPU=1`/`0` from the switch at the same point it sets `HAKUX_GPL`. An
  `HAKUX_SURFGPU` line in the `env_vars` pref still wins (applied after, by `xemu_android.cpp`), so
  `request.sh --env` can pick either path regardless of the switch.
- No startup banner, no native change: `surface.c`'s own default stays off for anything that doesn't set the env
  var (non-app builds, bare `request.sh` runs with no `--env`).

## Device proof (Nova, NBA Live 07, `nbalive07.route`, 480 s, `--perflog`, ref `214da4fe81`)

Two arms, queued at once (`HAKUX_RELEASE_PRIO=1`), both PASS:

| | A: no env (switch default) | B: `--env HAKUX_SURFGPU=0` |
|---|---|---|
| result id | `1-1791614519-surfgpudefault1009-2139156` | `1-1791614524-surfgpudefault1009-2139314` |
| `[surfgpu] on` in logcat | yes | no |
| `hold=`/`frames=` | 1.00/flip | n/a (switch off at native level) |
| gfps, post-mark median/mean | 47.0 / 44.9 (n=241) | 23.0 / 21.0 (n=114) |
| pass bar | `[surfgpu] on`, hold ~1.00/flip, gfps >= 40 | no `[surfgpu] on`, gfps ~22 |
| verdict | PASS | PASS |

A shows the app's on-by-default switch reaches `HAKUX_SURFGPU=1` with no env set. B shows an `--env
HAKUX_SURFGPU=0` on the request still reaches native code ahead of the switch's default, because the `env_vars`
pref line is applied by `xemu_android.cpp` after `MainActivity`'s own `nativeSetenv` call (confirmed in logcat:
`surfgpu: ON (#433)` then `env: HAKUX_SURFGPU=0`, 48 ms apart, same PID). Full read: NOTES.md section 4.

No pixel/golden check queued by this lane -- lane.surfgpu1009's own golden3 (worse=0, 266/266) and NBA07-held
reads already cover the native mechanism's pixel safety; this lane adds no native code.
