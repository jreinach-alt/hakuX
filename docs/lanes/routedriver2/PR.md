# routedriver2 session 2: Buffy's menus made robust, the ledge gap diagnosed (#433)

State: ready

Lane: routedriver2            Issue: #433 (0.5: 50 Playable)
Base: master @ d949607b2d (merged)
Files: docs/lanes/routedriver2/NOTES.md, docs/lanes/routedriver2/OUTBOX.md, docs/lanes/routedriver2/PR.md, docs/lanes/routedriver2/buffy/b10-route-solution.json, docs/lanes/routedriver2/buffy/b10-route-state.tsv, docs/lanes/routedriver2/buffy/b11-route-solution.json, docs/lanes/routedriver2/buffy/b11-route-state.tsv, docs/lanes/routedriver2/buffy/b11-y-off-ledge.jpg, docs/lanes/routedriver2/buffy/b12-route-solution.json, docs/lanes/routedriver2/buffy/b12-route-state.tsv, docs/lanes/routedriver2/buffy/b12-save-limit.jpg, docs/lanes/routedriver2/buffy/b13-false-play.jpg, docs/lanes/routedriver2/buffy/b13-load-game.jpg, docs/lanes/routedriver2/buffy/b13-route-solution.json, docs/lanes/routedriver2/buffy/b13-route-state.tsv, docs/lanes/routedriver2/buffy/b14-route-solution.json, docs/lanes/routedriver2/buffy/b14-route-state.tsv, docs/lanes/routedriver2/buffy/b15-route-solution.json, docs/lanes/routedriver2/buffy/b15-route-state.tsv, docs/lanes/routedriver2/buffy/b16-route-solution.json, docs/lanes/routedriver2/buffy/b16-route-state.tsv, docs/lanes/routedriver2/buffy/b17-route-solution.json, docs/lanes/routedriver2/buffy/b17-route-state.tsv, docs/lanes/routedriver2/buffy/b18-cursor-path.jpg, docs/lanes/routedriver2/buffy/b18-route-solution.json, docs/lanes/routedriver2/buffy/b18-route-state.tsv, docs/lanes/routedriver2/buffy/b7-route-solution.json, docs/lanes/routedriver2/buffy/b7-route-state.tsv, docs/lanes/routedriver2/buffy/b7-sky-then-pit.jpg, docs/lanes/routedriver2/buffy/b8-route-solution.json, docs/lanes/routedriver2/buffy/b8-route-state.tsv, docs/lanes/routedriver2/buffy/b9-route-solution.json, docs/lanes/routedriver2/buffy/b9-route-state.tsv, docs/testing/titles/classify.py, docs/testing/titles/classify_selftest.py, docs/testing/titles/drive-profiles/buffy.toml, docs/testing/titles/drive-profiles/buffy/save-limit.png, docs/testing/titles/drive-profiles/selftest/rdb12--055714-011-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb12--055717-012-cutscene.jpg, docs/testing/titles/drive-profiles/selftest/rdb13--062918-012-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb13--062920-013-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb13--062921-014-profile.jpg, docs/testing/titles/drive-profiles/selftest/rdb15--063621-012-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb15--063623-013-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb16--063846-012-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb16--063848-013-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb17--064840-018-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdb17--064900-027-main_menu.jpg, docs/testing/titles/drive.py
Prediction: none: no arm. Test harness only (the play driver, its classifier and a title profile), not emulator pixels or speed.
Needs device: yes (Nova held --find replays; done)    Needs NDK: no

Release note (none): test harness only -- no emulator code changes.

## What changed

Session 2 worked Buffy the Vampire Slayer, the strongest Playable candidate in this lane's hands (29.97 fps against a
30 target). Its one known blocker was the "ledge gap" ~12 s into play. Twelve held `--find` runs on the Nova (b7-b18).
Full record: `docs/lanes/routedriver2/NOTES.md` (session 2) and `buffy/`.

**The gap: diagnosed, not solved.**
- The first stall was never at the edge. She was already in a stream bed below the gap, and the stream bed is a
  closed pit: 8 escapes in four directions, filmed every 0.5 s, never left it.
- The "frozen sky" stall is the camera, and LT clears it. Every escape now starts with LT.
- B pressed while running never produced a jump frame. Tried: one press per capture, bursts of 3 and of 8, presses
  held 60 and 150 ms. Standing B is a kick (an attack trail). Y moved her off a ledge once, but Y bursts did not make
  the jump either.
- Next: find out what the jump is (the Options screen's controller map, or a person with a controller). Do not try
  more driver variants.

**Found and fixed: the Nova's disk holds Buffy's 10-save limit.** Each Start Game makes a save, the game keeps 10, and
the disk is kept between runs, dispatched runs included. Start Game now loops on "only allows 10 saved games". Buffy's
profile now takes Load Game, then the save, then the checkpoint, then the canyon. A `save-limit` crop catches the
dialog. Reported in OUTBOX: titleroutes' blind `buffy.route` will hit the same loop.

**New: `[[cursor]]`, a menu's lit row picks the press.** On Buffy's main menu one stick or hat pulse moves the cursor
one row or two (b15-b17), so a fixed `down, A` lands on Options by chance. Reference crops per lit row could not
follow the pulsing glow. The brightest row (99th-percentile grey) is right on all 25 labelled frames, by 89-126 grey
levels. b18 proved it on the device through that very jitter (down moved two, up moved two, then down, then A).

**New: `play_tap` bursts and `BTN/ms` presses** (`[btn, every, n, gap]`, `B/150`).

**What the classifier got wrong, honestly.** b13 ended `reached-play`, but its frames show the camera on the sky with
Buffy out of frame. The swaying camera passed both motion and the 10 s progress check (0.125 against a 0.07 bar). A
Buffy `--find` pass needs the frame review as its gate until that is fixed.

Each new rule has passing and counter-case fixtures in `classify_selftest.py` (0 failures), and its mutants are
caught. `preflight.sh` passed; its coverage gate did not run (gh suspended), so that check is unverified.

Not taken this session: Black Stone (its warrior never walks, which a screen driver cannot fix) and Forza steering
(still waiting on a faster screen signal). No confirmations queued.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
