# high-speed driving fps (GTA III + GTA: San Andreas)

State: ready

Lane: gta3fps1017b            Issue: #1049 #433
Base: master @ 4a504d9aaa
Files: docs/lanes/gta3fps1017b/NOTES.md, docs/lanes/gta3fps1017b/PR.md, docs/lanes/gta3fps1017b/tools/desk_census_nd.py, docs/lanes/gta3fps1017b/tools/dip_table.py, docs/lanes/gta3fps1017b/tools/suite_band.py, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: none: no arm. Both switches are off by default; the driving numbers come from the owner's sessions on the perflog APK
Needs device: no    Needs NDK: yes
Selftest: none -- no fragment in docs/testing/jobs/selftest.d exercises texture.c or this lane's docs (71, 86 and 65 only name vk/ paths as fixture data)

Release note (none): R2 and R3 are opt-in switches, off by default; a default build behaves as before.

Two switchable ways to make fewer surface-to-texture copies. Both are in
`hw/xbox/nv2a/pgraph/vk/texture.c`, are **off by default**, and act on R1 (folded,
4a504d9aaa). They are for the owner's one driving session on each title. They apply
to any title, because they act in `pgraph_vk_bind_textures` on every surface sampled
as a texture, so they cover GTA III and GTA: San Andreas alike.

- **R2, `HAKUX_S2T_WIDEN=1`.** A surface refused a direct bind only for its component map
  (GTA III's `map0002`, alpha forced to ONE) or for pad alpha is bound through a view of its own
  image. That view applies the mapping the texture's node view would have applied, so there is
  no copy. Logs `[s2twiden] on` and `[s2twiden] first bind`.
- **R3, `HAKUX_S2T_SHARE=1`.** When a second node would copy the same surface at the same
  draw_time with the same decode, it samples the first node's copy instead. Logs
  `[s2tshare] on` and `[s2tshare] first share`.
- **Census (perflog only).** The `[s2c]` line, every 60 flips, now has
  `r2[map pad] r3[share]` (the copies saved) beside `why[zs pad fmt map none]` and `dup`.

Pixel arguments, guard and invalidations: NOTES section 3. `fmt` is not handled: a
different-format view needs `MUTABLE_FORMAT` on surface images, which is a `surface.c` change.

## Desktop proof (lavapipe)

| check | result |
|---|---|
| pgraph suites (`r1suites.iso`, 363 tests), off / R2 / R3 / R3 rerun / both | all exit 0, 363 tests. Outside Texture_shadow_comparator only one test moves, and it moves between two off runs too. Each switch's `on` line printed. No suite reaches either branch (no `first` line), so this shows the switches are inert where they do not apply |
| GTA III on foot, `[s2c]` from 360 s, R1 only | **2.00 copies/flip**, `why[map]` 100%, dup 0 (15 windows) |
| the same, R1+R2 | **0.00 copies/flip**, `r2[map]` 2.00/flip in all 17 windows, `[s2twiden] first bind`, no Vulkan error |
| R3 on foot | not reachable: dup is 0 on foot. R3's branch first runs in the owner's session |
| GTA: SA on foot | not run: no SA image is staged (D: holds only the .7z) |

No driving fps is claimed: lavapipe fps does not measure this, and the driving numbers are
the owner's sessions.

`preflight.sh`: every step passes except `territory`, which is not a CI gate (preflight.sh:239).
`origin/board`'s `territory.toml` has three files claimed twice, all between other lanes:

- `selftest.d/97-dispatch-snapshot-drive.sh`: snaptargets1018 and pathclass
- `selftest.sh`: snaptargets1018 and selftestclean1011
- `dispatcher.sh`: snaptargets1018 and dispatchdoctor1017

None of them is this lane's file. Only the board can clear it.

## The perflog APK (built, not installed)

`/home/justin/hakux-work/wt/gta3fps1017b-apk/android/app/build/outputs/apk/debug/app-debug.apk`

- sha256 `43625e2e603338a0eb5e611c9cd3f22eb01c4a1d1de0c0f85d0cb591221d0489`
- package `com.jreinach.hakux.debug`
- built from 7343e14054 with `JAVA_HOME=/home/justin/toolchains/jdk21 ./gradlew assembleDebug -Pperflog=true`

## Env strings (the debug package's `env_vars` pref, set with run-as as the dispatcher's `apply_env_pref` does, app stopped)

| set | `env_vars` |
|---|---|
| R1 only | no `HAKUX_S2T_*` line |
| R1+R2 | `HAKUX_S2T_WIDEN=1` |
| R1+R3 | `HAKUX_S2T_SHARE=1` |
| R1+R2+R3 | `HAKUX_S2T_WIDEN=1` and `HAKUX_S2T_SHARE=1` on two lines |

`HAKUX_S2T_DRAIN=1` turns R1 off. Each switch is read once per process, so change sets with the
app stopped.

## Running it on GTA III (5454000E) and GTA: San Andreas (54540082)

The sessions are by hand: the owner drives, and nothing is scripted.

1. lane.local installs the APK and writes `env_vars`.
2. The owner launches the title and drives at speed.
3. The host captures logcat tags `hakuX`, `hakuX-stall`, `hakuX-perf` and `hakuX-pace`.

Suggested order:

1. **R1 only**: the baseline, and each switch's ceiling (`why[map]+why[pad]`, `dup`).
2. **R1+R2+R3**: `r2[...]` and `r3[share]` count each switch's saves separately in one run.
3. **R1+R2** and **R1+R3**: only if run 2 shows a fault or no gain.

The debug package has its own data. If the titles' saves are only in the release package,
use the release-id route below.

Expected effect on SA's dips, if SA's dip copies look like GTA III's:

- **R1** removes the #474 drain ahead of each plain colour copy (GTA III pilot: ~11.6 ms/flip).
- **R2** removes one surface-sized copy per `map`/`pad` refusal, but not the render-pass break.
- **R3** removes the copy and its render-pass break per `dup`.

SA's census will say which applies (NOTES 5.3).

## Three titles, one signature (NOTES 5)

Release captures (`tools/dip_table.py`, dip < 26 fps vs good >= 29 fps):

| title | G ms | Df | Tq | Ri ms | tc ms |
|---|---|---|---|---|---|
| GTA III (RT held) | 50.5 vs 33.2 | 81.5 vs 18.1 | 1408 vs 1092 | 3.6 vs 17.5 | 16.6 vs 11.9 |
| GTA: SA (driving) | 42.8 vs 32.7 | 56.2 vs 40.0 | 2009 vs 1065 | 10.0 vs 17.1 | 16.4 vs 12.4 |
| Blinx 2 (island) | 41.6 vs 33.4 | 92.8 vs 66.6 | 3842 vs 2556 | 7.6 vs 13.8 | 12.7 vs 9.7 |

In every title's dips, G, Df, Tq and the PGRAPH thread's CPU per frame (tc) rise, and
renderer idle (Ri) falls. That is a shared class (the renderer is busy while the guest
waits), not a shared cause; nothing here shows the S2T copy is SA's or Blinx 2's cause.

The shared measurement is the perflog's `txw[...]` and `[s2c]` lines (tag `hakuX-stall`), read
in dip windows against good ones.

Blinx 2's island save is in the release package only. To get `[s2c]` there, lane.local builds
`assembleRelease -Pperflog=true` (the same native code), signs it with the release key and
installs it with `adb install -r` over `com.jreinach.hakux`, which keeps the data. The owner's
release APK goes back afterwards. That is done by hand: the dispatcher refuses release APKs,
and the census needs no switch.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
