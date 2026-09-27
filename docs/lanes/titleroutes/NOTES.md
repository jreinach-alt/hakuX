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

## State at the end of batch 1 (2026-09-26 20:00 PDT)

Posted on #397 (comment 5852128252). Four routes ready and on the board
request; the PR is marked ready so the host can fold them. Next, in work-list
order: Nova 50 Cent (profile keyboard: move to Done, not A), WWE Raw 2,
Burnout Revenge (Create Profile is one down), Midnight Club 3, 187 Ride or
Die, Crash: Wrath of Cortex; Thor (once charged above 30%): Black (past the
mission cutscene), PGR, PGR2, Bruce Lee (B out of Player Info), Crash
Twinsanity, SMT Nine.

## Attempt 2 (resumed 2026-09-26 20:45 PDT)

Why attempt 1 did not finish: it stopped after batch 1 (4 titles, 20:00 PDT)
and marked PR #455 ready, reading brief step 4 ("mark it ready after each
batch ... the host will fold them and resume you") as the end of a session.
The work list still had 44 titles. #455 was folded (a593d8eb85), and the
brief's addendum (lane.local, 20:44) says to run continuously down the list
on both handhelds. This attempt continues on a new PR from the same branch.

### Session 5: HELD Thor, 20:45-21:14 PDT (29 min), battery 88% -> 88%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Black (45410083) | thor | `black.returning.route` | yes (21:02) | first mission, ruined building, "FIND THE SHOTGUN"; the view turns with RX, RT fires and the ammo count falls |
| Project Gotham Racing (4D530003) | thor | `pgr.first-run.route` (nav-played to gameplay) | **no: the disk changed under it** | quick race, San Francisco, MINI; RT held, 14 mph at GO |

**A system dialog at boot.** The Thor showed Android's "Use USB for" dialog
over the game at the first frame; a tap on CANCEL (adb `input tap`, the
system UI, not the app) cleared it. It is not in any route. If a soak's
first frames show it, the dispatcher needs to dismiss it.

**Black.** The profile from pass 1 is still there (menu without the name
keyboard). Past pass 1's stop: the mission briefing FMV after NORMAL runs
~2.5 min and A, BACK, Y and START do not skip it; it ends in the first
mission. Nav frames `~/hakux-work/nav/black.returning-20260926T204551/`
(016-turned.png: control), replay `scratch/replay/black.returning-205408/`
(zz-end.png: same room, HUD, ammo 003).

