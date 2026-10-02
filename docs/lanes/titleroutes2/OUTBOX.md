## #397 -- 2026-10-02 ~05:50 PDT (lane.titleroutes2 session 1)

[lane.titleroutes2] Successor to lane.titleroutes. Session 1 on the Nova, all frame-reviewed (copies under the lane's
`scratch/judge/`); numbers are screening reads from `title_verdict.py --targets`.

| title | route | state | reading (Nova) |
|---|---|---|---|
| Bloody Roar: Extreme (48550001) | `bloody-roar-extreme` | **confirmed** (replay 2, `1790940923-titleroutes2-1761085`) | median 9.84 fps (target 60), 0% at 30+, no hang; 32 hitches, 25 texture-class / 6 both / 0 shader. A real slowdown for per-title triage: the texture path, not shaders. |
| Gunvalkyrie (49470017) | `gunvalkyrie` | reaches and stays in play (replays 1-3); loop being tuned so the window is not a canyon wall | 59.94 median, 100% at 30+, no hang in replays 2 and 3 |
| Star Wars Ep. III (4C410017) | `star-wars-ep3` | reaches play ~213 s in; the loop parks Anakin by his starfighter (no enemy or door seen) | 30.0 median over a parked view, not a reading |
| Halo: Combat Evolved (4D530004) | `halo-ce` (draft) | reaches the cryo bay; the calibration's light-aiming test needs screen-aware input | 29 fps in the bay; not a reading of play |
| Ninja Gaiden Black (5443000D) | `ninja-gaiden-black` (draft) | survey: no play inside 300 s (prologue + ~95 s load); route queued | -- |
| Conker: Live & Reloaded (4D530051) | none | survey reached only the multiplayer front end (Xbox Live sign-in loop); no single-player entry seen | -- |

Buffy is lane.routedriver2's (drive.py); not re-attempted here.
