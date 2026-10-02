# lane.titleroutes2: per-title routes and surveys on the Nova (#397), successor to lane.titleroutes

The predecessor's record is `docs/lanes/titleroutes/NOTES.md` (65 sessions) and `OUTBOX.md`; read them first. This file
holds only what this lane did after it. Offline protocol (GitHub suspended): the PR is `PR.md` on this branch, issue posts
go to `OUTBOX.md`, folds are `offline-git/foldqueue.sh`'s.

## Session 1 (2026-10-02, Opus 5.5)

Branch at origin/master `333711ac66` (0 ahead / 0 behind at start). `dispatch/running/` empty, no Nova hold, Nova
battery 80%. Thor: `lanelocal-fanwait`, not used.

### The two queued surveys, read frame by frame (copies in `scratch/judge/`)

| title | request | reached play? | what the frames show |
|---|---|---|---|
| Halo: Combat Evolved (4D530004) | `1790933948-titleroutes-171581` | **in-engine, but only the cryo-bay look tutorial** | booted = main menu (CAMPAIGN lit). Cycle 1: START -> ENTER NAME (default "New001"), A -> CHOOSE DIFFICULTY (Normal lit). Cycle 2: START -> LOADING, A -> black. Cycle 3 A (`031129`): "Reveille", the cryo bay, the tech at the console: live, player-controlled. Every later cycle is START = pause panel (RESUME GAME / REVERT TO SAVED / RESTART LEVEL / SAVE AND QUIT; objective "Complete training diagnostic") and A = resume. The tip "Use RIGHT [stick] to look around" never clears: the training wants look-up/look-down input, which the survey never sent (only RX). Play frames `031405..031456` are the same room, camera swung right. Not representative play yet; route needs the training done. |
| Conker: Live & Reloaded (4D530051) | `1790933948-titleroutes-171701` | **no** | intro FMV, Rare logo, "Xbox Live & Co" intro, "Loading...", then the multiplayer front end: profile select (profile "kk", character Emily), then the drum menu Xbox Live / System Link / Dumbots / Profiles. A on Xbox Live gives "Connection to Xbox Live lost. Cannot sign in" (A = Continue back), and the survey looped there for minutes. The play loop's stick-UP + A reached a SHC / Tediz roster screen (`032005`, a Dumbots/bot lobby), then black (`032031`, the window's end; possibly a match loading). No single-player (Bad Fur Day) entry seen on screen. |

### Ranked next steps (probability x size of the win)

1. **Gunvalkyrie** (P high: 8 START/A cycles to play, every extra pair is pause + Continue; win high: 59.94 fps /
   100% in the survey, target 60, the strongest nomination candidate). Routed.
2. **Bloody Roar: Extreme** (P high: same START/A shape, a fighter where every stray press is an attack or pause +
   resume; win: a routed, measured title, and the measurement is a real 10 fps slowdown for #397 triage). Routed.
3. **Star Wars Ep. III** (P medium: 13 cycles through an unskippable crawl and movie, and the survey's loop wedged on a
   wall; win: a routed 30 fps title). Routed with a four-direction loop.
4. **Halo: Combat Evolved** (P medium: the path to the cryo bay is 3 cycles, but the look training needs input the
   survey never sent, and the survey's profile "New001" may change the menu; win high: the most-played title in the
   library). Next, after the pilot read.
5. Conker (P low open-loop: the single-player entry is not on screen, the multiplayer path needs a cursor move on a
   drum menu), Halo 2 / Ninja Gaiden Black / ToeJam & Earl III / Tron 2.0 surveys (blind; P ~0.5 each of learning a
   path).

Not mine: **Buffy** is lane.routedriver2's now (`drive-profiles/buffy.toml`; its NOTES: menu path and play detection
work, the open problem is the ledge gap ~12 s into the canyon). Checked on `origin/lane/routedriver2` before touching
it; not re-attempted here.

### Routes written from the survey frames (commit `282a5af148`)

Each route's header cites the frames it was read from. All open-loop (no `waitfor`), every post-mark press harmless on
any screen the game can fall into (no START after the mark).

- `gunvalkyrie.route`: 10 START/A cycles (play at cycle 8; 2 guard pairs = pause + Continue), mark, loop: LY forward,
  RT fire, LT jump, RX turns, LX strafe, one A.
