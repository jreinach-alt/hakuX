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

### Session 16: HELD Thor, 04:40-05:02 PDT (22 min; hold taken 04:31 while the Blood Wake soak ran), battery 62% -> 60%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Brute Force (4D53001E) | thor | `brute-force.route` | yes (04:54 and 05:00) | mission 1 in the jungle, Tex with HUD and radar; he walks, turns, fires, takes fire |

**Brute Force.** ~100 s of loading and intro FMV -> START/DEMOS -> CAMPAIGN
-> CAMPAIGN TYPE -> profile DEFAULT -> New Campaign -> name keyboard (DONE)
-> STANDARD -> JOIN CAMPAIGN (Tex, then START) -> two FMVs and an in-engine
intro, which A skips -> the jungle, and tutorial cards (A accepts one, Y
skips them all). Every choice is the default row. A stick flick and a hat
press each moved the CAMPAIGN TYPE cursor two rows, so the route counts no
cursor moves. The route is START at 100 s, A every 8 s eight times, START,
A every 4 s twenty times, Y twice, the mark. On the first replay the boot was
slower and the START came before the title menu was up. The A train still
carried the run into the mission, but a tutorial card was up 40 s past the
mark, so the play loop now starts with Y. The second replay was in a
firefight 60 s past the mark (`scratch/replay/brute-force-045442/zz-end.png`).
Nav frames `~/hakux-work/nav/brute-force.first-run-20260927T043949/`
(024-y1 -> 025-turned2).

### Session 17: HELD Thor, 05:12-05:23 PDT (11 min; hold taken 05:02 while the Brute Force soak ran), battery 60% -> 58%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Otogi: Myth of Demons (46530002) | thor | `otogi.route` | yes (05:22) | stage 1, the bamboo forest; Raikoh runs, slashes bamboo, a flying demon ahead |

**Otogi.** Title (START) -> New Game -> save slot 01 -> "Create a new save
game?" (A) -> story scroll and two cutscenes -> stage 1. In the nav
session A and START alternated through the intro. The last START landed in
the stage and opened PAUSE, whose default row is Restart Stage, and B
closed it. So the route skips with A only: A every 5 s through the menus
(the spare press covers the overwrite prompt a saved slot 01 adds), A
every 4 s through the intro, then one B. The replay was in the stage at the
mark and running at a demon 40 s later (`scratch/replay/otogi-051754/`).
Nav frames `~/hakux-work/nav/otogi.first-run-20260927T051231/`
(009-pre -> 010-moved).

### Session 18: HELD Thor, 05:33-05:44 PDT (11 min; hold taken 05:24 while the Otogi soak ran), battery 58% -> 56%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Burnout (41430006) | thor | `burnout.route` | yes (05:43; one failed replay before it) | Championship race 1, Interstate, lap 1/3; the Supermini at 45 mph, timer running |

**Burnout.** Title (START) -> first run only: "No Burnout saved game
present ... create a new saved game?" (Yes) and Enter Your Name ("PL1",
END) -> Championship -> Supermini -> AT -> Journeyman Grand Prix -> race
1/3 Confirm -> intro flyover -> "Continue (A)" -> the start. All choices
are defaults. A train of nine A presses 7 s apart stopped on the intro's
"Continue (A)" (`scratch/replay/burnout-053704/zz-end.png`). Thirteen
presses reached the race, and it was at 45 mph 40 s past the mark
(`scratch/replay/burnout-054037/zz-end.png`). Nav frames
`~/hakux-work/nav/burnout.first-run-20260927T053326/` (008-a7 -> 009-rt).

### State at the end of attempt 4 (05:45 PDT)

Seven titles routed, replayed and benchmarked (or queued) in this attempt:
Alien Hominid, Midtown Madness 3, Blood Wake, Brute Force, Otogi and Burnout,
plus the Ghoulies re-run. The session ended on its turn budget with the hold
released and the Thor at rest (56%). Burnout's soak
1-1790513065-titleroutes-1150288 is queued. The next titles on the Thor, by
xemu rank: Battlefield 2: MC (95), Azurik (96), Alias (104), D&D Heroes (59,
SD card), then the Japanese-only titles (Aoi Namida, Angelic Concert, Bistro
Cupid 1 and 2, Ex-Chaser, Innocent Tears; expect text menus), then All-Star
Baseball 2003/2004/2005, AMF Bowling 2004, AMF Xtreme Bowling, AFL Live and
American Chopper 2 (pushed at 05:01). From the older list, still open on the
Thor: Shin Megami Tensei: Nine, Capcom Classics 2 (nav stopped at the first
menu), Castlevania: CoD, THPS2x, Panzer Dragoon Orta, Psychonauts,
MechAssault, DOA3, RalliSport 2, Amped 2, Phantom Dust, ToeJam & Earl III,
Spikeout, Ninja Gaiden, Deathrow, Tork, Tron 2.0; Galleon and PGR2 are
parked (see sessions 6-7 and 11-12).

