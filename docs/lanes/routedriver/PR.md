# routedriver: a screen-aware play driver, replacing the blind play loop (#433)

State: ready

Lane: routedriver             Issue: #433 (0.5: 50 Playable)
Base: master @ 8e3b1f2ad2 (merged; lane/titleroutes bdea9b8ecd and lane/hitchwatch ea3ffa1876 are both on it)
Files: docs/lanes/routedriver/NOTES.md, docs/lanes/routedriver/PR.md, docs/lanes/routedriver/castlevania/run1-contact.jpg, docs/lanes/routedriver/castlevania/run1-route-solution.json, docs/lanes/routedriver/castlevania/run1-route-state.tsv, docs/lanes/routedriver/castlevania/run2-contact.jpg, docs/lanes/routedriver/castlevania/run2-route-solution.json, docs/lanes/routedriver/castlevania/run2-route-state.tsv, docs/lanes/routedriver/castlevania/run3-route-solution.json, docs/lanes/routedriver/castlevania/run3-route-state.tsv, docs/lanes/routedriver/castlevania/run4-contact.jpg, docs/lanes/routedriver/castlevania/run4-route-solution.json, docs/lanes/routedriver/castlevania/run4-route-state.tsv, docs/lanes/routedriver/castlevania/run5-contact.jpg, docs/lanes/routedriver/castlevania/run5-route-solution.json, docs/lanes/routedriver/castlevania/run5-route-state.tsv, docs/testing/jobs/selftest.d/99-play-share.sh, docs/testing/title_verdict.py, docs/testing/titles/classify.py, docs/testing/titles/classify_selftest.py, docs/testing/titles/drive-profiles/castlevania-cod.toml, docs/testing/titles/drive-profiles/castlevania-cod/hud.png, docs/testing/titles/drive-profiles/castlevania-cod/name-confirm.png, docs/testing/titles/drive-profiles/castlevania-cod/name-entry.png, docs/testing/titles/drive-profiles/castlevania-cod/overwrite.png, docs/testing/titles/drive-profiles/castlevania-cod/save-busy.png, docs/testing/titles/drive-profiles/castlevania-cod/save-create-no.png, docs/testing/titles/drive-profiles/castlevania-cod/save-create-yes.png, docs/testing/titles/drive-profiles/castlevania-cod/save-slots.png, docs/testing/titles/drive-profiles/castlevania-cod/start-nosave.png, docs/testing/titles/drive-profiles/castlevania-cod/status-menu.png, docs/testing/titles/drive-profiles/castlevania-cod/title-continue.png, docs/testing/titles/drive-profiles/castlevania-cod/title.png, docs/testing/titles/drive-profiles/forza.toml, docs/testing/titles/drive-profiles/forza/hud-lap.png, docs/testing/titles/drive-profiles/forza/menu-footer.png, docs/testing/titles/drive-profiles/forza/pause.png, docs/testing/titles/drive-profiles/forza/profile-select.png, docs/testing/titles/drive-profiles/forza/title-logo.png, docs/testing/titles/drive-profiles/selftest/1790830432--222229-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790830432--222505-play.jpg, docs/testing/titles/drive-profiles/selftest/1790830432--222514-play.jpg, docs/testing/titles/drive-profiles/selftest/1790830432--222523-play.jpg, docs/testing/titles/drive-profiles/selftest/1790839390--004157-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790839390--004215-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790839390--004222-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790839398--011417-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790839398--011423-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790839398--011428-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790839398--011452-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790839398--011459-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790839398--011505-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172548-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172554-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172631-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172702-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172712-rolling.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172713-gameplay.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172723-play.jpg, docs/testing/titles/drive-profiles/selftest/1790900520--172733-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902028--174750-boot.jpg, docs/testing/titles/drive-profiles/selftest/1790902028--174810-a1.jpg, docs/testing/titles/drive-profiles/selftest/1790902028--174838-name-a.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180331-boot20.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180421-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180444-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180456-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180538-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180544-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180608-running.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180609-gameplay.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180617-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180626-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180635-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180644-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180653-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180701-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180711-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180719-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180728-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180737-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180746-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180755-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180803-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180813-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180821-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180830-play.jpg, docs/testing/titles/drive-profiles/selftest/1790902215--180839-play.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200233-boot30.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200305-boot60.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200336-boot90.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200356-boot110.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200413-booted.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200413-pretitle.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200422-menu1.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200432-menu2.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200442-menu3.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200449-story.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200456-team.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200505-cutscene-start.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200648-cutscene-end.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200649-gameplay.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200657-play.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200707-play.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200717-play.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200727-play.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200737-play.jpg, docs/testing/titles/drive-profiles/selftest/1790910096--200746-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214158-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214204-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214211-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214308-menu-start.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214313-menu-a.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214437-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214502-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214527-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214553-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214618-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214644-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214710-play.jpg, docs/testing/titles/drive-profiles/selftest/1790914021--214735-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv2--225522-066-fail-profile.jpg, docs/testing/titles/drive-profiles/selftest/rdcv3--225649-020-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv3--225651-021-stalled.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230011-001-unknown.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230013-002-intro_video.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230014-003-logo.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230016-004-black.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230018-005-title.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230022-007-profile.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230034-014-cutscene.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230035-015-loading.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230037-016-profile.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230046-020-loading.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230052-024-cutscene.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230054-025-black.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230056-027-cutscene.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230058-028-black.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230100-029-cutscene.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230103-031-unknown.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230106-032-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230108-033-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230109-034-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230113-035-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230115-036-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230117-037-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230119-038-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230121-039-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230123-040-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230125-041-play.jpg, docs/testing/titles/drive-profiles/selftest/rdcv5--230127-042-play.jpg, docs/testing/titles/drive-profiles/selftest/sims.json, docs/testing/titles/drive-profiles/sonic-heroes.toml, docs/testing/titles/drive-profiles/sonic-heroes/hud.png, docs/testing/titles/drive-profiles/sonic-heroes/loading-stage.png, docs/testing/titles/drive-profiles/sonic-heroes/logo-dolby.png, docs/testing/titles/drive-profiles/sonic-heroes/logo-sonicteam.png, docs/testing/titles/drive-profiles/sonic-heroes/menu-banner.png, docs/testing/titles/drive-profiles/sonic-heroes/pause.png, docs/testing/titles/drive-profiles/sonic-heroes/profile-created.png, docs/testing/titles/drive-profiles/sonic-heroes/profile-nodata.png, docs/testing/titles/drive-profiles/sonic-heroes/profile-slots.png, docs/testing/titles/drive-profiles/sonic-heroes/title-art.png, docs/testing/titles/drive-profiles/sonic-heroes/title-logo.png, docs/testing/titles/drive-profiles/super-monkey-ball-deluxe.toml, docs/testing/titles/drive-profiles/super-monkey-ball-deluxe/hud.png, docs/testing/titles/drive-profiles/super-monkey-ball-deluxe/menu-banner.png, docs/testing/titles/drive-profiles/super-monkey-ball-deluxe/name-entry.png, docs/testing/titles/drive-profiles/super-monkey-ball-deluxe/pause.png, docs/testing/titles/drive-profiles/super-monkey-ball-deluxe/stage-select.png, docs/testing/titles/drive-profiles/super-monkey-ball-deluxe/title-deluxe.png, docs/testing/titles/drive.py, docs/testing/titles/route.sh, docs/testing/titles/routes/castlevania-cod.drive.route
Prediction: none: no arm. This changes the test harness (route grammar, a host-side driver, the verdict), not emulator pixels or speed.
Needs device: yes (Nova, held replays; done)    Needs NDK: no

