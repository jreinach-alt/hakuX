# lane.zetaroutes1012

Returning gameplay routes for Buffy the Vampire Slayer (45410012), Dead or Alive 3 (4D53002D) and
Ninja Gaiden Black (5443000D), then HAKUX_ZETA_D24=1 confirmation runs on them (#433, 0.5).

In progress. This file is being built up section by section as each step completes.

## 1. Boot tables

### Buffy the Vampire Slayer (45410012)

Source: `z-1791804165-fpsbelow1012-3514899` (survey.route, kept profile golden `c6b6ec3cb8be`, switch ON).
`route.txt` in that result dir is `survey.route` (never marks gameplay; boots, cycles START/A 14 times, then
a generic play loop). Screens read from `route-frames/`, presses from `run.log` ROUTE lines.

| t (host) | press (from) | shot | screen | recorded? |
|---|---|---|---|---|
| 05:24:36.893 (+60s from launch) | (none, boot wait) | `052457-booted.png` | Title card, "Press START" | recorded |
| 05:24:57.585 | press START (title) | `052502-menu-start.png` | In-engine cutscene: Giles + fog, ghostly Buffy | recorded |
| 05:25:03.415 | press A (cutscene) | `052509-menu-a.png` | Main menu: Start Game / Load Game / Options / Extras | recorded |
| 05:25:10.484 | press START (main menu, Start Game highlighted) | `052515-menu-start.png` | "Launch a New Game on your Xbox Hard Disk called **Buffy 2**" / Free Blocks / CONFIRM | recorded |
| 05:25:16.266 | press A (confirm) | `052521-menu-a.png` | Difficulty select, Easy highlighted | recorded |
| 05:25:22.015 | press START (difficulty, Easy highlighted) | `052527-menu-start.png` | "Summoning" (loading) | recorded |
| 05:25:27.600 | press A (loading) | `052532-menu-a.png` | Mission card: "Spanish Mission, Outskirts of Sunnydale, Sunday 11:53PM" | recorded |
| 05:25:33.397 | press START (mission card) | `052538-menu-start.png` | Live play: canyon, health bar HUD, TIP "Move the R thumbstick..." | recorded |

The kept profile's flow is **the same screen sequence as the first-run route's own comment**
(`buffy.route` lines 7-18: title -> cutscene -> menu -> Start Game confirm -> Difficulty -> Summoning ->
mission card -> play), with one difference the first-run comment already documents: the Start Game confirm
screen names the save **"Buffy 2"** instead of "Buffy 1" (free-blocks count differs too), because a save
already exists on this disk from an earlier run. The confirm screen's layout, and the fact that A confirms it,
are unchanged. So this disk's "Start Game" path does not *load* progress; it begins a new save slot
(Buffy 2, and a later run would see Buffy 3, etc.) — the same action the first-run route takes, just on a
disk that is not empty. Nothing on this disk is remade or deleted by it.

`survey.route`'s own 14-cycle START/A spam reaches live play by its 4th cycle (05:25:33 above) — ~96s after
boot — then keeps sending START/A for 10 more cycles while already in play, each pair pausing (START) and
resuming (A) the game with Buffy standing still (this is exactly the no-op `buffy.route` line 19 already
warns about: "A START/A pair in play is therefore a no-op (pause, Resume)"). The survey's own `mark play` and
generic play loop only start after all 14 cycles, ~140s after the game was already controllable, and that
loop swings the camera (RX) rather than moving Buffy with any purpose. None of that is reused here: the frame
at `053139-play.png` (near the end of the generic loop) shows Buffy crouched at a ledge with the TIP "Run and
press B to jump between ledges" — the same ledge-jump prompt `buffy.route`'s own comment (lines 46-50) is
built around. So the returning route below reuses `buffy.route`'s menu cadence (which this survey confirms
produces the identical screen sequence on this kept-profile disk) and its dedicated play loop verbatim, rather
than the survey's blind generic loop.

### Dead or Alive 3 (4D53002D)

