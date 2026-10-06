# hakuX status

What is in flight right now. Generated from the working tree and updated as work lands.

## 0.5 release: 50 Playable titles

**27 of 50** titles confirmed Playable (6 today). A title is Playable after a 600 s held run on a handheld at or above the frame-rate bar, with every kept frame reviewed.

| Confirmed | Title | Result |
|---|---|---|
| 2026-10-05 | MLB SlugFest - Loaded | PASS 600.8 s, play_share 0.9995, fps_ok 1.0 (30 fps bar, window median 58.9, min 29.7), 0 hitches, audio_starve 0, no crash/hang (flicker not yet checked) |
| 2026-10-05 | MLB SlugFest 2004 | PASS 603.9 s, play_share 0.9997, fps_ok 1.0 (30 fps bar, window median 44.4, min 32.0), 0 hitches, audio_starve 0, no crash/hang (flicker not yet checked) |
| 2026-10-05 | AMF Bowling 2004 | accepted on review (89.2% against a 90% bar: 66 s walk-back through title and controller select after the 10-frame game ended) (flicker not yet checked) |
| 2026-10-05 | MLB SlugFest 2003 | accepted on review (88.3% against a 90% bar: 74 s still between pitches, the game's pitch cycle) (flicker not yet checked) |
| 2026-10-05 | NBA 2K2 | PASS 606.8 s, play_share 0.9996, fps_ok 0.995 (30 fps bar, window median 57.0, min 20.1), 0 hitches, audio_starve 0, no crash/hang (flicker not yet checked) |
| 2026-10-05 | NFL Blitz 2002 | PASS 606.9 s, play_share 0.990, fps_ok 0.996 (30 fps bar, window median 45.1, min 25.2), 0 hitches, audio_starve 0, no crash/hang (flicker not yet checked) |
| 2026-10-04 | Tork: Prehistoric Punk | PASS 632.7 s, play_share 0.952 (30 s 'still' excluded), fps_ok 1.0 (30 fps bar, overlay reads 29), 0 hitches, audio_starve 0, no crash/hang (flicker not yet checked) |
| 2026-10-04 | Jet Set Radio Future | PASS 602 s, play_share 0.9997, fps_ok 1.0 (30 fps bar), 0 hitches, audio_starve 0, no crash/hang (flicker not yet checked) |
| 2026-10-04 | MTV Celebrity Deathmatch | accepted on review (87.8% against a 90% bar: 37 s cutscene + 34 s menu between rounds) (flicker not yet checked) |
| 2026-10-04 | Dark Summit | PASS 606 s, play_share 0.9998, fps_ok 0.9318 (28.5 bar, median 45.9, min 25.8), 2 hitches worst 128 ms, audio_starve 0 (flicker not yet checked) |
| 2026-10-04 | The Simpsons Hit & Run | PASS 605.7 s, play_share 0.9998, fps_ok 1.0 (30 fps bar, median 37.9, min 28.75), 0 hitches, audio_starve 0 (flicker not yet checked) |
| 2026-10-03 | Panzer Dragoon Orta | PASS 603.7 s, play_share 0.9997, fps_ok 0.9962 (30 fps bar, median 54.1), 7 hitches worst 386 ms (6 shader) |
| 2026-10-03 | Halo: Combat Evolved | PASS 722 s, fps_ok 0.994 (30 fps title, 29.97 median), static 0%, one 633-ms compile hitch at +8 s |
| 2026-10-03 | Spikeout: Battle Street | PASS 607.3 s, fps_ok 1.0, play_share 0.9996 |
| 2026-10-03 | Castlevania: Curse of Darkness | PASS 677 s, fps_ok 1.0, worst hitch 173 ms |
| 2026-10-03 | Gunvalkyrie | accepted on owner review |
| 2026-10-02 | ToeJam & Earl III: Mission to Earth | 600 s held run on the Nova |
| 2026-10-01 | Tony Hawk's Pro Skater 2x | 600 s held run on the Nova |
| 2026-10-01 | 187: Ride or Die | 600 s held run on the Nova |
| 2026-09-30 | Kabuki Warriors | 600 s held run on the Nova |
| 2026-09-30 | Crimson Skies: High Road to Revenge | 600 s held run on the Nova |
| 2026-09-30 | Baldur's Gate: Dark Alliance | 600 s held run on the Nova |
| 2026-09-30 | 50 Cent: Bulletproof | 600 s held run on the Nova |
| 2026-09-30 | WWE Raw 2 | 600 s held run on the Nova |
| 2026-09-29 | Azurik: Rise of Perathia | 600 s held run on the Nova |
| 2026-09-29 | KOF: Maximum Impact – Maniax | 600 s held run on the Nova |
| 2026-09-26 | Alien Hominid | 600 s held run on the Thor |

## Work in progress

| Branch | Topic | Tip | Last change |
|---|---|---|---|
| `lane/frametrace` | frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame | `7e47dde38c` | 2026-10-05 17:17 |
| `lane/pathfind` | pathfind: a screen-reading agent that drives a title from boot into gameplay | `13728a9fd5` | 2026-10-05 16:56 |

## Recently landed on master

- `8522288a77` 2026-10-05 fold: lane/dashretro (offline) -- dashretro: the 0.5 panel counts the Playable ledger and pathfind's held runs (#433)
- `22aa0df5d9` 2026-10-05 dashretro: the 0.5 panel counts the Playable ledger and pathfind's held runs (#433)
- `d354705c69` 2026-10-05 fold: lane/hitchcause (offline) -- hitchcause: the MTV 330 ms hitches are guest-side waits, not the IDE host read ([ide425d] held run on af3
- `750d572f1c` 2026-10-05 fold: lane/belowbar1005 (offline) -- belowbar1005: the #804 fence wait is not what holds Buffy, NG Black or DOA3 below the bar; their bounds
- `fde487f5a0` 2026-10-05 belowbar1005: answer, side effects, do-not-repeat; PR ready (#433)
- `01f1bfb7a1` 2026-10-05 belowbar1005: commit the survey output (#433)
- `73b699f27f` 2026-10-05 belowbar1005: cross-title non-render GPU survey; the answer table and per-title P x win (#433)
- `3c0433736b` 2026-10-05 belowbar1005: DOA3: no occlusion queries; the dojo stage is GPU-bound (58 ms/frame) plus one sync surface download per flip (#433)
- `583fa640fb` 2026-10-05 belowbar1005: NGB share fix; Buffy perflog walk soak queued (#433)
- `f078663ebc` 2026-10-05 belowbar1005: NG Black: reads occlusion queries but the wait never blocks (pend=0 x190); GPU-bound, half the GPU time outside render passes 
- `eef7590935` 2026-10-05 belowbar1005: OUTBOX Buffy verdict (#433)
- `8c14ed643d` 2026-10-05 belowbar1005: Buffy arm W: 0.67 vs 0.83 with the wait code not run in either arm; the gap is the walk (forest path vs courtyard) (#433)
- `a160529e4a` 2026-10-05 hitchcause: MTV [ide425d] hold on af37f7a3ea: the 330 ms hitches are guest-side waits, not the IDE host read (#433, #819)
- `0dd4c30436` 2026-10-05 belowbar1005: Buffy arm N: Buffy reads no occlusion queries, the fence wait never runs on it; NGB and DOA3 perflog soaks queued, routes from
- `097eb9567d` 2026-10-05 belowbar1005: build per below-bar run (Buffy/NGB ran without the #804 wait), offline bounds, Buffy WAIT A/B registered (#433)

_Updated 2026-10-05 17:58 PDT._