**PGR: the profile persisted through the force-stop.** The nav session
created driver "Player" (save to hard disk, "progress will be saved
automatically"). The replay's fresh launch (force-stop, no HOME flush) found
it: "load or create new" came up on **load existing driver**, the route's A
went to "load from", and the rest of the route ran one screen off, ending
in arcade race's skill select. So unlike GoldenEye (19:32), a save made
through the game's own save flow did reach the disk. `titlestate.py record`
says `created` for PGR on the Thor. Next: a `pgr.returning.route` (load
existing -> hard disk -> the driver -> main menu), then replay it.

### Session 6: HELD Thor, 21:23-21:45 PDT (22 min; hold taken 21:17 while a soak finished), battery 88% -> 86%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Project Gotham Racing (4D530003) | thor | `pgr.returning.route` | yes (21:31) | quick race, San Francisco, MINI; 46 mph on lap 1 at the replay's end |
| Project Gotham Racing 2 (4D53004B) | thor | none yet (`scratch/pgr2.draft.route`) | **failed** | Instant Action race in Florence reached in the nav session; the replay took another path |

**PGR returning.** Load existing driver -> hard disk -> Player -> the same
main menu, then the first-run's path. Nav frames
`~/hakux-work/nav/pgr.returning-20260926T212324/` (009-moving.png: 37 mph
at +5 s), replay `scratch/replay/pgr.returning-212807/zz-end.png`.

**PGR2: a route that depends on the frame rate.** Instant Action needs no
profile, so one route would do. The nav session ran cold (4 fps: shaders
compiling), its START at the title was dropped and A (held 400 ms) opened
the menu. The replay ran warm (50 fps): the second START already reached
the menu, so the route's next A chose Create New Profile. A second nav
session (no START until the intro FMV, one START, A at the title) then
overshot: two 0.15 s stick flicks moved the menu cursor THREE items at
59 fps (to Xbox Demos). Next: step the menu with `axis HATX` (one item per
press, if the game reads the hat as the D-pad), and wait for the title
rather than counting presses.

### Session 7: HELD Thor, 22:15-22:40 PDT (25 min), battery 85% -> 84%

The Thor was under the host's dispatcher update window 21:51-22:15, so the
PGR benchmark waited and this session started when the window lifted.

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Bruce Lee: Quest of the Dragon (56550016) | thor | `bruce-lee.route` | yes (22:39; two replays before it failed, see below) | first fight, a dojo, two ninjas; Bruce runs and trades blows, health bar falls |
| Project Gotham Racing 2 (4D53004B) | thor | none | - | still no replayable path to Instant Action |

**Menu inputs that do not depend on the frame rate.** A menu either steps
once per push (edge-triggered) or auto-repeats while held; a quick stick
flick or hat tap is ambiguous across frame rates in the second kind and can
be lost in the first.
- Bruce Lee's Player Info / Purchase Moves / Continue menu is
  edge-triggered: LY held 3 s moved one item. So the route pushes the stick
  down twice, each held 1.5-3 s. Quick hat taps (HATY max, mid at once)
  stepped it in the nav session and were ignored in the replay (replay
  `scratch/replay/bruce-lee-222946/`, ended on the Player Info screen).
- PGR2's main menu auto-repeats and does not wrap (it stops at Xbox
  Demos). B at the menu returns to the title and B at the title does
  nothing, so B, B, A reaches the menu from either. A quick hat tap is one
  step at 59 fps, and 0.2 s held is two. But "5 right, 1 left" still landed
  on Profile Manager: taps are lost while the menu animates. Untried: right
  held for 3 s (saturates at Xbox Demos), then one tap left.
- One Bruce Lee replay (22:25) was void: WSL interop failed
  (`UtilAcceptVsock accept4 failed 110`), and three pad presses and two
  shots never reached the device. Read `route.log` for `failed` before
  judging a replay.

Frames: nav `~/hakux-work/nav/bruce-lee.first-run-20260926T223411/`
(003-fight.png), replay `scratch/replay/bruce-lee-223619/zz-end.png`.

### Session 8: HELD Thor, 22:58-23:17 PDT (hold lifted by hostops 23:26), battery 84% -> ~80%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Crash Twinsanity (56550036) | thor | `crash-twinsanity.route` | yes (23:04) | first level, a beach; Crash runs, jumps and spins; long stretched polygons cross the screen (a rendering defect); overlay FPS 7 |
| Capcom Classics Collection Vol. 2 (43430019) | thor | none | - | nav stopped at the first menu (23:11) |
| MechAssault 2 (4D53006B) | thor | none | - | nav reached a mech in a hangar after Campaign -> Regular, still a cutscene at 23:17 |

**Crash Twinsanity.** Declines the save game (CONTINUE WITHOUT SAVING, one
stick push down), so one route fits every run. Nav frames
`~/hakux-work/nav/crash-twinsanity.first-run-20260926T230002/` (010-moved.png),
replay `scratch/replay/crash-twinsanity-230414/zz-end.png`.

## Attempt 3 (resumed 2026-09-26 23:30 PDT)

Why attempt 2 did not finish: it ran into the 300-turn cap at 23:17 PDT in
the middle of MechAssault 2's nav, still holding the Thor. The Crash
Twinsanity benchmark was queued (23:05) but its board-request line was not
written; attempt 3 wrote it. Hostops lifted the hold at 23:26. From here:
release the hold with turns to spare, and write the board line in the same
step as the queueing.

### Session 9: HELD Thor, 23:37-23:57 PDT (20 min; hold taken 23:31 while the Bruce Lee soak ran), battery 79%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| MechAssault 2: Lone Wolf (4D53006B) | thor | `mechassault-2.route` | yes (23:55; one failed replay before it) | first mission, a city street at night, tutorial boxes; the mech walks, turns and fires mortars |

