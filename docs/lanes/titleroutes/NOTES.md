# lane.titleroutes: profile-setup and gameplay routes for titles on the handhelds

Issue #397 (0.5 tracking #433). Brief: `briefs/titleroutes.md` (hostops,
2026-09-26 18:20 PDT). Base `ed6830c930`.

## 1. The work list (2026-09-26, `adb shell ls` of each DEVICE_ISO_ROOT)

57 distinct titles are on the two handhelds (Nova `ee317437`
`/storage/E6C6-D7AA/Games/XBox`, Thor `bdc158a5`
`/storage/388C-68F7/ROMS/xbox`); the other 60 ISOs are nxdk test discs.
Dropped: the 9 titles of the titlebench batch (25 to Life, Blinx 2, Crimson
Skies, Agent Under Fire, Blinx, Forza, DOA1U, CoD3, Burnout 3). ISOs without
an id prefix were mapped by name to the compat CSV by hand
(`scratch/worklist.py`, not committed); where the CSV has several regional
ids, the `canonical_title_id` is used. Order: xemu rating (Perfect, then
Playable), then `download-priority-2026-09-25.csv` (`-` = not in that list).

| # | title_id | name | xemu | dl prio | nova | thor |
|---|---|---|---|---|---|---|
| 1 | 43560001 | Kabuki Warriors | Perfect | 21 | `43560001-Kabuki_Warriors.xiso.iso` |  |
| 2 | 4B420001 | Batman: Dark Tomorrow | Perfect | 22 | `4B420001-Batman_Dark_Tomorrow.xiso.iso` |  |
| 3 | 54430007 | Dead or Alive Xtreme Beach Volleyball | Playable | 3 | `54430007-Dead_or_Alive_Xtreme_Beach_Volleyball.xiso.iso` |  |
| 4 | 45410083 | Black | Playable | 4 |  | `45410083-Black.xiso.iso` |
| 5 | 45410026 | 007: Nightfire | Playable | 5 | `45410026-007_Nightfire.xiso.iso` |  |
| 6 | 4D530003 | Project Gotham Racing | Playable | 6 |  | `4D530003-Project_Gotham_Racing.xiso.iso` |
| 7 | 4541005D | GoldenEye: Rogue Agent | Playable | 7 | `4541005D-GoldenEye_Rogue_Agent.xiso.iso` |  |
| 8 | 56550042 | 50 Cent: Bulletproof | Playable | 10 | `56550042-50_Cent_Bulletproof.xiso.iso` |  |
| 9 | 5451000D | WWE Raw 2 | Playable | 13 | `5451000D-WWE_Raw_2.xiso.iso` |  |
| 10 | 4D53004B | Project Gotham Racing 2 | Playable | 14 |  | `4D53004B-Project_Gotham_Racing_2.xiso.iso` |
| 11 | 45410076 | Burnout Revenge | Playable | 15 | `45410076-Burnout_Revenge.xiso.iso` |  |
| 12 | 56550016 | Bruce Lee: Quest of the Dragon | Playable | 18 |  | `56550016-Bruce_Lee_Quest_of_the_Dragon.xiso.iso` |
| 13 | 54540079 | Midnight Club 3: DUB Edition | Playable | 19 | `54540079-Midnight_Club_3_DUB_Edition.xiso.iso` |  |
| 14 | 56550036 | Crash Twinsanity | Playable | 20 |  | `56550036-Crash_Twinsanity.xiso.iso` |
| 15 | 55530036 | 187: Ride or Die | Playable | 23 | `55530036-187_Ride_or_Die.xiso.iso` |  |
| 16 | 41540002 | Shin Megami Tensei: Nine | Playable | 24 |  | `41540002-Shin_Megami_Tensei_Nine.xiso.iso` |
| 17 | 43430019 | Capcom Classics Collection Vol. 2 | Playable | 25 |  | `43430019-Capcom_Classics_Collection_Vol_2.xiso.iso` |
| 18 | 4B4E002D | Castlevania: Curse of Darkness | Playable | 26 |  | `4B4E002D-Castlevania_Curse_of_Darkness.xiso.iso` |
| 19 | 4D53006B | MechAssault 2: Lone Wolf | Playable | 27 |  | `4D53006B-MechAssault_2_Lone_Wolf.xiso.iso` |
| 20 | 56550003 | Crash Bandicoot: The Wrath of Cortex | Playable | 28 | `56550003-Crash_Bandicoot_The_Wrath_of_Cortex.xiso.iso` |  |
| 21 | 58490004 | Black Stone: Magic & Steel | Playable | 29 | `58490004-Black_Stone_Magic_Steel.xiso.iso` |  |
| 22 | 4C410017 | Star Wars: Episode III: Revenge of the Sith | Playable | 30 | `4C410017-Star_Wars_Episode_III_Revenge_of_the_Sith.xiso.iso` |  |
| 23 | 48550001 | Bloody Roar: Extreme | Playable | 31 | `48550001-Bloody_Roar_Extreme.xiso.iso` |  |
| 24 | 49470017 | Gunvalkyrie | Playable | 32 | `5345000B-Gunvalkyrie.xiso.iso` |  |
| 25 | 41540004 | Galleon | Playable | - | `Galleon (USA).xiso.iso` | `Galleon (USA).xiso.iso` |
| 26 | 41560001 | Tony Hawk's Pro Skater 2x | Playable | - |  | `Tony Hawk's Pro Skater 2x (USA).xiso.iso` |
| 27 | 43430003 | Dino Crisis 3 | Playable | - | `Dino Crisis 3.iso` |  |
| 28 | 45410012 | Buffy the Vampire Slayer | Playable | - | `Buffy the Vampire Slayer (USA).xiso.iso` |  |
| 29 | 49470018 | JSRF: Jet Set Radio Future | Playable | - | `JSRF - Jet Set Radio Future (USA).xiso.iso` | `JSRF - Jet Set Radio Future (USA).xiso.iso` |
| 30 | 4947002B | Panzer Dragoon Orta | Playable | - | `Panzer Dragoon Orta (Europe).iso` | `Panzer Dragoon Orta (Europe).iso` |
| 31 | 4D4A0012 | Psychonauts | Playable | - |  | `Psychonauts (USA).iso` |
| 32 | 4D530002 | Fuzion Frenzy | Playable | - | `Fuzion Frenzy (USA).xiso.iso` |  |
| 33 | 4D530004 | Halo: Combat Evolved | Playable | - | `Halo Combat Evolved.iso` |  |
| 34 | 4D530017 | MechAssault | Playable | - |  | `MechAssault.iso` |
| 35 | 4D53002D | Dead or Alive 3 | Playable | - |  | `Dead or Alive 3 (USA) (En,Ja).xiso.iso` |
| 36 | 4D530039 | RalliSport Challenge 2 | Playable | - | `RalliSport Challenge 2 (Japan, Europe).iso` | `RalliSport Challenge 2 (Japan, Europe).iso` |
| 37 | 4D530041 | Amped 2 | Playable | - | `Amped 2 (USA).xiso.iso` | `Amped 2 (USA).xiso.iso` |
| 38 | 4D530046 | Phantom Dust | Playable | - |  | `Phantom Dust (USA) (En,Ja).xiso.iso` |
| 39 | 4D530051 | Conker: Live & Reloaded | Playable | - | `Conker Live & Reloaded.iso` |  |
| 40 | 4D530053 | Grabbed by the Ghoulies | Playable | - | `Grabbed by the Ghoulies (USA) (En,Fr,De,Es,It).xiso.iso` | `Grabbed by the Ghoulies (USA) (En,Fr,De,Es,It).xiso.iso` |
| 41 | 4D530064 | Halo 2 | Playable | - | `Halo 2.iso` |  |
| 42 | 5345000F | ToeJam & Earl III: Mission to Earth | Playable | - | `ToeJam & Earl III - Mission to Earth (USA).iso` | `ToeJam & Earl III - Mission to Earth (USA).iso` |
| 43 | 53450029 | Spikeout: Battle Street | Playable | - | `Spikeout - Battle Street (Europe).iso` | `Spikeout - Battle Street (Europe).iso` |
| 44 | 54430003 | Ninja Gaiden | Playable | - |  | `Ninja Gaiden (Europe) (En,Fr,De,Es,It).iso` |
| 45 | 5443000D | Ninja Gaiden Black | Playable | - | `Ninja Gaiden Black.iso` |  |
| 46 | 55530004 | Deathrow | Playable | - |  | `Deathrow (USA).xiso.iso` |
| 47 | 55530040 | Tork: Prehistoric Punk | Playable | - | `Tork - Prehistoric Punk (USA).iso` | `Tork - Prehistoric Punk (USA).iso` |
| 48 | 42560001 | Tron 2.0: Killer App | Starts | - | `Tron 2.0 - Killer App (USA, Europe).iso` | `Tron 2.0 - Killer App (USA, Europe).iso` |

## 2. Sessions

Helpers (in `scratch/`, not committed): `dev.sh <dev> take|launch <iso>|release|state`
(launch = force-stop, wake, MAX perf 2/5, VIEW intent with `rom_path`),
`n.sh <dev> <nav.py args>` (touches the lease on every call), `lease.sh`
(touches the lease every 30 s while our hold exists), and `replay.sh <dev>
<iso> <route>` (fresh launch, `route.sh` under a timeout of the route's
pre-mark time + 40 s, frames to `scratch/replay/<route>-<hhmmss>/`).

### Session 1: HELD Nova, 18:37-18:54 PDT (17 min), battery 70% -> 64%

The Thor was taken first at 18:25 and released at once: battery 26%, under
the 30% floor (a titlebench soak was running on it at MAX).

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Kabuki Warriors (43560001) | nova | `kabuki-warriors.route` | yes, twice (18:42, 18:49) | Tour Mode fight vs a random CPU team; the timer and health bars run and the round restarts after a loss |

**Kabuki Warriors.** No profile step. Intro FMV (START) -> title (START)
-> Tour Mode is the default (START) -> Player Entry (A, then wait out the
30 s countdown) -> Tokaido map -> Character Select vs CPU (A x3) -> fight.
On the map, `LEFT` on the D-pad does nothing; START opens CONTINUE/MODE END,
and LX min held 1.2 s walks west, then A travels. Player control: with LX
min held the gap to the CPU grew (nav frames 016 -> 017), with LX max it
closed (021 -> 022). Frames:
`~/hakux-work/nav/kabuki.first-run-20260926T183708/022-forward5.png` (nav)
and `scratch/replay/kabuki-warriors-184913/185256-gameplay.png` (replay;
640x480 copy in `docs/lanes/titleroutes/frames/`).

- The first fight of the nav session ran at 2-16 fps with the game clock at
  about 1/20 of real time (shaders compiling for the first time); both
  replays ran the same fight at 59 fps. So the first run of a title on a
  device is not its speed.
- First replay: the mark came where nav.py put it, ~90 s into the fight,
  and by then the player had lost. The route was cut at the round start
  (`shot round` + 3 s) and the play pattern made to attack without pause
  (LX max, X, A, Y, B). After a loss A skips the winner pose and a new round
  starts by itself (probe session `kabuki-after.probe-20260926T185342`), so
  the 420 s window holds fights plus a few seconds of KO/winner poses per
  round.

### Session 2: HELD Nova, 19:02-19:17 PDT (15 min), battery 61% -> 56%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Batman: Dark Tomorrow (4B420001) | nova | none | - | alley fight vs three thugs; Batman is down in 5-15 s whatever is pressed |
| 007: Nightfire (45410026) | nova | `nightfire.route` | yes (19:14; one failed replay before it, 19:10) | Paris prologue: scoped on-rails sniping, auto-aim on, in-engine cutscenes between sections |

**Batman: Dark Tomorrow: no route (blocked on combat).** DC logo -> START ->
title -> START -> intro FMV (A, START) -> an alley with three thugs and a
HUD (health 53/91). The stick moves Batman, so it is gameplay, but he is
knocked out in 5-15 s idle and in ~5 s mashing X, then GAME OVER ->
CONTINUE (A) -> BATGEAR SELECTION (START) -> "start with this equipment?"
YES (A) -> the same alley. A soak would be mostly those menus. What would
unblock it: the button map for block/attack (A, B, X, Y and the triggers
were not tried one by one), or a later chapter reached by a save. Draft
inputs: `scratch/batman.draft.route` (not committed).

**007: Nightfire.** No profile step and no main menu: title START -> gun
barrel (A) -> the Paris prologue, "Tutorial: Limited weapon control". The
first RT pull shot a car's tyre (crash cutscene), so RT drives the game.
Two traps:

- Sweeping the aim (RX) while firing is not what fails the mission; idling
  is. Both the nav session and replay 1 failed ("Mission Failed: REPLAY
  TUTORIAL") during a 16 s idle before the mark with a target up.
- The prologue ran ahead of the nav session's timing in replay 1, so a
  timed shot missed its target. The route now marks gameplay right after
  the unpause and pulls RT every 0.8 s from there; auto-aim does the aiming
  and a pull during a cutscene does nothing. Replay 2: sniping at the mark,
  an in-engine cutscene and no failure 75 s later
  (`scratch/replay/nightfire-191407/`, 640x480 copy of the mark frame in
  `frames/nightfire-replay-gameplay.jpg`). What the 420 s window holds
  after those 75 s is not seen: if the prologue ends in a free-roam
  section, fire-only input will stand still there.

### Session 3: HELD Nova, 19:19-19:38 PDT (hold; device used from 19:25), battery 54% -> 50%

The Thor was at **9%** at 19:18 while running a titlebench soak at MAX
perf, so it could not be held (and is a device risk; written to
`host-tools/hostops-inbox.md`, 19:18).

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| GoldenEye: Rogue Agent (4541005D) | nova | `goldeneye-ra.first-run.route` | yes (19:32) | first person in the helicopter of Fort Knox; the view turns with RX |

**GoldenEye: Rogue Agent.** The profile keyboard (CREATE NEW PROFILE,
PLAYER1 pre-filled) comes up on every boot, because the profile the nav
session made was never flushed to the disk (the launch force-stops the app).
So the first-run route replays on this disk as it is. **pad.sh's D-pad
buttons did not move the keyboard cursor** (nor Kabuki's map); the left
stick does, one key per 0.15 s flick. pad.sh sends `press LEFT` as the
BTN_DPAD_LEFT key (code 546); it also has `axis HATX|HATY`, which is likely
what these games read as the D-pad (not yet tried).

**Variant choice:** `titlestate.py choose` for 4541005D on the Nova gives
`first-run` ("known to have no profile") once targets.toml names the
route. For a single-file route (Kabuki, Nightfire) it answers `survey.route`
with variant first-run, since it only looks for `<route>.<variant>.route`.
`request.sh --route <stem>` reads `routes/<stem>.route` directly, so the host queues these by file stem; on the board request.

### Session 4: HELD Nova, 19:43-19:57 PDT (device used from 19:46), battery 48% -> 44%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Dead or Alive Xtreme Beach Volleyball (54430007) | nova | `doax.route` | yes (19:51) | Exhibition 2-on-2 match; rallies at 14-25 fps, a reaction cutaway after each point |

**DOAX.** EXHIBITION instead of Zack Island avoids pass 1's trap (the
vacation's shop menu). Character select wants A for each pick, swimsuit and
mood: 13 A presses, 3-5 s apart. The nav session's match stood at 0-2 after
~30 s of play; the replay's at 1-1 at mark + 60 s
(`frames/doax-replay-end.jpg`), so the pattern (LX sweeps, A and B) does
return balls. The end of a match (7 points?) was not seen: the 420 s window
may reach a results screen, which A may or may not leave.