Release note (none): test harness only -- no emulator code changes.

## What it is

`drive <profile> <seconds> [find|mark]`, a new route.sh step. drive.py loops:
screencap, name the screen (classify.py, no model needed), send the input
the title's profile (`drive-profiles/<t>.toml`) maps that state to, log the
state. The states are a path: boot, logo, intro_video, title, main_menu,
profile, loading, cutscene, ingame_menu, play, plus paused, stalled, black and
unknown. Logos, intros and cutscenes are skipped with a ladder (A, START, B, X,
START+A, or the profile's own), and the button that worked is recorded and
tried first next time. `play` needs the title's HUD crop and motion between
captures, so a HUD and a ticking clock alone never count as play (Forza at
0 MPH reads `stalled` and ends in ROUTE FAIL). START is never sent in play.
Each state change goes to logcat (`hakuX-route: state=<s> t=<n>`), each
capture to `route-state.tsv`, and the path to play to `route-solution.json`.
With `find`, the run ends after 20 s of confirmed play. The Haiku 4.5
fallback (capped, cached, costed) only runs when ANTHROPIC_API_KEY is set,
and is never needed by default.

`title_verdict.py` now reports `timeline.play_share`. A confirmation under 90%
play fails as "menu time", and fps is judged over `play` seconds only, with
the excluded seconds reported. Old blind routes read `timeline: none` and are
judged exactly as before.

## Castlevania: Curse of Darkness first run (owner ADDENDUM 3): reached play

The replays were held on the Nova (22:47-23:02 PDT, 5 replays, each ended by
the driver itself) using the lane's own route.sh/drive.py via
`scratch/replay.sh`. The dispatcher's snapshot refuses `drive` until this
folds: `route.sh --check` on the snapshot gives `unknown step 'drive'`.

| run | result | lesson -> fix |
|---|---|---|
| 1 | ROUTE FAIL stuck | Disk has a save, so the title opens on Continue. HUD up but nothing held, then the HUD hides when idle and reads as a menu. Fixes: hold play input as a probe when the HUD is up; a still frame right after a HUD frame is `stalled`; title-continue crop |
| 2 | ROUTE FAIL stuck | Name Entry answered first time. "Overwrite this save data?" defaults to No. Fix: overwrite crop -> LX:min, A; title crops re-cut over the menu |
| 3 | ROUTE FAIL stalled | Walked into the fountain (the stall watch was right). START in the ladder picked Continue on the title fade and opened the status screen. Fix: play_cycle, ladder A/X |
| 4 | reached-play (49 s) | Returning path: X on the title fade took Continue. Fix: 3 s skip settle |
| 5 | **reached-play (74 s)** | **First-run path: title 6.6 s, play 53.6 s** |

**Inputs that reach play (run 5, replayed unattended by the committed profile):**
intro A -> title: LY:min onto New Game, A -> Name Entry: A, START (to
Accept), A -> "Is this correct?" A -> SAVE list A (slot 1) -> "Overwrite?"
LX:min, A -> Saving -> three cutscene skips, A each -> play (walk-a-square
play_cycle, A every 5 s).

**Skips:** `intro_video via A at +0.0 s -> logo`;
`cutscene via A at +0.0 s -> black` (3 of 4 visits). The Konami logo ended on
its own in 1.2 s. Nothing was unskippable.

**Old route vs this:** the fixed-wait first-run route pressed at 24.3 s and
marked gameplay at 192.5 s of waits, and never reached it unattended. This
driver reached the title at 6.6 s and play at 53.6 s.

**Classifier, run 5:** all 42 captures were named by the cheap classifier,
with 0 model calls (no API key on this host). 18 were named by crops, 12 by
the HUD crop plus motion, 6 by motion alone, 4 black, 1 static, 1 no-prev.
Wrong: "Save completed." was named `cutscene` (a harmless A). Two anomaly
entries are false (boot load screen named intro_video; the SAVE transition
named cutscene). The no-save-on-disk crops (save-create, start-nosave) are
from the authoring session and have not run on a device.

**Frame review (owner's rule).** I looked at all 11 frames of run 5's 20 s
play stretch, and at the path before it:
`/home/justin/hakux-work/wt/routedriver/scratch/run-cv5/route-frames/230106-032-play.png`
through `230127-042-play.png` (committed at 640x480 as
`docs/testing/titles/drive-profiles/selftest/rdcv5--*.jpg`; sheet:
`docs/lanes/routedriver/castlevania/run5-contact.jpg`). Every frame has the
HUD up (Player, HP 100/100). The character is in a different place from
frame to frame, sword swings follow the A taps, and the camera pans. No menu,
no pause overlay, nothing frozen. **Not a Playable claim: no confirmation was
queued.**

## Capture cost (brief item 4)

On the Nova, Crimson Skies, 195 s per arm: no capture vs 1 Hz vs 0.2 Hz
showed no fps cost (median 30.00 in all three; the no-capture run had the
worst stalls). That is the limit of this instrument on a 30-fps-paced title
with headroom. The driver captures every 1 s outside stable play and every
5 s in confirmed play in a scored (`mark`) run. No cheaper in-process signal
exists: hakuX-pace/perf and [shd413] do not name the screen. See NOTES.md.

## Not done (next session)

- Sonic Heroes (on-foot proof #2) and Burnout/Forza (the driving proof) have
  never driven the device. That follows the brief's one-title-per-session
  rule, with Castlevania first per ADDENDUM 3. Their profiles pass the
  selftest.
- The Castlevania no-save path (save-create prompt) needs one `--find` on a
  disk without a Castlevania save.

## Checks

- `python3 docs/testing/titles/classify_selftest.py`, and the same with `--disk`:
  0 failures (45 named cases with counter-cases, the never-`play`-under-another-profile
  checks, and 4 drive.py --sim runs including Castlevania boot-to-play).
- `SELFTEST_ONLY="66-status-titles 67-status-measured 99-status-fullwindow 99-play-share 89-title-verdict" bash docs/testing/jobs/selftest.sh`:
  143 passed, 0 failed.
- `route.sh --check routes/castlevania-cod.drive.route` (lane copy): ok.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
