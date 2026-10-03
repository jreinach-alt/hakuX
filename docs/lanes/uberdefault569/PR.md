# lane.uberdefault569: the ubershader on by default, a settings toggle, and a warning when it is off (#569, #672)
State: draft

Lane: uberdefault569         Issue: #569 #672
Base: master @ 9550493846
Files: docs/lanes/uberdefault569/PR.md, docs/lanes/uberdefault569/OUTBOX.md, docs/lanes/uberdefault569/NOTES.md, docs/lanes/uberdefault569/judge.py, docs/lanes/uberdefault569/routes/toejam-earl-3.route, docs/lanes/uberdefault569/routes/tron-newgame.route, docs/testing/predictions/uberdefault569-soaks.json, hw/xbox/nv2a/pgraph/vk/instance.c, android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsManager.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt, android/app/src/main/res/layout/activity_settings.xml, android/app/src/main/res/values/strings.xml
Prediction: pending (docs/testing/predictions/uberdefault569-soaks.json)
Needs device: yes    Needs NDK: yes

Work in progress. The plan:
1. `HAKUX_GPL` defaults to 3 (the uber ladder) when nothing sets it.
2. A setting, "Ubershader", on by default, global with a per-game override, which sets
   `HAKUX_GPL` at launch. An `HAKUX_GPL` line in the env_vars pref still wins, for testing.
3. When the ubershader is off, a brief banner at game load: "Ubershader is disabled. Loading
   some scenes may be delayed."
4. Cold first-launch confirmation arms on the Nova, ubershader on against off.

Release note (performance): pending
