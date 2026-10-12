# zetaroutes1012: returning gameplay routes for Buffy, DOA3 and NG Black, then HAKUX_ZETA_D24=1 runs (#433, 0.5)

State: ready

Lane: zetaroutes1012          Issue: none (lane.local dispatched directly; #433 umbrella)
Base: master @ 78cd417e9d (master 4ee94db999 merged in at 89483c898f)
Files: docs/lanes/zetaroutes1012/NOTES.md, docs/lanes/zetaroutes1012/PR.md, docs/lanes/zetaroutes1012/OUTBOX.md,
docs/testing/titles/routes/buffy.returning.route, docs/testing/titles/routes/doa3.returning.route,
docs/testing/titles/routes/ninja-gaiden-black.returning.route, docs/testing/predictions/zetaroutes1012-buffy.json,
docs/testing/predictions/zetaroutes1012-ninja-gaiden-black.json, docs/testing/predictions/zetaroutes1012-doa3.json
Prediction: docs/testing/predictions/zetaroutes1012-buffy.json (judged: LOSS),
docs/testing/predictions/zetaroutes1012-ninja-gaiden-black.json (judged: not a WIN; F and G fail, H passes),
docs/testing/predictions/zetaroutes1012-doa3.json (judged: confounded, the arms fought on different stages)
Needs device: yes (the Nova, sweep tier)    Needs NDK: no

Kept-profile gameplay routes for the three titles `HAKUX_ZETA_D24` lifted on fpsbelow1012's survey route,
and switch-on runs on them, with a switch-off pair where the switch-on run is at the bar. Boot tables are in
NOTES.md sections 1-3. All three routes pass `route.sh --check`, and `titlestate.py resolve-route` admits each
one (Buffy as `returning`; DOA3 and NG Black as `any`, since their kept goldens hold title data only, section 4).

| title | switch-on run | verdict | fps_ok | gameplay | moving | pair |
|---|---|---|---|---|---|---|
| Buffy | `z-1791820250-lane.zetaroutes1012-2510625` | PASS | 1.0 | 774.9 s | travels for 4.6 min, then stays at one ledge | LOSS: the off arm reads 0.9973, both at the 30 cap |
| NG Black | `z-1791823930-lane.zetaroutes1012-3542868` | PASS | 0.9964 | 714.4 s | yes, in the opening riverbed only | not a WIN: the off arm reads PASS, 0.97; share at 57 fps 0.08 -> 0.53, with the arms in different scenes after +45 s |
| DOA3 | `z-1791827119-lane.zetaroutes1012-335115` | FAIL on one 621 ms stall between rounds | 1.0 | 775.2 s | yes, fights against Zack throughout | confounded: the off arm fought Jann Lee on another stage, 0.9353 at 30; it FAILs on the same kind of stall |

- **Buffy** (NOTES.md sections 6, 7, 15 and 19). The first play loop pinned her against a wall. Short forward
  pulses with turns fixed that. The pair shows Buffy at its 30-fps cap without the switch on this route.
  The switch costs nothing: the minimum window is 29.24 fps with it and 28.37 without. The route's timing
  loop stops making progress at the shimmy ledge, and the next path past it needs reading the screen.
- **NG Black** (sections 12, 16, 17 and 20). The genre loop now repeats 15 times so it covers the 600-s
  window. Both arms PASS at the 30 bar: 0.97 without the switch and 0.9964 with it. The switch's effect is
  towards the title's 60 target. Both arms were at the same waterfall for the first 45 s. There the median
  rises from 28.7 to 50.9 fps and the share at the bar from 0.52 to 0.94. After that the arms play different
  areas. The route covers the opening riverbed and gorge only.
- **DOA3** (sections 18 and 21). The first run's combo loop never pressed START, so the CONTINUE countdown
  ran out to the title. The route now presses START/A after every combo, about every 7 s. Each screen this
  relies on is recorded in the survey run: START pauses mid-fight and A closes the pause; START at the
  countdown starts a fresh round. On the fixed route Kasumi fights Zack for the whole 775-s window, with
  fps_ok 1.0 at 30 and a share at 57 of 0.19 (`targets.toml` gives DOA3 a 60 target). The one failure is a
  621 ms stall between a lost round and the next round's intro, with no shader or texture work in that
  window. The switch-off arm (section 22) fought Jann Lee on the waterfall cliff, because the game draws a
  new opponent and stage on each boot. So the pair is confounded and gives no WIN or LOSS. That arm passes
  the 30 bar at master on its own stage (0.9353, 60-s medians down to 30.5). It FAILs on a 623 ms stall at
  the same kind of round change, so the stall happens with or without the switch.

Across the three titles, every switch-off arm on these gameplay routes passes the 30 bar: Buffy 0.9973,
NG Black 0.97, DOA3 0.9353 (on another stage). The switch's measured gain is towards each title's own
target, not across the bar. The cross-title screen and the default-on decision are lane.local's.

Run count: 10 of the 12-run budget. Nothing is queued.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
