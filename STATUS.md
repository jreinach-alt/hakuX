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
| `lane/pathfind` | pathfind: a screen-reading agent that drives a title from boot into gameplay | `27b2d82e2c` | 2026-10-05 20:21 |

## Recently landed on master

- `c3625aad90` 2026-10-05 fold: lane/frametrace (offline) -- frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame
- `fb3b8e652e` 2026-10-05 frametrace: Simpsons read; the lateness rule missed frames whose VBLANK the deferral held (period-late now; all four titles re-read); milest
- `7e47dde38c` 2026-10-05 frametrace: waiting on the Simpsons run (#433)
- `4633d9dadd` 2026-10-05 frametrace: Forza read; the in-row run class is wrong where the guest idles (Forza, most of Nightfire); duty overhead PASS; G1+G3 first; Sim
- `94968fcfb1` 2026-10-05 frametrace: duty overhead judged (pass), Forza captured; idlejoin.py splits guest idle from the in-row run; blind Simpsons route (#433)
- `02b01b7b44` 2026-10-05 Merge remote-tracking branch 'origin/master' into lane/frametrace
- `8522288a77` 2026-10-05 fold: lane/dashretro (offline) -- dashretro: the 0.5 panel counts the Playable ledger and pathfind's held runs (#433)
- `22aa0df5d9` 2026-10-05 dashretro: the 0.5 panel counts the Playable ledger and pathfind's held runs (#433)
- `f34c8cb6e0` 2026-10-05 frametrace: waiting on the duty overhead run and Forza (Nova); Simpsons script defaults to 65bd51712b (#433)
- `537607f767` 2026-10-05 frametrace: vCPU time in MMIO dispatch per frame and by region (in-row half of G9); hooks-g9.diff for system/memory.c ready for the grant (#
- `837f9c68b5` 2026-10-05 frametrace: first reads (Nightfire, Tron): late frames are the vCPU's (99.8%, 88.9%); GPU side waits on it; raw captures archived; one-run o
- `65bd51712b` 2026-10-05 frametrace: HAKUX_FRAMETRACE_DUTY, the overhead test inside one run (instrument off and on every s seconds); selftest 36 checks, 12 mutants 
- `d354705c69` 2026-10-05 fold: lane/hitchcause (offline) -- hitchcause: the MTV 330 ms hitches are guest-side waits, not the IDE host read ([ide425d] held run on af3
- `98c6791c56` 2026-10-05 Merge remote-tracking branch 'origin/master' into lane/frametrace
- `750d572f1c` 2026-10-05 fold: lane/belowbar1005 (offline) -- belowbar1005: the #804 fence wait is not what holds Buffy, NG Black or DOA3 below the bar; their bounds

_Updated 2026-10-05 20:31 PDT._
