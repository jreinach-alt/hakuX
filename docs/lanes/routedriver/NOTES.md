# routedriver (#433): a route that looks at the screen

## Session 1

Base: merged `lane/titleroutes` (bdea9b8ecd) into this branch first -- the
brief says it is not yet folded, and `drive` reuses its `waitfor_match.py`
region-score comparator and `routes/refs/<route>/` reference-crop
convention rather than inventing a second one. Merge was clean (only
`targets.toml` touched by both sides).

Plan, in the order the brief's expected-impact framing favours (build the
thing that reads the screen DURING play first -- cheap heuristics are not
a reason to defer it -- then measure what it costs, then convert two real
routes and read the frames):

1. `docs/testing/titles/classify.py`: the classifier (liveness diff +
   reference crops + dim-overlay + capped Haiku fallback), importable and
   with its own selftest against real frames already on disk.
2. `route.sh` grammar: `drive <profile> <seconds>`.
3. `drive-profiles/`: per-title policy files.
4. Capture-cost measurement on the Nova (1 Hz / 0.2 Hz / none), before
   shipping a default rate.
5. `title_verdict.py`: `play_share`, "menu time" failure, fps judged over
   play seconds, `timeline: none` label for old blind routes.
6. Convert Burnout Revenge (driving) and Sonic Heroes (on-foot) to `drive`,
   replay each once on the Nova, read the frames across the whole window.

Recording as I go; this file is updated, not replaced, each step.

## Session 2 (attempt 2, Opus 5.5), 2026-10-01 ~22:20 PDT

**Why attempt 1 did not finish.** It got as far as a first-cut
`classify.py` (flat classes: play/paused/menu/loading/cutscene/black/unknown)
and a bash `drive_step` in `route.sh`, both uncommitted, plus ONE capture-cost
request (`1790917588-routedriver-4171714`, Crimson Skies, no capture, 195 s),
and then the session ended with nothing measured, nothing committed beyond
the draft-PR commit, and no `waiting:` note. Its NOTES.md held only the plan.
Nothing in its code was run against a frame. The session-1 WIP is committed
as ffb2fc0327 so the history shows what it was; this session replaces most of
it (ADDENDUM 2 asks for a named-state machine with a skip ladder, which a
per-capture bash loop calling a stateless classifier could not carry).

Attempt 2 starts by merging origin/master (titleroutes bdea9b8ecd is now
folded: 0f07dbfede) and queueing the two missing capture-cost arms beside
attempt 1's no-capture run, same title/route/seconds/ref:
`1790918323-routedriver-72414` (every 1 s) and
`1790918326-routedriver-72649` (every 5 s).

### CAPTURE COST (brief item 4)

