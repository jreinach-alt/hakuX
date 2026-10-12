# zetaroutes1012 OUTBOX

(filled in per title once each route's device run is read; see brief step 7)

## Dead or Alive 3 (4D53002D / disk 54430001) -- final

Route: `doa3.returning.route` (any). Switch-on run: `z-1791820275-lane.zetaroutes1012-2514338`,
`fps_ok=0.9773` over `gameplay=781.2s`, `static_frac=0.0` -- the fight combo loop kept both fighters moving
for the whole window, no parked or menu-bound stretch. FAIL verdict is a single 632ms hitch 60s after the
mark: `logcat.txt`'s `[shd413]` line at the stall reads `pc_ms=559.6` for one newly created pipeline -- a
first-use shader/pipeline compile on this route's combo-press pattern, not seen on the survey route's bare-A
loop because that loop never pressed the combo. Not a `HAKUX_ZETA_D24` effect (no depth/stencil fields in the
stall's own perf line) and not a route defect (the route reached its gameplay target cleanly). No off-run
pair: the switch-on run did not reach the confirmation bar, so step 6's pair does not apply. Flag for a
Playable review: the single hitch, named above, is the only thing in this run a reviewer would need to weigh;
nothing else in the frames (no stale/torn/wrong surfaces noted).

## Buffy the Vampire Slayer (45410012) -- pending the off-run

Route: `buffy.returning.route` (returning), play loop fixed to short forward pulses + turns (section 7).
Switch-on run: `z-1791820250-lane.zetaroutes1012-2510625`, PASS, `fps_ok=1.0` over `gameplay=774.9s`,
`static_frac=0.0394` -- moving (fighting/running) the whole window, no parked stretch. Pair registered
(`docs/testing/predictions/zetaroutes1012-buffy.json`); switch-off run queued
(`z-1791823924-lane.zetaroutes1012-3538464`). Entry completed once that run lands.

## Ninja Gaiden Black (5443000D) -- pending the re-run

Route: `ninja-gaiden-black.returning.route` (any), outer loop repeat raised 11 -> 15 (section 12). First
switch-on run (`z-1791820279-lane.zetaroutes1012-2514939`) read `fps_ok=0.9956`, `static_frac=0.0216` (moving
the whole window) but FAILed on duration alone (589.7s against the 600s bar) -- a route-timing shortfall, not
a movement or switch defect. Fixed route + `--seconds 1020` queued
(`z-1791823930-lane.zetaroutes1012-3542868`). Entry completed once that run lands.
