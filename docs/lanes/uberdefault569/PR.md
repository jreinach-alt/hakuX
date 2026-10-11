# lane.uberdefault569: the ubershader on by default, a settings toggle, and a notice when it is off (#569, #672)
State: ready

Lane: uberdefault569         Issue: #569 #672
Base: master @ 9550493846
Files: android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsManager.kt, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, android/app/src/main/res/layout/activity_settings.xml, android/app/src/main/res/values/strings.xml, docs/lanes/uberdefault569/NOTES.md, docs/lanes/uberdefault569/OUTBOX.md, docs/lanes/uberdefault569/PR.md, docs/lanes/uberdefault569/ab-pixels.json, docs/lanes/uberdefault569/ab-pixels.txt, docs/lanes/uberdefault569/banner-nova.png, docs/lanes/uberdefault569/judge-soaks.json, docs/lanes/uberdefault569/judge.py, docs/lanes/uberdefault569/routes/toejam-earl-3.route, docs/lanes/uberdefault569/routes/tron-newgame.route, docs/testing/predictions/uberdefault569-pixels.json, docs/testing/predictions/uberdefault569-soaks.json, hw/xbox/nv2a/pgraph/vk/instance.c
Prediction: docs/testing/predictions/uberdefault569-soaks.json @ c3404e420977a0b8c410892fa3a6e0f930b9f6b6852e9588b3b88076727c9dc3; docs/testing/predictions/uberdefault569-pixels.json @ 9d906694e235f7bfb65c2c16f817e590b2b63220548f2cda5144cf95db2c271a
Needs device: yes    Needs NDK: yes

**What it changes.**
- `HAKUX_GPL_DEFAULT` goes from 0 to 3 (`vk/instance.c`). Mode 3 is #569's uber ladder: on a
  pipeline miss, the draw links a prebuilt uber vertex stage and draws this frame. The exact
  pipeline builds on the worker and swaps in later. `HAKUX_GPL=0..4` in the environment still
  overrides it.
- An **Ubershader** switch in Settings > Graphics, beside "Async shader compilation". It is on
  by default and has a per-game override (Enabled / Disabled / Use Global). The per-game part
  came free with the existing override keys.
- When the switch is off, `MainActivity` sets `HAKUX_GPL=0` before the emulator starts. It also
  shows "Ubershader is disabled. Loading some scenes may be delayed." at the top centre for 6 s
  at game load. The banner takes no touches, fades out by itself, and sits over the boot logos.
  An `HAKUX_GPL` line in the env_vars pref still wins, so `request.sh --env` can pick either path.
- The first-launch "expected delay" notice was not built, as the brief said.

**Device evidence, Nova, cold first launches** (no pipeline cache file, nothing pre-built), at
d4a02e2060. Off is `HAKUX_GPL=0`, on is the new default.

| title | draw-path creates off -> on | freezes off -> on | fps_ok off -> on |
|---|---|---|---|
| Kabuki Warriors | 141.3 s -> 2.8 s | 22.5, 10.7, 60.9 s -> none | 0.72 -> 0.93 |
| Dead or Alive 3 | 122.7 s -> 2.9 s | 11.0, 19.0, 12.7 s -> none | 0.63 -> 0.82 |
| ToeJam & Earl III | 15.6 s -> 3.1 s | none -> none | 0.99 -> 0.88 |
| Tron 2.0 (#672) | 49.8 s -> 3.2 s | the 226 s hang -> none | 0.48 -> 0.82 |

ToeJam's off arm is its first play earlier today (6b0c4a131f). Tron's is #672 run 6 (16f09aa346).
Both used the same route and env.

| leg | verdict |
|---|---|
| V validity (on: mode 3 with uber links; off: mode 0; both cold) | 4/4 valid |
| H no freeze, crash or lost gameplay with it on | **PASS**. A first Tron run hit a guest BugCheck 0xA at boot; its rerun passed. NOTES 4 |
| S1 creates on <= 0.5x off, each title | **PASS**: 0.020, 0.024, 0.198, 0.065 |
| S2 early (first 120 s) shader hitches fall | **PASS**: 31 -> 12 summed |
| F fps_ok on >= off - 0.10 | **FAIL** on ToeJam (-0.11); Kabuki +0.21, DOA3 +0.19 |
| pixels, 36 suites, on vs off | **PASS**: 1317/1317 same, all byte-identical; 1321 draws went through the uber stage |

**The F miss, checked.** A same-build ToeJam run with the ubershader off
(`1-1791001364-uberdefault569-1888217`, the first head run) reads fps_ok 0.996 against 0.881 on.
ToeJam's ladder had finished its work by 3.5 min, and the slow stretches with it on come at
7-8 and 10-11 min. So it looks like a steady-state cost in mode 3 on this title. The on arm's
13 C warmer start is the one confound left. 0.881 is under the Playable bar, and both off
runs pass it. NOTES section 8.

**Banner screenshot:** `docs/lanes/uberdefault569/banner-nova.png` (Nova, frame f00011 of
`1-1790994336-uberdefault569-990675`). It is visible from the first frame of the app window
until about 6 s, then gone.

**Next, by P x win** (NOTES 8):
1. Find ToeJam's steady-state cost: an on/off pair from a matched start temperature, with
   `--perflog` (GPU ms per frame in the slow minutes). P 0.6 that the ladder causes it. Win:
   whether the default keeps Playable titles Playable. 2 runs.
2. Persist the uber combinations and pre-build them at boot. P 0.8, using shaderprebuild569's
   shipped mechanism. Win: the ~3 s of creates left per first launch.
3. Split the stand-in's GPU cost (interpreter against non-LTO link), then cut it. P 0.6.
4. `NoContraction` on both paths, with its own pixel arm.

**Local checks in place of CI, at this head:**
- `./gradlew :app:compileDebugKotlin` (JDK 21): ok. The Kotlin and resource changes compile.
- The dispatcher built the full apk (native and Kotlin) at d4a02e2060 for all ten runs above.
  This head adds only docs.
- `judge.py --selftest`: ok.
- `docs/testing/preflight.sh --allow-tracker`: passed. Its coverage gate did not run, because it
  needs `gh`.
- No harness file changed, so `selftest.sh` does not apply.
- **Head run:** a DOA3 smoke, 150 s, at this head, queued after this commit with purpose
  `#569 head run`. The ToeJam check ran at effb0d001b, and this commit moved the head off it.

Nova runs: 10 at d4a02e2060, the ToeJam check, and the head smoke, 12 in all. That is two over
the brief's 10: the Tron rerun after the boot crash, and the smoke this correction needed.

Release note (performance): Games no longer freeze to compile shaders the first time a scene appears. A general "ubershader" draws it at once while the exact shader builds, which removes multi-second to minute-long stalls on first play (Kabuki Warriors, Dead or Alive 3, Tron 2.0). In some games it can lower the frame rate (ToeJam & Earl III ran at 54 fps instead of 60 in testing). It can be turned off in Settings > Graphics > Ubershader, globally or per game.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
