# savestate433: every title run starts from a golden profile, and a route's state is checked before device time

State: draft

Lane: savestate433            Issue: #433
Base: master @ 9550493846 (+ lane/buildstamp 568ec87e95, merged: fold buildstamp first)
Files: docs/lanes/savestate433/NOTES.md, docs/lanes/savestate433/PR.md, docs/lanes/savestate433/OUTBOX.md, docs/lanes/savestate433/add_state_headers.py, docs/lanes/savestate433/seed_goldens.py, docs/lanes/savestate433/inflight.py, docs/lanes/savestate433/route_audit.py, docs/lanes/savestate433/route_audit.out, docs/lanes/savestate433/tron-menu.route, docs/lanes/savestate433/proof_tron.sh, docs/lanes/savestate433/proof-tron-returning-menu.png, docs/lanes/savestate433/proof-tron-first-run-menu.png, docs/lanes/savestate433/proof/*/hdd.json, docs/lanes/savestate433/proof/*/release.json, docs/testing/titles/titlestate.py, docs/testing/titles/titlestate_selftest.py, docs/testing/titles/nav.py, docs/testing/titles/pathfind.py, docs/testing/request.sh, docs/testing/dispatcher.sh, docs/testing/soak_title.sh, docs/testing/jobs/selftest.d/85-savestate.sh, docs/testing/jobs/selftest.d/99-hdd-split.sh, docs/testing/jobs/selftest.d/89-title-verdict.sh, docs/testing/titles/routes/*.route (the `# state:` line only, 65 files)
Prediction: none: harness only, no emulator code
Needs device: yes (2 held Nova boots, Tron 2.0 returning vs first-run)    Needs NDK: no

## Summary

Owner, 10-02: "The dispatcher needs to either check whether there's a profile
and load it, or, preferably, load the archived profile to the disk."

- **One golden profile per title** (`titlestate.py`, `golden.json`). A title
  run's disk is composed from the goldens: every title's, minus the run's own
  title on a `first-run`. Harvests go to `latest`, and only `promote` replaces a
  golden. A disk a run wrote to is never booted again: it is harvested, or
  preserved whole if the harvest fails, then rebuilt.
- **A profile is a save directory.** Castlevania's newest harvest held title
  data only, and its returning route took New Game (10-01). A returning route on
  a settings-only golden is refused.
- **Routes declare `# state:`** (65 files). `request.sh --route` resolves a
  first-run/returning family by the golden and refuses a mismatch at queue time.
  The dispatcher refuses again at dispatch, before the soak.
- **Held sessions** (nav.py, pathfind.py, `titlestate.py prepare/release`) boot
  the same composed disk. `take-hdd` harvests the owner's hand play for `promote`.
- **The soak stops when its route dies** (CAPA T16: 904 s and 661 s held blind).
- **Seeded live:**
  - Blinx 2's golden is the owner's "Jaguars" save, from the 19:23 hdd-reset backup;
  - 83 other titles have a proposed golden for lane.local to confirm;
  - 3 TitleID aliases (DOA3, JSRF, Gunvalkyrie), where targets.toml's id is not
    the disk's.
- Void ledger (90 results since 09-26): NOTES.md section D.
- **Device proof** (Nova, 2 held boots, 20:25-20:30 PDT): Tron 2.0 with
  `--state returning` loaded its golden, and the Single Player cursor sat on Auto
  Load. With `--state first-run`, Auto Load and Load Game were greyed and the
  cursor was on New Game. Those are the two states of the 18:46 void, now chosen
  by the request. Frames: `proof-tron-*-menu.png`.

Release note (stability): title runs no longer void because a game showed a different menu (New Game vs Continue, name entry) from one run to the next; each starts from that game's archived profile, or from none when its route creates one.

## Local checks (no CI while offline)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed.
- `SELFTEST_ONLY=85-savestate.sh docs/testing/jobs/selftest.sh`: 27 passed,
  0 failed. Against master's code, 18 of 24 legs fail, and the route-died legs
  fail on master's soak.
- `SELFTEST_ONLY=99-hdd-split.sh`: 63 passed.
- `docs/testing/titles/pathfind_selftest.py`: all ok.
- Full `docs/testing/jobs/selftest.sh`: see below.

## Territory

Beyond the brief's list: `soak_title.sh` (18 additive lines, the route-died
stop), `99-hdd-split.sh` (3 legs asserted the void), `89-title-verdict.sh`
(one route name). Requested in OUTBOX.

## Next

NOTES.md "Next": P x win for each candidate.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