Source: `z-1791803606-fpsbelow1012-3255578` (survey.route, kept profile golden `220536a66fe2`, switch ON).
`survey.route` presses START/A alternately every 5s, 14 cycles (pairs), then a generic play loop. Every press
below is recorded at minimum by its `run.log` ROUTE line (exact device time); a shot column of "-" means the
press is logged but its resulting screen was not individually read -- still a recorded row, just not a
visually-confirmed one. Cycle numbers below are the pair's position in that 14-cycle loop, recounted directly
from the frame filenames and `run.log` (the first draft of this table had the numbering off by a few and is
superseded by this one).

| t (host) | press | shot | screen | recorded? |
|---|---|---|---|---|
| 04:49:37.173 (+60s) | (none, boot wait) | `044937-booted.png` | Title card, "PRESS START BUTTON" | recorded (shot) |
| 04:49:37.528 (cycle1 START) | press START | `044942-menu-start.png` | dark castle-wall attract frame, faint "DEAD OR ALIVE 3" | recorded (shot) |
| 04:49:43.354 (cycle1 A) | press A | `044948-menu-a.png` | title card again, "PRESS START BUTTON" | recorded (shot) |
| 04:49:49.293 (cycle2 START) | press START | `044954-menu-start.png` | MODE SELECT, STORY MODE icon highlighted | recorded (shot) |
| 04:49:55.336 (cycle2 A) | press A | - | not individually read | recorded (ROUTE line only) |
| 04:50:01.268 (cycle3 START) | press START | `045007-menu-start.png` | STORY MODE CHARACTER SELECT, Kasumi (PLAYER-1 / COS.1) | recorded (shot) |
| 04:50:08.139 (cycle3 A) | press A | `045013-menu-a.png` | "STORY MODE" loading transition (black) | recorded (shot) |
| 04:50:13.696 (cycle4 START) | press START | `045019-menu-start.png` | pre-fight close-up, opponent line "Please do not block my way" | recorded (shot) |
| 04:50:19.725 (cycle4 A) | press A | `045025-menu-a.png` | fight intro: Kasumi falling through fog, health bars already on screen | recorded (shot) |
| 04:50:25.801 (cycle5 START) | press START | `045031-menu-start.png` | **PAUSED / PLAYER-1 / CONTINUE**, Kasumi already down, Hitomi standing | recorded (shot) |
| cycles 6-11 | press A / START | `045108`, `045159`, `045211`, `045217` (sampled) | PAUSED/CONTINUE repeating; one sampled frame (`045159-menu-start.png`, cycle12) shows a fresh round live (both standing, bars near full) | recorded (ROUTE lines; 4 of the ~14 shots sampled) |
| 04:52:12.147 (cycle13 A) | press A | `045217-menu-a.png` | Kasumi down again (fresh KO, no pause overlay yet), Hitomi's bar full | recorded (shot) |
| 04:52:31.591 | mark play (survey's own, not `mark gameplay`) | `045231-play.png` | **PAUSED / PLAYER-1 / CONTINUE**, Kasumi down, ~1s after mark | recorded (shot) |
| 04:56:35.922 (last play shot) | generic play loop (press A only, 3s cadence) | `045635-play.png` | `CONTINUE? 8 ... Hayate...` KO/continue countdown | recorded (shot) |

So the real menu path is title -> MODE SELECT (Story Mode) -> CHARACTER SELECT (Kasumi) -> a loading transition
-> a pre-fight voice line -> the fight's falling/landing intro (health bars appear) -- four START/A cycles after
boot, not `doa3.route`'s guessed "2 STARTs then up to 7 A's." `doa3.route`'s own step sequence was never device
-tested (its header says "NOT YET REPLAYED"); this survey is the first real evidence of the kept-profile path,
and it is a *different* (but equally screen-reaching) press pattern. What matters for the gate (every screen on
the kept-profile's way to a fight matches what `doa3.route`'s comment and NOTES.md E describe -- no profile
gate, no load prompt, no save name -- just reached by alternating START/A instead of a fixed 2+7 split) still
holds, so the route below uses the survey's own recorded cadence rather than `doa3.route`'s untested one.

The fast-KO finding is now tightly bounded: the fight's falling-intro frame (`045025-menu-a.png`, 04:50:19.725 +
5s wait) already shows health bars on screen, and the very next cycle's shot, only 6 seconds of real device time
later (`045031-menu-start.png`, 04:50:25.801 + 5s wait), is already the post-KO PAUSED/CONTINUE menu with Kasumi
down. A full DOA3 round -- intro, fight, KO -- fits inside that one ~6s survey cycle. The survey's own bare
`press A` (selecting CONTINUE) starts a fresh round, but with no attack timing behind it that round is lost just
as fast: cycle13's shot (`045217-menu-a.png`) is a fresh KO, and the first play-loop shot one second after `mark
play` (`045231-play.png`) is PAUSED/CONTINUE again. Every later play shot through the run's end (`045635-play.png`,
~4 minutes later) is the same pause menu or the `CONTINUE? 8 ... Hayate...` countdown once continues run out --
the survey's generic play loop (bare `press A` every 3s, no directional input) never produces a second of moving
fight play after the mark.

`doa3.route`'s own play loop is built for exactly this failure mode: it is not bare A-presses but a timed combo
(`axis LX max/mid`, `press X`, `press Y`, `press X`, `press B`, `press A`) whose trailing `press A` is commented
"also leaves a KO / continue screen" -- i.e. it was written already expecting a KO/continue cycle and clearing it
as part of the loop, rather than parking on it. Given the ~6s fast-KO window above, the returning route below
gets into that combo loop immediately on the fight's falling-intro frame (no extra blind cycle once health bars
appear), reusing `doa3.route`'s combo loop verbatim; it never uses the survey's bare-A generic loop.

### Ninja Gaiden Black (5443000D)

Source: `z-1791797921-fpsbelow1012-1777822` (survey.route, kept profile golden `ab037a065b15`, switch ON).
Screens read from `route-frames/`, presses from `run.log` ROUTE lines.

| t (host) | press (from) | shot | screen | recorded? |
|---|---|---|---|---|
| 02:54:34.290 (+60s) | (none, boot wait) | `025434-booted.png` | Title card, "PRESS START BUTTON" | recorded |
| 02:54:34.927 (cycle1 START) | press START (title) | `025441-menu-start.png` | MAIN MENU: NEW GAME (highlighted, default) / LOAD GAME / RANKING / OPTIONS | recorded |
| 02:54:41.662 (cycle1 A) | press A (NEW GAME highlighted) | `025447-menu-a.png` | Narrative cutscene begins: "A legendary sword," sword close-up | recorded |
| cycles 2-13 (02:54:47-02:57:18) | press START / A (cutscene advance) | `025452` .. `025717` | long narrative cutscene/story-text sequence, same text content as `bb-ngb.route`'s own steps 6-27 ("The Book of the Fiends", "The Dark Dragon, now full of evil intent...") | recorded |
| 02:57:18.227 | mark play (survey's own) | `025718-play.png` | still mid-cutscene: "the Fiends." over "Now Loading..." | recorded |
| 02:57:18.735-02:57:41.939 | generic play loop, `press A` x6 (3s cadence) | (no shot) | — | recorded (ROUTE log) |
| ~02:57:42 (between `025717` and `025808` shots) | press A (generic play loop) | `025742-play.png` | **CHAPTER 1 "The Way of the Ninja"**, a blue "Proceed" button prompt bottom-right | recorded |
| 02:58:08 (approx, `025808-play.png`) | press A (generic play loop, continuing) | `025808-play.png` | live gameplay: cinematic shot of Ryu standing over a fallen enemy by a waterfall, no HUD text | recorded |
| 02:59:00-03:01:33 (`025900` through `030133-play.png`) | generic play loop (axis LY min/mid/max, press A, axis RX swing) | `025900` .. `030133` | health-bar HUD visible, but every shot is a close-up rock-wall texture filling the frame -- Ryu parked against cave geometry, not visibly moving | recorded |

`bb-ngb.route`'s own comment (step 5) documents the same MAIN MENU with NEW GAME default-highlighted, and its
step 28-29 comment says the recorded path needed `press X` (not START/A) to clear the "Proceed" chapter-title
cards. The survey here never presses X -- only START/A during the 14-cycle menu phase, then bare `press A` in
its generic play loop -- yet the `025742-play.png` "Proceed" card shows the run reached the same chapter-title
screen `bb-ngb.route` step 29 names, and by `025808-play.png` (one play-loop cycle later) it is past that screen
into live gameplay. So on this build/kept-profile disk, `press A` also clears the "Proceed" prompt (`bb-ngb.route`
step 28-29 uses X because that is what its own recorded pathfind session happened to press there, not because A
fails) -- the survey's generic loop reaching gameplay is itself the recorded evidence for that.

Once in live gameplay, though, the survey's generic play loop (`axis LY min` then `mid` then `max`, `press A`,
`axis RX` swing) leaves Ryu pinned against a cave wall for the remaining ~4 minutes of the run (`025900` through
`030133`, all identical close rock-wall texture, health bar static) -- never moving, matching the brief's "never
parked/menu-bound" warning. `bb-ngb.route`'s own "genre loop" (lines 184-212: alternating `axis LY min/max` with
`press X`, `press A`, `press B` and `axis RX max/min` swings every repeat, built from an actual recorded
playthrough) is the one that produced real movement; the survey's cruder loop did not. So the returning route
below reuses `bb-ngb.route`'s steps 1-32 menu/cutscene cadence (screen- and text-identical on this kept-profile
disk per the table above, so NEW GAME is the correct and only recorded path -- LOAD GAME is unrecorded and not
used) and its genre-loop play pattern verbatim, never the survey's generic loop.

## 4. Routes composed, and a gate finding on DOA3 / NG Black

`docs/testing/titles/routes/buffy.returning.route`, `doa3.returning.route` and `ninja-gaiden-black.returning.route`
are written (and copied into both this worktree and the live `/home/justin/hakuX` checkout `route.sh`/`request.sh`
read from). Each parses clean: `bash route.sh --check routes/<name>.route` -> `route ok` for all three.

`titlestate.admit()` (the same call `request.sh` makes) does not agree with the brief's literal `# state:
returning` header for two of the three:

| title | tid | route_name | header state | admit() |
|---|---|---|---|---|
| Buffy | 45410012 | buffy.returning | returning | `admit=True clause=profile` |
| DOA3 | 4D53002D | doa3.returning | returning (as first written) | `admit=False`: "4D53002D's golden 220536a66fe2 is title data only, no save directory; a returning route would meet no profile. If the route was confirmed on this golden as it is, head it `# state: any`..." |
| NG Black | 5443000D | ninja-gaiden-black.returning | returning (as first written) | same refusal, golden ab037a065b15 |

