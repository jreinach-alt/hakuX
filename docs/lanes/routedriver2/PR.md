# routedriver2: the screen-aware driver past its two proof titles (#433)

State: ready

Lane: routedriver2            Issue: #433 (0.5: 50 Playable)
Base: master @ 333711ac66 (merged)
Files: docs/lanes/routedriver2/NOTES.md, docs/lanes/routedriver2/OUTBOX.md, docs/lanes/routedriver2/PR.md, docs/lanes/routedriver2/buffy/b1-path.jpg, docs/lanes/routedriver2/buffy/b1-route-solution.json, docs/lanes/routedriver2/buffy/b1-route-state.tsv, docs/lanes/routedriver2/buffy/b2-route-solution.json, docs/lanes/routedriver2/buffy/b2-route-state.tsv, docs/lanes/routedriver2/buffy/b3-dark-canyon.jpg, docs/lanes/routedriver2/buffy/b3-route-solution.json, docs/lanes/routedriver2/buffy/b3-route-state.tsv, docs/lanes/routedriver2/buffy/b5-route-solution.json, docs/lanes/routedriver2/buffy/b5-route-state.tsv, docs/lanes/routedriver2/buffy/b6-play-then-gap.jpg, docs/lanes/routedriver2/buffy/b6-route-solution.json, docs/lanes/routedriver2/buffy/b6-route-state.tsv, docs/lanes/routedriver2/forza/f1-route-solution.json, docs/lanes/routedriver2/forza/f1-route-state.tsv, docs/lanes/routedriver2/forza/f1-steer-into-pit-wall.jpg, docs/lanes/routedriver2/forza/f1-steer.tsv, docs/lanes/routedriver2/forza/f2-parked-at-grandstand.jpg, docs/lanes/routedriver2/forza/f2-route-solution.json, docs/lanes/routedriver2/forza/f2-route-state.tsv, docs/lanes/routedriver2/forza/f2-steer.tsv, docs/lanes/routedriver2/forza/f3-find-stretch.jpg, docs/lanes/routedriver2/forza/f3-route-solution.json, docs/lanes/routedriver2/forza/f3-route-state.tsv, docs/lanes/routedriver2/sonic/t1-corner-false-play.jpg, docs/lanes/routedriver2/sonic/t1-path.jpg, docs/lanes/routedriver2/sonic/t1-route-solution.json, docs/lanes/routedriver2/sonic/t1-route-state.tsv, docs/lanes/routedriver2/sonic/t2-block-cleared.jpg, docs/lanes/routedriver2/sonic/t2-power-block-stuck.jpg, docs/lanes/routedriver2/sonic/t2-route-solution.json, docs/lanes/routedriver2/sonic/t2-route-state.tsv, docs/lanes/routedriver2/sonic/t3-power-block-cleared.jpg, docs/lanes/routedriver2/sonic/t3-route-solution.json, docs/lanes/routedriver2/sonic/t3-route-state.tsv, docs/lanes/routedriver2/sonic/t4-late.jpg, docs/lanes/routedriver2/sonic/t4-mid.jpg, docs/lanes/routedriver2/sonic/t4-route-solution.json, docs/lanes/routedriver2/sonic/t4-route-state.tsv, docs/testing/titles/classify.py, docs/testing/titles/classify_selftest.py, docs/testing/titles/drive-profiles/buffy.toml, docs/testing/titles/drive-profiles/buffy/difficulty.png, docs/testing/titles/drive-profiles/buffy/hud.png, docs/testing/titles/drive-profiles/buffy/main-menu.png, docs/testing/titles/drive-profiles/buffy/pause.png, docs/testing/titles/drive-profiles/buffy/start-game.png, docs/testing/titles/drive-profiles/buffy/summoning.png, docs/testing/titles/drive-profiles/buffy/title.png, docs/testing/titles/drive-profiles/forza.toml, docs/testing/titles/drive-profiles/selftest/1790931264--021330-gameplay.jpg, docs/testing/titles/drive-profiles/selftest/1790931264--021351-play.jpg, docs/testing/titles/drive-profiles/selftest/1790931264--021411-play.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030345-boot40.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030406-booted.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030413-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030418-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030424-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030430-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030436-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030500-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030531-play.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030552-play.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030633-play.jpg, docs/testing/titles/drive-profiles/selftest/1790932722--030654-play.jpg, docs/testing/titles/drive-profiles/selftest/rdb1--032146-014-black.jpg, docs/testing/titles/drive-profiles/selftest/rdb1--032215-025-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb1--032234-028-cutscene.jpg, docs/testing/titles/drive-profiles/selftest/rdb1--032323-048-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb1--032324-049-black.jpg, docs/testing/titles/drive-profiles/selftest/rdb3--033656-023-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb3--033705-024-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb3--033708-025-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb3--033718-026-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb3--033720-027-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb3--033749-035-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdb3--033751-036-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdf2--035643-083-unknown.jpg, docs/testing/titles/drive-profiles/selftest/rdf2--035645-084-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022614-001-logo.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022615-002-black.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022617-003-intro_video.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022619-004-black.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022620-005-logo.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022622-006-intro_video.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022625-007-title.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022626-008-profile.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022632-012-main_menu.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022649-022-cutscene.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022651-023-loading.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022655-026-unknown.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022658-027-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022700-028-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022702-029-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022704-030-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022707-031-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022710-032-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022712-033-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022714-034-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022717-035-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022719-036-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022721-037-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022723-038-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022725-039-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022727-040-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022758-048-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022906-071-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022912-074-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt1--022914-075-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023809-028-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023812-029-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023814-030-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023817-031-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023819-032-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023822-033-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023825-034-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023828-035-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--023830-036-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024145-088-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024148-089-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024150-090-unknown.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024152-091-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024155-092-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024157-093-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024159-094-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024201-095-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024203-096-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024206-097-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt2--024208-098-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdt4--025907-107-play.jpg, docs/testing/titles/drive-profiles/selftest/rdt4--025910-108-profile.jpg, docs/testing/titles/drive-profiles/selftest/sims.json, docs/testing/titles/drive-profiles/sonic-heroes.toml, docs/testing/titles/drive.py
Prediction: none: no arm. Test harness only (the play driver, its classifier and per-title profiles), not emulator pixels or speed.
Needs device: yes (Nova held --find replays; done)    Needs NDK: no

