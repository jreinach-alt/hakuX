# hakuX status

What is in flight right now. Generated from the working tree and updated as work lands.

The harness dashboard is [STATUS.md](STATUS.md).

## Right now

| Lane | Model | Running for | Working on |
|---|---|---|---|
| `pmucounters` | claude-opus-5-5 | 56 min | Lane: pmucounters            Issue: #433 |
| `surfgpu1009` | claude-opus-5-5 | 56 min | surfgpu1009: a GPU-side route for the reuse/surfupd rebind, behind HAKUX_SURFGPU=1 (NBA Live 05/06/07) (#433,  |

- **Handhelds:** 2 connected.
  - Nova: free for the queue
  - Thor: held by `lanelocal-fanwait`
- **Device queue:** 5 waiting, 1 running.
- **Latest nightly:** `nightly-2026-10-09`, build `5810476b58`.

## 0.5 release: Playable titles

**44 titles are confirmed Playable** (0 today), toward the 0.5 goal of 50. Each one ran for 10 minutes on a handheld at or above the frame-rate bar, and every kept frame was reviewed.

| Confirmed | Title | Result |
|---|---|---|
| 2026-10-08 | Max Payne 2: The Fall of Max Payne | Playable, 10-minute run |
| 2026-10-07 | Legacy of Kain: Defiance | Playable, 10-minute run |
| 2026-10-07 | The Lord of the Rings: The Fellowship of the Ring | Playable, 10-minute run |
| 2026-10-07 | SpongeBob SquarePants: Battle for Bikini Bottom | Playable, 10-minute run |
| 2026-10-07 | Indigo Prophecy | Playable, 10-minute run |
| 2026-10-07 | Blade II | Playable, 10-minute run |
| 2026-10-07 | Capcom vs. SNK 2 EO | Playable, 10-minute run |
| 2026-10-07 | Future Tactics: The Uprising | Playable, 10-minute run on the Nova, median 59.9 fps |
| 2026-10-06 | Call of Duty 3 | Playable, 10-minute run on the Nova |
| 2026-10-06 | NBA Live 2004 | Playable, 10-minute run on the Nova |
| 2026-10-06 | Blowout | Playable, accepted on review, median 0.34 fps |
| 2026-10-06 | Fight Club | Playable, 10-minute run on the Nova, median 43.4 fps |
| 2026-10-06 | Mortal Kombat: Armageddon | Playable, 10-minute run, median 59.2 fps |
| 2026-10-06 | NBA 2K3 | Playable, 10-minute run, median 42.9 fps |
| 2026-10-06 | World Soccer Winning Eleven 9 | Playable, 10-minute run, median 59.9 fps |
| 2026-10-06 | Ratatouille | Playable, 10-minute run, median 52.8 fps |
| 2026-10-06 | Rogue Trooper | Playable, 10-minute run, median 58.9 fps |
| 2026-10-05 | MLB SlugFest - Loaded | Playable, 10-minute run, median 58.9 fps |
| 2026-10-05 | MLB SlugFest 2004 | Playable, 10-minute run, median 44.4 fps |
| 2026-10-05 | AMF Bowling 2004 | Playable, accepted on review, median 59.9 fps |
| 2026-10-05 | MLB SlugFest 2003 | Playable, accepted on review, median 59.9 fps |
| 2026-10-05 | NBA 2K2 | Playable, 10-minute run, median 57.0 fps |
| 2026-10-05 | NFL Blitz 2002 | Playable, 10-minute run, median 45.1 fps |
| 2026-10-04 | Tork: Prehistoric Punk | Playable, 10-minute run |
| 2026-10-04 | Jet Set Radio Future | Playable, 10-minute run on the Nova |
| 2026-10-04 | MTV Celebrity Deathmatch | Playable, accepted on review, median 57.3 fps |
| 2026-10-04 | Dark Summit | Playable, 10-minute run, median 45.9 fps |
| 2026-10-04 | The Simpsons Hit & Run | Playable, 10-minute run, median 37.9 fps |
| 2026-10-03 | Panzer Dragoon Orta | Playable, 10-minute run, median 54.1 fps |
| 2026-10-03 | Halo: Combat Evolved | Playable, 10-minute run, median 29.97 fps |
| 2026-10-03 | Spikeout: Battle Street | Playable, 10-minute run |
| 2026-10-03 | Castlevania: Curse of Darkness | Playable, 10-minute run |
| 2026-10-03 | Gunvalkyrie | Playable, accepted on review |
| 2026-10-02 | ToeJam & Earl III: Mission to Earth | Playable, 10-minute run on the Nova |
| 2026-10-01 | Tony Hawk's Pro Skater 2x | Playable, 10-minute run on the Nova |
| 2026-10-01 | 187: Ride or Die | Playable, 10-minute run on the Nova |
| 2026-09-30 | Kabuki Warriors | Playable, 10-minute run on the Nova |
| 2026-09-30 | Crimson Skies: High Road to Revenge | Playable, 10-minute run on the Nova |
| 2026-09-30 | Baldur's Gate: Dark Alliance | Playable, 10-minute run on the Nova |
| 2026-09-30 | 50 Cent: Bulletproof | Playable, 10-minute run on the Nova |
| 2026-09-30 | WWE Raw 2 | Playable, 10-minute run on the Nova |
| 2026-09-29 | Azurik: Rise of Perathia | Playable, 10-minute run on the Nova |
| 2026-09-29 | KOF: Maximum Impact – Maniax | Playable, 10-minute run on the Nova |
| 2026-09-26 | Alien Hominid | Playable, 10-minute run on the Thor |

28 of these still await the owner's flicker check.

## Work in progress

| Branch | Topic | Tip | Last change |
|---|---|---|---|
| `lane/pmucounters` | Lane: pmucounters            Issue: #433 | `0afc17fbbc` | 2026-10-09 15:41 |
| `lane/surfgpu1009` | surfgpu1009: a GPU-side route for the reuse/surfupd rebind, behind HAKUX_SURFGPU=1 (NBA Live 05/06/07) (#433, 0.5) | `52f9b89435` | 2026-10-09 15:50 |

## Recently landed on master

- 2026-10-09 usagemode1009: usage Low is a read-time cap, re-evaluated every tick (#433)
- 2026-10-09 fpstelemetry1008b: the four titles lane A could not measure -- NFS Most Wanted, Midnight Club II, Fantastic 4, Dino Crisis 3 (#433)
- 2026-10-09 fpstelemetry1008: one cause table for the below-bar titles -- perflog + GPU xfr + frame trace on the Nova (#433)
- 2026-10-09 surfdl1008: does the NBA Live 05 surface-download finding generalise? NBA Live 06/07, Midnight Club 2 (#433, 0.5)
- 2026-10-09 profileddefault1008: TU_AUTOTUNE_ALGO=profiled behind an autotune override
- 2026-10-08 fpstelemetry1008: one cause table for the below-bar titles -- perflog + GPU xfr + frame trace on the Nova (#433)
- 2026-10-08 surfdl1008: does the NBA Live 05 surface-download finding generalise? NBA Live 06/07, Midnight Club 2 (#433, 0.5)
- 2026-10-08 selfdeps: builds fetch nothing from GitHub (#433)
- 2026-10-07 stuckdetect1007: a stuck/menu detector for pathfind's 600-s hold, validated offline on stored frames (#433)
- 2026-10-07 harnessfix1006: the Nova's runs record their build, and a test build never stays on it -- fixed the release check itself, which never matched a real run
- 2026-10-07 gpunonrender: GMEM vs sysmem on the replay-bound titles, census on
- 2026-10-06 dispatchgate1006: a generated title registry and one admit() gate between "decide to run it" and a handheld (shadow mode)

_Updated 2026-10-09 16:00 PDT. Rebuilt on the host every 15 minutes and pushed here at most every 30._