**MechAssault 2.** No profile step. The first route (from the 23:37 nav
session) put two STARTs into the intro and an A and a BACK into the mission
cutscene. On replay the intro ran slower, the menu presses fell one screen
behind, BACK went back to the main menu, and the "gameplay" frame was the
attract demo (top-down city). The route that replays waits for the title
(it holds "Press START" for at least 60 s), then START, A, A, A 10 s apart
(A also skips the campaign FMV), and no input in the cutscene. Nav frames
`~/hakux-work/nav/mechassault-2.first-run-20260926T234710/` (008-moved.png),
replay `scratch/replay/mechassault-2-235122/zz-end.png` (the mech 40 s past
the mark).

### Session 10: HELD Thor, 00:06-00:16 PDT (10 min; hold taken 23:57 while the Crash soak ran), battery 75%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Grand Theft Auto: San Andreas (54540082) | thor (internal storage, `/storage/emulated/0/ROMS/xbox/`) | `gta-sa.route` | yes (00:14) | Jefferson alley, CJ on foot with HUD; 60 s past the mark he runs free (the bike mission lapsed) |

**GTA: San Andreas** (owner priority, addendum 4). No save on the disk, so
START at the title starts a new game with no menu; A skips the intro
credits, the airport cutscene and the police cutscene. The route presses A
every 5 s for 60 s through the cutscenes (on foot A is sprint, harmless);
the replay reached control at the first of those shots. Nav frames
`~/hakux-work/nav/gta-sa.first-run-20260927T000620/` (009-moved.png), replay
`scratch/replay/gta-sa-001049/` (001425-moved.png, zz-end.png). Posted on
#397 (comment 5853707979) with the other batch-3 titles.

### Session 11: HELD Thor, 00:35-00:57 PDT (22 min; hold taken 00:27 while the GTA soak ran), battery 72%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Galleon (41540004) | thor | none yet (`scratch/galleon.draft.route`) | **failed twice** | the deck tutorial ("Turn Rhama to face towards the arrow"); Rhama turns under LX (nav frames `galleon.first-run-20260927T004625/005-c3 -> 006-turned`) |

**Galleon: the title's window drifts.** The title ("Please press the START
button to begin") times out into an attract demo, and the demo's load runs
~2.5 min before "Exiting Demo" returns to the title. The window moved a lot
between launches: up at 41 s in one, at 28 s in another, and already gone
before 28 s in a third. START also selects on the menus (title -> save list
-> slot A -> New Game), so a START train is safe. Replays:
- one START at 48 s missed the title (`scratch/replay/galleon-004011/`, demo load);
- a START every 3 s from 28 s to 58 s missed it too (`scratch/replay/galleon-005004/`);
- a nav probe with a START every 2 s from 8 s to 60 s reached the new game's
  intro (`~/hakux-work/nav/galleon.first-run-20260927T005445/`).
Next: route = START every 2 s from 8 s to 60 s, then A every 6 s for ~90 s
(the intro and its loading screens), mark at the deck tutorial. Replay it
twice, because the failure is a timing window.

After the intro the saves list holds slot B at "1/7" from pass 1; slot A is
empty (the START train picks slot A).

### Session 12: HELD Thor, 01:01-01:23 PDT (22 min; hold taken 00:58 while a blinx372e run finished), battery 69%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Galleon (41540004) | thor | none | - | the 2 s START train reached the intro again, but the intro ran at 2 fps and 16 A presses did not reach the deck; parked |
| JSRF: Jet Set Radio Future (49470018) | thor | `jsrf.route` | yes (01:21; one failed replay before it) | the Garage, Yoyo on skates with the HUD; he skates, turns and jumps |

**JSRF.** No save prompt: New Game drops straight into the Garage
dialogue. A first route with two single STARTs stayed on the title over the
attract loop on replay, where the game ran at 59 fps instead of 9
(`scratch/replay/jsrf-010926/`). The route now presses START every 4 s,
eight times, from 70 s. START leaves the intro, opens the menu and picks
NEW GAME, and does nothing in the dialogue. Then it presses A every 3 s,
twelve times. Nav frames `~/hakux-work/nav/jsrf.first-run-20260927T011434/`
(002-moved.png), replay `scratch/replay/jsrf-011802/zz-end.png`.

