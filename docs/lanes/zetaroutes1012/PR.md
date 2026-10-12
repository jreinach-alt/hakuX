# zetaroutes1012: returning gameplay routes for Buffy, DOA3 and NG Black, then HAKUX_ZETA_D24=1 runs (#433, 0.5)

State: in-progress

Lane: zetaroutes1012          Issue: none (lane.local dispatched directly; #433 umbrella)
Base: master @ 78cd417e9d (master 755ac97c96 merged in at ede8663c9c)
Files: docs/lanes/zetaroutes1012/NOTES.md, docs/lanes/zetaroutes1012/PR.md, docs/lanes/zetaroutes1012/OUTBOX.md,
docs/testing/titles/routes/buffy.returning.route, docs/testing/titles/routes/doa3.returning.route,
docs/testing/titles/routes/ninja-gaiden-black.returning.route, docs/testing/predictions/zetaroutes1012-buffy.json,
docs/testing/predictions/zetaroutes1012-ninja-gaiden-black.json
Prediction: docs/testing/predictions/zetaroutes1012-buffy.json (judged: LOSS),
docs/testing/predictions/zetaroutes1012-ninja-gaiden-black.json (switch-off arm running)
Needs device: yes (the Nova, sweep tier)    Needs NDK: no

Kept-profile gameplay routes for the three titles `HAKUX_ZETA_D24` lifted on fpsbelow1012's survey route,
and switch-on runs on them, with a switch-off pair where the switch-on run is at the bar. Boot tables are in
NOTES.md sections 1-3. All three routes pass `route.sh --check`, and `titlestate.py resolve-route` admits each
one (Buffy as `returning`; DOA3 and NG Black as `any`, since their kept goldens hold title data only, section 4).

| title | switch-on run | verdict | fps_ok | gameplay | moving | pair |
|---|---|---|---|---|---|---|
| Buffy | `z-1791820250-lane.zetaroutes1012-2510625` | PASS | 1.0 | 774.9 s | travels for 4.6 min, then stays at one ledge | LOSS: the off arm reads 0.9973, both at the 30 cap |
| NG Black | `z-1791823930-lane.zetaroutes1012-3542868` | PASS | 0.9964 | 714.4 s | yes, in the opening riverbed only | registered; off arm `z-1791826706-lane.zetaroutes1012-104008` running |
| DOA3 | `z-1791820275-lane.zetaroutes1012-2514338` | not a gameplay reading | - | - | lost at +30 s, attract mode from +55 s | fixed route queued: `z-1791827119-lane.zetaroutes1012-335115` |

- **Buffy** (NOTES.md sections 6, 7, 15 and 19). The first play loop pinned her against a wall. Short forward
  pulses with turns fixed that. The pair shows Buffy at its 30-fps cap without the switch on this route.
  The switch costs nothing: the minimum window is 29.24 fps with it and 28.37 without. The route's timing
  loop stops making progress at the shimmy ledge, and the next path past it needs reading the screen.
- **NG Black** (sections 12, 16 and 17). The genre loop now repeats 15 times so it covers the 600-s window.
  With the switch, the share of the window at the title's own 60 target is 0.53.
- **DOA3** (section 18). The first run's combo loop never pressed START, so the CONTINUE countdown ran out to
  the title. The route now presses START/A after every combo, about every 7 s. Each screen this relies on is
  recorded in the survey run: START pauses mid-fight and A closes the pause; START at the countdown starts a
  fresh round.

Run count: 8 of the 12-run budget.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
