# hakuX status

What is in flight right now. Generated from the working tree and updated as work lands.

The harness dashboard is [STATUS.md](STATUS.md).

## Right now

| Lane | Model | Running for | Working on |
|---|---|---|---|
| `gtasagpu1011` | claude-opus-5-5 | 2 min | gtasagpu1011: GTA San Andreas, hard-edged sky polygons and no shadow under CJ (#433, 0.5) |
| `nfsaudio1011` | claude-opus-5-5 | 15 min | nfsaudio1011: NFS Most Wanted audio stutter -- the APU plays 50 ms-old audio in place of ~15% of the sound (#4 |
| `profilegate1011` | claude-sonnet-5 | 11 min | profilegate1011: NOTES.md -- attempt 2/3 status (#433) |
| `snapshot1011` | claude-opus-5-5 | 53 min | snapshot1011: save states phase 0 -- a save and a load that survive a scene change (#433) |

- **Handhelds:** 2 connected.
  - Nova: free for the queue
  - Thor: held by `lanelocal-fanwait`
- **Device queue:** 4 waiting, 1 running.
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
| `lane/gtasagpu1011` | gtasagpu1011: GTA San Andreas, hard-edged sky polygons and no shadow under CJ (#433, 0.5) | `71c112273b` | 2026-10-11 18:14 |
| `lane/nfsaudio1011` | nfsaudio1011: NFS Most Wanted audio stutter -- the APU plays 50 ms-old audio in place of ~15% of the sound (#433, 0.5) | `cf35ffaea0` | 2026-10-11 18:01 |
| `lane/profilegate1011` | profilegate1011: NOTES.md -- attempt 2/3 status (#433) | `0b39d33f3f` | 2026-10-11 18:04 |
| `lane/snapshot1011` | snapshot1011: save states phase 0 -- a save and a load that survive a scene change (#433) | `6c484868b9` | 2026-10-11 17:48 |

## Recently landed on master

- 2026-10-11 soakvideo1011-step2: device proof of the dispatcher's soak video capture (#433, 0.5)
- 2026-10-11 nfsdefault1011: the three NFS switches on by default, and "Submit frame buffering" honoured (#433, 0.5)
- 2026-10-11 profileconv1011: gta-sa and amped2 measure on their golden profiles (#433)
- 2026-10-11 soakvideo1011: screen video during a routed soak, from the dispatcher
- 2026-10-11 fastpaths1010: the six renderer switches as one Graphics toggle, on by default (#433, 0.5)

_Updated 2026-10-11 18:15 PDT. Rebuilt on the host every 15 minutes and pushed here at most every 30._