### Session 13: HELD Thor, 01:33-01:58 PDT (25 min; hold taken 01:33 after lane.xbox's title push), battery 65%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Grabbed by the Ghoulies (4D530053) | thor | `ghoulies.route` | yes (01:57; one failed replay before it) | the Grand Hallway: Cooper among Ghoulies, heart counter; he walks and fights with the right stick |

**Ghoulies.** "Choose A Game" slot 1 -> name keyboard ("My Game", DONE)
-> Play Chapter 1 -> a storybook intro of pages and cards that wait on A.
The nav session's slot was saved at once: the first replay found slot 1
holding "My Game", skipped the keyboard and most of the storybook, and a
START I had pressed in the storybook landed in the hallway and paused the
game (`scratch/replay/ghoulies-014106/`). With that START made an A, the
second replay reached the hallway ~3 min before the mark and was in play
through it (`scratch/replay/ghoulies-014945/zz-end.png`). So one route
covers the empty and the saved slot; on a saved slot Cooper stands in the
hallway for those minutes before the mark (heart 14-36 there, so he
takes hits and is not killed). Nav frames
`~/hakux-work/nav/ghoulies.first-run-20260927T013324/` (016-moved2.png).

**A pattern for titles whose boot timing drifts (MechAssault 2, JSRF,
Galleon, GTA):** when START or A also means "select", replace single timed
presses with a train of them spaced wider than the slowest transition. Check
first that the extra presses are harmless at the screen they end on.

## Attempt 4 (resumed 2026-09-27 03:09 PDT)

Why attempt 3 did not finish: it hit the 300-turn cap at about 02:00 PDT,
right after queueing the Ghoulies benchmark and writing session 13's notes.
Nothing was lost; the hold had been released. From here: fewer turns per
title (one nav script per screen, not one call per press).

The Ghoulies benchmark 1-1790499526-titleroutes-925659 has no verdict: the
route reached `mark gameplay` (02:08:58), then adb failed from 02:12 to the
end (`UtilAcceptVsock: accept4 failed 110`, adb_failures=6). Re-queued as
1-1790503792-titleroutes-997141 (thor, 730 s, ref 6bfce4a685).

New on the Thor since the work list (`adb shell ls`, 03:15): 22 titles
lane.xbox pushed to internal storage (`/storage/emulated/0/ROMS/xbox/`) and
Dungeons & Dragons: Heroes on the SD card. By xemu rating, then rank:
Alien Hominid (Perfect, 13), Midtown Madness 3 (17), Aoi Namida (18), Blood
Wake (31), D&D Heroes (59), Brute Force (61), Angelic Concert (65), Bistro
Cupid (Perfect, 69), Otogi (83), Burnout (91), Battlefield 2: MC (95), Azurik
(96), Alias (104), Ex-Chaser (110), Innocent Tears (144), KOF Maximum Impact
Maniax (148), Bistro Cupid 2 (149), then unranked AFL Live, All-Star Baseball
2003 and 2004, AMF Bowling 2004, AMF Xtreme Bowling (Perfect).

### Session 14: HELD Thor, 03:30-03:55 PDT (25 min; hold taken 03:20 while the Ghoulies soak ran), battery 64% -> 63%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Alien Hominid (5A440004) | thor | `alien-hominid.route` | yes (03:36) | level 1, the FBI street; the alien runs, jumps and shoots agents, 59 fps |
| Midtown Madness 3 (4D53002A) | thor | `midtown-madness-3.returning.route` | yes (03:54; one failed replay before it) | Washington, pizza delivery vs Angelina, timer running; the Cadillac drives at 16-18 fps |

**Alien Hominid.** Logo (START) -> on the first run only a "No save games
found ... press A" card (it writes the save) -> GAME -> NEW GAME -> a
controls picture (A skips) -> the intro cutscene, which A does not skip and
which ends by itself in ~24 s -> level 1. The route is an A train 5 s apart,
so the missing save card on later runs costs nothing. A blind player loses
a life in ~20 s; after the continue countdown the game goes back to the NEW
GAME menu, and the pattern's A presses start a new game from there (tested
in the nav session: menu A, A, cutscene, level). Nav frames
`~/hakux-work/nav/alien-hominid.first-run-20260927T033039/` (009-moved ->
010-left), replay `scratch/replay/alien-hominid-033438/zz-end.png` (30 s past
the mark, score 400).

