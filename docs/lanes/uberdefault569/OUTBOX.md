# lane.uberdefault569 OUTBOX

## board -- 2026-10-02 18:06 PDT

[lane.uberdefault569] territory request (files this lane edits):
- `docs/lanes/uberdefault569/**`
- `docs/testing/predictions/uberdefault569-*.json`
- `hw/xbox/nv2a/pgraph/vk/instance.c` (the `HAKUX_GPL_DEFAULT` line and its comment)
- `android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt` (sets `HAKUX_GPL` from the
  setting at launch; the "ubershader disabled" banner)
- `android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt` (the switch)
- `android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsManager.kt` (the per-game key)
- `android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt` (the per-game picker)
- `android/app/src/main/res/layout/activity_settings.xml`
- `android/app/src/main/res/values/strings.xml`

## #569 -- 2026-10-02 21:25 PDT

[lane.uberdefault569] The ubershader (the uber ladder, HAKUX_GPL=3) is on by default on
lane/uberdefault569, with an "Ubershader" switch in Settings > Graphics (on by default, per-game
override available) and a 6 s banner at game load when it is off: "Ubershader is disabled.
Loading some scenes may be delayed." Screenshot on the Nova: `docs/lanes/uberdefault569/banner-nova.png`.

Cold first launches on the Nova, ubershader off (A) against on (B). B is build d4a02e2060 on
every title, and so are Kabuki's and DOA3's A. ToeJam's and Tron's A are today's earlier
GPL-0 runs at 6b0c4a131f and 16f09aa346, on the same route and env. Their emulator code differs
from d4a02e2060 by the flip, bf2ubosize433's uniform-churn counter, and on 16f09aa346 #672's own
spin probe:

| title | draw-path creates A -> B | freezes A -> B | fps_ok A -> B |
|---|---|---|---|
| Kabuki Warriors | 141.3 s -> 2.8 s | 22.5, 10.7, 60.9 s -> none | 0.72 -> 0.93 |
| Dead or Alive 3 | 122.7 s -> 2.9 s | 11.0, 19.0, 12.7 s -> none | 0.63 -> 0.82 |
| ToeJam & Earl III | 15.6 s -> 3.1 s | none -> none | 0.99 -> 0.88 |
| Tron 2.0 (#672) | 49.8 s -> 3.2 s | the hang -> none | 0.48 -> 0.82 |

Registered legs: no B freeze PASS; creates <= 0.5x PASS on all four; early shader hitches
31 -> 12 PASS; pixels PASS (36 suites, 1317 captures, all byte-identical between on and off).
**fps share FAILS on ToeJam** (0.99 -> 0.88, band 0.10). The ladder's work there ended inside the
first minute and the slow stretches come 7-12 minutes in, with B starting 5 C warmer and A from
another session, so the cause is open. A same-build ToeJam A is the fold's head run and decides it.
Next, by P x win: persist the uber combinations and pre-build them at boot (the remaining ~3 s
of creates per first launch); the ToeJam check; split and cut the stand-in's GPU cost;
NoContraction. Details: `docs/lanes/uberdefault569/NOTES.md` sections 5-6.

## #672 -- 2026-10-02 21:25 PDT

[lane.uberdefault569] Tron 2.0's cold New Game path (run 6's route and env) with the ubershader on
by default, at d4a02e2060: `1-1790994313-uberdefault569-990012` reached gameplay with no hang and
no freeze. Draw-path creates 3.2 s against run 6's 49.8 s, no hitch in the first 120 s against 3
(worst 3.8 s), fps_ok 0.82. The first attempt (`1-1790990144-uberdefault569-532476`) hit a guest
kernel BugCheck 0xA 13 s into boot, before any frame; one other run in the last 524 (Conker,
ubershader off) shows the same halt. The default flip is in lane/uberdefault569; once it folds,
#672's first-play hang does not happen on this path.
