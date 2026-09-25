# #311: Grabbed by the Ghoulies decays from 29 to 1-2 fps hands-off -- what grows, and since when

Lane: ghoul311            Issue: #311 (game-visible; from #265; ties to #68)
Base: origin/master @ 248f1312c7
Files: docs/lanes/ghoul311/**, docs/testing/predictions/ghoul311-*.json (diagnosis first; no source claimed)
       Coordinate, do not edit: profile.c and perf/** are lane.perfbase's; accel/tcg, target/i386 are lane.tcgchurn's;
       tcg/** is lane.perfarch's. A fix hunk is NAMED on #311 for the board to grant.
Needs device: yes (Thor free; Nova held by lane.gamecheck until 21:22 UTC). Needs NDK: yes (bisect builds).
Prediction: yes, before any arm.

## Goal
Boot the Ghoulies disc, touch no input: 29 gfps in the logos, 13-26 as the title builds, 4-7 by ~50-110 s,
1-2 fps in the attract loop (G ms 34 -> 330-546). Spikeout and RalliSport 2 hold 41-59 on the same apk, and the
0.3.1 review saw no speed complaint on this title at 2x, so this may be a regression. Find WHAT GROWS.

## The job
1. **Reproduce twice** (device runs flake once; see the memory on lone score changes). Soak spec as
   gamecheck's `1790365974-gamecheck-732876`; frames every 2 s.
2. **A simpleperf guest-thread profile at ~20 s and ~120 s**, plus the `hakuX-pages` counters over the run.
   Report the symbol whose self share rises and the counter that climbs. Candidates from the issue: TB/jump
   cache churn (#68), an unpruned surface/texture/shader-key list, or something the title does per frame
   that we make expensive. Name which, from the numbers -- do not pick by plausibility.
3. **Bisect** against v0.3.1 and v0.4.0-j1 only if the growth is not obvious from step 2 (the two releases
   bound the regression; report each on the same 240 s hands-off spec).
4. Check perfbase's and tcgchurn's PRs (#310, #309) for numbers on the same symptom before duplicating a
   measurement; comment your finding on #68 so they can use it.

## Falsifier
The candidate cause must predict the curve: state the counter's value at 20 s and 120 s BEFORE the arm. A cause
whose counter is flat while the fps collapses is refuted. Must-not-move: Spikeout / RalliSport 2 fps.

## Do not
Hold a device for more than 60 minutes or while another request runs there; trigger CI as a self-check;
edit files held by the lanes above.

## Done when
#311 carries the growing quantity and its curve, and either a named fix hunk with a registered prediction or a
bisect range; or NOTES state why the collapse is not reproducible on the current apk.