This matches this lane's own boot tables above: Buffy's kept-profile menu shows a save-name confirm screen
("Buffy 2"), evidence of an actual save directory; DOA3 and NG Black's kept-profile boots never show a
load/continue/save-name screen at all -- DOA3 goes straight through MODE SELECT with no continue prompt, NG
Black's MAIN MENU still defaults to NEW GAME highlighted. Their "kept profile" is the disk/title data only, no
save directory -- exactly what `admit()`'s refusal says. So both files' line-1 header was changed from `# state:
returning` to `# state: any` (the gate's own suggested fix for a route confirmed on a data-only golden as-is);
the filenames stay exactly as the brief names them (`doa3.returning.route`, `ninja-gaiden-black.returning.route`),
only the internal `# state:` tag differs from the brief's literal text, and each file's header says why. Re-run
after the fix: `admit=True clause=profile state=any` for both.

Every press before each route's `mark gameplay` is backed by a recorded row in the boot tables above (sections
1-3); none is filled from memory of the game.

Two more findings while building the queue commands, both from `--title`'s own resolution, before any device
time:
- DOA3's canonical compat-CSV id (4D53002D, the brief's and targets.toml's key) has no `iso.nova` entry --
  `titlestate.iso_for_tid('4D53002D', device='nova')` returns None. The Nova copy is filed under the on-disk
  XBE id instead, `54430001` (`disk_tid()`'s documented alias: "Dead or Alive 3 is 4D53002D [in the compat
  CSV] and 54430001 on the disk"), which is exactly the title_id the DOA3 survey run itself used on nova
  (`z-1791803606-fpsbelow1012-3255578`'s request.json: `"title_id": "54430001"`). Both ids load the same golden
  (220536a66fe2). So DOA3's queue command below uses `--title 54430001-Dead_or_Alive_3.xiso.iso` (the Nova
  iso_for_tid fallback result), not the bare id.