Waiting (PR #466 comment 5855932850): dispatch request
1-1790513065-titleroutes-1150288, the Burnout soak, running on the Thor at
05:46. PR #466 marked ready; preflight passed at 05:47.

**Do not skip with START in an action game** unless its pause menu has
been seen: in Otogi (Restart Stage) and Midtown Madness 3 (the race) START
opens a pause menu the moment control starts.

## Attempt 5 (resumed 2026-09-27 06:09 PDT)

Why attempt 4 did not finish: it did finish its batch, and it ended
correctly on a `waiting:` for the Burnout soak (1-1790513065). The host
resumed the lane once that soak was done. PR #466 was folded during this
session, so batch 5 is on a new PR, #476.

Burnout's result: 304 s of gameplay, fps window median 10.85 (min 7.68),
7.0% at >= 30, no hang; target 30.

### Session 19: HELD Nova, 06:09-06:27 PDT (18 min), battery 80% -> 75%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| 50 Cent: Bulletproof (56550042) | nova | `50cent.route` | yes (06:15) | the Intro level: an alley at night, two G-Unit allies, enemies behind an SUV; walks, turns, fires (15/20 -> 5/20) |
| WWE Raw 2 (5451000D) | nova | `wwe-raw-2.route` | yes (06:25) | Quick Start singles match, The Rock (1P) vs The Undertaker (CPU); the clock runs, both health bars show |

**50 Cent.** Logos (A) -> Title Screen, New Game (A) -> Thug (Normal)
(A) -> "- Create New Profile -": X is Continue without saving, and it
avoids the profile keyboard the old note warned about. The confirm's cursor
is on No, so flick LY up once, then A -> the intro cutscene (A skips) -> the
Intro level. Nav frames `~/hakux-work/nav/50cent.first-run-20260927T061007/`
(009-pre -> 010-moved). Replay `scratch/replay/50cent-061258/zz-end.png`.

**WWE Raw 2.** No profile step. START skips the intro FMV. At the title,
START -> "Now checking free blocks." -> Main Menu on Quick Start (A) -> 1P
vs CPU (A, A) -> default superstars (A, A) -> "start the next match?" (A)
-> two entrances, each skipped with A -> the match. The nav mark was at
00:14 on the match clock and the replay's at 00:41. Both are in the match,
so the soak (560 s) scores about 276 s of it. Nav frames
`~/hakux-work/nav/wwe-raw-2.first-run-20260927T061604/` (014-gameplay ->
015-moved). Replay `scratch/replay/wwe-raw-2-062043/zz-end.png` (01:01).

Benchmarks (Nova, 0.5 priority, ref 2ce8f4a985), judged with
`scratch/judge.py` (apk 397ae7dca16a):

| title | request | seconds | fps median / share >= 30 |
|---|---|---|---|
| 50 Cent: Bulletproof | 1-1790515600-titleroutes-1194351 | 440 | 309 s of gameplay; median 29.97 (min 19.07), 95.9% at >= 30; no hang; target 30 |
| WWE Raw 2 | 1-1790515603-titleroutes-1194477 | 560 | 278 s of gameplay; median 59.94 (min 39.97), 100% at >= 30; no hang; target 30 |

### Session 20: HELD Thor, 06:46-06:59 PDT (13 min; hold taken 06:27 while lane.local's Alien Hominid soak ran), battery 55% -> 54%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Battlefield 2: Modern Combat (45410062) | thor | `bf2mc.route` | yes (06:59) | mission 1, first person in a snowy square at night, "Fight Through To The Rendezvous"; walks, turns, fires (23 -> 15) |

**BF2: MC.** Its ISO is on the Thor's INTERNAL storage
(`/storage/emulated/0/ROMS/xbox/`), and so are Alias and Azurik. Launching
the SD-card path opens the app's library instead. The campaign-name
keyboard ignores the left stick and START; the hat moves it (HATX left
from A wraps to BACKSPACE, then HATY down x2 reaches ENTER). "Do you want to
save?" -> No keeps the disk unchanged. The mission load takes about 2
minutes, and B on the first Help box turns help off. Nav frames
`~/hakux-work/nav/bf2mc.first-run-20260927T064649/` (019-gameplay ->
020-moved). Replay `scratch/replay/bf2mc-065258/zz-end.png`. Benchmark
1-1790517591-titleroutes-1523259 (thor, 640 s, ref 3ea9cd9a34). The
replay's mark came 375 s after launch, so the soak scores about 265 s.

### Session 21: HELD Thor, 07:02-07:28 PDT (26 min; the hold was taken the moment lane.titlestate's hdd.img pull released it), battery 54% -> 48%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Azurik: Rise of Perathia (4D530007) | thor | `azurik.route` | yes (07:07) | the Arena after the "first challenge" box; Azurik runs out through the far arch |
| Alias (41430016) | thor | `alias.route` | yes (07:14) | Operation Casino, Sydney on the casino floor; the replay walked her the length of the bar at 19 fps |
| Dungeons & Dragons Heroes (49470013) | thor | draft only (`scratch/dnd-heroes.draft.route`) | two replays, both failed | ARADIN (Fighter) in the ruins after the dwarves' cutscene |

**Azurik.** FMV (A) -> START -> Start New Game (A) -> A presses through the
opening and the Arena tutorial box (A is jab in play). Nav frames
`~/hakux-work/nav/azurik.first-run-20260927T070214/` (006-gameplay ->
007-moved). Replay `scratch/replay/azurik-070456/zz-end.png`.

**Alias.** Intro (A) -> NEW GAME (A) -> briefing (A) -> Operation Casino
load -> door cutscene (A) -> the casino. Vaughn's radio box does not stop
movement. The nav session ran at 5-7 fps (first run) and the replay at 19.
Nav frames `~/hakux-work/nav/alias.first-run-20260927T070810/` (006-gameplay
-> 008-walk). Replay `scratch/replay/alias-071116/zz-end.png`.

**D&D Heroes (not done).** Three A presses 5 s apart go from the logos to
the hero select without showing the menus. Fighter (A) -> name "ARADIN" (A)
-> load -> a dwarves' cutscene that neither A nor START ends (~40 s). In the
nav session one START landed in the cutscene. Replay 1 marked inside a
slower cutscene (2 fps). Replay 2 (+60 s before the mark) was in play when
that START landed, so it opened Game Options, and the play pattern's A then
picked Save Game. Next time: drop the START press, wait out the cutscene,
and replay again. Frames `scratch/replay/dnd-heroes-071819/` and
`scratch/replay/dnd-heroes-072237/`.

Benchmarks (thor, ref c6e2be0936): Azurik 1-1790519286-titleroutes-2112912
(440 s), Alias 1-1790519290-titleroutes-2113140 (450 s).

### State at the end of attempt 5 (07:35 PDT)

Five titles routed and replayed in this attempt: 50 Cent, WWE Raw 2
(Nova, both measured), BF2: MC, Azurik and Alias (Thor, soaks queued). PR
#476 is ready; preflight passed at 07:33. Both devices are at rest with no
hold of mine.

Waiting on the three Thor soaks: 1-1790517591-titleroutes-1523259 (BF2),
1-1790519286-titleroutes-2112912 (Azurik) and
1-1790519290-titleroutes-2113140 (Alias). About 75 min of other Thor work is
queued ahead of or alongside them (lane.local's 1500 s soak, flip474,
tbflip424). Next session: judge them (`scratch/judge.py <id>`), add the rows
to the #397 table, then:
- Thor: finish D&D Heroes (see session 21), then the Japanese-only titles,
  All-Star Baseball 2003/2004/2005, AMF Bowling 2004, AMF Xtreme Bowling,
  AFL Live and American Chopper 2, then the older open list (SMT Nine,
  Capcom Classics 2, Castlevania: CoD, THPS2x, Panzer Dragoon Orta,
  Psychonauts, MechAssault, DOA3, RalliSport 2, Amped 2, Phantom Dust,
  ToeJam & Earl III, Spikeout, Ninja Gaiden, Deathrow, Tork, Tron 2.0).
- Nova-only titles still without a route (work-list rows 11, 13, 15,
  20-24, 27, 28, 32, 33, 39, 41, 45): Burnout Revenge, Midnight Club 3,
  187: Ride or Die, Crash: Wrath of Cortex, Black Stone, Star Wars Ep. III,
  Bloody Roar: Extreme, Gunvalkyrie, Dino Crisis 3, Buffy, Fuzion Frenzy,
  Halo, Conker, Halo 2, Ninja Gaiden Black. Each needs a held Nova session
  in a gap in the #462 work (Addendum 3: the Nova is #462's first).
- Check a new title's ISO path first. Titles lane.xbox pushed after 09-26
  sit on the Thor's internal storage (`/storage/emulated/0/ROMS/xbox/`).

### Attempt 6, 2026-09-27 10:00-10:40 PDT (offline: no device free)

**Why attempt 5 did not finish.** It did not fail. It ended on a `waiting:`
for three Thor soaks, as the lane rules require, and PR #476 folded.
Hostops resumed this attempt once the soaks were done. No held session was
possible. The Thor was at 9% under the `battery-hostops` hold, which lifts
at 80%, and the Nova is reserved for #462 today.

Readings (Thor, apk 17eff0363df9, `scratch/judge.py` on a copy of each
result dir):

| title | request | fps median (min) / share >= 30 | gameplay | route-frames at the mark |
|---|---|---|---|---|
| Battlefield 2: MC | 1-1790517591-titleroutes-1523259 | 19.14 (3.64) / 0% | 270 s; ten 12.7-16.5 s hangs | `081338-gameplay.png`: mission 1, first person in the snowy square, overlay FPS 10 |
| Azurik | 1-1790519287-titleroutes-2112912r | **void** (29.97 flat) | 285 s of the attract demo | `092535-gameplay.png`: "Press START to play. Press X for Game Demos" |
| Alias | 1-1790519290-titleroutes-2113140 | 20.80 (19.69) / 0% | 305 s; no hang | `093303-gameplay.png`: Sydney on the casino floor, overlay FPS 19 |

**Azurik's soak never left the title.** The boot was cold, and at `a2` the
Adrenium logo was still up at 8 fps. In the warm nav session the title was
already showing by then. The route's one START went to the intro, and every
later frame is the attract demo, which runs at a flat 29.97. The route now
presses A once more and START twice, with 20 s more slack. The title shows
"Press START to play" over the demo, so a late START still works. Two more A
presses come before the mark. It has not replayed yet. Its soak is the
replay: 1-1790527983-titleroutes-2100312 (480 s, ref 0dadfc79c5).

**D&D Heroes** is now `routes/dnd-heroes.route` with a targets.toml entry.
The START is gone, it waits 150 s after `skip` for the cutscene (cold runs
play it at 2 fps), and the play pattern presses A only, because X opens the
skill list. It has not replayed yet either. Its soak is
1-1790527983-titleroutes-2100395 (580 s, ref 0dadfc79c5). If the frames at
the mark are not the ruins, the reading is void and the route goes back to a
held session.

I did not draft the next Thor titles. A route without a nav session is a
guess, and a guess costs a soak slot.

**Do not repeat:** a route made in a warm nav session can miss its presses
on a cold boot. The nav session is warm (its shaders are cached), and a soak
may not be. Before trusting a reading, open the route-frame at the mark. A
flat 29.97 with min = median is what an attract demo looks like.

### Attempt 7, 2026-09-27 12:20-12:50 PDT (offline: both soaks void, no Thor input until a focus guard is live)

**Why attempt 6 did not finish.** It did not fail. It ended on a `waiting:`
for the Azurik and D&D Heroes soaks, and PR #487 folded. This attempt was
resumed when both were DONE.

Both readings are void, and neither says anything about its route.

| title | request | verdict's number | what the run was | evidence |
|---|---|---|---|---|
| Azurik | 1-1790527983-titleroutes-2100312 (thor, 11:05-11:13 PDT, apk 6ed0b8d20937) | 28.32 median (min 20.42), 43.1% at >= 30, 288.7 s after the mark: **void** | display 0 covered by the AYN dual-screen assistant's overlay; hakuX without input focus | 7 of 7 route frames are 10,899 B, a 1920x1080 all-black PNG with no FPS overlay |
| D&D Heroes | 0-0-x-1790527983-titleroutes-2100395 (thor, 12:11-12:21 PDT, apk 6ed0b8d20937) | no mark, 0 s of gameplay: **void** | hakuX rendered on display 0, but no press reached it; devwatch stopped the route at 12:14:30, 187 s in, because Lime3DS was the app in front | `121221-a3.png`: main menu. `121257-name.png`, `121324-load.png`, `121347-skip.png`: the attract demo (heroes with keys and potions already collected) |

What happened on the Thor (hostops-inbox.md, 11:50 to 12:14 PDT; #397
deliveries at 11:53 and 12:12):
- The Thor came back from a USB drop at about 11:05 with the launcher in
  front. Azurik's soak launched hakuX, but gamepad events go to the focused
  window. The route's first A came at 11:05:53 and Lime3DS started at
  11:06:02. The presses most likely opened it from the launcher. Route input
  also changed `dual_screen_display_mode` to 2, and the assistant's overlay
  then covered display 0 until hostops set the mode back at 12:10.
- D&D Heroes ran after that fix. Its frames are real, so the display was
  clear. Its input still went elsewhere. The logcat's frame rate alternates
  between 59-60 (menu, about 40 s) and 28-31 (demo, about 80 s) for the
  whole 580 s, in step, including across the route's presses at 12:12:31,
  12:12:50, 12:13:34 and 12:13:40. An A that reached the game would have
  left the demo or chosen NEW GAME. lane.gta482 read the focus on display
  1's launcher at 12:10 (SecondaryDisplayLauncher), which fits.
- So the display-covered check (PR #495) would have refused the Azurik run
  and would NOT have refused the D&D Heroes run. That one needs the focus
  check (hostops 12:07, item 2: abort the route when hakuX is not in front).

Azurik's number looks like play, and that is the trap. It is not flat like
the attract demo (16 to 30 after 11:09). I still cannot say what was on the
screen, and the presses went to another app, so it is not a reading.

**I queued nothing on the Thor in this attempt.** A route soak presses
buttons into whatever holds the focus. Twice today that was the owner's own
apps, and devwatch needs 90 s to notice, which is three to five presses.
Azurik and D&D Heroes go back in the queue when a soak refuses to press
without the focus (the signal is in the `waiting:` comment on the PR). The
Nova is reserved for the fps-focus work today, so no held Nova session
either. Every title left on the work list is behind one of those two.

Offline work done: the two route headers say what the void soaks showed;
`python3 scratch/chk431.py` confirms all 35 of #431's targets are in
targets.toml with the same `target_fps` (61 titles, 27 with a route).

Board request (dispatch/board-requests/titleroutes.md, 12:40 PDT): the D&D
Heroes run as the case the display-covered check misses.

**Waiting (PR #497, 12:50 PDT).** Nothing of mine is queued or running.
The signal is outside this lane: issue #494 (lane.displayguard; PR #495 is
its display-covered half) landing a check that hakuX holds the input focus
before a route presses, live on the Thor's dispatcher, and hostops saying
so on #397. Then: re-queue Azurik (480 s) and D&D Heroes (580 s) with
`scratch/bench.sh`, open the frame at the mark before reading either
number, and go on down the Thor list in a held session (the Japanese-only
titles, All-Star Baseball 2003/2004/2005, AMF Bowling 2004, AMF Xtreme
Bowling, AFL Live, American Chopper 2, then the older open list).
#397 comment for this batch: 5859098639.

### Attempt 8, 2026-09-27 12:48 PDT (held Thor sessions behind an input-focus read)

**Why attempt 7 did not finish.** It did not fail. It ended on a `waiting:`
for a focus check (#494), with nothing queued, and PR #497 folded. Hostops
resumed this attempt at 12:48 PDT with two changes:

- The Thor's "focus on display 1" was a misread. `dumpsys window | grep -m1
  mCurrentFocus` prints the second screen's line first. `dumpsys input` is
  the input dispatcher's own view, and on a cold launch at 12:43 PDT it read
  `FocusedDisplayId: 0` with hakuX as display 0's focused window. The AYN
  setting `screen_focus_lock` read 2 after the 12:03 reboot; hostops set it
  to 0 at 12:41. Whether that setting sent the 12:12 D&D Heroes presses to
  display 4's launcher is unproven.
- Held sessions are allowed again, behind a read before the first input and
  between steps (`scratch/focus.sh`): `screen_focus_lock` is 0,
  `FocusedDisplayId` is 0, and display 0's `FocusedWindows` entry names
  hakuX. If any of the three fails, nothing is sent and the hold is
  released. Queued Thor route soaks still wait for PR #495's guard.

### Session 22: HELD Thor, 12:59-13:25 PDT (26 min; hold taken 12:56 while a sweep disc ran), battery 86% -> 84%

Every input in this session was sent behind `scratch/focus.py thor`. It
reads `settings get system screen_focus_lock` (0) and `dumpsys input`
(`FocusedDisplayId: 0`, and display 0's `FocusedWindows` entry naming
`com.jreinach.hakux`), and it sends nothing itself. The nav steps read it
before each group of inputs (`scratch/step.sh`), and the replays read it
before the launch, 6 s after it, and every 20 s while the route plays
(`scratch/replay.sh`). All 43 reads in the three replays passed. Display 4's
focused window was the secondary launcher throughout; that is the second
screen and takes no pad input while `FocusedDisplayId` is 0.

`dumpsys input` prints the dispatcher state twice (the second copy is the
last ANR's). The first copy is the live one.

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Azurik: Rise of Perathia (4D530007) | thor | `azurik.route` | yes (13:00, warm) | the Arena; the training box is still up at the mark and the pattern's first A closes it; 40 s later Azurik is at the far arch, overlay FPS 29 |
| Dungeons & Dragons Heroes (49470013) | thor | `dnd-heroes.route` | yes (13:04, warm) | ARADIN in the ruins at the mark (FPS 15); 40 s later at a torch-lit sign (FPS 11) |
| BloodRayne (4D4A0001) | thor | `bloodrayne.route` | draft: the pre-mark part replayed (13:20), the play pattern was changed after it | Act 1, Rayne on the grass below the church; the stick walks her, RX turns the camera; 18-29 fps |

Frames: `scratch/replay/azurik-130014/`, `scratch/replay/dnd-heroes-130437/`,
`scratch/replay/bloodrayne-132018/`; nav frames
`~/hakux-work/nav/bloodrayne.first-run-20260927T131543/` (005-cut3 ->
006-moved). 640x480 copies: `frames/azurik-replay-end.jpg`,
`frames/dnd-heroes-replay-gameplay.jpg`,
`frames/bloodrayne-replay-gameplay.jpg`.

**BloodRayne.** Two A presses pass the logos and open New Game. The
highlighted entry in its menus is the DIM one, which reads backwards: my
first pass pressed A on "Training" while reading the bright "Act 1 -
Louisiana" as selected, and landed in the training level, whose tutorial
cutscenes interrupt control every few seconds. The left stick does not move
these menus; the hat does. The opening cutscene with Mynce takes about 70 s
and A does not end it. The replay's forward-only pattern walked Rayne into
the swamp water in 40 s, and water drains her health (the bar was at about
60% in `zz-end.png`), so a 300 s window would have ended in a death screen.
The committed pattern walks 1 s forward and 1 s back around a turn. It has
not replayed.

The leave state at 13:25: app stopped, performance_mode 0, fan_mode 4,
dual_screen_display_mode 0, screen_focus_lock 0, screen asleep, 84%.

### Session 23: HELD Thor, 13:38-14:00 PDT (22 min; hold taken 13:38 after lane.gta482's), battery 83% -> 82%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| BloodRayne (4D4A0001) | thor | `bloodrayne.route` | yes (13:38, as a held soak) | Rayne at the church wall at the mark, overlay FPS 22 |
| AMF Bowling 2004 (42530009) | thor | none | - | not reached: the title does not take START |
| Baldur's Gate: Dark Alliance (5655001A) | thor | `baldurs-gate-da.route` | no: a draft | the Human Archer on the Elfsong Tavern's floor, bars top left; the stick walks him and the camera follows; 59 fps |

**The same-pass fps reading, inside the hold.** Queued Thor route soaks are
closed until PR #495's guard is live, so BloodRayne's replay was run as a
soak in the hold (Addendum 2's second option). `scratch/heldsoak.sh` runs
`docs/testing/soak_title.sh` itself (MAX regimen, REST on the way out, the
dispatcher's logcat spec) with the route, and reads the input focus before
the launch, 8 s after it and every 15 s. A failed read TERMs the soak. It
runs in a transient user unit (`scratch/heldunit.sh`), because a soak of
pre-mark + 300 s does not fit a 10-minute tool call. `title_verdict.py`
then judges the dir.

| title | held result | apk | gameplay | fps median (min) / share >= 30 | notes |
|---|---|---|---|---|---|
| BloodRayne | `scratch/held/bloodrayne-20260927T133838` | f5abfa521745 (= ref a593d8eb85) | 288.2 s | 22.89 (5.48) / 0% | target 30. Four gaps of 10.1-10.9 s without 60 guest flips, which the verdict calls a hang. 22-25 fps for the first 130 s, then 6-7 to the end |

What this reading is not:
- It is not a dispatch result. It is in the lane's scratch, and the status
  page does not count it. The title is still owed a queued soak.
- The build is whatever the device's last request installed. Here that was
  f5abfa521745, which is the apk of my benchmarks on ref a593d8eb85
  (`scratch/heldread.py` finds the dispatch results with the same apk_sha).
  Before session 22 the device had a8dd8484d799. Read the apk before
  comparing a held reading with anything.
- No frame shows the last 150 s, where the rate fell to 6-7. The route takes
  no frame after the mark. `heldsoak.sh` now takes one frame 10 s before the
  end (`end-frame.png`); this run was before that change.

**AMF Bowling 2004: blocked at the title.** The intro video ends on A. The
title says "Press START". START (300 ms and 1 s) and A do nothing there that
I could see: the title and its attract demo (a bowler at the lane, "Press
START" over it) alternate whatever is pressed. Six presses, frames
`~/hakux-work/nav/amf-bowling-2004.first-run-20260927T134830/` (001 to 008).
Not tried: BACK, the triggers, or a second pad. On the board request file.

**Baldur's Gate: Dark Alliance.** The logos need no press: the main menu is
up about 60 s after launch. Four A presses pick Start New Game, One Player,
Normal and Human Archer. A ends the Act I video. The tavern conversation
with Alyth is a tree: A picks the bright line, and the first line of each
choice loops back, so my 18 A presses went round it several times. B does
not leave it. The way out is the second line of the last choice ("I'll go
speak to him, then."): hat down, A. The pre-mark time is 422 s, most of it
that conversation. The play pattern is a square walk with the stick only,
because A talks to whoever is near. Nav frames
`~/hakux-work/nav/baldurs-gate-da.first-run-20260927T135112/` (016-free ->
017-moved -> 019-played); 640x480 copy `frames/baldurs-gate-da-nav-played.jpg`.

The leave state at 14:00: app stopped, performance_mode 0, fan_mode 4,
dual_screen_display_mode 0, screen_focus_lock 0, screen asleep, 82%. At
13:58:47 PDT the host's update window took both handhelds (bounded 30 min).

### Session 24: HELD Thor, 14:02-14:28 PDT (26 min; hold taken 14:02 as the host's update window lifted), battery 82% -> 80%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Baldur's Gate: Dark Alliance (5655001A) | thor | `baldurs-gate-da.route` | yes (14:02, as a held soak) | the archer on the tavern floor at the mark, overlay FPS 59 |
| Mercenaries (4C410015) | thor | none | - | not reached: the first load never ends |
| KOF: Maximum Impact - Maniax (534E0007) | thor | `kof-mi.returning.route` | no: a draft | round 1, Alba Meira against Soiree Meira; the pattern's kick lands and Soiree's bar drops; 30-33 fps |

Held reading (same instrument and caveats as session 23's):

| title | held result | apk | gameplay | fps median (min) / share >= 30 | notes |
|---|---|---|---|---|---|
| Baldur's Gate: Dark Alliance | `scratch/held/baldurs-gate-da-20260927T140214` | f5abfa521745 (= ref a593d8eb85) | 245.5 s | 59.94 (58.31) / 100% | target 30 (none from #431). No hang. The tavern is an indoor room with five characters, so this is the title's light end |

The soak was sized at pre-mark + 300 s from the route's waits (422 s), but
the replay reached the mark 487 s after the launch: each `shot` costs about
3 s and this route has 19. So the window was 245 s. `premark.py` should add
3 s per `shot`; until it does, add it by hand for a route with many frames.
`end-frame.png` was not written in this run either (the frame step in
`heldsoak.sh` did not fire; not looked into).

**Mercenaries: blocked at the first load.** The title needs no press up to
"PRESS START". START, then A on NEW GAME, A on JACOBS, A on ACCEPT, and A
ends the news-footage video. The loading screen ("Allied M1025 Scout") then
never ends. Three frames over 95 s (14:19:41 to 14:21:16) are identical
pixel for pixel below the FPS overlay, spinner included
(`scratch/same.py`), while the overlay reads 59. The logcat's `fifoskew`
lines read `kicks=0` over the same time, so the guest submits nothing to
the GPU; the vblank keeps its 59.94 Hz. Frames
`~/hakux-work/nav/mercenaries.first-run-20260927T141501/` (007 to 010),
640x480 copy `frames/mercenaries-loading-frozen.jpg`, logcat tail
`scratch/merc-logcat-tail.txt`. The menus before it ran at 12-14 fps.

**KOF: Maximum Impact.** START ends the intro video. The first box asks to
create option data. I meant to answer NO twice over (NO, then "begin game
play anyway" YES), which would have left the disk alone and given one route
for every run. The hat moved the cursor down on the first box and did not
move it on the next ones, up or down, so an A meant for NO landed on YES and
the data was saved. It persisted (HOME flush, then a relaunch showed "OPTION
DATA ALREADY EXISTS"). So the Thor's disk now has KOF's option data, and the
committed route is the returning one. lane.titlestate's registry does not
know about this save yet; it is on the board request file.

**Do not repeat:** do not answer a save prompt by moving the cursor blind.
Take a frame after the move and before the A. `step.sh` takes its frame
after the last step, so put `shot` between the move and the press.

The leave state at 14:28: HOME flush, app stopped, performance_mode 0,
fan_mode 4, dual_screen_display_mode 0, screen_focus_lock 0, screen asleep,
80%.

### Session 25: HELD Thor, 14:29-14:44 PDT (15 min; hold taken 14:29 after lane.xbox's title push), battery 80% -> 80%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| KOF: Maximum Impact - Maniax (534E0007) | thor | `kof-mi.returning.route` | yes (14:29, as a held soak) | a fight against Leona on the airfield stage, at the mark and 20 s before the end |
| Arctic Thunder (4D570002) | thor | `arctic-thunder.route` | no: a draft | a snowmobile race, position 8 of 8; with A held the sled passes the first checkpoint; 14-26 fps |

Held reading (same instrument and caveats as session 23's):

| title | held result | apk | gameplay | fps median (min) / share >= 30 | notes |
|---|---|---|---|---|---|
| KOF: Maximum Impact - Maniax | `scratch/held/kof-mi.returning-20260927T142953` | f5abfa521745 (= ref a593d8eb85) | 319.3 s | 14.56 (11.34) / 17.2% | target 30 (none from #431). No hang. The stage was the airfield (FPS 33 at the mark, 11 near the end); the nav session's cage stage ran at 30-33. Story mode does not draw the same opponent each run, so two runs of this route are not the same place |

`end-frame.png` works now that the loop takes it (the last 25 s of the
soak). KOF's is a round in progress, so the window ended in play.

**Arctic Thunder.** START ends the intro video. A on START, A on RACE. On
PLAYER SELECT, A joins player 1; the hat does nothing there and the left
stick moves to DONE. A on the driver, A on the track. In the race RT does
nothing and A is the throttle. The race has a checkpoint countdown, so an
idle sled runs out of time. #431's target for it is 60.

I gave the Thor back after 15 minutes. Five requests pinned to it were
waiting (thermal507's GTA soak, two of flip474's, two arms), and I had held
it for 89 of the 105 minutes since 12:59.

The leave state at 14:44: app stopped, performance_mode 0, fan_mode 4,
dual_screen_display_mode 0, screen_focus_lock 0, screen asleep, 80%.

### The held readings against the Thor's thermal pause (#507), 14:50 PDT

Hostops, 14:26 PDT on #397: PR #495's guard is live on the dispatcher
(folded as a04b5c59fc, dispatcher tree at 0800f26eec), so queued Thor route
soaks are open again and held sessions are for nav work only. The same note
says the Thor's thermal pause (#507) voids fps after 4 to 6 minutes at MAX.
#507: the kernel pauses cpu3-7, every emulator thread moves to cpu0-2, and
the frame rate falls by 5 to 7 times for the rest of the run.

`scratch/fpsbins.py <result dir>` bins a soak's fps at 30 s from `soak
start` (60-flip windows, as `title_verdict.py` counts them) and applies
lane.thermal507's test: at 200 s or later, the three preceding bins' median
is 10 or more and every later bin is under a third of it.

| title | mark at | bins before the fall | fall | bins after | #507 shape |
|---|---|---|---|---|---|
| BloodRayne | 245 s | 20-26 fps from 30 s to 389 s | 390 s (mark +144 s) | 6-7 to the end (534 s) | **yes**: 23.1 -> 6.5 |
| Baldur's Gate: Dark Alliance | 486 s | 60 in every bin, 0 s to 731 s | none | - | no |
| KOF: Maximum Impact | 234 s | 33-34 from 210 s to 299 s | 300 s (mark +66 s) | 13-15 to the end (553 s) | no by the test (the fall is to 0.42 of the rate before, not under a third) |

So:
- **BloodRayne's title rate is the 20-26 fps before 390 s.** The verdict's
  median of 22.89 happens to sit there, because the fall came halfway
  through the window. Its 5.48 minimum and its four "hang" gaps are the
  pause. Session 23's question (what was on the screen in the last 150 s)
  has this answer: the same place, on three cores.
- **Baldur's Gate held 60 for 12 minutes at MAX.** Either the pause did not
  happen or the tavern fits in what is left. I did not read the cooling
  device, so I cannot say which.
- **KOF's 14.56 median is not the title's rate, and I cannot say what is.**
  The same fight on the same stage ran at 33-34 for 66 s and at 13-15 for
  the 253 s after. A fall at 300 s fits #507's 4 to 6 minutes. It fails the
  one-third test, and nothing else I have separates the pause from the
  fight getting heavier. The cooling device's state was not read.

**What to do differently.** Read `thermal-pause-F8` (the cooling device
#507 names) at the end of a Thor soak, or run `fpsbins.py` on the result,
before writing a median down. For a title whose mark comes late, the window
is after the 4 to 6 minutes by construction: Baldur's Gate's mark is at
486 s. A shorter way in (a returning route from a save in play) is the fix
on the route side; the rest is #507's.

**Older Thor readings of mine, same test** (lane.thermal507's scan on #507,
PR #508): Blood Wake `1-1790508532-titleroutes-1074940` falls at 300 s
(mark +98 s), 38.5 -> 6.2, and its scored median 37.4 is from before the
fall; Battlefield 2: MC `1-1790517591-titleroutes-1523259` falls at 480 s
(mark +90 s), 19.3 -> 4.1. Midtown Madness 3's 3.13 with ten 12-20 s hangs
(against 16-18 in its nav session) has the same look and was not in that
table; I did not re-scan it.

### Queued soaks after the guard went live (ref 92560461c5, 0.5 priority, Thor)

`scratch/bench8.sh` sizes a soak as the route's pre-mark waits + 3 s per
`shot` before the mark + 300 s.

| title | route | request | seconds | reading |
|---|---|---|---|---|
| Azurik | `azurik` | 1-1790545605-titleroutes-65853 | 500 | **void**: refused by the guard before the first input (14:52 PDT), with hakuX in front. See "The guard reads the last-ANR copy" |
| D&D Heroes | `dnd-heroes` | 1-1790545622-titleroutes-76653 | 600 | **void**: the same (14:53 PDT) |

### The guard reads the last-ANR copy of the dispatcher state (15:00 PDT)

Both re-queued soaks ran 45 s and were refused: `not-foreground:
com.magneticchen.daijishou (the focused application on display 0 of
bdc158a5, not hakuX)`, then `soak aborted: not-foreground before the route's
first input`. No input was sent. hakuX was running: Azurik's logcat has its
`gfps=29` lines.

On the Thor `dumpsys input` prints the dispatcher state twice. At 14:54:31
PDT, during the D&D Heroes run, line 593 (`Input Dispatcher State:`) named
hakuX as display 0's focused application and window, and line 805 (`Input
Dispatcher State at time of last ANR:`) named Daijishou as the application,
with `FocusedWindows: <none>`. `hakux_in_front` (devices.sh, PR #495) keeps
the last entry per display, so it answers from the ANR copy.

Until that is fixed or the Thor reboots, no route soak runs on the Thor,
for any requester. Reported: #494 comment 5860177923, #397 comment
5860180117, and an ASK on the board request file. `scratch/focus.py` reads
the first copy; it met the same dump at 12:59 and failed on it until I
looked at why.

### Session 26: HELD Thor, 14:56-15:11 PDT (15 min; the Thor was idle), battery 80% -> 79%

I had written on the board file that I would not take the Thor before
15:15. I took it at 14:56 because nothing was running on it and its route
soaks were being refused.

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Arctic Thunder (4D570002) | thor | `arctic-thunder.route` | yes (14:56, as a held soak) | the race, at the mark and 15 s before the end (race clock 02:01.22, the lava section, overlay FPS 18) |
| Barbarian (54530002) | thor | none | - | not reached: Quest needs a save slot, and the session ended on a lost focus before Training was tried |

Held reading (same instrument as session 23's; `heldsoak.sh` now reads the
cooling devices at the start and in the last 25 s, `thermal.txt`):

| title | held result | apk | gameplay | fps median (min) / share >= 30 | notes |
|---|---|---|---|---|---|
| Arctic Thunder | `scratch/held/arctic-thunder-20260927T145652` | de1f28453e96 (the build the two refused soaks installed, ref 92560461c5) | 317.2 s | 20.29 (14.67) / 8.9% | target 60 (#431). No hang. 18-22 fps in most bins after the mark, 34 in one. No thermal pause: every `thermal-pause-*` device read 0/1 at 15:06:36, hottest cpu zone 93.9 C (66.7 C at the start) |

**Barbarian.** START ends the intro video and a second START opens QUEST's
box (NEW GAME / LOAD GAME). A, then Warrior Select (Keela, A), then three
initials on a letter wheel (A three times gives AAA, and a fourth A on END
accepts). Then SAVE GAME: the hard disk and five EMPTY slots. B goes back to
Warrior Select, so Quest cannot start without writing a save. I did not
write one. VERSUS and TRAINING are on the main menu and should need none.
On the main menu the hat did not move the cursor.

**The focus was lost at 15:10:53, and I stopped.** What I have:

| host time (PDT) | what |
|---|---|
| 15:10:39.6 | frame `010-mm.png`: Barbarian's main menu |
| about 15:10:48 | `focus.py` passes (the read before the next inputs) |
| 15:10:49.5-15:10:51.6 | I send two left-stick flicks down (`axis LY max`, 0.2 s, `axis LY mid`). No button |
| 15:10:53.2 | frame `011-mm2.png` is 10,899 B: the all-black frame |
| 15:11:00 | `focus.py` fails: `screen_focus_lock` 2, `FocusedDisplayId: 4`, display 0's focused window `primaryScreenTopLayout`; `dual_screen_display_mode` 2 |

The Thor's logcat (device clock; `scratch/thor-focusloss-151100.logcat.txt`)
has `PhoneWindowManager.interceptKeyBeforeDispatching` sending a broadcast
at 15:10:52.886 and 15:10:53.028, and the `com.odin.dualscreen.assistant`
window opening at 15:10:53.175. That is a KEY, down and up, 140 ms apart. My
steps in those seconds were stick axis events, and nav.py sent no button
after the B at about 15:10:30. I did not measure the offset between the host's
clock and the device's, so I cannot place my last axis event against that
key to better than a second or two. A second pair of the same lines is at
15:11:00.196 and 15:11:00.425, when I was sending nothing at all (a
`dumpsys` read and a `settings get`). So a key that is not mine reached the
policy at least once. Whether the first one was mine is open: a hand on the
device and an AYN hotkey both fit.

I sent nothing after the failed read. Release: app stopped,
performance_mode 0, fan_mode 4, `dual_screen_display_mode` put back to 0
(device_rest.conf), KEYCODE_SLEEP. `screen_focus_lock` read 0 afterwards
without my touching it, so it follows the dual-screen mode. Battery 79%.

### Hand-over (15:20 PDT, the end of this lane's last attempt)

**Routes committed today, all replayed on the Thor:**

| title | route | pre-mark + shots | queued soak it still needs | held reading |
|---|---|---|---|---|
| Azurik | `azurik` | 177 s + 6 | 500 s | none |
| D&D Heroes | `dnd-heroes` | 279 s + 7 | 600 s | none |
| BloodRayne | `bloodrayne` | 218 s + 7 | 540 s | 20-26 fps before the thermal pause |
| Baldur's Gate: Dark Alliance | `baldurs-gate-da` | 422 s + 18 | 780 s | 59.94 |
| KOF: Maximum Impact | `kof-mi.returning` | 205 s + 10 | 540 s | 33-34 for 66 s, then 13-15; not settled |
| Arctic Thunder | `arctic-thunder` | 238 s + 15 | 590 s | 20.29, no thermal pause |

Queue them with `scratch/bench8.sh <iso> <stem> <ref> thor` once the guard
reads the live copy. None is in `dispatch/results` with a reading, so none
counts as benchmarked on the status page.

**Blocked, with what would unblock each:**
- AMF Bowling 2004: the title does not take START or A. Try BACK, the
  triggers, a second pad.
- Mercenaries: the first load never ends (frozen frame, `kicks=0`). An
  emulation defect, not a route problem.
- Barbarian: route TRAINING or VERSUS. Quest needs a save slot.
- Batman: Dark Tomorrow (Nova), from session 2: the combat button map.

**Next on the Thor's internal storage, by xemu rating** (`scratch/thorlist.py`):
Bicycle Casino, Breeders' Cup, AMF Xtreme Bowling (Perfect); The Lord of the
Rings: The Third Age, The Urbz, Area 51, The Bard's Tale, Bad Boys: Miami
Takedown, Backyard Wrestling 2, Arena Football, Battlestar Galactica,
American Chopper 1 and 2, All-Star Baseball 2003/2004/2005, AFL Live,
AFL Premiership 2005 (Playable); then the Japanese text titles (Bistro
Cupid 1 and 2, Aoi Namida, Angelic Concert, Ex-Chaser, Innocent Tears),
where "an input moves the player" needs a definition first; Antz Extreme
Racing (Starts). Big Bumpin' landed at 14:27 and is not in that list. The
SD-card list from attempt 4 is still open as well.

**For whoever drives the Thor next:**
- Read the focus from the FIRST dispatcher state in `dumpsys input`.
- A title's menus may take the hat, the stick, or neither. Take a frame
  after the move and before the A, above all on a save prompt.
- Size a soak with 3 s per `shot`, and check the result with
  `scratch/fpsbins.py` and the cooling devices before writing a median down.
- A black 10,899 B frame means stop: read the focus, send nothing.

### State at the end of attempt 8 (15:30 PDT)

Six routes replayed on the Thor in this attempt (Azurik, D&D Heroes,
BloodRayne, Baldur's Gate: Dark Alliance, KOF: Maximum Impact, Arctic
Thunder), four of them new titles, with a held reading for four. Three
titles are blocked (AMF Bowling 2004, Mercenaries, Barbarian's Quest mode).
Nothing of mine is queued or running, and I hold no device.

Merging origin/master at 15:25 brought #431's target for Baldur's Gate into
targets.toml: 60, not the default 30 my session 24 table names. Its held
reading (59.94, min 58.31) is at that target.

PR #499 is marked ready. `preflight.sh --allow-tracker` passed on
92560461c5 (14:45) and again after the merge.

**Waiting (PR #499, 15:30 PDT).** The signal is outside this lane: a fix to
`hakux_in_front` (devices.sh) so that it reads the live dispatcher state and
not the last-ANR copy, live on the Thor's dispatcher, with hostops saying
so on #397 (the defect is on #494, comment 5860177923). Then the six soaks
in the hand-over table can be queued. This was the lane's last attempt, so
that is a successor's or the host's to do; everything it needs is in
"Hand-over" above.

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
| Blood Wake | blood-wake | 1-1790508532-titleroutes-1074940 | 480 | 287 s of gameplay; fps window median 37.36 (min 5.12), 29.5% at >= 30; three ~11 s hangs; target 30 (*) |
| Brute Force | brute-force | 1-1790510457-titleroutes-1101937 | 570 | 294 s of gameplay; fps window median 13.16 (min 7.57), 0% at >= 30; no hang; target 30 (*) |
| Otogi | otogi | 1-1790511808-titleroutes-1129571 | 550 | 273 s of gameplay; fps window median 12.62 (min 9.53), 0% at >= 30; no hang; target 30 (*) |
| Burnout | burnout | 1-1790513065-titleroutes-1150288 | 460 | queued 05:45 |

Batch-4 table posted on #397 (comment 5855637410).

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
- Do not read a soak's fps before its frames AND its input. Black frames
  (10,899 B each) mean a covered display. Real frames with a menu/demo
  rhythm in the logcat's `gfps` (D&D Heroes: 40 s at 60, 80 s at 30,
  repeating) mean no press reached the game. `scratch/timeline.py <dir>`
  prints that rhythm.
- Do not queue a route soak on a device that has just reconnected or
  rebooted until something has checked that hakuX holds the input focus. The
  presses go to the focused window, whoever owns it.

### Attempt 9 (resumed 2026-09-27 15:19 PDT)

Why attempt 8 did not finish: it ended on purpose, waiting on something
outside the lane. The focus guard read the last-ANR copy of the dispatcher
state (#513), so no route soak could be queued. Hostops put an interim patch
on the dispatcher's devices.sh at 15:13 and queued the pilot soak
1-1790547557-titleroutes-979135 (Arctic Thunder, 590 s, Thor, ref
677ae13af8). This attempt reads that pilot first. If it plays, the other five
hand-over soaks go in the queue, and the lane goes on down the Thor list.

**The pilot (1-1790547557-titleroutes-979135, Arctic Thunder, ref 677ae13af8).**
The guard passed on the live state (`in-front: bdc158a5
app=com.jreinach.hakux.debug focus=com.jreinach.hakux.debug display=0`), and
the route's input reached the game: frames boot -> title -> SELECT GAME MODE
-> PLAYER SELECT -> SELECT A DRIVER -> SELECT A TRACK -> race. Verdict:
reached_gameplay, 319.6 s after the mark, adb_failures 0, no hang, apk
5cc9d88172f4. **Its fps is not a reading of the race.** Frame m10 is
already GO! with the checkpoint clock at 54, the sled stays still through
m11, rt and gas (clock 41, 22, 16), and the mark frame
(`route-frames/152432-gameplay.png`) reads TIME IS UP. The race began about
27 s earlier than it did in the held soak. So the fps median of 21.37 (9.4%
at >= 30, target 60) covers the time-up screen and whatever followed it.
Fix (f57c1e3b05): hold A from m10 on, with the mark 17 s later, and drop the
RT probe. The pilot verdict is in `pilots/titleroutes.ok`.

**Batch 9 queued (Thor, 0.5 priority, ref e884ad260e, `scratch/q9.sh`, log
`scratch/q9.log`):**

| title | route | request | seconds |
|---|---|---|---|
| Azurik | azurik | 1-1790548501-titleroutes-1529314 | 500 |
| D&D Heroes | dnd-heroes | 1-1790548501-titleroutes-1529756 | 600 |
| BloodRayne | bloodrayne | 1-1790548501-titleroutes-1530145 | 540 |
| Baldur's Gate: DA | baldurs-gate-da | 1-1790548501-titleroutes-1530514 | 780 |
| KOF: Maximum Impact | kof-mi.returning | 1-1790548502-titleroutes-1531011 | 540 |
| Arctic Thunder | arctic-thunder (fixed) | 1-1790548502-titleroutes-1531400 | 550 |

For each result, read the mark frame and the contact sheet before the fps.
The Arctic pilot is the example: a route can reach its mark and still be
off target. Check the cooling devices too (#507).

**Waiting (PR #515, 15:45 PDT)** on those six requests. They hold the Thor
for about 70 min, so a held nav session would only block them. After they
land: read them, then go on down the Thor list in held sessions (Bicycle
Casino, Breeders' Cup, AMF Xtreme Bowling, then the Playable list in the
hand-over).

### Attempt 10 (resumed 2026-09-27 19:02 PDT, handback)

Why attempt 9 did not finish: it ended on purpose, waiting on the six batch 9
requests above. Those requests were outside the session, but it left PR #515
in draft, so no job could fold it. Handback resumed the lane once all seven
results (six plus hostops' BloodRayne re-queue) had landed.

**Batch 9 results (Thor, MAX regimen, apk 6d334facad15, ref e884ad260e).**
Scored with `scratch/judge.py` (title_verdict.py on a copy). Each mark frame
was read before its fps. None of the four scored runs hit the thermal pause:
every run.log reads `no thermal-pause device above 0`, and the hottest zone
was 95-97 C.

| title | request | mark frame | gameplay s | median fps | >= 30 | target |
|---|---|---|---|---|---|---|
| BloodRayne | 1-1790548501-titleroutes-1530145r | 183450-gameplay: Rayne at the church wall, overlay 26 | 323 | 24.89 (min 20.53) | 4.4% | 30 |
| Baldur's Gate: DA | 1-1790548501-titleroutes-1530514 | 182353-gameplay: the archer on the tavern floor, overlay 59 | 298 | 59.94 (min 56.55) | 100% | 60 |
| KOF: Maximum Impact | 1-1790548502-titleroutes-1531011 | 184428-gameplay: Alba vs Soiree, round timer 50, 2 hits, overlay 32 | 311 | 32.89 (min 19.47) | 99.0% | 30 |
| Arctic Thunder | 1-1790548502-titleroutes-1531400 | 185625-gameplay: in the race, clock 00:20.61, overlay 26 | 310 | 24.07 (min 18.24) | 14.2% | 60 |

The Arctic fix (f57c1e3b05) worked: this time the mark lands mid-race rather
than on TIME IS UP. This queued KOF run held 33 fps where the 14:29 held soak
fell to 13-15 after 300 s, so that held soak's median (14.56) was not the
title's rate either.

**Did not run:** Azurik (1-1790548501-titleroutes-1529314), D&D Heroes
(1-1790548501-titleroutes-1529756) and the first BloodRayne run
(1-1790548501-titleroutes-1530145) all read `soak aborted: not-foreground
before the route's first input`. `com.odin.settings`, a stale USB-debugging
dialog, held display 0's focus. The guard refused them as it should. These
are not route failures. Hostops re-queued BloodRayne. This session re-queued
the other two on the same ref:
Azurik 1-1790560999-titleroutes-2862460 (500 s) and D&D Heroes
1-1790560999-titleroutes-2862610 (600 s), Thor, `scratch/q9b.log`.

**Next (for this lane or a successor):** read those two results (mark frame
first). Then go on down the Thor list in held nav sessions under the focus
read: Bicycle Casino, Breeders' Cup, AMF Xtreme Bowling, then the Playable
list in the hand-over.

### Attempt 11 (resumed 2026-09-27 19:30 PDT, handback)

Why attempt 10 did not finish: it did. Its NOTES (the batch 9 table above)
were in 9020dc32cd, and PR #515 folded with them. The handback that started
this attempt listed #515 as a draft, but #515 had already merged. All seven
results it named were already read and recorded above.

State at 19:36 PDT: nothing of mine is running, and the Thor has no hold. My
two re-queued soaks are still in the queue, behind arms and forza414 work:
Azurik 1-1790560999-titleroutes-2862460 and D&D Heroes
1-1790560999-titleroutes-2862610. I did not take a held nav session, because
a hold would stop the Thor from claiming those two. This attempt ends
`waiting:` on them.

Next, once they land: read each mark frame first, then the fps. Then take
held nav sessions for Bicycle Casino, Breeders' Cup and AMF Xtreme Bowling,
then the Playable list in the hand-over.

### Attempt 12 (resumed 2026-09-27 19:45 PDT, handback)

Why attempt 11 did not finish: it did; it ended `waiting:` on the Azurik
and D&D Heroes re-queues (still in the queue at 19:45). This handback listed
the seven batch 9 results again, which attempt 10 had already read and
recorded above, and PR #515 had already folded. Nothing to re-read.

**lane.local's 19:55 list, "queue every ready benchmark now".** Five of its
eight titles already have a benchmark result with a reading, so they were
not queued again:

| title | device | request (already DONE) | reading |
|---|---|---|---|
| Baldur's Gate: DA | thor | 1-1790548501-titleroutes-1530514 | 59.94 / 100% (batch 9) |
| KOF: Maximum Impact | thor | 1-1790548502-titleroutes-1531011 | 32.89 / 99.0% (batch 9) |
| WWE Raw 2 | nova | 1-1790515603-titleroutes-1194477 | 59.94 / 100% (attempt 5) |
| 50 Cent: Bulletproof | nova | 1-1790515600-titleroutes-1194351 | 29.97 / 95.9% (attempt 5) |
| Battlefield 2: MC | thor | 1-1790517591-titleroutes-1523259 | 19.14 / 0%, ten hangs (attempt 6) |

Queued at 19:47 PDT (0.5 priority, ref 4fcbe0262e, `scratch/q12.sh`, log
`scratch/q12.log`). Their only earlier readings were the 300 s titlebench
soaks, which score little or no gameplay (see "Soak length" above):

| title | device | route | request | seconds |
|---|---|---|---|---|
| 007: Nightfire | thor | nightfire | 1-1790563604-titleroutes-373432 | 400 |
| Burnout 3: Takedown | thor | burnout3.returning | 1-1790563604-titleroutes-374056 | 620 |
| Kabuki Warriors | nova | kabuki-warriors | 1-1790563605-titleroutes-374601 | 550 |

### Session 27: HELD Thor, 20:09-20:27 PDT (18 min), battery 72%

**First, an error of mine (20:01-20:03).** The arm
1-1790560694-arms-pacing-base-2707775 claimed the Thor at 20:01:23. I took
the hold at 20:01:24. `hold.sh take` does not wait for a running request, and
I did not re-read running/ before I launched. My launch at 20:01:39 and
my second one at 20:02:53 went to a device the arm owned, and the second
killed its fast.iso process. I stopped, released, and reported it on PR #529
(comment 5862515829) and in hostops-inbox.md. `scratch/takeloop.sh` now takes
the hold and prints READY only once no running/*.owner names the device.
The hold covering 20:04-20:27 was taken that way.

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| RalliSport Challenge 2 (4D530039) | thor | `rallisport-2.returning.route` | yes (20:22, warm, 15/15 focus reads) | Time Attack on Australia / Copperhead. At the mark the car is on the start straight with the race clock at 00:25.55 (overlay FPS 22). At the end (01:08.95) it is off the track by a stand after reversing and steering |

Frames: nav `~/hakux-work/nav/rallisport-2.first-run-20260927T200957/`
(profile creation), `~/hakux-work/nav/rallisport-2.returning-20260927T201734/`
(s-015-p1: 27 mph on the banked turn); replay
`scratch/replay/rallisport-2.returning-202218/` (202650-gameplay.png,
zz-end.png). The profile "00" is on the Thor's disk (flushed with HOME at 20:17).

What the title taught:
- The letter grid and the main menu's carousel both auto-repeat. A stick flick
  registered one move in two. A hat held 0.6-0.9 s moved 2-4 entries. A short
  hat tap moves one. The carousel stops at both ends, so seven left taps
  always land on TIME ATTACK.
- START on the name grid types a character. Done needs the hat.
- The **triggers rest at `min`**. `axis LT mid` is a half-pressed brake, and
  it held the car at 0 mph with the engine revving. That cost 3 minutes.
- In Time Attack the car starts nosed into the first-turn barrier. LT full
  reverses it off.

Benchmark queued: 1-1790566122-titleroutes-1417504 (thor, 570 s, ref
023e26510f). targets.toml: the existing 4D530039 entry (#431 target 60) now
has a thor ISO and the route.

### Session 28: HELD Thor, 20:39-20:50 PDT (11 min; hold taken 20:30 while the pacing FIX arm ran), battery 68%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Spikeout: Battle Street (53450029, USA disc) | thor | `spikeout.returning.route` | yes (20:46, warm, 10/10 focus reads) | Story 1 "Reunion": Spike Jr. fighting Grasshopper's gang on the dock, 59 fps. At the end the score reads 250 |

Frames: nav `~/hakux-work/nav/spikeout.first-run-20260927T203923/` (player
creation; s-013-walk, s-015-fought) and
`~/hakux-work/nav/spikeout.returning-20260927T204333/`; replay
`scratch/replay/spikeout.returning-204621/` (204903-gameplay.png, zz-end.png).
The player "A" is on the Thor's disk (flushed with HOME at 20:43).

- targets.toml had the Europe disc for the Thor. The route was recorded on the
  USA disc, which is also on the Thor, so the entry now names that one.
- The story FMVs decode as green blocks (#303). A still skips them.
- On the name grid, START types a letter (as it did in RalliSport 2). Two hat
  taps up reach Done.

Benchmark queued: 1-1790567423-titleroutes-2191714 (thor, 460 s, ref 5b4294aa5d).

### Session 29: HELD Thor, 21:01-21:16 PDT (15 min; hold taken 20:53 while a sustain507 run finished), battery 62%

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Project Gotham Racing 2 (4D53004B) | thor | `pgr2.route` | yes (21:11, the second replay; 14/14 focus reads) | Instant Action in Florence. At the end the clock reads 4:12, LAP 1 of 2, and the car is further down the street, by the Duomo |

**PGR2 is unparked.** The earlier failures (sessions 6-7) came from counting
menu moves in a menu that auto-repeats. This route holds the hat right for
3 s, which stops at Xbox Demos, then taps left once to Instant Action. It
does not depend on the frame rate or on where the cursor started. The first
replay (`scratch/replay/pgr2-210557`) reached Xbox Demos and then went two
left, to Profile Manager, because the tap was replayed as recorded, a 0.3 s
hold (the time nav.py's own round trip took). The route now holds the tap
0.1 s, and the second replay (`scratch/replay/pgr2-211124`) went into the
race. B, B, A after the first A handles a START that lands early.

Frames: nav `~/hakux-work/nav/pgr2.first-run-20260927T210151/` (s-009-gas:
37 mph); replay `scratch/replay/pgr2-211124/` (211518-gameplay.png, zz-end.png).

Benchmark queued: 1-1790569004-titleroutes-3006458 (thor, 530 s, ref
29420ebf48). targets.toml: route added to the existing entry (#431 target 30).

**A general rule for a menu that auto-repeats:** push to a stop, then step
back with taps held 0.1 s *in the route file*. A tap sent through nav.py is
recorded with nav.py's own round trip, 0.3-0.6 s, so correct it by hand.

### Session 30: 2026-09-27 ~22:00 PDT, no device work

Why session 29 did not finish: it hit the 300-turn cap at 21:43 PDT while it
still held the Thor, and hostops lifted the hold. The PGR2 work it had left
was already done before the cap. The second replay reached the race
(`scratch/replay/pgr2-211124/211518-gameplay.png`), and its benchmark
1-1790569004-titleroutes-3006458 was queued.

State at the start of session 30:
- The Thor is held by `cooldown-devwatch` (xo-therm 74.1 C, #507). It waits
  until the Thor is at 65 C, so there is no held nav session.
- Nothing of mine has run. The seven earlier benchmarks were renamed
  `1-9-...` in queue/ (lowered within priority 1), and their results/ entries
  are dangling symlinks. They are Azurik 2862460, D&D Heroes 2862610,
  Nightfire 373432, Burnout 3 374056, Kabuki (nova) 374601, RalliSport 2
  1417504 and Spikeout 2191714. PGR2 3006458 is queued as well.
- Merged origin/master (43 commits).

Next titles, on the Thor once it is cool and running/ is empty for it: 25 to
Life, Call of Duty 3, Midnight Club 3: DUB Edition, Tork: Prehistoric Punk,
Blinx 2. After those: Bruce Lee (a load inside the scored window), Galleon,
GoldenEye RA (returning route) and Burnout Revenge (the profile loop).

### Session 31: 2026-09-28 05:48 PDT, no device work

Why session 30 did not finish: it did. It pushed its NOTES, PR #534 folded,
and it ended with every benchmark queued and the Thor on cool-down. There
was nothing to drive, so no device work was lost. The harness resumed it as
attempt 2 because the lane had no open PR.

State at 05:48 PDT:
- Both handhelds are under `battery-hostops` holds: the Nova since 01:10
  (14%), the Thor since 04:49 (11%, retagged from cooldown-devwatch). Each
  lifts at 80%, which takes hours on the 500 mA port. No held nav session is
  possible.
- running/ is empty. None of my eight benchmarks has run: Azurik 2862460,
  D&D Heroes 2862610, Nightfire 373432, Burnout 3 374056, Kabuki (nova)
  374601, RalliSport 2 1417504, Spikeout 2191714 and PGR2 3006458 are all
  still in queue/. There are no new results to add to the #397 table.
- Merged origin/master (fast-forward to 9d777502fa).

Next titles are unchanged from session 30: 25 to Life, Call of Duty 3,
Midnight Club 3: DUB Edition, Tork: Prehistoric Punk, Blinx 2, then Bruce
Lee, Galleon, GoldenEye RA (returning) and Burnout Revenge.

### Session 32: 2026-09-28 06:05 PDT, no device work

Why session 31 did not finish: it posted its `waiting:` comment and stopped
with PR #550 still a draft. A draft is skipped by board, fleet and fold, so
the NOTES could not land. The waiting itself was right; the draft was not.
This session marks #550 ready.

State at 06:05 PDT is unchanged from session 31: both handhelds under
`battery-hostops` holds (Nova since 01:10, Thor since 04:49; each lifts at
80%), running/ empty, and all eight benchmarks still in queue/. Next titles
are unchanged.

### Session 33: 2026-09-28 08:05 PDT

Why session 32 did not finish: it did. It marked PR #550 ready, #550 folded,
and it ended `waiting:` on the battery holds. The harness resumed the lane
because it had no open PR and one benchmark had landed.

State at 08:05 PDT:
- The Thor reads 84% and has no hold. It is running
  0-0-x-1790575473-rendermode474-966130 (critical path), with Azurik
  1-1790560999-titleroutes-2862460, two remote461 runs, two dirtytlb runs and
  four arms queued ahead of my six `1-9-` benchmarks. No held nav session
  until running/ has nothing for the Thor (hostops, 09-27 21:54).
- The Nova reads 70% and is held by lane.sustain507.
- Merged origin/master (11 commits).

**Kabuki Warriors on the Nova (1-1790563605-titleroutes-374601, 550 s, MAX,
apk 5910c8c41dd3, ref 4fcbe0262e).** The route reached the fight: the mark
frame `route-frames/074815-gameplay.png` shows round 1, timer 60, the
player's fighter mid-strike, overlay FPS 0. adb_failures 0, no thermal pause
(19 samples, hottest zone 95.1 C).

| gameplay s | window median | window min | time at >= 30 | flips | target |
|---|---|---|---|---|---|
| 329.1 | 58.71 | 0.68 | 22.4% | 4320 (13.5 per s over 320.9 s) | 30 |

**The median is not the title's rate.** It is the median of the 72 windows
of 60 flips, and a window only exists while the guest flips. The guest
flipped at 59 for about 80 s and 40 s, and did not flip at all for the rest:

| after the mark | guest flips |
|---|---|
| 0 - 80 s | none (one perf line, `gfps=0`, worst frame 9667.7 ms) |
| 80 - 160 s | 51-60 per s, with single seconds at 17-35 |
| 160 - 290 s | none |
| 290 - 330 s | 54-59 per s |

The verdict counts five gaps: 71.8, 21.4, 11.5, 88.2 and 53.4 s. In the
first gap the guest is idle, not busy: `[rr425w]` reads `idlepc=8001b02e
idle_us=1906607 busy_us=92760` of each 2 s window, the vblank timer runs at
59.94 Hz, and the emulator keeps presenting the same surface (`refresh ...
flip=0`). So the game is waiting for something that does not arrive. It is
not short of CPU. The route has no frame after the mark, so which screens
the two 59 fps stretches show is not known. Session 1's nav frames read 2-16
on the overlay in the fight, which fits the same stalls.

The 300 s titlebench reading ("Nova 59") scored about 100 s after the mark
and carries the same window median. Read the share of time (22.4%), not the
median, for this title.

**Bruce Lee's 59.94 is not a reading of the fight
(1-1790487611-titleroutes-261841, Thor, 09-26).** lane.local's 19:55 list
asked for the frames behind "21.2 s without 60 guest flips". The run has no
frame after the mark, so this is from the perf lines
(`scratch/scoredscan.py`, 30 s bins from the mark):

| after the mark | guest fps | what it is |
|---|---|---|
| 0 - 60 s | 16-19 | the fight. The 21.2 s gap is here (12 s to 34 s): slow frames, the worst 6.6 s. It is not a load |
| 60 - 150 s | 42-47 | the fight |
| 150 - 289 s | 59, no vblank defers (`Df:0`) | not known |

More than half of the window is the flat 59 stretch, so the median is that
stretch. `Df` is `defers_total`, a pacing count. It says nothing about what
was drawn, so it cannot tell a menu from a light scene. Queued to see the
screens: 1790608228-titleroutes-824349 (Thor, 420 s, `--frames-every 15`,
plain priority, ref 29420ebf48, `scratch/q33.sh`). It is a route check, not
a benchmark. If the frames show a menu or a game-over screen, the route's
play pattern needs an answer to it, and the title needs a new benchmark.

The same scan over my other 27 scored results shows no other window that
changes level upward like this. The downward falls (Blood Wake, Battlefield
2: MC, PGR, BloodRayne) are the #507 shape already recorded above.

Posted on #397: comment 5872826156 (Kabuki and Bruce Lee).

Device state at 08:11 PDT: lane.xbox holds the Thor for a title push (ESPN
MLS ExtraTime 2002) that follows the running rendermode474 request. The
Thor's queue then holds Azurik 2862460, two remote461 runs, two dirtytlb
runs and four arms before my six `1-9-` benchmarks.

**Waiting (PR #558, 08:15 PDT)** on eight requests of mine, all pinned to
the Thor, none of which has run:

| title | request | kind |
|---|---|---|
| Azurik | 1-1790560999-titleroutes-2862460 | benchmark, 500 s |
| D&D Heroes | 1-9-1790560999-titleroutes-2862610 | benchmark, 600 s |
| 007: Nightfire | 1-9-1790563604-titleroutes-373432 | benchmark, 400 s |
| Burnout 3: Takedown | 1-9-1790563604-titleroutes-374056 | benchmark, 620 s |
| RalliSport Challenge 2 | 1-9-1790566122-titleroutes-1417504 | benchmark, 570 s |
| Spikeout: Battle Street | 1-9-1790567423-titleroutes-2191714 | benchmark, 460 s |
| Project Gotham Racing 2 | 1-9-1790569004-titleroutes-3006458 | benchmark, 530 s |
| Bruce Lee | 1790608228-titleroutes-824349 | route check with frames, 420 s |

I took no held nav session. Eight critical-path requests of other lanes are
queued for the Thor, and a hold would put title work ahead of them.
`scratch/thorgap.py` reads that state without touching a device: it exits 0
when the Thor has no hold, runs nothing, and no other requester's `0-` or
`1-` request is queued for it.

**Next, in this order:**
1. Read the eight results. Look at the mark frame and the fps bins
   (`scratch/scoredscan.py`, `scratch/fpsbins.py`) before the median, and at
   the thermal line in run.log.
2. Bruce Lee: read `frames/` of 824349. If the flat 59 stretch is a menu,
   fix the play pattern in a held session and queue a new benchmark.
3. Held Thor sessions (focus read first, hold by `scratch/takeloop.sh`):
   25 to Life, then Blinx 2. Then the Thor list in the hand-over (Bicycle
   Casino, Breeders' Cup, AMF Xtreme Bowling, then the Playable list).
4. Nova titles wait for the Nova: Call of Duty 3, Midnight Club 3, Tork,
   GoldenEye RA (returning), Burnout Revenge. The Nova is on fps-focus work.
5. Kabuki Warriors: a second run with `--frames-every` would show what the
   59 fps stretches are. Not queued, because the Nova's queue is full.

### Session 34: 2026-09-29 16:20-17:0x PDT

Why session 33 did not finish on its own: it did finish -- it posted the
waiting table above on PR #558, #558 merged, and every one of the eight
requests ran to completion afterward. The harness resumed the lane because
the PR had merged and the waited-on requests were done.

**Correction to the carry-forward list.** "Call of Duty 3" and "25 to Life"
have been in section 1's Dropped line (the titlebench batch, already
benchmarked) since this file's first line -- they were never unstarted work,
and Addendum 5 in the brief separately assigns Blinx 2 to lane.slowdown462.
Carrying them in the "next titles" list for four sessions running was a
brief-premise-from-NOTES error, not a re-check of the actual work list
(section 1). The real next Nova titles, in row order, are: Burnout Revenge
(row 11, blocked on the profile loop per Addendum 2), Midnight Club 3
(row 13, this session), 187: Ride or Die (row 15), Crash Bandicoot: The
Wrath of Cortex (row 20), Black Stone: Magic & Steel (row 21).

**A live dispatch wipe removed all eight results mid-session, and the
dispatcher log is the only surviving record of most of them.** Around
16:25 PDT hostops ran a "dispatch wipe" (dispatcher.log:11805, an
arms-uberspike569 re-queue note: "the 16:25 dispatch wipe removed arms pair
c5c0e63aed4e's ..."). I had read `result.json` for two of the eight
(Azurik, PGR2) and grepped `run.log` for all seven completed ones in the
few minutes before the wipe; a repeat of the same Glob/Read a minute later
returned nothing for any of the seven -- `results/<id>/` is a symlink into
storage the wipe cleared, not a real removal of the directory entry (Glob
found the DONE dirs, then found nothing, with no directory-listing
permission change in between). This is the same shape session 30 flagged
("their results/ entries are dangling symlinks") but live, not just found
stale. What I got out before it went, from `dispatcher.log` and the two
`run.log` reads:

| title | request | mark gameplay | adb_failures | thermal after mark |
|---|---|---|---|---|
| Azurik | 1-1790560999-titleroutes-2862460 | 08:21:51 (09-28) | 0 | none, hottest 95.8 C |
| D&D Heroes | 1-1790560999-titleroutes-2862610 | 09:39:08 (09-28) | 0 | none, hottest 95.8 C |
| 007: Nightfire | 1-1790563604-titleroutes-373432 | 10:32:45 (09-28) | 0 | none, hottest 95.0 C |
| Burnout 3 (returning) | 1-1790563604-titleroutes-374056 | 13:59:55 (09-28) | 0 | none, hottest 96.6 C |
| RalliSport Challenge 2 (returning) | 1-1790566122-titleroutes-1417504 | 18:36:58 (09-28) | 0 | pause at +341/375 s of 570 s, hottest 95.0 C |
| Spikeout (returning) | 0-0-x-1-1790567423-titleroutes-2191714 | 07:57:48 (09-29) | 0 | pause at +356/389 s of 460 s, hottest 95.4 C |
| PGR2 | 1-1790569004-titleroutes-3006458 | 13:19:59 (09-29) | 0 | pause at +360/392 s of 530 s, hottest 95.4 C |

All seven reached `mark gameplay` with zero adb failures; the batch's
purpose (routes reach gameplay under MAX and score) holds, same conclusion
as hostops's 09-28 15:37 PDT pilot-file review. The window median / share
at >= 30 that would normally go in this table is gone with the wipe and
cannot be recovered from this session; a later reader who needs those
numbers has to re-run the soak. **Do not re-queue these seven**: the
purpose was already proven twice (this session and the 09-28 pilot-file
review) and a third run is not needed to re-establish it.

Bruce Lee's route-check request (1-1790608228-titleroutes-824349, later
renamed `1-9-...`) never ran: `BATTERY: skip` on it recurs from 14:18 PDT
09-29 through 16:22:59 PDT, the Thor never above 21% battery in that
window. Still queued, still battery-gated. Do not re-queue it either; it is
already in queue/.

**Device state at 16:30 PDT:** Thor 21% battery (below the 30% held-session
floor; an arms run, uberspike569, was admitted there at 16:29 and is
running). Nova 37%, no hold, no running or queued request for it --
free, and above floor. `nova` had six `charge-hostops` hold/lift cycles
between 09:00 and 16:16 PDT today (all under `dispatch/hold/lifted/`), so
its battery has been marginal all day; a HELD session there was kept short.

**Midnight Club 3 (54540079), first-run route, held Nova session
midnight-club-3.first-run-20260929T163330 (16:33-16:47 PDT, hold
lane.titleroutes, 37% -> battery not re-read at release):** no title-state
entry existed for it on the Nova (`titlestate.py show --device nova`), so
this was a clean start, not a repeat of anyone else's work.

Path: sponsor splash (A) -> Rockstar/legal text (A) -> a night-city
flythrough FMV with no control (A) -> MC3 logo, "Checking saved games" ->
four empty CREATE PROFILE slots (A) -> "Enter Profile Name" keyboard,
default "Player 1", ACCEPT highlighted (A) -> "Saving progress and
settings" -> main menu (Career/Arcade/Networking/Race Editor/Options,
Career highlighted).

**The main menu list ignores the digital d-pad.** `press DOWN` and
`press UP` (pad.sh codes 544/545) did nothing across four tries (confirmed
by re-shooting the same frame twice with no visible change). Only the left
stick moves it, and only in fixed jumps: one `axis LY max` (or `min`) then
`axis LY mid`, with >= 0.3 s between the two calls, reliably moved the
highlight exactly THREE rows in that direction, wrapping past the ends of
the 5-row list -- reproduced at gaps of 0.3 s, 1 s and 3 s. A gap of 0 s
(the two axis calls back to back) moved it only two rows, twice. Two
down-pulses from Career (row 0) land on Arcade (row 1): 0 -> 3 -> 1 mod 5.
This is the same family of trap as PGR2's auto-repeating menu (session 29)
but the unit here is "rows per pulse", not "time held".

Arcade -> "San Diego / Cruise / Players: 1 / P1 Stock: Eclipse" (A) -> a
settings screen, Time of Day/Weather/Pedestrians/Traffic all Default (A) ->
"Start" (A) -> LOADING -> **mark gameplay**: a red coupe parked outside
"SIX-ONE-NINE CUSTOMS", minimap/tach/speedo up. RT accelerates -- the
speedo read ~50 mph and the camera showed motion blur and passing
buildings within 1.5 s of `axis RT max`. Frames:
`~/hakux-work/nav/midnight-club-3.first-run-20260929T163330/031-loaded2.png`
(control, stationary) and `033-moving.png` (moving, ~50 mph).

Route: `docs/testing/titles/routes/midnight-club-3.first-run.route` (hand-
written from the nav session, trimming the menu-tick experimentation and
one broken step nav.py logged verbatim -- `press DPAD_DOWN`, which errors
against pad.sh -- rather than replaying the exploration literally).
`route.sh --check` passes.

**REPLAYED unattended, same session, fresh launch -- and it did NOT reach
the same screen. This is a DRAFT, not a working route.** Frames in
`scratch/replay/mc3-1640/` (not committed). Up through "Saving progress
and settings" and the main menu it matched the nav session frame for
frame. At `mark gameplay` (164134-gameplay.png) it showed a static
garage/showcase view of the same red car (tire stacks, no minimap/tach/
speedo), not the street-with-HUD frame the nav session marked. It never
left that frame: a `press A` probe, a `press START` probe, and the route's
own `repeat forever { axis RT max ... }` running for over two minutes all
left the screen pixel-identical (`scratch/replay/mc3-1640/zz-now.png`,
taken ~3 min after the mark). `hakuX-stall` logcat kept incrementing
(`flip`, `pres`, texture cache growth) through that whole window, so the
emulator was rendering, not hung -- the GAME was holding still.

The likely cause: this route marks gameplay only 9.0 s after the Start
press (`wait 4.0` then `wait 5.0`); the nav session took 13.9 s to reach
its street-with-HUD frame from the same point
(`~/hakux-work/nav/midnight-club-3.first-run-20260929T163330/031-loaded2.png`).
9.0 s is probably mid-transition or lands a `press`/`axis` in a state that
does not take it. **Not fixed this session** -- time and the Nova's
battery (37% -> 31% over the ~15 min hold) both had room left, but a third
guess at the wait without seeing what the extra 5 s actually contains
would be exactly the kind of cheap-first probe the project has already
been burned by; the next held session should watch the transition
directly (shorter waits, more shots) rather than guess a bigger number.
targets.toml: `54540079`'s notes point at this route and say why it is not
linked; no `route =` key was added (matching Black's still-draft
`45410083`, which also has no `route` key). No benchmark was queued --
Addendum 2 queues a benchmark only once a route replays, and this one has
not. Do not queue one until it does.

`titlestate.py record` on the Nova: `54540079` observed `created` (the
profile "Player 1" was made and the run reached "Saving progress and
settings"), noting the route is still a draft.

Released the Nova hold at 16:47 PDT (battery 37% -> 31%, app stopped,
asleep). Device state at release: Thor still under the uberspike569 arms
run from before this session, battery unread since 21%; Nova free, 31%,
no hold, no queued request.

**Next:**
1. Fix `midnight-club-3.first-run.route`: re-open a HELD Nova session,
   relaunch, drive to the Start press, then take shots every 1-2 s (not
   one long wait) through the garage frame so the actual transition to the
   street-with-HUD frame is seen and timed, not guessed at. Replay again
   before trusting it or queuing its benchmark.
2. Then continue the corrected Nova work list (section 1): Burnout Revenge
   (row 11, the profile-loop blocker from Addendum 2 -- worth a fresh look
   since it may share MC3's transition-timing shape), 187: Ride or Die
   (row 15), Crash Bandicoot: The Wrath of Cortex (row 20), Black Stone:
   Magic & Steel (row 21).
3. Thor work resumes once its battery clears 30% and running/ has nothing
   pinned to it ahead of title work: the hand-over's Bicycle Casino,
   Breeders' Cup, AMF Xtreme Bowling, then the rest of section 1's Thor
   column. Bruce Lee's route-check request (1-1790608228-titleroutes-824349)
   is still queued and battery-gated; do not re-queue it.
4. The seven results the 16:25 PDT dispatch wipe removed (Azurik through
   PGR2, table above) do not need a re-run: mark gameplay and zero
   adb_failures were confirmed for all seven before the wipe, and hostops's
   09-28 15:37 PDT pilot-file review already reached the same verdict from
   a different two of them. A re-run would only be for the window-median
   numbers, which is a job for whoever needs them, not a default action.

### Session 35 (attempt 2 of 4): 2026-09-29 17:05-17:50 PDT

Why attempt 1 did not finish: it did finish. Batch 12 (PR #623) merged, and
the resume brief for this attempt confirms both -- the merge and that
nothing of the lane's was left running or queued. This is a fresh
continuation, not a recovery from a stall.

Bruce Lee's route-check request (1-1790608228-titleroutes-824349, later
renamed 1-9-...) never ran and is gone from `queue/` -- its four
dispatcher.log lines are all `BATTERY: skip`, the last at 09-29 16:22:59,
and it is absent from `queue/` and `queue/withdrawn/` alike. Something
(another dispatch-state event, unlogged under this id) removed it rather
than running it. Not re-queued this session; Thor battery (21%, see below)
would refuse it again immediately regardless.

**Device state at session start:** Thor 21% (below the 30% held-session
floor; no hold, no running/queued request), Nova 32% (above floor, no
hold). Per the brief's "Next" list, item 1 (fix the MC3 first-run route's
transition timing) was next, and the Nova was the only device clear to
hold.

**Midnight Club 3 (54540079), returning, held Nova session
midnight-club-3.returning.returning-20260929T170935 (17:09-17:16 PDT
interactive drive; hold titleroutes-s35, released 17:4x, battery
32% -> 29%):**

Drove interactively from a fresh `am start` (profile "Player 1" already on
disk from session 34's first-run) through to real gameplay, timing the
Start-press-to-HUD transition directly instead of guessing: `press A` on
"Start" at host time 1790727206.978; a shot after one `wait 2.0`
(1790727211.869, ~4.9 s including two nav.py/adb round trips and a
screencap) already showed the full street-with-HUD frame -- much faster
than the first-run route's assumed 9.0 s (session 34), let alone the 13.9 s
the first-run NAV session itself took. Confirmed player control: `play axis
RT max wait 2 axis RT mid wait 1` moved the car from parked outside
"SIX-ONE-NINE CUSTOMS" out into street traffic (frames 017-018 of the nav
session).

**The main-menu pulse mapping session 34 recorded does not hold here.**
That session found `axis LY max` then `mid` moved the highlight THREE rows
per pulse. This session, checked with a shot after every pulse (not
inferred from the label alone): a two-pulse shell call moved Career(0) to
Race Editor(3) -- consistent with ONE row per pulse in the opposite
(wrapping) direction, i.e. -2 mod 5 = 3, not +2*3 mod 5. Two further
single-pulse calls then moved Race Editor(3) -> Networking(2) ->
Arcade(1), each -1. Four `axis LY max` pulses from Career reaches Arcade,
by this model. Whether "3 rows" or "1 row, reversed" is the title's actual
behavior, or whether it depends on which list is on screen (profile-select
has 4 rows, the main menu 5), was not isolated -- both readings are only
as good as the specific screens they were taken on.

**Wrote `routes/midnight-club-3.returning.route` from the nav session,
trimmed the same way the first-run route was (collapsing the recorded
wait-to-my-own-reading-time gaps, some over 50 s, to fixed 1.3-3.0 s
per-step waits matching the first-run route's style). `route.sh --check`
passed. REPLAYED unattended (fresh `am force-stop` + wake + relaunch,
`scratch/replay/mc3ret-1735/`, capped at 78 s so the `repeat forever` tail
did not run indefinitely) -- AND IT DID NOT REACH GAMEPLAY.** The replay
hit a "Press START to begin" attract screen right after "Checking saved
games" that the interactive drive never showed (or showed and dismissed
without a screenshot catching it -- the interactive drive used the same
3.0 s wait at that point with no intermediate shot). The route's `press A`
there did nothing for over 2 s (two shots 3.5 s apart, both still reading
"Press START to begin": frames `171649-profile-select.png`,
`171651-profile-select.png`). The NEXT `press A` landed once the screen
had cycled back through "Checking saved games" to the SAME 4-row
profile-select list (Player 1 + three "Create Profile" rows,
`171657-main-menu.png` -- mislabeled by the route, since it expected the
real 5-row main menu there). Every step after that operated on the wrong
list: the four LY pulses landed on "Create Profile", and the route's final
`press A` began creating a second profile -- `mark gameplay`
(`171734-gameplay.png`) shows "Career / Purchase a Vehicle / Enter
Nickname", not gameplay. The 78 s cap ended the run before any `flush`, so
nothing was written to disk; `titlestate.py show --device nova` still
reads Player 1, created 2026-09-29T23:47:50Z, unchanged.

This is a **falsifier that worked as intended**: the route claimed to
reach gameplay and the replay checked that claim against the device
instead of trusting the interactive walkthrough, and found it false. The
route file itself now carries this finding (not a second, contradicting
copy of it) so the next session does not re-drive the same interactive
path expecting it to hold. **Not fixed this session** -- the fix needs a
shot immediately after "Checking saved games" resolves, before assuming
either the profile list or the attract screen, and a `press START`
(pad.sh's START code, not A) if the attract screen is there. Time and the
Nova's battery (32% -> 29% over the session) were both nearly spent by the
time the replay's actual failure mode was legible from the frames, so a
same-session retry would have pushed well past the 30-minute hold budget
and the battery floor.

`targets.toml`'s `54540079` notes now cover both drafts (first-run,
returning) and why neither is linked. No benchmark was queued -- neither
route replays.

Released the Nova hold at query, battery 29% (at floor already), app
stopped, REST perf/fan (0/4) set, screen asleep (`KEYCODE_SLEEP`).

**Next:**
1. Fix `midnight-club-3.returning.route`: a held Nova session (battery
   permitting -- it ended this session at 29%, below the 30% floor, so it
   may need to clear that first) that shoots right after "Checking saved
   games" resolves and does not assume what comes next. If "Press START to
   begin" is there, `press START`, re-shoot, and only proceed once the
   actual "Player 1" row is confirmed on screen.
2. The Thor is still battery-gated (21% at session start; unread since).
   Check it before taking a held session there; if still below 30%, work
   the offline parts of the Thor's queued list or wait for it to charge.
3. Bruce Lee's route-check request is gone from the queue (see above) and
   was never run. Re-queue it once the Thor clears the battery floor for a
   route-check-with-frames request, or drive it in a held session instead.
4. The rest of the corrected Nova work list (section 1) after Burnout
   Revenge / Midnight Club 3: 187: Ride or Die (row 15), Crash Bandicoot:
   The Wrath of Cortex (row 20), Black Stone: Magic & Steel (row 21).

### Session 36 (attempt 3 of 4): 2026-09-29, no device work

**Why attempt 2 (session 35) did not need recovery: it finished.** PR #625
merged as `4d648aed31`, and the two hostops addenda that followed (00:56
and, after PR #622 folded, again) both confirm nothing of the lane's was
left running or queued. This attempt is a fresh continuation, not a
recovery from a stall -- there is no unfinished work from session 35 to
pick up beyond its own "Next" list, which this session tried to follow.

**Merged `origin/master`** (fast-forward, 6 commits: PR #622 `lane.hddsplit`
-- the title-disk/nxdk-disk split now wired into the dispatcher, touching
`titlestate.py`/`saves.py`, not this lane's files -- and PR #624
`dispatchguard`). `titlestate_selftest.py` passes on the merged tree (all
checks, including hddsplit's new device-choice and route-selection cases).

**Both handhelds are held for a charging top-up, not by this lane, so no
device work happened this session.** `adb devices -l` (after `adb
kill-server`) returned nothing for either serial. `dispatch/hold/thor` and
`dispatch/hold/nova` both read `lanelocal-topup`:

- `thor.why`: "owner evening top-up 2026-09-29 17:12 PDT: the owner charges
  the Thor off the harness; lane.local releases when it is back on adb"
  (placed 2026-09-30T00:11:24Z)
- `nova.why`: "owner top-up 2026-09-29: the owner charges the nova off the
  harness; lane.local's topup_release.sh releases it when it is back on adb
  at >= 60%" (placed 2026-09-30T00:20:07Z)

Per the lane role rules, a hold placed by another actor is never removed by
this lane, and a device with no adb connection cannot take a HELD session
regardless. So no route work, no replay, no benchmark this session.

**Checked what the offline record shows instead, since a hold is not a
reason to go idle:**

- Bruce Lee's route-check request (`1-9-1790608228-titleroutes-824349`,
  queued since 09-28 15:10 PDT) was promoted by hostops at 23:20:42Z
  (09-29 16:20 PDT) to `1-1790608228-titleroutes-824349`, per #397. It is
  gone a second time: absent from `queue/`, `queue/withdrawn/`, `running/`
  and `results/` alike (checked by id and by `56550016-Bruce_Lee` inside
  `request.json`/`result.json` text, which only turns up its earlier
  session-27 run `1-1790487611-titleroutes-261841` and titleplay's old
  pass-1 run). The charging hold (17:11-17:12 PDT) came about 51 min after
  the promotion, which may or may not be why -- same disappearance-without-
  a-log-line pattern as session 35 noted for the first attempt. Not
  investigated further (not this lane's file; the dispatcher is), but worth
  a board ask if a third promotion also vanishes.
- PGR2's fill-tier benchmark (`1-1790569004-titleroutes-3006458`, queued
  09-28 04:16 UTC, its sibling to the Bruce Lee request) DID run, 09-29
  13:14 PDT on the Thor. `title_verdict.py` on its result: **VOID**
  (`thermal-pause: thermal-pause-F8 1/1 began after +140 s ... still paused
  at the last reading`) -- the Thor's known #507 thermal pause, not a route
  problem. `adb_failures=0` and the route reached gameplay
  (`gameplay=340.0s`). No action needed: PGR2 already has a route and a
  target in `targets.toml`; a clean re-read is a job for whoever needs the
  number, same standing note as the 09-28 dispatch-wipe titles (session
  34, "Next" item 4).
- `docs/testing/titles/targets.toml` now has 65 titles, 31 with a `route =`
  key (routes/ directory has 43 files, some first-run/returning pairs and
  the `black.first-run`/`generic`/`survey` scaffolding routes that are not
  per-title). The 34 titles still reading `route = None` in targets.toml
  are the ones this lane's device work would continue against once a
  handheld is back on adb (Section 1's work list plus the titles routed
  since it was written: 25 to Life, Call of Duty 3, Crimson Skies, Forza,
  DOA1U, Blinx/Blinx 2, Agent Under Fire are lane.slowdown462's / the
  original 9-title batch's, out of scope here).

**No prediction, no capture, no route/targets.toml change this session --
analysis and bookkeeping only, gated entirely on device availability.**

**Next**, once a handheld clears its charging hold and shows up on `adb
devices`:
1. Nova: fix `midnight-club-3.returning.route`'s "Checking saved games" ->
   attract-screen branch (session 35's finding), then continue the work
   list (Burnout Revenge, 187: Ride or Die, Crash Bandicoot: The Wrath of
   Cortex, Black Stone: Magic & Steel).
2. Thor: re-drive or re-queue Bruce Lee's route check if it vanishes a
   third time, file it on the board; then the hand-over's remaining titles
   (Bicycle Casino, Breeders' Cup, AMF Xtreme Bowling, ... and the rest of
   Section 1's Thor column).
3. Either device: any new title lane.xbox has landed since 09-26 that is
   not yet in targets.toml (not checked this session -- no device to
   confirm what is actually on each handheld's disk beyond what targets.toml
   already lists).

### Session 37 (attempt 4 of 4): 2026-09-29 18:48-20:05 PDT, four HELD Nova sessions

**Why attempt 3 (session 36) did not finish:** it did, as a waiting
session. Both handhelds were off adb on the owner's charging top-up hold,
so there was no device work to do. It ended with PR #626 still in draft
and no `waiting:` comment, so nothing marked the wait. Hostops's 18:47
addendum resolved it: both devices were back on adb at 18:35-18:36 PDT.
This session carries on the same branch and PR (#626).

**Device state at start:** Thor 97%, held by lane.xbox's title push
(Darkwatch) and out of service for heat work (fan). Not used. Nova 77%;
lane.ibcache's run was on it. I took the hold with `hold.sh take nova
lane.titleroutes` and started once `running/` had nothing for the Nova.
Each session read `dumpsys input` (FOCUS_OK) before it sent any input
(`scratch/focus.py`), and every release left the Nova at rest: app stopped,
perf 0 / fan 4, asleep.

| session | Nova held (driving) | battery | title | result |
|---|---|---|---|---|
| 37a | 18:56-19:11 | 76 -> 71% | Midnight Club 3 (54540079) | returning route REWRITTEN, replayed clean |
| 37b | 19:19-19:35 | 71 -> 65% | 187: Ride or Die (55530036) | first-run (draft) + returning, returning replayed clean |
| 37c | 19:41-19:50 | 63% | Crash Bandicoot: Wrath of Cortex (56550003) | single route, replayed clean twice |
| 37d | 19:52-20:01 | ~62% | Black Stone: Magic & Steel (58490004) | DRAFT: replays to a room, but the player never walks |

**Benchmarks queued** (Nova, 0.5 priority `1-`, MAX regimen, ref
`1c0c23fabb` = origin/master, `--seconds` = pre-mark + 300, via
`scratch/bench.sh`). All three were still in `queue/` when this session
ended:

| title | request | seconds |
|---|---|---|
| Midnight Club 3 | `1-1790734333-titleroutes-3037624` | 460 |
| 187: Ride or Die | `1-1790735661-titleroutes-3181153` | 370 |
| Crash: Wrath of Cortex | `1-1790736688-titleroutes-3301413` | 400 |

`titlestate.py choose` picks the replayed route for all three (MC3 and 187
`returning`, Crash `single`).

#### Midnight Club 3: the fix for session 35's failed replay

Session 35's diagnosis ("an intermittent attract screen after Checking
saved games") was wrong. Read from frames this time:
- **"Press START to begin" is the title screen.** It always appears, and
  "Checking saved games" comes only AFTER START. The draft pressed A
  there, which does nothing.
- **The boot presses were the real defect.** The interactive session
  pressed A three times during the boot. On replay those presses landed on
  different screens, so START arrived during the intro FMV and every later
  step ran one screen behind. The first rewrite failed in exactly this way
  (`scratch/replay/midnight-club-3.returning-190114`: it ended in Career /
  Purchase a Vehicle).
- **A no-input boot watch** (`scratch/bootwatch.sh`, frames in
  `scratch/replay/bootwatch-190402`): Rockstar logos 6-20 s, intro FMV
  25-80, trademark pages 85-98, fly-in 103, then the title screen from ~107
  to ~155 s after launch, after which the attract FMV loops. The route now
  sends nothing until ~120 s and then one START.
- **The profile list highlights the last-used profile, and it wraps.** It
  now holds Player 1 and Player 2; session 35's failed replay DID save a
  second profile, even though it ended with no `flush`. The route takes the
  highlighted profile with A and does not steer.
- **Menu movement:** the D-pad buttons do nothing. The left stick moved
  +2, +1, +1 rows on three identical pulses. The hat moves ONE row for a
  back-to-back `axis HATY max` / `axis HATY mid`, and TWO when the pulse is
  held ~0.5 s. The route uses one back-to-back hat pulse (Career ->
  Arcade), then START, START, A (San Diego cruise).
- **Replay:** `scratch/replay/midnight-club-3.returning-190751`. Frames:
  `191000-title.png` (title), `191007-profile-select.png`,
  `191018-menu-arcade.png` (Arcade highlighted), `191056-gameplay.png`
  (Jetta on the street in 4th), `zz-end.png` (25 s later, a different
  street, 3rd gear).

#### 187: Ride or Die

- No-input boot (`scratch/replay/bootwatch-191916`): Ubisoft and ESRB,
  then "Please press START to begin" from ~22 to ~50 s, then an **attract
  race with a full HUD**. That race is not gameplay.
- First run (nav `187-ride-or-die.first-run-20260929T192056`): START ->
  PLAYER PROFILE (all Empty) -> A (Create) -> keyboard: A types the
  highlighted "N", Y validates -> MAIN MENU (a horizontal list: Story
  mode, Quick hits, Xbox Live, ...). One LX pulse moved one item; the hat
  moved two. Then Quick hits -> Western Whip Race -> Buck -> sport car ->
  Controller Configuration (first time only) -> a narrated tutorial clip
  that drives itself. START does not skip it; A does. The race starts ~8
  s after the skip. Control: the stick steered the car into a tanker (44
  -> 22) and holding A (Classic: accelerate) brought it back to 37 (frames
  045-048).
- The profile was flushed with a HOME intent (`deferred bdrv_flush_all
  completed`), and the returning route was driven next. **The first boot
  after the flush hung**: a black screen with a spinner at 3 fps,
  `hakuX-watchdog: STALL` and `FORCED IF=1 (stuck 2 hb, eip=0x800151ed)`,
  for 60+ s (nav `187-ride-or-die.returning-20260929T192645`). The next
  launch booted normally, and so did the replay. That is 1 hang in 3 boots.
- A 60 ms START on the title was missed once, so the routes hold it
  150 ms.
- Replay: `scratch/replay/187-ride-or-die.returning-193134`. Frames:
  `193219-profile-select.png` ("N 0%"), `193226-quick-hits.png`,
  `193245-tutorial.png`, `193259-gameplay.png` (race, lap 1/4, 49 mph),
  `zz-end.png` (25 s on, 88 mph).
- `187-ride-or-die.first-run.route` is a DRAFT. Its own session made the
  profile, so a first-run replay needs that profile gone first.

#### Crash Bandicoot: The Wrath of Cortex

- No-input boot (`scratch/replay/bootwatch-194127`): NEW GAME / LOAD GAME
  from ~26 to ~52 s, then a "DEMO" level. NEW GAME -> a name entry
  ("CRASH", DONE highlighted) -> A -> the intro cutscene (START skips it)
  -> a warp-room cutscene on the monitor (START skips it; it was still up
  21 s after the first skip) -> **the warp-room hub**. The stick walked
  and turned Crash.
- First replay (`crash-wrath-of-cortex-194543`) reached the hub, but the
  play loop's stick-up plus A walked Crash into the LOAD/SAVE monitor and
  opened its menu (`zz-end.png`). That menu also showed a "CRASH" save
  already on the hard disk. The loop now uses the stick only and moves
  toward the camera and side to side.
- Second replay (`crash-wrath-of-cortex-194814`), with the save present:
  clean. `194959-gameplay.png` shows the hub; `zz-end.png`, 40 s on,
  shows Crash walking with the camera turned.
- **The scored window is the hub, not a level**, so its fps is an upper
  bound on the title's.

#### Black Stone: Magic & Steel: not reached

The route replays to a green octagonal room with the HUD
(`scratch/replay/black-stone-195702`, `195814-gameplay.png`). The stick
changes the warrior's facing and stance, and A swings his sword. He never
walks: not with the stick held 3 s, and not with the hat. HP fell 410 ->
390 while A was pressed. A room the player cannot leave does not show
play, so the file is `routes/black-stone.draft.route`. It is not linked in
targets.toml and has no benchmark.

#### Do not repeat

- **Do not press buttons during a boot to "skip" it.** Where the presses
  land depends on timing, and one landing on a different screen shifts
  every later step. Watch the boot with no input first (`bootwatch.sh
  <dev> <iso> <s> <every>`), find the title's window, and put a single
  START in the middle of it.
- **Do not steer to a fixed row in a list that highlights the last-used
  entry and wraps** (MC3's profile list). Take the highlighted entry.
- **Test a menu pulse's step size on the screen you will use it on**:
  MC3's hat moved 1 back-to-back and 2 when held; 187's hat moved 2 and
  its stick 1.
- **A play loop must not bring the player back to where it started** if
  something interactive is there (Crash's LOAD/SAVE monitor).

**Next:**
1. Read the three Nova benchmarks above once they land (`title_verdict.py`
   on each result dir). Put the medians in the #397 table.
2. Black Stone: find what makes the warrior walk, from the room the draft
   reaches.
3. Burnout Revenge (Nova, row 11): the profile loop from earlier sessions.
4. Thor titles (Bicycle Casino, Breeders' Cup, AMF Xtreme Bowling, ... from
   the hand-over; Bruce Lee's route check) once the Thor is back in
   service for title work and is not held.

## Session 38 (resumed 2026-09-30, attempt 1): why attempt 37 did not finish, and re-queuing the lost benchmarks

**Why the previous attempt did not finish:** session 37 ended after queueing
three Nova benchmarks (Midnight Club 3 `1-1790734333-titleroutes-3037624`,
187: Ride or Die `1-1790735661-titleroutes-3181153`, Crash: Wrath of Cortex
`1-1790736688-titleroutes-3301413`) and its own commits had already folded
into `origin/master` as `a3681ccb0b` (PR #626) by the time this session
started -- so the branch itself was not the problem. hostops's 03:31
addendum expected those three results to be waiting in `dispatch/results`.
They are not: no trace of any of the three request ids anywhere under
`dispatch/` (queue, running, results, void). Between session 37 (ending
~20:01 PDT 09-29) and now, the harness went through the GitHub suspension,
the offline-git cutover, and lane.hddcrash's mode-660 fix for a bug that
crashed **every** titles.qcow2 boot 2-7 ms after `sdl2_display_early_init`
(dispatch/board-requests/hddcrash's NOTES: ~190 hdd.img runs with 0 early
crashes vs. 10 of 11 titles.qcow2 runs dead, 09-28 00:00 to 09-29 20:05).
My three requests were queued at 19:22-19:41 PDT 09-29, inside that crash
window, against the Nova's titles disk -- the most likely explanation is
they died the same way and were later reaped, though I have no surviving
run.log to confirm it was this bug specifically rather than the dispatch
disruption itself. Either way, nothing about the routes or targets.toml
entries is in question: all three replayed clean interactively in session
37, and `titlestate_selftest.py` still passes.

**This session:**
- Merged `origin/master` (fast-forward, no conflicts): HEAD moved from
  `9c922e017a` to `146b8887db`, bringing in `lane/cithrottle` (CI throttle)
  and `lane/hddcrash` (titles-disk mode 660 fix), both folded offline by
  lane.local while GitHub was suspended. `gh api user` still returns 403
  ("Sorry. Your account was suspended") as of this session, so this PR
  follows the offline protocol in `offline-git/README.md`: `docs/lanes/
  titleroutes/PR.md` in place of a GitHub PR, `OUTBOX.md` in place of a
  #397 comment.
- Confirmed the titles-disk kill-switch drop-in is gone
  (`offline-git/titlesdisk-off.conf.removed-20260930`) and the live
  dispatcher snapshot (`dispatch/bin/dispatcher.sh`) already has the
  mode-660 fix (`dev_make_660`, `mode_found`/`mode` in hdd.json).
- **The Thor is out of service.** `dispatch/hold/thor` = `lanelocal-fanwait`
  since 2026-09-30T02:22:37Z: the Thor's fan is dead (owner 09-29, a
  warranty replacement is shipping). Not mine to release. No Thor work
  this session.
- Nova is free (no hold), asleep, battery 35% -- above the 30% floor but
  with little margin, so I re-queued rather than took an interactive hold.
  Re-queued the three lost benchmarks at ref `146b8887db` (current
  `origin/master`, carries the disk fix), same routes and `--seconds` as
  before:
  - Midnight Club 3 (`54540079`, `midnight-club-3.returning`): `1-1790764527-titleroutes-2436824`, 460 s
  - 187: Ride or Die (`55530036`, `187-ride-or-die.returning`): `1-1790764530-titleroutes-2437076`, 370 s
  - Crash: Wrath of Cortex (`56550003`, `crash-wrath-of-cortex`): `1-1790764531-titleroutes-2437119`, 400 s
- `titlestate_selftest.py`: all checks pass. `targets.toml` parses with
  `tomllib`.

**Next:** read the three re-queued results once they land, put them in the
#397 table (via OUTBOX until GitHub is back), then continue with Black
Stone / Burnout Revenge on the Nova. Thor work waits for `lanelocal-fanwait`
to lift.

## Session 39 (resumed 2026-09-30 12:37 PDT, attempt 1): previous attempt finished cleanly; both devices restricted today

**Why attempt 38 did not need recovery:** it did finish. Its own commits
(`39d518f9b6` and the NOTES/OUTBOX/PR.md above) were already folded into
`origin/master` as `2c59b7bbba` ("fold: lane/titleroutes (offline)") before
this session started -- confirmed by `git log origin/master` showing that
fold directly above session 38's own commit. This is a routine continuation,
not a failure recovery.

**This session:**
- `git fetch origin && git merge origin/master` fast-forwarded
  `39d518f9b6..2ba1a6e9a2` (3 commits: PR #628 escalation-parser fold, plus
  `lane.defecttriage433`'s classification of the six titles blocking 0.5
  Playable -- analysis only, no files of mine touched). No conflicts.
- `gh api user` still 403 "account was suspended": still offline protocol.
- **Session 38's three re-queued Nova benchmarks never ran.** They are not
  in `dispatch/{queue,running,results}` anywhere; they are parked at
  `dispatch/parked/titleroutes-daypark-0930/{2436824,2437076,2437119}.req`.
  The park's README: "lane.local 2026-09-30 10:05 PDT: owner plan -- the
  Nova battery goes to Playable confirmations first today (no top-up until
  the evening dock). These three route runs return to queue/ tonight after
  the dock." Not mine to unpark; nothing to do here but wait for tonight.
- **The Thor's hold text changed since the "Thor screening program" addendum
  above was written.** `dispatch/hold/thor.why` now reads (timestamp
  2026-09-30T17:48:12Z, i.e. today, after the 12:40 PDT addendum):
  "lanelocal-fanwait: the Thor's fan is dead ...: light work only --
  staged new titles push under this hold (push-under-hold flags); **no
  queued runs**; lane.local releases after the repair." That supersedes the
  addendum's "queued requests only, `--device thor --hard-pin`" allowance --
  even queued Thor screening soaks are out today, not just interactive
  holds. Confirmed no active hold file for Nova (only `hold/lifted/nova.*`
  entries), so the Nova restriction is the owner-plan/battery one above, not
  a hold.
- **Net: no device work is available from either handheld this session.**
  Dispatched an Explore agent to check whether route-authoring work is
  possible without new device time (the Thor-screening addendum's own
  suggestion: "author the route from pass-1 survey soaks and their
  route-frames" that already exist on disk from earlier campaigns) --
  findings below once it returns.
- Did not touch `dispatch/parked/titleroutes-daypark-0930` or
  `dispatch/hold/thor*` (not mine; per brief "Do not restore or touch"
  applies in spirit even though that line names a different parked dir).
- `titlestate_selftest.py`: all checks pass (no code of mine changed this
  session). `targets.toml` still parses with `tomllib`.

**Offline-work check (Explore agent):** the Thor-screening addendum's own
suggestion was to author routes from pass-1 survey soaks already on disk,
without new device time. The agent found 4 Thor titles with `iso.thor` set,
no route yet, and pass-1 `route-frames/` reaching gameplay per
`titleplay/NOTES.md`'s review table: Blinx, Blinx 2, Forza, 25 to Life.
Three of those four (Blinx, Blinx 2, Forza) are explicitly reserved for
`lane.slowdown462` (brief addendum 3), so not mine to draft. The fourth,
**25 to Life**, has only one thin summary line in `titleplay/NOTES.md`
("profile created, chapter 1 Warehouse, third-person shooting") with no
step-by-step input sequence -- not enough evidence to draft a route with
any confidence, unlike routeprep's detailed drafts (below). Left undrafted
rather than guess at a title defecttriage433 already ranked lowest priority
of its six ("may resolve to 'fine' once measured properly").

**`lane.routeprep`'s backlog (real, useful offline-prep work): drafts
awaiting device validation.** routeprep (`docs/lanes/routeprep/`, its own
lane, offline, not my files) prepares route drafts from exactly this kind
of survey evidence; "lane.titleroutes validates each one on a device and
adopts it into `docs/testing/titles/routes/`" (its NOTES.md, line 6). Cross
-referenced its 24 drafts against my adopted `routes/`: 8 titles have
**already been superseded** by my own validated routes under different
filenames (187-ride-or-die, mc3 -> midnight-club-3, jsrf, mechassault2,
pgr2, rallisport2, spikeout, wwe-raw2) -- no action needed, routeprep's
NOTES is just stale on naming. The other **9 are still pending validation**,
never driven on a device:

| draft | device | evidence quality (routeprep NOTES) |
|---|---|---|
| `burnout-revenge.first-run.route`, `.returning.route` | Nova | pass-1 input frames + Burnout 3's played routes; open: name keyboard, save default, pre-race video |
| `galleon.route` | Nova, Thor | pass-1 input frames to an in-game load; open: main-menu order |
| `doa3.route` | Thor | pass-1 input frames through the 200 s copyright wait; open: Story entry, costume step |
| `capcom-classics2.route` | Thor | no frames on disk, `[recalled]`/`[guess]` only |
| `castlevania-cod.first-run.route`, `.returning.route` | Thor | no frames on disk, `[guess]` only |
| `smt-nine.route` | Thor | no frames on disk, Japanese menus, `[guess]` only |
| `thps2x.route` | Thor | no frames on disk, `[guess]` only |
| `tork.route` | Nova, Thor | hands-off frames only (no input evidence past the title), `[guess]` past START |

Priority for the next device session, ranked by evidence quality (a draft
built on real input frames is far more likely to replay clean on the first
try than a `[guess]`-only one): **Burnout Revenge** first (Nova, already on
my own "next" list from session 38; strong evidence), then **Galleon**
(Nova+Thor, strong evidence; also already on my radar from the 09-27
addendum's "fast titles blocked by their route" note, so validating it
finally answers whether its actual route matches that note's account), then
**DOA3** (Thor, strong evidence). The `[guess]`-only five need a short nav
session before they're worth a full validation replay, same as any
no-evidence title on my own work list.

## Session 40 (resumed 2026-09-30 12:45 PDT, attempt 2): the three "lost" benchmarks were never lost

**Why attempt 1 (session 39) did not need recovery.** It did finish, cleanly:
it ended on a `waiting:` naming two external signals (the Nova park returning
to queue tonight, the Thor's `lanelocal-fanwait` hold lifting), and PR body
`State: ready`. Nothing failed; there was just no device work available at
the time. This session resumes as a routine continuation, not a rescue.

**The mystery session 38 reported ("no trace of any of the three request ids
anywhere under `dispatch/`") is resolved: they were never lost.** Re-checked
`dispatch/results/` for the three *original* session-37 request ids (not the
session-38 re-queue duplicates) and all three are `DONE` with real frames and
logcat, at a later admission time than session 38's check:

| title | request (original, session 37) | gameplay_s | fps median (min) | share >= target | target | hang |
|---|---|---|---|---|---|---|
| Midnight Club 3: DUB Edition | `1-1790734333-titleroutes-3037624` | 288.7 | 29.67 (13.81) | 87.5% | 30 | no |
| 187: Ride or Die | `1-1790735661-titleroutes-3181153` | 302.2 | 59.94 (59.88) | 100% | 30 | no |
| Crash: Wrath of Cortex | `1-1790736688-titleroutes-3301413` | 308.9 | 56.18 (41.78) | 100% | 60 | no |

(`scratch/judge.py` on each, `docs/testing/title_verdict.py` under the hood,
apk `eae7a2f00588`, ref `1c0c23fabb`.) All three route-frame sequences in the
result dirs show real play through to the mark (MC3: Jetta on the San Diego
street; 187: the Western Whip race; Crash: the warp-room hub), matching what
the interactive replays in session 37 showed. Most likely explanation: these
three requests were still in flight (or briefly stuck) during the
GitHub-suspension/offline-git cutover session 38 investigated, and their
results only landed in `dispatch/results/` sometime after session 38's check
-- not evidence of the titles-disk crash session 38 blamed them on. Nothing
here contradicts that crash's existence (lane.hddcrash's fix is real and
independently documented), just that these three particular requests survived
it.

**Consequence: session 38's three re-queued duplicates are now redundant.**
`1-1790764527-titleroutes-2436824` (MC3), `1-1790764530-titleroutes-2437076`
(187), `1-1790764531-titleroutes-2437119` (Crash) sit parked at
`dispatch/parked/titleroutes-daypark-0930/`, due back in `queue/` tonight per
lane.local's 10:05 PDT plan. Running them would re-spend Nova device time
re-measuring titles that already have clean, non-void readings above. This
parked dir is under lane.local's management, not named in my brief's "do not
touch" list (that names a different parked dir, titleplay-p1), but I am not
unparking, editing or deleting its contents unilaterally -- flagging it here
and in OUTBOX for lane.local/hostops to drop before tonight's return, since
they are not mine to withdraw from the queue.

**Device state, checked fresh this session (not reused from session 39):**
- **Nova** (`ee317437`): no hold file (only `hold/lifted/nova.*` entries).
  Battery 43%. But `dispatch/running/1-1790775886-lane.verdict433-3086903`
  names it (`.owner` = `nova`) -- confirmed live via
  `dumpsys activity activities | grep mFocusedApp`: hakuX is in front on the
  Nova right now, mid soak (Arctic Thunder, #433 Playable confirmation batch
  6, 910 s). Per the brief, a device whose `.owner` names it is off limits
  for a hold regardless of battery. Also per lane.local's 10:05 PDT plan,
  today's Nova battery goes to Playable confirmations first even once this
  soak ends -- so I did not queue behind it either.
- **Thor** (`bdc158a5`): `dispatch/hold/thor` = `lanelocal-fanwait`,
  `thor.why` still reads the 17:48 PDT "no queued runs" text from session
  39's check. Unchanged; still out for both interactive and queued title
  work.

So, same as session 39, no device work is available this session. What
changed is real: three benchmark numbers that were reported as missing now
have a home in the #397 table above, and the duplicate re-queue is now known
to be pure waste whenever it runs tonight.

`python3 docs/testing/titles/titlestate_selftest.py`: all checks pass (no
code of mine touched). `targets.toml` parses with `tomllib` (unchanged;
these three titles' entries already carried routes, fps is reported in NOTES
and OUTBOX, not stored in targets.toml).

**Next, once a device is actually free:** validate `lane.routeprep`'s ranked
drafts in the order session 39 set (Burnout Revenge and Galleon on the Nova
first, then DOA3 on the Thor, once its fan is repaired), then the five
guess-only drafts.

**Waiting**, same two external signals as session 39, now with the
duplicate-withdrawal flag added:
1. The Nova returning to general availability (tonight, per lane.local's plan,
   or whenever `dispatch/running/1-1790775886-lane.verdict433-3086903`'s
   successor confirmations stop filling its queue).
2. The Thor's `lanelocal-fanwait` hold lifting after the replacement fan
   arrives.
3. (new) lane.local or hostops deciding whether to drop the three now-
   redundant parked re-queue requests before they return to `queue/` tonight.
