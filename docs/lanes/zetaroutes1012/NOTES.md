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

Attempt 1 ended there, correctly: the Buffy run was queued and the session stopped rather than poll a
device run from inside its own turn. It did not fail -- it reached the WAITING state the lane role asks for.
This is attempt 2, resumed once that run's `DONE` file existed.

## 6. Buffy's first returning run: reached play, failed on a route defect (not the switch)

`z-1791817586-lane.zetaroutes1012-2316443` ran to completion (`DONE` present). `title_verdict.py --require
confirmation --reviewed-gameplay yes`:

```
VERDICT Buffy the Vampire Slayer nova FAIL(static window: 23% of pixels never moved more than 10/255 from
the window's first frame, over 36 sampled frames from route-frames (bar 20%)) gameplay=777.6s fps_ok=1.0
crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.229 timeline: none
battery_w=+0.51 net_w=7.04 j_per_frame=0.2349
```

Everything the switch itself is responsible for passed: `fps_ok=1.0`, `gameplay=777.6s` (over the 600s bar),
no crash, no hang. The FAIL is `static_frac=0.229` against the 0.20 bar -- a movement failure, i.e. exactly
the brief's "parked or menu-bound window is not a confirmation" case, not a `HAKUX_ZETA_D24` finding.

Reading `route-frames/` confirms it directly: `083157-gameplay.png` (the mark) and `083219-play.png` (one
loop iteration later, ~21s after the mark) already show Buffy pressed face-first into a canyon wall/rock
corner. Every later play shot through the run's end (`084448-play.png`, the last one, ~13 minutes later) is
the same framing -- a running-in-place animation (legs/arms cycling, enough per-pixel motion to keep
`static_frac` just under 1.0 but not enough to clear the 0.20 bar) with no translation. `run.log`'s ROUTE
lines confirm the loop ran as written: `axis LY min` at 08:31:58.223 (immediately after mark) holds forward
for the next 7.1s (through `press B`, `press B`, `press A`, `press X`) before the loop's first turn (`axis
LX max` at 08:32:06.862) -- i.e. she is run forward, unsteered, for over 7 seconds straight into whatever is
ahead. That pattern is `buffy.route`'s own play loop, reused verbatim per the brief's step 2 -- but
`buffy.route`'s header says this exact loop was never device-confirmed: it is itself a guess ("Replay ...
sat 4 min on one frame ... the first loop never pressed B. So: run forward and jump (B) twice per cycle, and
turn for longer") written after a DIFFERENT stuck replay, and the file is still headed `DRAFT until a
dispatch run replays it and its frames from the mark on are reviewed`. Reusing an unconfirmed loop verbatim
reproduced the same failure mode (stuck against geometry) in a different spot of the same canyon.

Wrote the pilot verdict (`dispatch/pilots/lane.zetaroutes1012.ok`, naming this run, what it showed, and the
fix below) so the gate would admit the DOA3/NG Black requests already prepared in section 5.

## 7. Route fix: pulse-and-turn instead of a long held run

`spikeout.returning.route` (in the same routes directory, confirmed working: nav.py, Thor, 2026-09-27) plays
its post-mark loop very differently from `buffy.route`'s: `axis LY min; wait 1; axis LY mid` -- a 1-second
forward pulse that returns to neutral -- interleaved with turns in both directions (`axis LX max` / `axis LX
min`) AND a backward pulse (`axis LY max`), never holding one direction long enough to pin the character
against one piece of geometry.

`buffy.returning.route`'s play loop (only; the boot/menu steps above the mark are unchanged, since those
worked -- `fps_ok=1.0`, mark reached on schedule) now uses that same pattern: 1s forward pulses back to
`mid`, a turn or a backward pulse between them, and jump/attack presses (B / A / X) varied every cycle. The
route's header now says what the first run showed and why the loop changed (not the brief's literal `buffy.
route`-verbatim text) -- public text, no process narration. `route.sh --check` passes (86 lines); `titlestate.
py resolve-route --route buffy.returning --title-id 45410012 --device nova` still gives `refuse: null,
state: returning`, unaffected by the play-loop change.

This is run 2 of the "at most 2 more runs" the brief allows for a route defect; 1 more remains if it still
does not reach 600s of moving play.

## 8. Queued: fixed Buffy re-run, DOA3, NG Black

```
z-1791820250-lane.zetaroutes1012-2510625   Buffy (fixed buffy.returning.route), switch on
z-1791820275-lane.zetaroutes1012-2514338   DOA3 (54430001-Dead_or_Alive_3.xiso.iso), doa3.returning, switch on
z-1791820279-lane.zetaroutes1012-2514939   NG Black (Ninja Gaiden Black.iso), ninja-gaiden-black.returning, switch on
```

DOA3 and NG Black's requests both printed `pilot gate: ... reviewed pilot .../lane.zetaroutes1012.ok (0.0 h
old) admits it` -- the gate is working as designed, not held this time. Run count so far: 1 (read) + 3
(queued) = 4 of the 12-run budget.

WAITING: on all three result dirs' `DONE` files, same reason as before (overnight Playable-chain hold on the
Nova; sweep tier starts only when it is idle). Nothing further to do until they land.

## 9. Why attempt 2 did not finish (resuming as attempt 3)

Attempt 2 picked up at the WAITING state section 8 left: three runs queued (fixed Buffy, DOA3, NG Black),
nothing left for that turn to do but wait on the Nova's overnight Playable-chain hold to clear. It ended the
turn there rather than poll a device run from inside its own turn, per the lane role's "never end a session
waiting on your own background task" -- that is a correct, finished state, not a failure. All three `DONE`
files exist now; this attempt reads them.

## 10. Reading the three queued runs

```
python3 docs/testing/title_verdict.py <dir> --require confirmation --reviewed-gameplay yes
```

| title | run | verdict |
|---|---|---|
| Buffy | `z-1791820250-lane.zetaroutes1012-2510625` | **PASS** Playable, `gameplay=774.9s fps_ok=1.0 static_frac=0.0394` |
| DOA3 | `z-1791820275-lane.zetaroutes1012-2514338` | FAIL(hitches: a 632ms stall after the first 60s, bar 500ms), `gameplay=781.2s fps_ok=0.9773 static_frac=0.0` |
| NG Black | `z-1791820279-lane.zetaroutes1012-2514939` | FAIL(duration: 590s of gameplay < 600s confirmation), `gameplay=589.7s fps_ok=0.9956 static_frac=0.0216` |

The fixed pulse-and-turn play loop (section 7) worked: Buffy is a clean confirmation, and the other two
titles' failures are not movement failures (both read static_frac well under the 0.20 bar) -- they are a
real stall and a timing shortfall respectively. (DOA3's reading is wrong: its frames show attract mode
from +55 s, section 18.)

## 11. DOA3's hitch is a shader pipeline-create stall, not a route defect

**WRONG, superseded by section 18:** the frames show the fight lost at +30 s and attract mode from +55 s to
the end. This was a route defect, and the hitch is at the change to attract mode.

`result.json`'s own fields read fine (`fps_ok=0.9773`, no crash/hang, `static_frac=0.0`), and the FAIL is
entirely the 632ms hitch. Reading `logcat.txt` around the stall (mark at 09:11:42.610; the hitch bar is "after
the first 60s", i.e. ~09:12:42): the `[shd413]` perf line at 09:12:40.546 reads `pc_ms=559.6` (pipeline-create
milliseconds for that frame) with `dpc_ms=0.0 dpn=1` -- one new pipeline created, taking over half a second,
exactly the shape of the hitch (632ms worst_ms). This is a first-use shader/pipeline compile on this route's
particular combat move (DOA3's combo loop presses X/Y/X/B/A in a pattern the survey's generic bare-A loop
never produced), not a `HAKUX_ZETA_D24` effect and not a route construction defect: the route reached 781.2s
of moving fight play with `fps_ok=0.9773`, well inside the bar, and the brief's step 5 "whatever its fps"
clause is about the route having done its job once it reaches 600s of moving play, which it did.

No re-run: a route fix cannot remove a first-use pipeline-create stall (that is the ubershader-class problem
`docs/lanes/shaderplan569/NOTES.md` describes), and re-running the same route+golden pair would very likely
just hit the same first-use compile again since nothing clears the shader cache between runs on this disk.
This is reported as a finding for the cross-title screen (OUTBOX.md), not chased further -- the switch and
the route are each doing their job; the stall is a different, known class of problem.

## 12. NG Black: a route-timing shortfall, fixed by extending the loop

`title_verdict.py`'s `gameplay_s` is `end_t - mark_t` (session end minus the mark), not time spent inside the
route script's own loop. This run's own `run.log` ROUTE lines show why 589.7s fell short of 600s: mark at
09:32:31.005, the route's 11-repeat genre loop (each outer repeat ~43-44s by the `shot hold` timestamps) ran
to its own `done`/`end` at 09:40:31.831 (~480.8s of scripted movement), then the run held without further
input for the rest of the 900s request. The ~314.5s the boot/menu/cutscene cadence (section 3, screen- and
text-identical to `bb-ngb.route`, all recorded) takes before the mark left only ~590s before the 900s request
ran out -- 10s short of the bar, not a movement failure (`static_frac=0.0216`, `fps_ok=0.9956`).

Fix: raised the loop's outer `repeat` from 11 to 15 (~650s of scripted movement, so the loop itself covers the
whole required window instead of leaning on an idle post-script hold) and the request's `--seconds` from 900
to 1020 to match. `route.sh --check` passes (205 lines); `titlestate.py resolve-route` still gives
`refuse: null, state: any`. Edited in both the worktree (`docs/testing/titles/routes/
ninja-gaiden-black.returning.route`, committed) and the live `/home/justin/hakuX` checkout `request.sh` reads
from, kept in sync. This is run 1 of the "at most 2 more runs" the brief allows for NG Black's route defect.

## 13. Buffy's pair registered and queued; NG Black's fix queued

Buffy's switch-on run is at the bar (section 10), so its pair is registered before the off run, per step 6.
`ab_compare.py --register` refuses this shape outright (`REFUSED: a registration with nothing falsifiable in
it is not a prediction` -- it requires a `--must-not-move`/`--expect-value`/`--expect-count`, all of which are
capture-bound checks, and this is a soak with no captures). This matches what fpsbelow1012's NOTES.md section
9d already found: `ab_compare.py` has no capture-based oracle for an fps_ok-share leg, and the soak
predictions already on disk (`fpsbelow1012-zetad24.json`, `uberdefault569-soaks.json`,
`async794-mc3-soak.json`) are all hand-written JSON with `expect: {}` and an `expect_note` saying so, not
`ab_compare.py --register` output -- `request.sh`'s own `--expect` check (its soak branch) only requires the
file to exist, be readable JSON, and not bind any `expect` key to a real golden capture, which an empty
`expect: {}` satisfies. `docs/testing/predictions/zetaroutes1012-buffy.json` is written the same way: `a_ref
7cbd788e00` / `b_ref 76a2c15333` (no emulator-code diff between them -- `git diff --stat` over `hw/ target/
accel/ android/ tcg/ ui/ audio/` between the two refs is empty, only this lane's own route/NOTES commits), leg
F (A's `fps_ok_share < 0.90`) and leg G (B's `fps_ok_share` >= A's + 0.10, a conservative half of the survey's
measured 0.79->1.00 gain on the same canyon scene).

Queued:
```
z-1791823924-lane.zetaroutes1012-3538464   Buffy, buffy.returning, --ref 7cbd788e00, no HAKUX_ZETA_D24 (the A leg of the pair, --expect zetaroutes1012-buffy.json)
z-1791823930-lane.zetaroutes1012-3542868   NG Black, ninja-gaiden-black.returning (repeat 15, --seconds 1020), HAKUX_ZETA_D24=1 (re-run of the route-timing fix)
```
Pilot gate admitted both (`.ok` file read 1.0h old at the second request). Run count: 4 read (section 10) + 2
queued = 6 of the 12-run budget. DOA3 needs no further run (section 11).

WAITING: on both result dirs' `DONE` files, same overnight Nova-hold reason as before. Nothing further to do
until they land.

## 14. Why attempt 3 did not finish (resuming as attempt 4)

Attempt 3 ended in the WAITING state section 13 names: two device runs queued on the Nova (Buffy's switch-off
arm, NG Black's re-run), both outside the session, with nothing else open. That is a finished state, the same
as attempts 1 and 2, not a failure. Both `DONE` files exist now (read 2026-10-12 17:31 UTC). This attempt reads
them, judges Buffy's pair, and registers NG Black's.

Before any new registration, `origin/master` (755ac97c96, 119 commits ahead) was merged in (`ede8663c9c`).
`git diff 76a2c15333 origin/master` touches only `docs/`: the emulator code every run in this lane used is
master's.

## 15. Buffy's pair, judged as registered: LOSS

| arm | run | switch (logcat init line) | verdict | fps_ok | min window fps | G median | gameplay | static_frac |
|---|---|---|---|---|---|---|---|---|
| A (off) | `z-1791823924-lane.zetaroutes1012-3538464` | `0x82, depth stored as float` | FAIL (static window) | 0.9973 | 28.37 | 33.4 ms | 782.4 s | 0.354 |
| B (on) | `z-1791820250-lane.zetaroutes1012-2510625` | `0x81, depth stored as unorm` | PASS | 1.0 | 29.24 | 33.4 ms | 774.9 s | 0.039 |

(G median and the init lines from fpsbelow1012's `tools/zread.py <A> <B>`; no `XFR rp` lines, since neither
arm set `HAKUX_GPUXFR`, so the GPU in/out and outer-span columns cannot be read.)

Legs of `zetaroutes1012-buffy.json`:
- **V passes.** Route start to `mark gameplay`: A 127.9 s, B 129.0 s. Both over 600 s of gameplay, no crash or
  hang.
- **F fails.** A's fps_ok is 0.9973, not under 0.90.
- **G fails.** B - A = 0.0027, not >= 0.10.

So the pair is a **LOSS**: on this gameplay route, Buffy runs at its 30-fps cap without the switch. Per
60-s bucket from the mark, A reads 1.00 in every bucket but one (60-120 s: 0.96), median 30 in all of them.

What the pair does NOT show. The two arms left the same opening canyon within ~25 s of the mark and then
played different stretches. B at +26 s (`085625-play.png`) is past the opening, under the tip "Push into low
ledges to climb onto them", and spends the rest of the run at the ledges ("Run and press B to jump between
ledges", then "While on a ledge, move left or right to shimmy"; from about +4.6 min she stays at that one
ledge, section 19). A at +35 s (`095543-play.png`) is still in the
opening stretch under its first tip ("Move the R thumbstick to move the camera around"), and that tip is on
screen until the run's last shot (`100806-play.png`). The camera spends most of A's window pressed into dark
canyon walls. That is why A fails the static-window check. So A never measured the ledge stretch B ran. The
pair cannot say what the switch does there.

Two readings still stand. The opening stretch is at the cap without the switch: A's first 60 s read 1.00
at a median of 30. And the survey's slow buckets (A 90-120 and 210-270 s, G 37-38 ms; fpsbelow1012 section 9c)
did not appear in either arm of this route. The prediction is not re-registered on these arms, and the A arm
is not re-run: a timing-only route has no way to make A follow B's path, so a second A would differ in the same
way.

For lane.local's cross-title screen: Buffy is Playable with the switch on this route (B, PASS), and at master
without it this route reads fps_ok 0.997 with no hitches. The A arm's FAIL is its route (static window), not
its frame rate. So Buffy is not evidence that the switch is needed. It is evidence that the switch costs Buffy
nothing on gameplay: no hitch, and the minimum window rises from 28.37 to 29.24.

## 16. NG Black's re-run: PASS

`z-1791823930-lane.zetaroutes1012-3542868` (repeat 15, `--seconds 1020`, switch on; init line `0x81, depth
stored as unorm (HAKUX_ZETA_D24)` at 10:08:54):

```
VERDICT Ninja Gaiden Black nova PASS Playable gameplay=714.4s fps_ok=0.9964 crash=False hang=False
audio_short=6.1e-05 hitches=2/0.183pm worst_ms=273.6 static_frac=0.0292 timeline: none below_own_target
```

Its own target is 60 (`targets.toml`): `own_target_share` 0.5307, window median 58.0, min 23.35. Per 60-s
bucket from the mark, the share at the 30 bar is 0.96 in the first minute and 1.00 after it. The share at 57
fps is 0.00-0.02 for the first 180 s (median 51-52), then 0.30-0.96 (median 57-60). All five hitches are
classified `shader`, the worst 273.6 ms at +2.9 s, under the 500 ms bar.

Section 12's fix is confirmed: with 15 repeats the loop covers the window, and the duration shortfall is
gone. Hitches: the first run had 19 (15 `unexplained`), 13 of them after warm-up (1.47/min). This run has
5, all `shader`, and 2 after warm-up (0.18/min). That is one run each, so it is reported, not judged.

## 17. NG Black's pair registered

The switch-on run is at the bar, so step 6 applies. Before registering, the survey's switch-off arm
(`z-1791797927-fpsbelow1012-1778929`) was read from its `mark play` on, with Ryu in the same gorge and cliff
walls the survey's B shows. Over that window the share at the 30 bar is 0.847 and at 57 fps it is 0.146
(B: 0.960 and 0.542). At the bar, A's 30-s buckets read 0.45-0.85 at 270, 390, 450 and 480 s from the first
perf line, where B's read 0.91-1.00. The 240-s bucket dips in both arms (0.70 / 0.73).
Frame `032917-play.png` (A, overlay 38 fps) shows Ryu facing the gorge; `033100-play.png` (A, overlay 59) shows
a wall filling the frame.

`docs/testing/predictions/zetaroutes1012-ninja-gaiden-black.json`, hand-written like `zetaroutes1012-buffy.json`
(section 13 says why `ab_compare.py --register` refuses a soak). Both refs are `76a2c15333`, the build B ran.
The legs:
- V: validity as Buffy's, plus both init lines and A moving (static_frac <= 0.20).
- F: A's fps_ok < 0.90, the brief's share at the Playable bar.
- G: B - A >= 0.05 at the bar.
- H: B - A >= 0.20 in the share at the 60 target.

WIN is V, F and G. H is reported on its own. P(F) is about 0.5, given Buffy (section 15), and the file says
so. P(H) is about 0.85.

## 18. Correction: DOA3's first run did not play for 781 s (section 11 is wrong)

Section 11 read DOA3's run from `result.json` and `logcat.txt` alone. Its frames say otherwise.
`z-1791820275-lane.zetaroutes1012-2514338`, mark at 09:11:42.610:

| shot | screen |
|---|---|
| `091147-play.png` (+5 s) | Kasumi down, "COUNTER BLOW" |
| `091212-play.png` (+30 s) | YOU LOSE |
| `091217-play.png` (+35 s) | "CONTINUE ? 7 / Press start to continue / Hayate..." |
| `091227-play.png` (+45 s) | GAME OVER |
| `091237-play.png` (+55 s) to the end (09:24:28) | title attract mode under "PRESS START BUTTON", stages cycling |

The combo loop (X/Y/X/B/A) never presses START, so the countdown ran out and the run spent its last ~12.5
minutes on the title. That is a route defect under step 5, not a confirmation. The 632 ms hitch at 09:12:40
(`pc_ms=559.6`) is at the GAME OVER to attract-mode change, not a combo move. `static_frac=0.0` because the
attract mode keeps changing stages: the static-window check compares each window against its first frame,
so it cannot tell attract mode from play. For lane.local: the run's `fps_ok=0.9773` is mostly attract mode.

The fix (run 8, DOA3's second of three) keeps the menu path and the combo and adds `press START; wait 0.8;
press A` after every combo, so a START comes about every 7 s. The recorded screens behind it:
- **START mid-fight pauses.** `045031-menu-start.png` shows PAUSED with CONTINUE highlighted and "SELECT (A)".
  The A after it brings the fight back (`045037-menu-a.png`: no overlay, Hitomi in stance).
- **A at the countdown does nothing.** `045152-menu-a.png` shows "CONTINUE ? 3".
- **START at the countdown continues.** 5 s later, `045159-menu-start.png` shows a fresh round, both bars full,
  with no character select.

The countdown lasts about 10 s (7 at +35 s, GAME OVER by +45 s), so a 7-s START always lands in it. The cost
is a pause overlay for about 1 s of each 7-s cycle. `route.sh --check` passes (91 lines), and
`titlestate.py resolve-route --route doa3.returning --title-id 54430001 --device nova` reads `refuse: null,
state: any`. The live copy in `/home/justin/hakuX` is identical.

What this route cannot do: if a match is ever won through to the story's end, or the countdown is missed,
it falls back to the title. From there the combo's LX/X/Y/B presses in the menus are unrecorded.

## 19. Corrections to the Buffy and NG Black readings

**Buffy (section 15 and OUTBOX).** B's contact sheet does not show "the rest of the run at the ledges" as
travel:
- **Moving at first.** Buffy moves through four tutorial tips: the opening, "Push into low ledges", "Run and
  press B to jump between ledges" and "jump and grab hold of the ledge". That lasts until about 09:00:43
  (+4.6 min).
- **Then stuck at one spot.** From there to the end (09:08:38), she stays at one spot under the "While on a
  ledge, move left or right to shimmy" tip, jumping and swinging the camera in place.

The static-window check passed (0.039) because the camera keeps moving. So B is about 4.6 min of travel and
then about 8 min stuck at one ledge. That is not a moving-player confirmation for a Playable review. The
pair's LOSS stands: it is about frame rate, and both arms are at the cap.

Buffy has one fix run left. **It is not spent on another timed loop.** The owner's profile gate (10-11) bars
repeat blind navigation, and Buffy's `targets.toml` note asks for "a path found by looking at the screen".
The pulse-and-turn loop has already played out what timing alone can do. The next step is a screen-read
path past the shimmy ledge (lane.pathfind's agent, folded at 755ac97c96). That is lane.local's call, not a
third blind run.

**NG Black (sections 12, 16 and OUTBOX).** The 15-repeat run's frames show Ryu in the opening riverbed by the
waterfall from 10:13:56 to 10:23:17. He steps forward and back and swings his sword, and the camera swings,
but he never travels through the level. `f00033` near the end shows "Ryu has not yet found the map to this
area". So the run is 714 s of moving play (static_frac 0.029) in one area. That suits the like-for-like pair,
since both arms play the same stretch. As a Playable confirmation it covers one scene only.

Queued as run 8: `z-1791827119-lane.zetaroutes1012-335115`. Same request as the first DOA3 run (`--ref
76a2c15333`, sweep, 900 s, frames every 30 s, `HAKUX_ZETA_D24=1 HAKUX_FRAMETRACE=1`) on the fixed route. The
pilot gate admitted it (`.ok` 1.9 h old).
