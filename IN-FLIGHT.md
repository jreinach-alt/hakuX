# hakuX status

What is in flight right now. Generated from the working tree and updated as work lands.

The harness dashboard is [STATUS.md](STATUS.md).

## Right now

| Lane | Model | Running for | Working on |
|---|---|---|---|
| `drawrec1010` | claude-opus-5-5 | 33 min | drawrec1010: census of consecutive-draw state at the NFS Most Wanted race start, then dirty-tracked reuse (#43 |
| `texscan1010` | claude-opus-5-5 | 12 min | lane.texscan1010 -- create_texture()'s surface-range scan: a GPU-side copy instead of the synchronous download |

- **Handhelds:** 2 connected.
  - Nova: free for the queue
  - Thor: held by `lanelocal-fanwait`
- **Device queue:** 6 waiting, 1 running.
- **Latest nightly:** `nightly-2026-10-10`, build `7d574ece8b`.

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
| `lane/drawrec1010` | drawrec1010: census of consecutive-draw state at the NFS Most Wanted race start, then dirty-tracked reuse (#433, 0.5) | `a12cab4e54` | 2026-10-10 11:18 |
| `lane/texscan1010` | lane.texscan1010 -- create_texture()'s surface-range scan: a GPU-side copy instead of the synchronous download, behind H | `8fa509de16` | 2026-10-10 09:51 |

## Recently landed on master

- 2026-10-10 Lane: perdrawon1010       Issue: #433 (umbrella), none filed
- 2026-10-10 perdraw1009: cut the renderer's per-draw CPU cost (NFS Most Wanted, ~11 us per draw) (#433, 0.5)
- 2026-10-10 Lane: nightlywrap1010            Issue: none (dispatched directly by lane.local, #433 umbrella)
- 2026-10-10 lane.lanepath1009: lane.sh gives each lane unit a shim-first PATH with --setenv (#433, 0.5)
- 2026-10-10 ghlive1010 -- AGENTS.md: GitHub is up
- 2026-10-10 Lane: restoreleak1009            Issue: #433
- 2026-10-10 boardgateenv1009 -- the board push gate stages master's docs/testing into the pushing tree's index (#433, 0.5)
- 2026-10-10 surfgpudefault1009: the surfgpu switch as a Graphics toggle, on by default (#433, 0.5)
- 2026-10-10 surfgpu1009: a GPU-side route for the reuse/surfupd rebind, behind HAKUX_SURFGPU=1 (NBA Live 05/06/07) (#433, 0.5)
- 2026-10-09 nightlynotes1009: list offline folds, and publish nothing when nothing changed (#433, 0.5)

_Updated 2026-10-10 11:29 PDT. Rebuilt on the host every 15 minutes and pushed here at most every 30._
