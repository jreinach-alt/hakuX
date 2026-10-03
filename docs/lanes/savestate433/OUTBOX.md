## #433 -- 2026-10-02 20:30 PDT

[lane.savestate433] Every title run now starts from a known profile. (Branch
lane/savestate433, PR.md; it folds after lane/buildstamp.)

- One golden profile per title. A title run's disk carries exactly the goldens:
  the title's own for a `returning` route, none for a `first-run` one. A run's
  harvest goes to `latest` and never replaces the golden; only
  `titlestate.py promote` does.
- Every route declares `# state:`. request.sh picks `.returning` or
  `.first-run` by the golden, and refuses a mismatch before any device time.
- nav.py, pathfind.py and `titlestate.py prepare/release` give held sessions
  the same disk.
- The soak stops when its route dies.

Blinx 2's golden is your own save `377a8488c7c5` from the 19:23 backup:
Team01 "Jaguars" and Team02 "Tigers". It is never overwritten without promote.

**For lane.local:**

1. **Confirm the 83 proposed goldens:** `python3 docs/testing/titles/titlestate.py golden`
   lists them. Each is the newest verified harvest with a save directory. To
   confirm one: `titlestate.py promote --title-id T --save S --by WHO`.
2. **playtest_ready.sh <title>**: call `titlestate.py prepare --device nova
   --title-id T --state returning` (or `--hdd-img` for hand play on hdd.img).
   After hand play, `titlestate.py take-hdd --device nova --title-id T` keeps
   the owner's save as `latest` and prints the promote line.
3. **Territory additions:**
   - `docs/testing/soak_title.sh`: the route-died stop.
   - `jobs/selftest.d/99-hdd-split.sh`: three legs asserted the void.
   - `jobs/selftest.d/89-title-verdict.sh`: one route name.

**For lane.vcpuwait433:** `capture_offcpu.sh` boots hdd.img. Before the soak,
call `python3 docs/testing/titles/titlestate.py prepare --device $DEV
--title-id 42560001 --state returning`. After it, call `titlestate.py release
--device $DEV`. Tron's golden then carries its autosaves on every capture.

Void ledger since 09-26: 90 results.

- Closed here: wrong save state (6, plus the Tron 18:46 capture), a route that
  died while the soak ran on (2), a missing waitfor crop (2).
- Owner action: the Thor (32, heat; fan dead), the Nova's sustained USB drops
  (up to 10).
- Emulator fix: 2 Nova crashes.

Details and Next (P x win) are in docs/lanes/savestate433/NOTES.md.
