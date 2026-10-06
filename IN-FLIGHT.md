# hakuX status

What is in flight right now. Generated from the working tree and updated as work lands.

The harness dashboard is [STATUS.md](STATUS.md).

## Right now

| Lane | Model | Running for | Working on |
|---|---|---|---|
| `pathfind` | claude-sonnet-5 | 59 min | pathfind: a screen-reading agent that drives a title from boot into gameplay |

- **Handhelds:** 2 connected.
  - Nova: held by `lane.pathfind`
  - Thor: held by `lanelocal-fanwait`
- **Device queue:** 5 waiting, 0 running.
- **Latest nightly:** `nightly-2026-10-05`, build `d32c35d3ce`.

## 0.5 release: Playable titles

**27 titles are confirmed Playable** (0 today), toward the 0.5 goal of 50. Each one ran for 10 minutes on a handheld at or above the frame-rate bar, and every kept frame was reviewed.

| Confirmed | Title | Result |
|---|---|---|
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

11 of these still await the owner's flicker check.

## Work in progress

| Branch | Topic | Tip | Last change |
|---|---|---|---|
| `lane/pathfind` | pathfind: a screen-reading agent that drives a title from boot into gameplay | `33babeca6b` | 2026-10-06 01:41 |

## Recently landed on master

- 2026-10-06 frametrace: the PFIFO thread's GPU waits named per title (draw.c:4386 under pfifo.lock on Simpsons
- 2026-10-05 frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame
- 2026-10-05 dashretro: the 0.5 panel counts the Playable ledger and pathfind's held runs (#433)
- 2026-10-05 hitchcause: the MTV 330 ms hitches are guest-side waits, not the IDE host read ([ide425d] held run on af37f7a3ea) (#433)
- 2026-10-05 belowbar1005: the #804 fence wait is not what holds Buffy, NG Black or DOA3 below the bar
- 2026-10-04 accuracy804 (re-open): the #804 fix keeps the rival cars
- 2026-10-04 accuracy804: RalliSport's cars blink on alternate frames (#804): identified and fixed
- 2026-10-04 dispatcher: a soak from a pre-libfolders ref still finds its games folder
- 2026-10-04 hddperm: dev_push removes <path>.new on a failed push
- 2026-10-04 303: surface write-back probe for Spikeout's FMV green blocks (lane.fmv303c)
- 2026-10-04 hangwatch: a locked-up title is caught on telemetry in about 90 s, not waited out

_Updated 2026-10-06 01:48 PDT. Rebuilt on the host every 15 minutes and pushed here at most every 30._