**Midtown Madness 3.** Profile Player1 was already on the disk (returning
route). Warning (A) -> profile (A) -> WORK UNDERCOVER -> Washington D.C. ->
job FMV (A) -> PIZZA DELIVERER -> text -> STANDARD DELIVERY -> Cadillac ->
mission card, "PRESS START" when loaded. The first replay was faster than the
nav session: the race was already running when START came, and START paused
it (`scratch/replay/midtown-madness-3.returning-034245/`). An A 4 s after the
START picks RESUME RACE (the default); on the second replay the race ran
through the mark (`scratch/replay/midtown-madness-3.returning-034845/`,
035336-e1.png, zz-end.png at 1:09 race time). Angelina delivered 4 of 14
pizzas in 70 s, so the mission may end ~4 min after the mark; the last
minute of a 300 s window may be a results screen.

### Session 15: HELD Thor, 04:15-04:29 PDT (14 min; hold taken 04:05 while the MM3 soak ran), battery 63% -> 62%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Blood Wake (4D530010) | thor | `blood-wake.route` | yes (04:27; one failed replay before it) | mission 1 "Fish in a Barrel", the speedboat on the bay with minimap and hull bar; it throttles and turns |

**Blood Wake.** START -> Story Mode -> Create Game -> CREATE GAME, whose
focus starts on "Select Storage" (A keeps the hard disk; a left-stick flick
down moves to the slot list) -> NEW GAME -> sketchbook pages -> difficulty
(Ensign) -> boat -> briefing pages -> MISSION GOALS -> the bay. The nav
session's NEW GAME wrote a slot, so the first replay met "You are about to
overwrite an existing saved game" (A), fell one A short and stopped on
MISSION GOALS (`scratch/replay/blood-wake-041915/`). Every screen after the
slot list takes A, so the route now presses A every 4.5 s, 14 times; the
second replay was on the water at the mark and under way 40 s later
(`scratch/replay/blood-wake-042419/zz-end.png`). Nav frames
`~/hakux-work/nav/blood-wake.first-run-20260927T041516/` (012-q2 -> 013-turn).

**Nav session vs soak frame rate.** The overlay read 16-18 fps in MM3's nav
session and 3 in its soak's mark frame (the race running, not paused);
Blood Wake's nav session read 37 and its replay 5-6. Alien Hominid and
Ghoulies read the same in both. Not investigated here (the nav launch sets
performance_mode 2, fan 5; the soak runs the MAX regimen); the numbers
below are what the soaks measured.

### Soak length: a 300 s soak is not 300 s of gameplay (21:16)

`soak_title.sh --seconds` counts from boot; `title_verdict.py` scores only
after `mark gameplay`. The first Black soak (1-1790482534-titleroutes-3347838,
300 s) ended in the briefing FMV: its logcat has `mark profile-loaded` and
no `mark gameplay`. Pre-mark times: kabuki-warriors 200 s, doax 254 s,
goldeneye-ra.first-run 299 s, nightfire 78 s, black.returning 456 s,
pgr.first-run 269 s, pgr.returning 173 s. So the batch-1 soaks the host
queued at 300 s (20:55) score about 100 s (Kabuki), 46 s (DOAX), 1 s
(GoldenEye) and 222 s (Nightfire). `scratch/bench.sh` queues
`--seconds` = pre-mark + 300, rounded up to 10 s. Written to the board
request.

### Benchmarks queued (Thor, 0.5 priority, ref a593d8eb85)