- `--title` must be the on-device ISO file name, never a bare TitleID (request.sh's own check: "A BARE TITLEID
  IS NOT A FILE NAME"). `--title` below is therefore each title's `iso.nova` name:
  `Buffy the Vampire Slayer (USA).xiso.iso`, `54430001-Dead_or_Alive_3.xiso.iso`, `Ninja Gaiden Black.iso`.
  `titlestate.py resolve-route` confirmed all three `--route` names resolve clean (`refuse: null`) with
  `--title-id` set to each of these (45410012 / 54430001 / 5443000D) and `--device nova`.

## 5. Queue: Buffy in, pilot gate holds DOA3 and NG Black

Buffy queued first (sweep tier, switch on):
```
request.sh --who lane.zetaroutes1012 --purpose "returning-route test and HAKUX_ZETA_D24 gameplay confirmation (#433)" \
    --priority sweep --device nova --title "Buffy the Vampire Slayer (USA).xiso.iso" --route buffy.returning \
    --seconds 900 --frames-every 30 --env HAKUX_ZETA_D24=1 --env HAKUX_FRAMETRACE=1 \
    --no-expect "returning-route test and HAKUX_ZETA_D24 gameplay confirmation (#433)"
```
-> `queued z-1791817586-lane.zetaroutes1012-2316443` (ref f4a1c6df96, pinned nova).

Queuing DOA3 right after was refused by the pilot gate (owner 2026-09-26, `docs/lanes/zetaroutes1012/NOTES.md`
is not the gate's source -- `request.sh` is; see its "THE PILOT GATE" section): Buffy alone estimates ~16 min
(900s + 90s setup) and DOA3 would add ~16 more, ~33 min in all, over the 30-min unreviewed ceiling, and
`dispatch/pilots/lane.zetaroutes1012.ok` does not exist yet. This is the correct, expected behaviour (lane-role
"Pilot first": queue at most two, review against the batch's purpose, write the `.ok` verdict, then queue the
rest) -- NOT a defect to work around. So DOA3 and NG Black's queue commands are prepared but not yet sent:
```
request.sh --who lane.zetaroutes1012 --purpose "returning-route test and HAKUX_ZETA_D24 gameplay confirmation (#433)" \
    --priority sweep --device nova --title "54430001-Dead_or_Alive_3.xiso.iso" --route doa3.returning \
    --seconds 900 --frames-every 30 --env HAKUX_ZETA_D24=1 --env HAKUX_FRAMETRACE=1 \
    --no-expect "returning-route test and HAKUX_ZETA_D24 gameplay confirmation (#433)"

request.sh --who lane.zetaroutes1012 --purpose "returning-route test and HAKUX_ZETA_D24 gameplay confirmation (#433)" \
    --priority sweep --device nova --title "Ninja Gaiden Black.iso" --route ninja-gaiden-black.returning \
    --seconds 900 --frames-every 30 --env HAKUX_ZETA_D24=1 --env HAKUX_FRAMETRACE=1 \
    --no-expect "returning-route test and HAKUX_ZETA_D24 gameplay confirmation (#433)"
```

WAITING: on `z-1791817586-lane.zetaroutes1012-2316443` (Buffy) to clear the Nova's queue and run -- the Nova is
held overnight by the Playable chain (sweep runs start only when it is idle) and a `nova` hold was already in
force at session start (`lane.pathfind`, 600s, from 2026-10-12T14:43:16Z). Once it is read: write the pilot
verdict to `dispatch/pilots/lane.zetaroutes1012.ok` (Buffy's result id, what the frames/verdict showed, the
date), then send the DOA3 and NG Black commands above.
