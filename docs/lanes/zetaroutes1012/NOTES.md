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
Screens read from `route-frames/`, presses from `run.log` ROUTE lines.

| t (host) | press (from) | shot | screen | recorded? |
|---|---|---|---|---|
| 04:49:37.173 (+60s) | (none, boot wait) | `044937-booted.png` | Title card, "PRESS START BUTTON" | recorded |
| 04:49:37.528 (cycle1 START) | press START (title) | `044942-menu-start.png` | still title-ish (dark castle wall, different attract frame) | recorded |
| cycles 2-6 (04:49:43-04:50:01) | press A / START (attract/menu) | not individually read | not read | unrecorded |
| 04:50:01.268 (cycle7 START, ~04:50:08) | press START | `045007-menu-start.png` | STORY MODE, CHARACTER SELECT, Kasumi highlighted (PLAYER-1 / COS.1) | recorded |
| cycles 8-10 (04:50:08-04:51:02) | press A / START | not individually read | not read | unrecorded |
| 04:51:02.765 (cycle11 START, ~04:51:08) | press START | `045108-menu-start.png` | Live fight already resolved: Kasumi down, Hitomi standing, **PAUSED / PLAYER-1 / CONTINUE** menu up | recorded |
| cycles 12-13 | press A / START | `045159-menu-start.png` (cycle ~13) | same PAUSED/CONTINUE menu, Kasumi down (one frame shows a fresh round mid-fight, both standing, full-ish bars, at 04:52:06-ish) | recorded |
| 04:52:18.352 (cycle14 START) | press START | `045217-menu-a.png` | fresh round: Kasumi and Hitomi both standing, Kasumi's bar ~55%, no pause overlay | recorded |
| 04:52:31.591 | mark play (survey's own, not `mark gameplay`) | `045231-play.png` | **PAUSED / PLAYER-1 / CONTINUE**, Kasumi down again, taken ~1s after mark | recorded |
| 04:56:35.922 (last play shot) | generic play loop (press A only, 3s cadence) | `045635-play.png` | `CONTINUE? 8 ... Hayate...` KO/continue countdown | recorded |

The menu path through cycle 7 (title -> attract/menu cycling -> STORY MODE character select, Kasumi) matches
`doa3.route`'s own comment exactly: "START twice from t~75 ... then A to walk STORY -> character select ->
costume -> fight intro," and its header's claim that DOA3 has no profile gate on this path (confirmed: the
kept-profile disk shows the identical character-select screen, no load/continue prompt, no save name). So the
boot and menu cadence below is `doa3.route`'s own, unchanged.

Between cycle 7 (character select, 04:50:08) and cycle 11 (04:51:08) -- four more blind START/A pairs, ~60s --
the survey's blind A-presses (which `doa3.route`'s own comment says read as attacks once in a fight: "Extra A
presses in the fight are attacks, so over-pressing is safe") carried the run all the way through costume select,
fight intro, and a full round, ending with Kasumi KO'd and the post-KO **PAUSED/PLAYER-1/CONTINUE** menu already
on screen by cycle 11's shot. That menu's "CONTINUE" entry is what the survey's bare `press A` (in both the
cycle loop and the later generic play loop) selects -- it resumes a fresh round, but a single blind A-press has
no attack timing or guard behind it, so the next round is lost just as fast: cycle 14's shot (`045217-menu-a.png`)
catches one fresh round standing, but by the first play-loop shot one second into `mark play` (`045231-play.png`)
Kasumi is down and paused again. Every later play shot through the end of the run (`045635-play.png`, the last
one, ~4 minutes later) is the same PAUSED/CONTINUE menu or the `CONTINUE? 8 ... Hayate...` countdown that follows
once continues run out -- the survey's generic play loop (bare `press A` every 3s, no directional input) never
produces one second of moving fight play after the mark.

`doa3.route`'s own play loop is built for exactly this failure mode: it is not bare A-presses but a timed combo
(`axis LX max/mid`, `press X`, `press Y`, `press X`, `press B`, `press A`) whose trailing `press A` is commented
"also leaves a KO / continue screen" -- i.e. it was written already expecting a KO/continue cycle and clearing it
as part of the loop, rather than parking on it. So the returning route below reuses `doa3.route`'s menu cadence
(steps 1-7, screen-identical on this kept-profile disk per the table above) and its combo play loop verbatim,
never the survey's bare-A generic loop.

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