Three dispatch soaks on the Nova, the same title, route, ref (abfd3ece0f) and
length (Crimson Skies, `crimson-skies` route, 195 s), differing only in
`--frames-every` (soak_title.sh's `adb exec-out screencap -p` loop). Read with
scratch/costab.py: per-window fps = 60 / dt between consecutive hakuX-perf
lines after `mark gameplay`, and the hakuX-pace counters over the same span.

| run | capture | frames | windows | fps median | fps mean | fps min | flips at 3+ vblanks | worst flip gap (median / p90 / max ms) |
|---|---|---|---|---|---|---|---|---|
| 1790917588-routedriver-4171714 | none | 0 | 42 | 30.00 | 29.77 | 26.57 | 0.81% | 35.4 / 61.6 / 292.3 |
| 1790918323-routedriver-72414 | every 1 s | 139 | 43 | 30.00 | 29.98 | 29.84 | 0.42% | 34.5 / 37.0 / 44.8 |
| 1790918326-routedriver-72649 | every 5 s | 38 | 43 | 30.00 | 29.98 | 29.50 | 0.95% | 34.9 / 38.2 / 74.0 |

A screencap a second costs Crimson Skies nothing this instrument can see:
the no-capture run is the one with the worst stalls, so the spread is run
noise, not capture. LIMIT, stated so nobody reads more into it: Crimson
Skies paces itself to 30 and has headroom on the Nova; a title running at its
limit (60 with no slack) could still lose frames to a capture, and this does
not price that. One run per arm. So the driver's rates are: `fast_s` 1.0 s
everywhere that is not stable play (boot, logos, intros, title, menus,
cutscenes: nothing is scored there anyway), `slow_s` 5.0 s once play is
confirmed in a scored (`--mark`) run -- the 0.2 Hz arm, the rate the old
blind routes already captured at (their `shot play` every ~10 s) -- and
back to 1 s for one capture after any press. `--find` runs stay at 1 s
throughout: they end at confirmed play and score nothing.

IN-PROCESS SIGNALS (brief: prefer one if it exists). Searched the emulator
for a cheaper signal than a screencap. None names the screen:
- `hakuX-pace` / `hakuX-perf` (hw/xbox/nv2a/pgraph/profile.c:621-634) are
  flip pacing only; a 60 fps menu and 60 fps play print the same line. They
  stop only when the guest stops flipping.
- `[shd413] dph=` (profile.c:666-711) tracks pipeline lookups per 60 flips,
  roughly draws; a menu over a 3D scene draws like play.
- the frame dump (vk/renderer.c:1691-2499; marker file `frame_dump.on` in
  the app's files dir, polled once a second) gives an exact per-frame draw
  count and, with `images`, a 900 KB PPM per frame with a fence wait per
  frame. It still has to be fetched over adb and still does not say "pause
  menu": it is a costlier screencap, not a cheaper one.
- no guest pause/menu flag and no pad feedback are exposed.
So the driver reads screencaps.

## Session 3 (attempt 3, Opus 5.5), 2026-10-01 22:42 - 23:30 PDT

**Why attempt 2 did not finish.** It committed the named-state classifier,
drive.py, four profiles and the selftest (23496a9311, 22:36), then ended at
22:41 in the middle of an end-to-end check of route.sh's rewritten `drive`
step against a fake adb (scratch/fake_test.sh; the route.sh/drive.py edits
were uncommitted). It ended before the Castlevania `--find` that ADDENDUM 3
made the first priority, with no `waiting:`/`blocked:` note. The record does
not say why it stopped; the session was cut off. This session finished the
fake-adb check (route.sh -> drive.py -> pad.sh -> logcat, ROUTE FAIL exit
propagates), then went straight to Castlevania.

### Castlevania: Curse of Darkness (4B4E002D) first run -- REACHED PLAY

Nova, held under `hold.sh take nova routedriver:a3` 22:47:41 (the Nova was
running lane.collapse433's Battlefield request; the hold took effect when it
ended, nothing else was waiting on the hold), released 23:02. Five replays
with the lane's own route.sh/drive.py (`scratch/replay.sh`), because the
dispatcher's snapshot refuses `drive`:
`bash /home/justin/hakux-work/dispatch/bin/titles/route.sh --check
routes/castlevania-cod.drive.route` -> `unknown step 'drive'` (exit 1);
the lane copy -> `route ok`. Route: `drive castlevania-cod 360 find`. Battery
80% throughout, AC powered. Records: `docs/lanes/routedriver/castlevania/`
(each run's route-state.tsv, route-solution.json, replay.log, hakuX-route
logcat lines, contact sheet).

| run | result | what it taught (fix in the profile/driver) |
|---|---|---|
| 1 22:49 | ROUTE FAIL stuck, 100 s | The disk HAS a Castlevania save (the authoring session's "A", 0:00:00), so the title opens on Continue and the run took the returning path to the courtyard in 31 s. Then: HUD up, nothing held (play is only confirmed by motion, an idle character makes none), the HUD hid itself when idle, and the still frames read `main_menu static` -> 25 A presses. Fixes: hold the play input as a probe whenever the HUD is up; a still frame within 20 s of a HUD frame is `stalled`, not a menu; `title-continue` crop -> LY:min onto New Game. |
| 2 22:53 | ROUTE FAIL stuck, 115 s | New Game -> Name Entry answered first time (A, START, A, "Is this correct?" A). Then the SAVE list -> A on slot 1 -> "Previous save data exists. Overwrite?" defaults to No, so A bounced back to the list 25 times. Fix: `overwrite` crop, LX:min then A. Also: the title crops only covered the logo (y 40-540; the menu is at 600-800), so they could not tell the cursor apart; re-cut over the menu. |
| 3 22:56 | ROUTE FAIL stalled, 76 s | START in the cutscene ladder hit the title's fade-in (took Continue) and later opened the Player status screen in play (`status-menu` crop named it `paused`, B resumed it). Play confirmed, then LY-forward walked him into the gargoyle fountain: HUD up, changed 0.004-0.010 for 40 s. The stall watch was right. Fix: `play_cycle` (forward 4 s, right 2 s, back 3 s, left 2 s) + A every 5 s; ladder A, X (no START). |
| 4 22:58 | **reached-play**, 49 s | Play at 27.9 s, 20 s sustained. Returning path again: the X rung landed on the title's fade-in and picked Continue. Fix: `skip_settle_s` 3.0. |
| 5 23:00 | **reached-play**, 74 s | **First-run path, end to end.** Title 6.6 s, play 53.6 s. |

**THE SOLUTION (run 5), as the profile now replays it unattended** --
`drive-profiles/castlevania-cod.toml`, route `routes/castlevania-cod.drive.route`:

| t (s) | state (classifier source) | input | lands on |
|---|---|---|---|
| 2.2 | intro_video (moving) | A (skip) | Konami logo |
| 3.8-5.2 | logo (static), black | -- (settle) | title |
| 6.8 | title (crop title-continue) | LY:min | cursor on New Game |
| 8.8 | title (crop title) | A | Name Entry |
| 10.9 / 14.3 / 17.8 | profile (crop name-entry) | A, START, A | name "A", Accept |
| 21.2 | profile (crop name-confirm) | A ("Is this correct?" Yes) | SAVE "Checking..." |
| 24.8 | loading (crop save-busy) | -- | SAVE slot list |
| 26.5 | profile (crop save-slots) | A (slot 1) | Overwrite? (No) |
| 30.1 / 32.3 | profile (crop overwrite) | LX:min, A | Saving... |
| 34.2-38.8 | loading (crop save-busy) | -- | Save completed |
| 40.5 / 44.8 / 48.0 | cutscene (moving) | A, A, A (skip) | Save completed, Valachia crawl, castle shots |
| 51.8 | unknown (hud+after-cutscene) | hold play_cycle | -- |
| 53.6-74.4 | play (hud+motion, changed 0.26-0.34) | play_cycle + A every 5 s | 20 s of play -> `reached-play`, app stopped |

Skip table (`drive.py learn` on run 5, written into the profile so the next
run tries these first): `skip: intro_video via A at +0.0 s -> logo` (1 of 1);
`skip: cutscene via A at +0.0 s -> black` (3 of 4 visits; the fourth was the
"Checking..." dialog's fade, which ended before a press was due). The Konami
logo was never pressed through: it went to black on its own in 1.2 s.
No state was unskippable (`skip=none` never logged).

**Time to title / play vs the old fixed-wait route.** The open-loop
`castlevania-cod.first-run.route` pressed its first A at 24.3 s (fixed
waits) and wrote `mark gameplay` at 192.5 s of fixed waits plus up to 30 s of
`waitfor` -- and never got there unattended (1790902028, 1790903439,
1790918365). drive.py: title 6.6 s, play 53.6 s, on the same disk.

**Classifier outcome, run 5** (route-state.tsv, 42 captures): every capture
was named by the cheap classifier; **0 model calls** (no ANTHROPIC_API_KEY is
set on this host, so the Haiku fallback was never available; the run did
not need it). By source: 18 named by a crop (name-entry 5, save-busy 5,
overwrite 3, name-confirm 2, title-continue 1, title 1, save-slots 1), 12
by the HUD crop + motion (11 play, 1 unknown right after the cutscene), 6 by
motion alone (5 cutscene, 1 intro_video), 4 black, 1 static logo, 1 no-prev.

**What the classifier got wrong in run 5, honestly:** (a) "Save completed."
(frame 230052-024) was named `cutscene` (motion 0.095 from the dialog
fading in) and got a skip A; harmless (A dismisses it) but it is a dialog,
not a cutscene. (b) The anomaly log has two false entries: `logo after
intro_video` (the first moving frame at boot is the save-load screen fading
out, named intro_video, before the Konami logo) and `profile after
cutscene` (the SAVE screen's transition read as a cutscene). (c) Runs 1-4
show it is honest about the HUD-hidden case only through the drive.py
rule, not the classifier: an idle character with the HUD hidden is
`static` to classify.py. (d) The `save-create-no/-yes` and `start-nosave`
crops (the no-save-on-disk path) come from the authoring session's frames
and have NOT been exercised by a drive run: this disk has a save.

**Frames I looked at to call it live play** (run 5, all 11 of the 20 s
stretch, plus the path before it): full size in the lane worktree,
`/home/justin/hakux-work/wt/routedriver/scratch/run-cv5/route-frames/`
`230106-032-play.png` ... `230127-042-play.png`; committed at 640x480 as
`docs/testing/titles/drive-profiles/selftest/rdcv5--230106-032-play.jpg` ...
`rdcv5--230127-042-play.jpg`, and as one sheet,
`docs/lanes/routedriver/castlevania/run5-contact.jpg`. What they show: HUD up
(Player, HP 100/100) in every frame; the character at different places in
the courtyard from frame to frame (left of centre at 033-034, right of centre
at 036 and 041-042), the sword out mid-swing at 036, 038 and 041-042 (the A
taps), and the camera panning so the fountain shifts across the frame. Not a menu, not a pause
overlay, not frozen. Run 4's stretch (225903-017 ... 225923-027) shows the
same. This does NOT make Castlevania Playable: no confirmation was queued.

### title_verdict.py: play_share (brief item 5)

`TIMELINE` in title_verdict.py's module doc. From drive.py's
`hakuX-route: state=<s>` lines over the scored window: `timeline.play_share`
(seconds in `play` / scored seconds) and `by_state`; a confirmation under
`play_share_min` (0.90, targets.toml [defaults] may override; I did not
edit targets.toml) fails "menu time: 66.7% of the scored window in `play`
(bar 90%; play 400 s, main_menu 200 s)", named before the fps bar; fps is
judged over windows whose midpoint is in a `play` span, with
`fps_excluded_s`/`fps_excluded_windows` reported; no state lines -> judged as
before, `timeline: none`. hitchwatch's ea3ffa1876 was already on master and
in this branch, so this is on top of its form. Old blind runs re-judged
read `timeline: none` with their old failures (1790914021, 1790900520,
1790902215). Selftest `99-play-share.sh`: 4 legs + 3 mutants, all caught;
`SELFTEST_ONLY="66-status-titles 67-status-measured 99-status-fullwindow
99-play-share 89-title-verdict"` -> 143 passed, 0 failed.

### For the next session (do not repeat)

- The Castlevania profile is done for a disk WITH a save. Before trusting it
  on a fresh disk, one `--find` on a disk without a Castlevania save would
  exercise `save-create-no/-yes`. Do not re-learn the ladder: the skip
  table is in the profile.
- Sonic Heroes (brief item 6, on-foot proof #2 in the brief's order) is NOT
  done: one title per session on the Nova, and Castlevania came first per
  ADDENDUM 3. Its profile exists (drive-profiles/sonic-heroes.toml, from
  attempt 2) and passes the selftest, but has never driven the device. Expect
  the same two lessons: an on-foot title needs `play_cycle`, and a skip
  ladder with START can pick a title's default entry on its fade-in.
- Burnout/Forza (the driving proof) is not done either.
- `drive` cannot run from the dispatcher until this branch is folded and the
  dispatcher's checkout fast-forwarded (route.sh --check on the snapshot
  refuses the step). Until then every drive run is a held replay.
- The Haiku fallback is coded and capped but has never made a call: this
  host has no ANTHROPIC_API_KEY in the lane's environment.

## Session 4 (attempt 4, Opus 5.5), 2026-10-01 23:33 PDT -

**Why attempt 3 did not finish.** It did finish what it set out to do.
Castlevania reached play, the records were committed, and PR.md was set to
`State: ready` at 23:30. It stopped short of brief item 6: the two
conversion proofs, one on-foot (Sonic Heroes) and one driving (Burnout or
Forza), had never driven a device. Its reason was the one-title-per-Nova-
session rule, but it did not use ADDENDUM 4 (supervised `--find` on the Thor
for titles already there). It also did not run `preflight.sh` and left no
`waiting:` note, so the lane was resumed. This session merges origin/master
(titleroutes session 61, collapse433; clean). It then does both proofs in
parallel on separate devices: Sonic Heroes on the Nova (hold
`routedriver:a4`, taken 23:35), and Forza on the Thor under ADDENDUM 4.
Both titles are on the Thor per onhand's listings, but only Forza runs
there. The Thor stays under lane.local's `lanelocal-fanwait` hold, which
`hold.sh take` cannot take over and ADDENDUM 4 says not to lift, so the
Thor replay runs under that hold. The replay script checks that no request
is running there, starts cold (xo-therm <= 50 C) and stops at 70 C.
`scratch/replay.sh` now takes `DEV=nova|thor`.