Release note (none): test harness only -- no emulator code changes.

## What changed

The screen-aware play driver (`drive`, lane.routedriver) now gets past
obstacles, knows more reliably when it is NOT playing, and is safer. All of
it is opt-in per title profile, and each new rule has a passing case and a
counter-case in `classify_selftest.py` (0 failures; the mutants of each new
rule are caught).

**Sonic Heroes past the Seaside Hill block (brief item 1).** The formation
gate before the block sets Fly, and Fly's own move clears it: climb in place
(stick released, 12 A taps), then 1.2 s of forward onto the top (0:12 →
0:17). `[[mode]]` reads the formation from the HUD's leader circle (Speed
blue, Fly yellow, Power red, the same on Nova and Thor frames). Each mode has
its own escapes, and each list ends in a different formation. A stall at a
new place gets a fresh budget. Across 4 Nova trials: the lower block was
cleared every time, the POWER block too (2:03). Trial 4 played 450 s with no
ROUTE FAIL, through a fall into the sea and a Game Over the driver menued
back from. Seaside Hill is not solved end to end.

**False play, fixed.** A team struggling in a corner, or a camera swaying at
the sky, read `play` 40-45% of the time over 100 s stretches. Fixes:
- `progress_bar`: the 32x24 scene against ~10 s earlier. Running 0.46-0.71,
  stuck 0.07-0.29.
- `stall_clear_s`: after a stall, play must hold 10 s before it counts.

A selftest fixture had been passing on exactly this false play; it is
corrected.

**Forza steering (item 2): tried, off.** The suggested line (green chevrons)
is easy to locate. A steering thread follows it, sending LX plus throttle in
one sendevent call, and its table and selftest stay. On the Nova it ran at
~1.1 Hz (screencap bound) and put the car into a wall within 12 s in both
runs, so `[steer] enabled = false`. The next step is a faster screen signal,
not a steering law. Kept: HUD bars so a parked car beside an animated crowd
is `stalled`, not play.

**Buffy (item 3).** A new profile drives title → menus → difficulty → load →
canyon. Live play is frame-checked ~35 s after boot. Dark-scene settings
were needed: `motion_pixel` 8 and `black_luma` 3, measured on a fully kept
run. It stops at a ledge gap ~12 s into play, so `--find` gets 10-12 s of
its 20 and does not pass. The bar was not lowered.

**Item 4 (play_share gate): BLOCKED for dispatched runs.** The dispatcher's
script snapshot carries route.sh but not drive.py, classify.py,
waitfor_match.py or drive-profiles/, so `route.sh --check` on the snapshot
fails "no profile" for every `drive` route. Fix list: NOTES.md item 4
(dispatcher.sh; not this lane's file). The gate's reader checks out on a held
run's full logcat: play_share 0.51 on Forza f3, matching the tsv and the
frames.

**Fixes found on the way:**
- Every axis release sent `mid`, which is a half press on a trigger.
  Triggers now rest at `min`.
- No press goes out unless hakuX is the focused app. After an emulator abort
  in Buffy's intro, an A opened Calendar from the launcher.
- That abort is reported for a tracker row: `pgraph.c:2163 assertion
  "channel_valid"`, pfifo_thread, intermittent (excerpt in buffy/).

Also new: `--set KEY=VALUE` and `keep_all` for trials, and `BTN/ms` long
presses.

Every held run, its tsv, solution json and contact sheets:
`docs/lanes/routedriver2/{sonic,buffy,forza}/`. Full account: NOTES.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
