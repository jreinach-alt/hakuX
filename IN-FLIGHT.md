# hakuX status

What is in flight right now. Generated from the working tree and updated as work lands.

The harness dashboard is [STATUS.md](STATUS.md).

## Right now

| Lane | Model | Running for | Working on |
|---|---|---|---|
| `gtaroutes1011` | claude-sonnet-5 | 1h 27m | gtaroutes1011: routes into play for GTA III, Vice City, and a San Andreas driving route (#433, 0.5) |
| `gtasagpu1011` | claude-opus-5-5 | 47 min | gtasagpu1011: GTA San Andreas, hard-edged sky polygons and no shadow under CJ (#433, 0.5) |
| `pathclass` | claude-sonnet-5 | 32 min | pathclass: a local GPU screen-state classifier for pathfind (#433) |
| `snapshot1011` | claude-opus-5-5 | 15 min |  |
| `soakvideo1011` | claude-sonnet-5 | 2h 39m | soakvideo1011: screen video during a routed soak, from the dispatcher; route crops now travel with the request |

- **Handhelds:** 2 connected.
  - Nova: free for the queue
  - Thor: held by `lanelocal-fanwait`
- **Device queue:** 24 waiting, 1 running.
- **Latest nightly:** `nightly-2026-10-11`, build `7f986f73f6`.

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
| `lane/gtaroutes1011` | gtaroutes1011: routes into play for GTA III, Vice City, and a San Andreas driving route (#433, 0.5) | `a117f85735` | 2026-10-11 13:36 |
| `lane/gtasagpu1011` | gtasagpu1011: GTA San Andreas, hard-edged sky polygons and no shadow under CJ (#433, 0.5) | `d2b6d51d6f` | 2026-10-11 13:03 |
| `lane/pathclass` | pathclass: a local GPU screen-state classifier for pathfind (#433) | `f442726741` | 2026-10-11 13:21 |
| `lane/soakvideo1011` | soakvideo1011: screen video during a routed soak, from the dispatcher; route crops now travel with the request (#433, 0. | `bee8b76571` | 2026-10-11 13:34 |

## Recently landed on master

- 2026-10-11 fastpaths1010: the six renderer switches as one Graphics toggle, on by default (#433, 0.5)
- 2026-10-11 lockwake1011: NFS Most Wanted's cold race start, which pfifo.lock site holds the guest's last 2.2 ms, and a lock-free wake (#433, 0.5)
- 2026-10-11 coldstart1010: NFS Most Wanted's first race start after loading, census and largest fix (#433, 0.5)
- 2026-10-11 Lane: restoreprio1011            Issue: #433
- 2026-10-11 Lane: restoreprio1011            Issue: #433

_Updated 2026-10-11 13:45 PDT. Rebuilt on the host every 15 minutes and pushed here at most every 30._