- `bloody-roar-extreme.route`: 10 START/A cycles (fight at cycle 8), mark, fight loop (LX toward, X/Y/X, B, A, LX back).
- `star-wars-ep3.route`: 15 START/A cycles (play at cycle 13), mark, loop walking up/right/down/left with X/Y attacks
  (the survey's stick-UP loop held Obi-Wan against a wall: frozen_frac 0.95).
- `targets.toml`: `route` + notes on 48550001 and 49470017, a new 4C410017 entry (no #431 target; default 30).
  `tomllib`: 83 titles. `titlestate_selftest.py`: all checks passed. `route.sh --check` (the dispatcher's snapshot):
  route ok on all three.

### Replays queued (Nova, `--hard-pin`, 420 s, ref `282a5af148`, `--no-expect`, plain priority: gh is down)

Device pin read back from each `.req` as `nova`. 3 x (420 + 90) s = 25.5 min, inside the first-30-min pilot allowance.

| title | route | request |
|---|---|---|
| Gunvalkyrie | `gunvalkyrie` | `1790939914-titleroutes2-1445425` |
| Bloody Roar: Extreme | `bloody-roar-extreme` | `1790939919-titleroutes2-1446231` |
| Star Wars Ep. III | `star-wars-ep3` | `1790939919-titleroutes2-1446307` |

### Replay results (frames copied to `scratch/judge/`, scored locally with `title_verdict.py --targets`)

- **Gunvalkyrie, replay 1** (`1790939914-titleroutes2-1445425`): no ROUTE FAIL. The title came one cycle sooner than in
  the survey (play on cycle 7's START, `042146`); the two guard pairs were pause + Continue as designed; the mark
  `042221-gameplay.png` is live play with the HUD. But 9 of the 13 later frames are the advisor's tutorial boxes ("Use
  the Left Thumbstick to move...", "Pull the Right Trigger...", "...Dash in any direction while in the air"): the scene
  dims, the game waits, and a yellow down-arrow asks for A. One A per ~25 s cycle left each page up for most of a cycle.
  Between the boxes the moves work (walking, firing at `042347`, static_frac 0.01). Scorer: 251 s of play, median
  59.94, 97.4% at 30+, no hang; worst hitch 2.75 s at +4.7 s (shader). Not a reading of play yet (much of it is the
  paused box). Fix `685c52e514`: A every ~2-3 s in the loop. Replay 2 queued: `1790940485-titleroutes2-1611958`.
- **Bloody Roar: Extreme, replay 1** (`1790939919-titleroutes2-1446231`): **never left the attract loop.** Each frame is
  shot 5 s after its press: the title came up, A landed on it, it timed out to black and a DEMONSTRATION fight, and the
  next START (11 s after the last) only brought the title back, six times; then the title for the whole window. The
  title takes START only for a few seconds, and an 11 s cycle kept missing it; the survey's cycle 4 hit it by luck of
  phase. **Do not repeat: a START/A cycle with 5 s waits is a sampling clock; a screen shorter than the cycle is hit or
  missed by phase.** Fix `8fee881326`: START/A pairs 1.2 s apart for ~110 s, a frame every 4 pairs. Replay 2 queued:
  `1790940923-titleroutes2-1761085`.
- **Star Wars Ep. III, replay 1** (`1790939919-titleroutes2-1446307`): no ROUTE FAIL; same path as the survey (no
  Continue menu despite the store's 4C410017 save), play on cycle 13's A (`043818`), the mark `043846` is live play.
  The player is Anakin (HUD portrait); Obi-Wan is the AI partner. Then 11 near-identical frames to the end
  (static_frac 0.82): the four legs of the loop cancel out, so he never left the wrecked starfighter, and the one shot
  per loop lands at the same loop phase every time. No enemy and no door in any frame. Scorer: 183 s of play, median
  30.0, 97.2% at 30+, no hang, worst hitch 484 ms -- over a parked view, so not a reading of play. **Do not repeat: a
  loop whose legs cancel never leaves its spot, and one shot at a fixed loop phase can make a moving loop look frozen
  (or a frozen one look alive); shoot on every leg.** Route v2 is an exploring loop (net movement up, a frame per
  leg); queued only when the Nova has room.

Also queued (one backlog survey, per the one-at-a-time rule): Ninja Gaiden Black `1790941402-titleroutes2-1890328`
(generic survey, 300 s, ref `8fee881326`). Chosen over Halo 2 because Halo 2 opens on the same kind of look-training
as Halo CE, which `halo-ce` replay 1 is about to test; NGB has no such known trap.

Pilot verdict written to `dispatch/pilots/titleroutes2.ok` (04:28 PDT) after reading the Gunvalkyrie replay; queued
after it: Gunvalkyrie replay 2, `halo-ce` replay 1 (`1790940485-titleroutes2-1612232`, ref `685c52e514`), Bloody Roar
replay 2.

### Second round of results

| title | request | outcome | what the frames show |
|---|---|---|---|
| Bloody Roar: Extreme, replay 2 | `1790940923-titleroutes2-1761085` | **CONFIRMED** | the fast START/A phase reached the fight (Yugo vs Busuzima) ~150 s after launch; mark `050149` is the live round; every later frame is the same round moving (timer 55 -> 23, Busuzima's beast change). Median 9.84 fps (min 8.26), 0% at 30+, no hang; 32 hitches, classified 25 texture / 6 both / 0 shader: a texture-path slowdown for #397 triage. Not nominated. targets.toml updated. |
| Gunvalkyrie, replay 2 | `1790940485-titleroutes2-1611958` | play all window, partly against a wall | boxes now clear (2 of 14 frames); 100% at 30+, no hang; but `044546..044755` Kelly faces one cliff (turns nearly cancel). |
| Gunvalkyrie, replay 3 | `1790941860-titleroutes2-2053231` | play all window, mostly against walls | 1.2 s turns per cycle only randomise the heading; 100% at 30+, no hang, static 0.009; most frames are canyon walls. v4 (`bd03a589f7`) never turns: forward always, alternate strafes, double-LT boost. Queued `1790944628-titleroutes2-2686999`. |
| Halo: Combat Evolved, replay 1 | `1790940485-titleroutes2-1612232` | in the cryo bay, past the tube, short of the scripted walk | SELECT PROFILE (New001) -> LOAD LEVEL (Pillar of Autumn) -> difficulty -> cryo bay; look test cleared; mark `045315` still has "Use X to exit the cryo-tube" up; the loop's X took it; then the window wandered the bay under "Stand on the red square" (99% at 30+, static 0.0). |
| Ninja Gaiden Black, survey | `1790941402-titleroutes2-1890328` | no play in 300 s | title -> MAIN MENU (NEW GAME) -> prologue (not skipped by START/A) -> "The Book of the Fiends" over Now Loading (~95 s) -> "CHAPTER 1: The Way of the Ninja" (A = Proceed) -> the chapter's opening cutscene at the window's end. Route `ninja-gaiden-black` written (20 cycles, START x2 to skip the cutscene [guess], B x3, run/attack loop); queued `1790944628-titleroutes2-2687135`. |

### Held Nova session: Halo CE's calibration (05:11 take, 05:19-05:35 PDT on the device, released)

`hold.sh take nova lane.titleroutes2` while my own Gunvalkyrie replay 3 ran, `wait-idle` until it ended (05:19), focus
read (`FOCUS_OK`) before and after launch, `nav.py` session `~/hakux-work/nav/halo-ce.returning-20261002T051941/` (59
frames), then `nav.py end`, force-stop, perf/fan back to 0/4, screen off, `hold.sh release` (05:35, `who` = free).
Device time 16 min, battery 80% on AC.

The calibration, in order (the route header has it in full): look test -> "Use X to exit the cryo-tube" (X, not A) ->
exit cutscene, control facing the tube row -> "Use LEFT to move" -> step on the red square in front of the light pillar
-> "Target each of the flashing lights" (five lights in a cross; each goes green under the crosshair) -> the same five
again "Vertical looking is now inverted" -> "Press B to try it the other way / A to leave it" (A) -> a GAMEPLAY HELP
panel that A does not close and START does -> "Checkpoint... done". Nothing scripted happened in the next ~2 min of
looking around (both doors shut); that is where the session stopped.

The light test needs aimed input: full-throw right stick turns ~90 degrees in a ~0.4 s tap (nav.py's own round trip is
most of that), a third-throw tap (RX 16000) ~25 px, two-thirds (22000) ~65 px. Ten aimed taps after an open-loop walk to
the square is not a route that replays; it is drive.py's kind of problem (screen-aware), or a save made after the
checkpoint. **Do not repeat: nav.py's per-step round trip (~0.3-0.5 s) is added to every axis hold, so a "wait 0.15"
turn is really ~0.6 s; use partial-throw values (RX 16000/22000 on the Nova's +-32767 pad) for fine aim.**

Queued after the session (ref `bd03a589f7`): Gunvalkyrie v4 `1790944628-titleroutes2-2686999`, Ninja Gaiden Black route
`1790944628-titleroutes2-2687135`, Star Wars v2 (exploring) `1790944635-titleroutes2-2688279`.

### Third round of results (ref `bd03a589f7`)

| title | request | outcome | what the frames show |
|---|---|---|---|
| Gunvalkyrie, replay 4 (no-turn loop) | `1790944628-titleroutes2-2686999` | worse | a dark rock face within 14 s of the mark, pressed against one wall from `060508` to the end; same numbers (59.94, 100% at 30+, 96% at 60, no hang). **Decision: the route goes back to replay 2's loop, steps byte-identical to `685c52e514` (checked with a diff of the non-comment lines), so replay 2 is its confirmation. CONFIRMED and nominated (#433).** Travelling the level for a whole window needs drive.py, not a fifth blind loop. |
| Ninja Gaiden Black, route replay 1 | `1790944628-titleroutes2-2687135` | **CONFIRMED** | chapter card on cycle 19 (`061202`), opening cutscene, HUD by `061240`; skip1's START opened the in-game menu, skip2's closed it; mark `061303` Ryu in the waterfall basin; live play to the end (static 0.007). Median 39.4, 75% at 30+, 0% at 60, shader hitches to 1.5 s. Below its own target; not nominated. |
| Star Wars Ep. III, run 2 (exploring loop) | `1790944635-titleroutes2-2688279` | **CONFIRMED, nominated (#433)** | the net-forward walk crosses the hangar, fights droids, reaches the force-field door, and the level advances through its own objectives ("DEFEAT ENEMIES WHILE R2-D2 EXTENDS CATWALK", "OBJECTIVE ACHIEVED"); 3 of 41 frames are short scripted cutscenes; static 0.0. Median 29.97, 96.3% at 30+ (target 30), no hang. Measured with ~5 screencaps per cycle; the file is kept exactly as run. |

**What worked, for the next title:** a net-forward loop with a frame on every leg both maps the level and plays it; a loop
whose legs cancel (Star Wars v1) or that turns blind (Gunvalkyrie v3) parks the player. Combat titles whose levels pull
the player along (Star Wars) suit it; open canyons (Gunvalkyrie) do not.

Queued next (one backlog survey): Halo 2 `1790946979-titleroutes2-3257388` (300 s), to see whether it opens on an aimed
calibration like Halo CE's.

## Session 2 (2026-10-02, attempt 2, Opus 5.5)

**Why attempt 1 did not finish:** its session was stopped from outside at 06:27:59 PDT (systemd `Stopping`/`Stopped`,
empty output log), about ten minutes after it queued the Halo 2 survey and committed the third round's notes
(`8ce3813ed6`). hostops found no host tool or tick that issued the stop; the cause is undetermined, and this lane does
not know it either. Nothing was lost: every result through the third round is recorded above, and the only open item
was the Halo 2 survey, which finished (DONE) unread.

Merged origin/master (`edcb5afd06`; the branch was 18 behind). Nova: held by `routedriver2:s2c` (a <=5 min Buffy read)
at start; nothing of mine running or queued. Thor: `lanelocal-fanwait`.

### Halo 2 survey, read frame by frame (`1790946979-titleroutes2-3257388`, copy in `scratch/judge/`)

**In-engine, but only the Armory's look test.** Title -> CHOOSE PROFILE (Create New Profile) -> PROFILE NAME keyboard
("Halo0001"; START = Done) -> main menu (CAMPAIGN) -> New Campaign -> SELECT LEVEL (The Heretic) -> Normal -> loading
-> the Heretic prologue cutscene (START/A do not skip it) -> cycle 8's START: "Updating profile... done", the Armory, the
Chief in the calibration ring, the Gunnery Sergeant beside it. Every later START is GAME PAUSED (Continue lit, objective
"Follow the Gunnery Sergeant's instructions"), every A is Continue. From `062604` the ring's top light is red under "Use
[RIGHT] to look up" for the rest of the window; the four play frames are identical. Same trap as Halo CE's survey: the
survey loop sends no vertical look. Unlike Halo CE, the first prompt only asks for a direction (look up), not an aimed
crosshair, so an open-loop block may clear it; what follows it is unknown, so the route shoots a frame after every leg.

The survey saved a profile (4D530064 harvested), so the next run may list "Halo0001" first; START and A both select on
these menus and two guard pairs absorb a one-press shift.

Route `halo-2.route` written: 10 START/A cycles, 3 x (look up, look down, A, step + X) with a frame per leg, mark, a walk
loop (forward, X, turns, A, B, small up/down looks) with a frame per leg and no START. `route.sh --check`: route ok.
`targets.toml`: `route = "halo-2"` on 4D530064 (DRAFT); `tomllib` 83 titles; `titlestate_selftest.py`: all checks passed.

Queued (Nova, `--hard-pin`, ref `93203cee0a`, `--no-expect`): `halo-2` replay 1 `1790948386-titleroutes2-3358105` (420 s);
ToeJam & Earl III survey `1790948390-titleroutes2-3358315` (300 s, the next backlog title; Tron 2.0 has no targets.toml
entry, so it waits).

### Halo 2, replay 1 (`1790948386-titleroutes2-3358105`, 77 frames, read in full)

No ROUTE FAIL. The saved profile did list "Halo0001", but "Create New Profile" stayed lit, so the path was the survey's
exactly (keyboard default "Halo0002"); the Armory came on cycle 7's A (`064224`, one cycle sooner: "One Size Fits All").
Three guard pairs were pause + Continue. Then the look block:

- `064314` look-up (RY min = stick UP): view tilts up, the top light test answered.
- `064318` look-down (RY max): the view goes FURTHER up (ceiling lights). By now the look is inverted, as in Halo CE's
  calibration ("Vertical looking is now inverted", then "B to try it the other way / A to leave it").
- `064321` A, `064325` step + X: unchanged.
- `064331` (2nd round RY min): level again, "Updating profile... done" (the look setting saved).
- `064335` RY max: straight up at the ceiling hatch; the third round never comes back level.

Mark `064358`. The whole play window (`064403..064708`, 40 frames) is the ceiling: panels, light strips, yellow beams,
the ring's top light from below at `064346`. The view turns with RX and the room moves a little with LY, but the pitch
is pegged up, and the play loop's 0.4 s up/down taps cancel. Live (29 fps), but not a reading of play, and no frame
shows what the Armory asks for after the look test. **Do not repeat: a look block that pushes up and down in equal
amounts leaves the camera wherever the game's invert switch put it; after an invert question the stick's sense is
unknown open-loop.** Next: a held Nova nav session to read the invert question, re-level the view, and map what the
Armory asks next (walk to the tram?), before a v2.

### Held Nova session: Halo 2's Armory (07:24-07:36 PDT, released)

`hold.sh take nova lane.titleroutes2` after my ToeJam survey ended, `wait-idle` (a bf2stall433 request ran out first),
`FOCUS_OK` before input, `nav.py` session `~/hakux-work/nav/halo-2.returning-20261002T072440/` (47 frames), `nav.py end`,
force-stop, perf/fan back to 0/4, screen off, `hold.sh release` (`who` = free). 12 min on the device, battery 80% on AC.

- A presses skip parts of the Heretic prologue. Left alone it ran well past a minute; the replays' 5 s presses cut it
  to ~30 s.
- The look test is two rounds of "Use [RIGHT] to look up" (top light), then "look down" (bottom light). A light goes
  dark when the crosshair crosses it, and overshooting is fine. Single full-throw taps (~0.4 s with nav.py's round
  trip) move the view ~160 px. A 20000 tap barely moves it. Up x2, down x2, up x3, down x3 passed both rounds with the
  look NOT inverted, then "Updating profile... done". Replay 1's 1.5 s holds passed it too, but saved the look inverted.
- After the test the Armory is free-roam under "Follow the Gunnery Sergeant's instructions". The Sergeant walks off
  down a corridor, and both doors I reached show red locks. ~3 min of walking toward him and waiting found no trigger.

**Decision: Halo 2 stays a DRAFT (route header and targets.toml say so), same class as Halo CE.** An open-loop route
ends in the Armory however well the look test goes. Reaching Cairo Station needs screen-aware driving (drive.py,
lane.routedriver2's) or a save made past the Armory. No v2 queued: a level-view Armory replay would still not be a
reading of play.

### ToeJam & Earl III survey (`1790948390-titleroutes2-3358315`, 34 frames, read in full)

**Reached live play.** Title -> ONE PLAYER GAME -> STORY MODE -> character select (ToeJam) -> his intro -> the ship over
Earth -> black (load, FPS 3) -> cycle 4's A (`071306`): ToeJam on the stone circle in level 1, HUD up. Every later START
toggles the PLAYER STATS panel (open, then closed). A is a jump. The play frames (`071511..071601`) walk him off the
circle to the bridge, the fence and the cliff edge at 38-59 fps (target 60). Route `toejam-earl-3` written: 4 START/A
cycles, wait 10, mark, then an exploring walk loop (forward, right + jump, forward, left + jump, a frame per leg, no START).
`route.sh --check` ok, `targets.toml` route + note (DRAFT), `tomllib` 83, selftest all checks passed.

Queued (ref `162ca56fd8`): `toejam-earl-3` replay 1 `1790951866-titleroutes2-46925` (420 s). Tron 2.0 survey
`1790951914-titleroutes2-68595` (300 s; Nova file `Tron 2.0 - Killer App (USA, Europe).iso` per the predecessor's
table; no targets.toml entry yet, one gets added if the survey reaches play). After Tron the Nova-only backlog is empty.
`rank_untouched.py` ranks the Thor's file list (`thor-int.txt`), and the Thor is closed to this lane, so those titles
wait for the Thor or for a copy (one-copy-per-title rule, amended 09-28).

### ToeJam & Earl III, replay 1 (`1790951866-titleroutes2-46925`, 84 frames, read in full): CONFIRMED

Same path as the survey. Play on cycle 4's A (`075718`), the `loaded` frame and the mark (`075730`) are live play. Every
leg's frame to the end is ToeJam moving and jumping (static 0.009). But the right and left legs form a circuit, so he
laps one hill of level 1 (tree, fence, waterfall, a cake): the same five views repeat every ~16 s. Live, but one corner
of the level, the Gunvalkyrie class. `title_verdict.py --targets`: 299.1 s of play, median 51.55, 98.8% at 30+, 29.3% at
its own 60, no hang, worst hitch 515 ms. Below its own target: not nominated. targets.toml and the route header updated.

**The verdict's crash=True is not hakuX.** The four tombstones (07:56:05, 07:58:01, 08:00:41, 08:02:14) are all
`Cmdline: media.extractor`: Android's extractor aborting on a malformed MP4 (`MPEG4Extractor.cpp:1991 CHECK_EQ`).
`title_verdict.py` (lines 420-422) counts any F-level DEBUG/libc line as a crash, whatever the process. My three earlier
Nova logcats today have none; this run has one every ~2 min, so something new on the Nova's storage is being re-scanned.
Filed on `dispatch/board-requests/titleroutes.md` (08:10 PDT): key the crash test on the soaked process, and find the
file. **Do not repeat: read a crash verdict's `Cmdline:` line before calling a run a crash.**

### Tron 2.0: Killer App survey (`1790951914-titleroutes2-68595`, 34 frames, read in full): no play

ESRB card, black, the KILLER APP title -> cycle 1's START: an Xbox Live **Sign In** screen (two slots, "Controller
Disconnected" under each, footer "B Skip Xbox Live sign-in"). From there to the end of the window, A opens "Select account"
(Guest / <New Account>), the next press picks Guest ("Press A to sign in / Y to deselect"), the next gives "At least one
valid account must be chosen / OK", and round again: 14 cycles and the play loop on one screen. START/A cannot leave it,
and the survey never pressed B, the footer's way out. Route `tron-2-killer-app` (`77b3523fd3`): START, one B (a second could
back out of the next menu), 10 START/A cycles with a frame per press to map what follows, mark, an FPS loop (LY forward,
RT fire, A jump, RX turns, frame per leg, no START). No targets.toml entry yet (added once a replay reaches play). Queued
replay 1 `1790953776-titleroutes2-447685` (420 s).

Tron replay 1 (`1790953776-titleroutes2-447685`, 77 frames): **the B came too soon.** 4 s after START the title was still
up (`081413`), so B landed before the Sign In screen and was lost; the rest is the sign-in loop again. Worse: in the
play loop the sticks moved the account cursor to <New Account>, and A raised "This will send you back to the Xbox
Dashboard to create a new account. Yes / No" (`081911`, Yes lit). One A there leaves the game. **Do not repeat: a
press meant for a screen that comes after a transition needs a wait longer than the transition. The sign-in screen
holds until input, so waiting costs nothing.** v2 (`7ebe5300a1`): START, wait 10, B. Queued replay 2
`1790954531-titleroutes2-667637`.