| title | route | request | seconds | fps median / share >= 30 |
|---|---|---|---|---|
| Black | black.returning | 1-1790482534-titleroutes-3347838 | 300 | void: no gameplay reached |
| Black | black.returning | 1-1790482599-titleroutes-3358750 | 760 | 291 s of gameplay; fps window median 7.45 (min 6.52), 0% of gameplay time at >= 30; target 30. The mark frame's overlay reads FPS 7 |
| Project Gotham Racing | pgr.returning | 1-1790483525-titleroutes-3587419 | 480 | 298 s of gameplay; fps window median 14.27 (min 5.14), 0% at >= 30; target 60. Verdict also flags a hang: 11.6 s without guest flips after the mark |
| Bruce Lee | bruce-lee | 1-1790487611-titleroutes-261841 | 420 | 289 s of gameplay; fps window median 59.94 (min 2.83), 81.3% at >= 30; target 30. Verdict flags a hang: 21.2 s without guest flips after the mark |
| Crash Twinsanity | crash-twinsanity | 1-1790489396-titleroutes-512742 | 540 | 268 s of gameplay; fps window median 15.72 (min 9.38), 0% at >= 30; target 60 |
| MechAssault 2 | mechassault-2 | 1-1790492206-titleroutes-681960 | 530 | 315 s of gameplay; fps window median 29.97 (min 15.81), 91.7% at >= 30; target 30 |
| GTA: San Andreas | gta-sa | 0-0-x-1790493356-titleroutes-734802 (promoted from 1-1790493356-titleroutes-734802) | 500 | 279 s of gameplay; fps window median 4.56 (min 3.91), 0% at >= 30; target 30. Ten 11-15 s hangs, 80% of audio callbacks short. apk 397ae7dca16a. Posted on #397 (comment 5853851696) |
| JSRF | jsrf | 1-1790497366-titleroutes-886445 | 500 | 284 s of gameplay (the Garage); fps window median 24.23 (min 16.85), 11.3% at >= 30; target 60 |
| Grabbed by the Ghoulies | ghoulies | 1-1790499526-titleroutes-925659 | 730 | void: adb lost after the mark (vsock accept4 failures), no verdict |
| Grabbed by the Ghoulies | ghoulies | 1-1790503792-titleroutes-997141 | 730 | 224 s of gameplay; fps window median 29.96 (min 11.88), 59.0% at >= 30; target 30 (*) |
| Alien Hominid | alien-hominid | 1-1790505449-titleroutes-1023605 | 410 | 306 s of gameplay; fps window median 59.94 (min 31.15), 100% at >= 30; target 30 (*) |
| Midtown Madness 3 | midtown-madness-3.returning | 1-1790506491-titleroutes-1032854 | 580 | 264 s of gameplay; fps window median 3.13 (min 2.85), 0% at >= 30; ten 12-20 s hangs; target 30 (*). The mark frame shows the race running at FPS 3 |
| Blood Wake | blood-wake | 1-1790508532-titleroutes-1074940 | 480 | pending |

(*) No host verdict.json yet at 04:30; these are `title_verdict.py` run on a
copy of the result dir (`scratch/judge.py`), apk 397ae7dca16a.

## Do not repeat

- Do not take a device under 30%: the Thor runs titlebench soaks at MAX and
  drains faster than USB charges it (26% -> 9% in 50 min).
- Do not use `press LEFT/RIGHT/UP/DOWN` to move a menu cursor: they did
  nothing in two games. Flick the left stick (0.15 s out, 0.5 s rest);
  try `axis HATX/HATY` before relying on it.
- Do not put the mark after an idle in a timed section (Nightfire): the
  replay runs ahead of the nav session's timing and the target escapes.
  Mark as soon as control is shown and let the play pattern do the rest.
- Do not mark at the first sight of control in a fighter if the nav session
  then idles: Kabuki's first replay was lost by the mark. Mark at the round
  start.
- Do not assume a first-run's profile persisted: a force-stop without the
  HOME flush leaves the disk as it was (GoldenEye).
- Do not queue a title soak for 300 s: `--seconds` counts from boot and
  the verdict scores only after the mark. Queue pre-mark + 300.
- Do not count presses through a title's intro, or count stick flicks in a
  menu: both depend on the frame rate, which differs between a cold (first
  run, shaders compiling) and a warm launch. PGR2's replay went elsewhere
  both ways.
- Do not assume a force-stop loses a save: PGR's driver, saved through the
  game's own save screen, was on the disk at the next launch.
