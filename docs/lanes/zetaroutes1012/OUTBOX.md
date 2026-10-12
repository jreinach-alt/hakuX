# zetaroutes1012 OUTBOX

(filled in per title once each route's device run is read; see brief step 7)

## Dead or Alive 3 (4D53002D / disk 54430001) -- pending the fixed route's run

Route: `doa3.returning.route` (any). First switch-on run: `z-1791820275-lane.zetaroutes1012-2514338`,
verdict FAIL (one 632 ms hitch), `fps_ok=0.9773 gameplay=781.2s static_frac=0.0`. It is **not a gameplay
reading**. Its frames show the first fight lost at +30 s (YOU LOSE), the CONTINUE countdown running out
(GAME OVER at +45 s), and title attract mode from +55 s to the end. The combo loop never pressed START. The
hitch is at the change to attract mode. `static_frac=0.0` because attract mode keeps changing stages, which
the static-window check cannot tell from play. The route now adds START/A after every combo: START pauses
mid-fight and continues at the countdown, and A closes the pause. Each of those screens is recorded in the
survey run. The re-run is queued (NOTES.md section 18).

## Buffy the Vampire Slayer (45410012) -- final

Route: `buffy.returning.route` (returning), play loop of short forward pulses and turns (NOTES.md section 7).
Switch-on run: `z-1791820250-lane.zetaroutes1012-2510625`, **PASS**, `fps_ok=1.0` over `gameplay=774.9s`,
`static_frac=0.0394`, no hitches. **Moving for about 4.6 min, then stuck.** Buffy moves through four tutorial
stretches (opening, low ledges, jumping between ledges, grabbing a ledge). From +4.6 min to the end she
stays at one ledge under the "shimmy" tip, jumping and swinging the camera in place. That is not a full
moving-player confirmation for a Playable review.

Switch-off run: `z-1791823924-lane.zetaroutes1012-3538464`, `fps_ok=0.9973` over `gameplay=782.4s`, no
hitches. It FAILs on the static window (`static_frac=0.354`): that arm stayed in the opening stretch with the
camera pressed into dark walls. The two arms parted about 25 s after the mark.

Pair (`zetaroutes1012-buffy.json`): **LOSS**. V passes, F fails (A 0.9973, not < 0.90), and G fails (gain
0.0027). Both arms sit at the title's 30 cap, with a G median of 33.4 ms in each. So this route gives no
evidence that Buffy needs the switch. The switch-on arm has the higher minimum window (29.24 vs 28.37 fps),
and the switch costs it nothing.

Next for Buffy is a screen-read path past the shimmy ledge, not another timed loop (NOTES.md section 19).
For a Playable review: the switch-on frames show tutorial TIP banners on screen throughout. The sampled
shots show no dropouts, flicker or wrong surfaces.

## Ninja Gaiden Black (5443000D) -- final

Route: `ninja-gaiden-black.returning.route` (any): bb-ngb.route's menu path and genre loop, with the outer
loop raised from 11 to 15 repeats (NOTES.md section 12).

| run | id | verdict | fps_ok | share at 57 | gameplay | static_frac | hitches after warm-up |
|---|---|---|---|---|---|---|---|
| first switch-on | `z-1791820279-lane.zetaroutes1012-2514939` | FAIL (duration only) | 0.9956 | | 589.7 s | 0.0216 | |
| switch-on | `z-1791823930-lane.zetaroutes1012-3542868` | **PASS** | 0.9964 | 0.5307 | 714.4 s | 0.0292 | 2, worst 273.6 ms, both `shader` |
| switch-off | `z-1791826706-lane.zetaroutes1012-104008` | **PASS** | 0.97 | 0.0819 | 715.5 s | 0.0085 | 7, worst 304.7 ms, 4 `unexplained` |

**Moving, but in one area.** Ryu steps, swings and turns, and the camera swings, but he never travels
through the level. With the switch on, he stays by the waterfall in the opening riverbed. Near the end of
that run, `f00033` reads "Ryu has not yet found the map to this area". With the switch off, he walks up the
gorge and stays there.

Pair (`zetaroutes1012-ninja-gaiden-black.json`): **not a WIN.**
- V passes.
- F fails: A reads 0.97, not under 0.90.
- G fails: the gain is 0.0264.
- H passes: the share at 57 rises by 0.4488.

So NG Black is Playable by the 30 bar at master on this route, and the switch's effect is towards the
title's 60 target. **The arms parted after +45 s.** A walked up the gorge and B stayed at the waterfall, so
H mixes the switch with a change of scene. Over the first 45 s both arms were at the waterfall:

| first 45 s | share at the bar | median |
|---|---|---|
| A (switch off) | 0.52 | 28.7 fps |
| B (switch on) | 0.94 | 50.9 fps |

That slice is 21 and 36 windows, not a 600-s reading (NOTES.md section 20).

For a Playable review: either arm's confirmation covers the opening riverbed or the gorge only. At
contact-sheet size, neither arm's shots show dropouts, flicker or wrong surfaces.
