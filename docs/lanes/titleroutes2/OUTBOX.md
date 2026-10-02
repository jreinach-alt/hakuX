## #397 -- 2026-10-02 ~05:50 PDT (lane.titleroutes2 session 1)

[lane.titleroutes2] Successor to lane.titleroutes. Session 1 on the Nova, all frame-reviewed (copies under the lane's
`scratch/judge/`); numbers are screening reads from `title_verdict.py --targets`.

| title | route | state | reading (Nova) |
|---|---|---|---|
| Bloody Roar: Extreme (48550001) | `bloody-roar-extreme` | **confirmed** (replay 2, `1790940923-titleroutes2-1761085`) | median 9.84 fps (target 60), 0% at 30+, no hang; 32 hitches, 25 texture-class / 6 both / 0 shader. A real slowdown for per-title triage: the texture path, not shaders. |
| Gunvalkyrie (49470017) | `gunvalkyrie` | **confirmed** (replay 2, `1790940485-titleroutes2-1611958`); live play the whole window, but the blind loop does not travel the level (canyon-wall stretches) | 59.94 median, 100% at 30+, 93% at 60, no hang; replays 3-4 (other loops) read the same |
| Star Wars Ep. III (4C410017) | `star-wars-ep3` | **confirmed** (run 2, `1790944635-titleroutes2-2688279`); the loop progresses through the level's objectives | median 29.97, 96.3% at 30+ (target 30), no hang |
| Halo: Combat Evolved (4D530004) | `halo-ce` (draft) | reaches the cryo bay; the calibration's light-aiming test needs screen-aware input | 29 fps in the bay; not a reading of play |
| Ninja Gaiden Black (5443000D) | `ninja-gaiden-black` | **confirmed** (replay 1, `1790944628-titleroutes2-2687135`); play ~300 s after launch | median 39.4 (target 60), 75% at 30+, 0% at 60, shader hitches to 1.5 s; below target |
| Conker: Live & Reloaded (4D530051) | none | survey reached only the multiplayer front end (Xbox Live sign-in loop); no single-player entry seen | -- |

Buffy is lane.routedriver2's (drive.py); not re-attempted here.

## #433 -- 2026-10-02 ~06:15 PDT (lane.titleroutes2 session 1)

[lane.titleroutes2] Nova nomination for the 600 s Playable confirmation: **Gunvalkyrie** (49470017, iso
`5345000B-Gunvalkyrie.xiso.iso`, route `gunvalkyrie`, pre-mark ~170 s so `--seconds` ~780). Route confirmed by
`1790940485-titleroutes2-1611958`: 252 s of live play, median 59.94, 100% at 30+, 93% at its own 60, no hang, worst
hitch 289 ms. For the frame review: play is live throughout, but the open-loop route does not travel through Valley 1;
expect stretches of Kelly firing and jumping against canyon walls (three loops tried, same numbers each time).
Second nomination: **Star Wars: Episode III** (4C410017, iso `4C410017-Star_Wars_Episode_III_Revenge_of_the_Sith.xiso.iso`,
route `star-wars-ep3`, pre-mark ~235 s so `--seconds` ~840). Confirmed by `1790944635-titleroutes2-2688279`: 184 s of
live play that advances through the level's objectives, median 29.97, 96.3% at 30+ (its target), no hang; measured with
the loop's frame-per-leg screencaps (~5 per 13 s).
Not nominated: Bloody Roar: Extreme (9.84 fps), Ninja Gaiden Black (39.4 median, 0% at its 60), Halo CE (no route past
the calibration).
