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
### Ninja Gaiden Black (5443000D)

(sections 2 and 3 to follow)
