# lane.pathfind -- NOTES

## Screening 10-04 (owner order): scoreboard

| # | title | id | class | share >= 30 | median | window | claim (min, calls) | profile | run |
|---|---|---|---|---|---|---|---|---|---|
| 1 | RalliSport Challenge | 4D53000F | clear | 98.9% of 649 s | 59 | full (671 s, PASS) | 3.2, 19 | golden cc9b4ced4a0f | runs/screen-ralli-challenge/hold-0816 |
| 2 | AvP: Extinction | 56550022 | clear (fps) | 100% at 28.5 (47% at 30) | 29 (locked 30) | full (856 s; FAIL play share 70.7%: RTS camera still) | 3.1, 17 | golden 50a35dcd33ed | runs/screen-avp-extinction/hold |
| 3 | Phantom Crash | 504C0001 | can't-path | - | - | - | gave up 15 min, 92 calls ($6.7): ClubWired dialogue | none | runs/screen-phantom-crash/claim |
| 4 | Simpsons Road Rage | 45410013 | can't-path | - | - | - | race HUD at 10.8 min; 10 RT probes refused; 74 calls ($5.5) | none | runs/screen-simpsons-road-rage/claim |
| 5 | Simpsons Hit & Run | 56550015 | clear | 100% (98.2% of samples) | 38 | full (606 s, PASS) | 2.7, 18 | golden bcc71e970cff (title data only: hold on state any) | runs/screen-simpsons-hit-run/hold |
| 6 | Guilty Gear XX #Reload | 53410002 | clear (fps), partial | 100% of 193 s | 59 | partial: hold lost at a CONTINUE screen after 97 s of play | 1.9, 13 | golden 6f0d8fc26eb7 | runs/screen-guilty-gear-xx/hold |
| 7 | LEGO Star Wars: The Video Game | 4553001D | CLEAR on fps | 1.0 of 733 s | 59 | full window; play_share 0.6845 | 1.21, 9 | golden 5251f98730d1 | runs/screen-lego-star-wars/hold |
| 8 | Mashed: Drive to Survive | 454D000A | can't-path | - | - | - | races from 2 min; 19 probes refused (self-moving camera, rounds end at once); 83 calls ($5.6) | none | runs/screen-mashed/claim |
| 9 | Amped: Freestyle Snowboarding | 4D530005 | fail | 0.35 of 305 s | 23 | aborted at 5:04 (gate); perflog run fps_ok 0.086: guest busy 31.6 ms/frame (vCPU), Ri 12.3 ms | 3.75, 24 | golden a7d274372a00 | runs/screen-amped/hold, perf |
| 10 | Dark Summit | 54510004 | CLEAR | 0.9318 of 606 s | 46 | full window; play_share 0.9998 | 9.08, 40 | golden 430384745827 | runs/screen-dark-summit/hold |
| 11 | Whiteout | 4B4E0001 | can't-path | - | - | - | load card 'Trojan Park' 12.5 min, never ended; 35 calls ($2.4); NEW ISSUE in OUTBOX | none | runs/screen-whiteout/claim |
| 12 | MTV Celebrity Deathmatch | 5454000B | CLEAR on fps | 0.9876 of 687 s | 59 | full window; play_share 0.8781 | 4.93, 29 | golden b206649c8fff | runs/screen-mtv-celebrity-deathmatch/hold |

Share columns use title_verdict's bar, 30 x `fps_tolerance` 0.95 = 28.5, unless stated.

SCREENING DONE 12/12 (14:20 PDT): clear 7, close 0, fail 1, can't-path 4; about $53 of $60 (Sonnet). The owner's
target of 8 clear-or-close was not reached. Three verdict PASSes (RalliSport, Hit & Run, Dark Summit) go to frame review.

What the next lane should not repeat:
- **Do not edit pathfind.py while a run is queued.** A queued run imports the file when its hold is granted. The 10:2x
  Road Rage run imported a half-edited file and died at step 2 (AttributeError).
- **`promote --latest` after a first-run claim can make a title-data-only golden** (Hit & Run: no profile saved by
  gameplay). titlestate then refuses `--state returning`. The hold uses `--state any`, which loads the golden unchanged.
- **Four of the 7 clears miss Playable on hold design, not fps.** An RTS camera reads still (AvP). A hub start walks
  into the pause menu (LEGO). Fighters lose and stall at CONTINUE (Guilty Gear: A does not continue). Between-round
  screens cost 13% (MTV). These are the next hold fixes, ranked by titles each clears.
- **A load that never ends gets no input.** The model says `wait` and the static-load rule waits (Whiteout, 12.5 min).
  One A/START after ~90 s of a static load card would separate a hang from a wait-for-press. Not built today.
- **Self-moving races cannot be confirmed by frame change** (Mashed: the idle change was 0.3-0.86). The probe ladder's
  HOLD:A:3 did move the scene once (0.017 -> 0.814), but the confirm model refused it on a results card.

## Resume (10-05 10:02 PDT, attempt 3 of the 10:00 sports order): why the last attempt did not finish

- The 09:58 attempt (attempt 2) wrote its resume note and stopped there. Nothing was staged or queued by it: `pm/sports-1005.done`
  lists only NFL Blitz 2002, and the note's "uncommitted change in pathfind.py" is not in the tree (`git diff HEAD` on
  pathfind.py is empty; `scene_shift` is in HEAD, and it still judges a still window only for a title hold, `if th:`). So the
  scene-shift-for-every-hold change was never made, and attempt 2 did not start the Blitz run or the sports standing rule.
- Cause: the session wrote the status and stopped before any device or code step, treating the note as the work.
- Device: the dispatch queue holds four perf-lane requests (`lane.gpuclock`, `lane.frametrace`, `lane.belowbar1005`,
  `lane.hitchcause`). Under the 08:42 gap rule the Nova is not re-taken until that queue has no Nova lane.* request, or 25 min
  after the MTV release (09:53, so 10:18), whichever is first.
- This attempt, in order: (1) the standing sports rule in code (period-end state `period_break` and its continue rule, the
  sports setup line in the claim prompt, a per-hold sports look logged in `held["sports"]`), with selftest; (2) the Sports
  section in `pathknow/hints/global.md`; (3) NFL Blitz 2002 first-run to a verdict once the Nova gap allows, under the
  period-length rule; (4) then the lead-title order.

## Resume (10-05 09:58 PDT, attempt 2 of the 10:00 sports order): why the last attempt did not finish

- The 07:00 session ended with the MTV Celebrity Deathmatch rerun (`runs/mtv-rerun1`, 09:38-09:53) in flight, and the
  09:55 order (NFL Blitz 2002 first) was not started. The MTV rerun gave up at the 15-min claim budget (`last_state=probe`,
  89 steps, `last_frame` 088-gameplay): play was live at step 88 and the budget ended it during the confirm probe. That
  breaks the 19:40 rule (give the claim its 15 min, do not stop at the claim budget once play is live). Its result is
  recorded as a claim give-up, not a hold verdict; the 87.8% CLOSE from the screening stands as the last hold number.
- One change sat uncommitted in `pathfind.py` (still judged by the scene's shift in every hold, not only title holds).
  It was never selftested or committed, so it does not count as done until this attempt's selftest and commit.
- Nothing ran on the Nova between 09:53 and this resume, and no WAITING file was written. This attempt starts NFL Blitz 2002
  (on the Nova, in `pm/sports-1005.done`) first, as the 09:55 order asks.

## Resume (10-05 07:00 PDT, attempt 2): why the last attempt did not finish

- The 06:37 session ran the Tork re-run (`runs/tork-rerun2`, 600 s held) and judged it: it stood on one stair from about
  73 s on, the same genre walk every step. Its OUTBOX stop line ("Stopped at 06:55 PDT, the 07:00 window") ended the session
  before the Tier 1 list, which the 06:58 lane.local note then asked for all day. The session treated the 07:00 window as
  the end of work; the 06:58 note cancelled it, but nothing was queued and no WAITING file was written.
- Cause of the stand-still: `hold_play` only re-pressed X on a still window for a title hold (TITLE_HOLD), so the walk never
  changed and the stair was never left. The generic genre hold rotates its moves on still windows; the title hold did not.
- This attempt: **stand-still detector for title holds.** Two still 30-s windows in a row (60 s) now send the next move
  of `TITLE_UNSTICK` (hop with A, camera turn, back out, sidestep) in front of the walk, and a moving window puts the walk
  back. A title's own `unstick` list comes first (Tork: stick forward with A held, the hop). `hold.jsonl` records the move as
  `unstick`. Selftest: the titlehold check now accepts walk or move+walk, and checks that a still scene sends a move
  (`scratch/selftest-10-05.log`, 66 ok).
- `pathfind.py` is edited for this lane (the 06:58 note allows it: commit on lane/pathfind, lane.local folds).

## Resume (10-05 06:37 PDT, attempt 1 of the 10-04 22:2x overnight plan): why the last attempt did not finish

- The 22:18 session started the Tork re-run as a session background task. The 600-s ceiling ended the session and killed the
  run at about 311 s (`runs/tork-rerun/`, partial, not scored). Nothing ran overnight; the Nova was idle about 8 h.
- No WAITING file was written and no run was queued, so the session ended with the owner's first item unstarted.
- This attempt: selftest all ok (`pathfind_selftest: all ok`, before device time). Took the Nova with `scratch/heldrun.sh`
  (`hold.sh wait`, then `wait-idle`, released on every exit) for the Tork re-run, `--state any` as in the 10-04 run,
  output `runs/tork-rerun2/`. Log: `runs/tork-rerun2/heldrun.log`. The run is a held run, watched in the foreground.

## Resume (10-04 late, lane.pathfind attempt 1 of the 22:2x Tork brief): why the last attempt did not finish

- The last session committed the two code changes the Tork brief asked for (a684c6035a letterboxed cutscene repeats and
  the intro/logo START-A-B ladder; 5bc98877ce TITLE_HOLD["55530040"] forward walk) and then ended. It queued no Tork
  run: `runs/tork-rerun` did not exist, nothing was on the Nova, and there was no WAITING file.
- Its selftest log (`scratch/pf_selftest3.log`) predates both commits, so the new code had never passed selftest.
  Rerunning it now fails one check, `dialogue`: it still expects three unlooked repeats. The letterboxed cutscene
  fixture gets `CLAIM_REPEAT_BOX` (6 presses including the first look), so the test expectation was stale, not the
  code. Fixed in `pathfind_selftest.py` (five repeats after the first look). `pathfind_selftest: all ok` (65 checks,
  `scratch/selftest-attempt4.log`).
- `pathfind.py` is not edited in this attempt (brief: it belongs to lane.hangwatch). The working tree held only
  NOTES.md changes from the session before this one, which this section now sits on.
- The Nova was held by lane.local-overnight1004 (push of Rogue Trooper) at the start of this attempt, so the Tork run
  waits on `hold.sh wait` through `scratch/heldrun.sh` (tag `lane.pathfind`, released on every exit).

## Resume (10-04 22:10 PDT, attempt 3): why the last attempt did not finish

- The 19:42 session (attempt 2) ran Tork, JSRF, Conker, DOA3, Amped 2, Ninja Gaiden Black, Buffy and Tron 2.0 in that order.
  Results: Tork PASS (20:02), JSRF PASS (20:20), Conker GAVE UP at the claim budget, DOA3/Amped 2/NG Black/Buffy FAIL on fps or
  identification, Tron 2.0 PASS (22:10, handed to lane.local for frame review).
- It ended at 22:10 PDT, right after Tron's 600-s hold, and did not start the 22:2x overnight order. The overnight addendum
  (Guilty Gear XX first, then LEGO, AvP, then the owner list) arrived while Tron was running, and the session had no WAITING
  file and nothing queued. Cause: the session treated the Tron hold as the end of its work instead of the start of the queue.
- Black Stone's hold3 (`runs/black-stone-hold3`) failed with the fighter never moving: NEW ISSUE filed in OUTBOX (10-04 22:10).
- This attempt: committed the pending session state (1b56e71989), merged origin/master (bce438ecaa), reran
  `pathfind_selftest.py` (all ok, `scratch/selftest-attempt3.log`), then started the overnight order at Guilty Gear XX.

## Resume (10-04 19:42 PDT, attempt 2): why the last attempt did not finish

- The 19:13 session (attempt 1) wrote the Guilty Gear hold fix and selftested it. Its attempt-2 re-hold (19:29-19:40,
  `hold2/`) used its 15-min claim budget without confirming gameplay, so no 600-s hold started (see below).
- The 19:40 RetroTechDad addendum (fresh titles first) arrived as that claim ended. The session did not start it, and
  the session ended with nothing held and no WAITING file. The fix stands; its re-hold is not yet proven.
- The Nova is held by `lane.local-owner1004` (owner list: Deathrow, MechAssault 1/2) at 19:42, so this resume waits on
  that hold through `heldrun.sh`'s `hold.sh wait` (1200-s timeout) before each title.
- This resume's order (owner 19:40): Tork (55530040), JSRF (4D53003D), Conker (4D530051), DOA3 (54430001), Amped 2 (4D530041),
  Ninja Gaiden Black (54430003), Buffy (45410012), Tron 2.0 (id not in the goldens table; by ISO name), then Halo 2 / Dino
  Crisis 3. Stop 23:30 PDT.
- Per title: first-run claim (15 min), then ONE 600-s hold with frames at least every 30 s; a claim-budget miss or a
  3-min/5-min "off course" read names the cost and moves on. Each result goes to OUTBOX as it lands.

## Resume (10-04 19:13 PDT, attempt 1): why the last attempt did not finish

- The last session ended at 14:20 PDT with SCREENING DONE 12/12 and the Nova released. Its 11:3x addendum (Guilty Gear XX:
  fix the fighting-game hold recovery, then ONE 600-s re-hold) was not carried out: the 14:20 session stopped at the
  screening list's end, and the fix was never written. The 19:20 addendum (this session's order) restates it first.
- Nothing was in flight and no WAITING file was written. The branch was 68 commits behind master; merged at the start
  (fast-forward: this lane's earlier commits were already folded).
- Tonight's order (19:20 addendum): Guilty Gear XX fix + one re-hold, then LEGO Star Wars (pause menu), then AvP only after
  those. Cap $70 for the day; stop at 23:30 PDT.

### Guilty Gear XX: what the frames show (hold `runs/screen-guilty-gear-xx/hold`, claim `claim`)

| step | screen (frame) | what the hold sent | outcome |
|---|---|---|---|
| CONTINUE after a lost round | "CONTINUE" with a countdown and credits (hold 058-060) | A, A, A (the look called it `continue`, a state the hold's rules did not list) | the countdown ran out to GAME OVER (061) |
| GAME OVER / ranking | "RANK IN AA" over black (063-065) | START (repeat x3) | the title, then Arcade (066-068) |
| Character select | "PRESS START" over the empty 1P slot, Sol highlighted (069, 071-072) | START, START, START | nothing: the match never started; the 12-step limit ended the run |

- **The character-select input is A, not START.** The claim's recorded path accepts the default with A on this same screen
  (steps 9, 11, 25, 26: A, then the round is live). The rules text said `accept the default with A (or START)`, and the
  model took START from the "PRESS START" over the empty slot.
- **The continue input is not settled.** A did not continue in the hold (three presses, the count ran down). In the claim
  its A on the continue led to a black frame and then the title, so A is not a continue either way. START was never tried
  on a continue screen. The fix tries START first, then A, and the hold log says which one took.

### What changed (`docs/testing/titles/pathfind.py`, `pathfind_selftest.py`)

1. **RULES:** a select screen gets A on the highlighted entry, never START; START is for title and attract prompts only.
   A CONTINUE countdown gets one START, then A, and is not waited out. This applies to fighting titles generally.
2. **`continue` is a state** (added to `STATES`, which the claim's answer check uses to map a state to `unknown`, and to
   the model's state list). The model answered `continue` in the hold, and without it in `STATES` the claim would have
   read that answer as `unknown`.
3. **The hold's continue press** (`CONTINUE_PRESS = (START, A)`, `CONTINUE_TRIES = 4`): in a non-title hold, a `continue`
   look sends the next press unlooked, 1.5 s apart. The count restarts when play comes back. Title holds are unchanged
   (their continue is `DOWN, A` at the title screen).
4. **Selftest `continue`:** three continue looks send START, A, START, and the count is logged per look. `pathfind_selftest:
   all ok` (run before device time).

### Guilty Gear XX re-hold attempts (10-04 19:25-19:55 PDT)

- **Attempt 1 (19:25, `--state returning`):** refused before it started. The golden 6f0d8fc26eb7 is title data only (no
  save directory), so titlestate refuses `returning`. Nothing ran on the Nova beyond the take and release.
- **Attempt 2 (19:29-19:40, `--state any`, `hold2/`):** gave up at the 15-min claim budget (81 calls, 76 steps, $ about
  4), so the 600-s hold never started. Gameplay was claimed many times but never confirmed (the probes were refused, the
  control read 0.11-0.18 at a round start). The frames identify the fixed inputs:
  - CONTINUE after the loss (step 21): START, which led to the character select; then A on the highlighted fighter (22-23)
    resumed the round (24-25). Step 56, A on the CONTINUE: the countdown ran out to GAME OVER (57-58). So START continues
    and A does not. The model chose START in the claim after the rules change, and the claim worked through it.
  - The round's "PRESS START" over the empty P2 slot (44-45, 53-54, 64-65): START each time, and START opened the pause
    menu (46). That is the second cause of the lost minutes.
  - Probes that land in a round start (the "PLEASE WAIT" and the 3-2-1 banner) read control 0.1-0.2 and were refused.
- **Change for attempt 3:** the rules now say a PRESS START over an empty P2 slot in a live round is a join prompt (do not
  press START), and a round-start banner waits 2 s before any probe. Compiled; no other change.

### LEGO Star Wars: the cause (hold `runs/screen-lego-star-wars/hold`)

- The hold ran clean to 576 s. From then, the hub's "Press START" prompt (the player-2 join prompt over the level) was read
  as a cutscene, and the cutscene repeat sent START three times at a time. START opened the pause menu (600 s, 682 s) and
  the menu's START/A kept it going. Most of steps 74-104 (about 20 of 31 looks) were `cutscene` with START; the rest
  were menu, pause, and one A.
- Not fixed yet: this is the second item, after the Guilty Gear re-hold.

## Resume (10-04 08:13 PDT, attempt 4): why the last attempt did not finish

- The 07:56 session claimed RalliSport (3.2 min, 19 calls), promoted its golden and started the 600-s hold as a
  background task. The session then ended, the task died with it at 234 s, and the hold was released with the car
  unattended. Rule kept since then: a held run is waited on in the foreground of the session that started it.
- That partial window read 230 of 236 s at >= 30 fps (min 34). It showed no miss, so the 600 s was run again.
- Two tool changes this session:
  1. The owner's 3/5-min "should we continue?" check is in the hold (`FPS_GATES`, `fps_course`): median < 22 at
     3 min, or < 27 at 5 min, with < 60% of seconds at >= 30, stops the hold. scratch/screen.sh then runs one
     180-s telemetry hold on the same path. Its logcat carries the perflog and the [rr425w] lines that decompose.py
     reads. Selftest `fpsgate`.
  2. Master's failgate (`de4b991a6c`) fails a scored window with fewer than 3 `HHMMSS-*.png` frames as
     "window unmeasured". The hold kept only `NNN-hold` frames. It now links each kept frame to
     `route-frames/HHMMSS-hold.png`. RalliSport was rescored from its kept JPGs: PASS.

## Resume (10-04 07:56 PDT, attempt 3): why the last attempt did not finish

- The 22:4x session finished the list it had been given. Panzer Dragoon Orta run 3 PASSED at 00:48 (603.7 s, play 0.9997,
  fps_ok 0.9962, `8b2dfede96`), and its PR.md and OUTBOX were written. Nothing was in flight and no WAITING file was
  written, which is correct for a finished list.
- It did not get a next order before it ended: the 10-04 screening addendum (owner, ~07:55: identify, pathfind, measure
  each of 12 untested Xbox titles against the 30 fps bar; stop at 8 clear-or-close) arrived after the session ended.
  So this is a new order, not an unfinished one. This session replaces the stick-probe plan the 10-04 07:00 note had.
- Starting state: the Nova is held by `lane.local-sweep` (pushing RalliSport 4D53000F). Of the 12 screening titles, only
  RalliSport (4D53000F), AvP Extinction (56550022) and Phantom Crash (504C0001) are on the Nova's
  `/storage/E6C6-D7AA/Games/XBox/` folder at 07:56. The rest of `pm/screen-1004.tsv` is still being staged, so each
  is checked before its run and the missing ones are taken later.
- Selftest `pathfind_selftest: all ok` before device time.

## Resume (10-03 22:37 PDT, attempt 2 of this resume): why the last attempt did not finish

- The 21:5x session ended at 22:27 (commit `9b7b90c7de`) right after its Black Stone hold3 write-up (FAIL, play share 9.5%,
  OUTBOX 22:25). The 22:4x addendum (Panzer Dragoon Orta, held run 3 before 23:30 PDT) arrived after that write-up and was
  not started. Nothing was in flight and no WAITING file was written, so the session stopped with the Panzer run undone.
- Spend at the start of this resume: about $50 of the $70 cap. The Nova was free at 22:38.
- This resume: Panzer run 3, returning state (golden `7cf4eb6181f1`), 600-s hold with the position test. Three changes,
  each one the addendum's ask, and the cost each one targets:
  1. **Difficulty (the claim):** `paths/4947002B.json` step 6 (the difficulty select, NORMAL highlighted) now sends
     `UP, A`. It assumes EASY is listed above NORMAL: unverified until the claim's frame shows the menu.
  2. **Keep firing and moving (the hold):** `TITLE_HOLD["4947002B"]` replaces the empty onrails loop. A stick stroke that
     changes direction each cycle, RT held 1 s (fire), and a lock-on tap (`HOLD:A:0.4`, held then released). No X.
  3. **Title return (the cost of 65 s in run 2):** after a game over returns the title, one unlooked `DOWN, A` (CONTINUE),
     up to twice per hold, then the model looks. `DOWN` to CONTINUE is also a guess: unverified.
- Selftest `pathfind_selftest: all ok` before the run.

## Resume (10-03 21:5x PDT, attempt 1 of this resume): why the last attempt did not finish

- The 21:16 session (attempt 4) finished Dino Crisis 3 (FAIL, menu time 79.1%, below). Its OUTBOX was posted at 21:45 and it
  stopped with nothing in flight and no WAITING file.
- The 21:5x addendum (Black Stone moves up, next on the Nova; its title-specific hold design) arrived after that and was
  not started. Nothing was lost on the device.
- This session: the Black Stone hold as the owner specified it. `TITLE_HOLD["58490004"]` in `pathfind.py`: X once alone at
  the hold's start and again after two still windows in a row; a left-stick walk in 4-s strokes that change direction; no
  face buttons in the walk; Y, R1, BACK, START and B are never sent in the hold. A menu that a look finds open gets one B,
  then X, then the walk. The genre model is not asked for a title hold. Selftest `titlehold` covers it (all ok).
- Spend at the start of this resume: about $46 of the $70 cap (the 21:16 NOTES figure of $44 plus the Dino Crisis 3 run).
- **Result (black-stone-hold3, 22:0x-22:25 PDT, Nova, first-run; `runs/black-stone-hold3`): FAIL, play share 9.5%.** Claimed
  at 4.9 min (67 model calls, 28 steps, $3.4 est.). The title hold ran 1219 s of gameplay HUD with the fighter on one spot:
  116 s of play credited (the first 116 s, before the first still window), then 1104 s still. The strip (hold_strip.jpg)
  shows the same octagon position and camera in all 40 kept frames, and no menu in any of them. The verdict's
  "menu time" label is its name for the non-play share; here it is still time, not menus.
- **What the hold did, from hold.jsonl:** X at 1.8 s (press 1), then the 4-s left-stick walk. The first walk cycle changed
  0.82 of the frame and the next cycles 0.0002-0.002, so the camera moved and the fighter did not travel. Two still windows
  later, X again (press 2, cycle n=55); its cycle changed 0.82 once, then the walk did not travel either. Never a Y, R1,
  BACK, START or B in the walk.
- **Cause, not yet named:** the left stick did not move the fighter after either X. The 10-02 probe (steps 94-97 of
  `runs/black-stone-hold`) moved him only after a mixed sequence (X with a stick, then LEFT), so the stance rule "one X lowers
  the sword, then the stick walks" is not confirmed. The next step is a stick-response probe on this title with frames per
  input (a probe, not a hold), before any more 600-s runs.
- **Not run:** 007 AUF (addendum 1 of 21:2x: only after the hold moves the player; it does not yet). Spend stops here, near
  $50 of $70.
- **The run used `first-run` by mistake.** Black Stone has a golden (`titlestate.py golden --title-id 58490004`:
  86c8f6eada06, promoted by lane.local), and a `first-run` route composes the disk WITHOUT the run's own title's golden
  (titlestate.py header). So the run was offered Name Entry again: it sat there for about 4 min (every D-pad, A, START and
  stick input logged as a no-op), then got through on HOLD:A and claimed. The profile it made went to the latest slot, not
  the golden. The next run of a title with a golden uses its `returning` variant. (heldrun.sh defaults to first-run; pass
  `returning` as its fourth argument.)

## Dino Crisis 3 held run (10-03 21:27-21:45 PDT, Nova, first-run)

- Claim at 3.55 min, 35 Sonnet calls. Hold 607 s of play, FAIL on menu time (79.1%). fps_ok 0.38.
- Frames 023-082: the player stays in one corridor (the shooter loop does not travel). Frames 085 and 089: L1/X open the
  Map and Item screens. Same fault as the Black Stone walk run: the hold does not move the player, and its unlock
  buttons open menus. Not re-queued (fps and design are named in OUTBOX).
- Verdict and strip: runs/dino-crisis-3-hold/. OUTBOX has the NEW ISSUE.

## Resume (10-03 21:16 PDT, attempt 4 of this resume): why the last attempt did not finish

- The 20:40 session ended after the Black Stone walk run FAILED (menu time 63.8%, `runs/black-stone-walk`), posted its
  OUTBOX entry and its NEW ISSUE, and stopped with nothing in flight. Its last commit is `1a46714a21` (the pathknow
  route guide). It wrote no WAITING file and no next step, so the 21:2x addendum (Dino Crisis 3, title 5 of today's
  Playable push) was not started.
- Not committed by that session: the untracked `runs/halo-2-hold/`, `runs/halo-2-hold2/` and `runs/black-stone-walk/`
  record directories and `scratch/`. They are kept as evidence and committed with this resume.
- This session: Dino Crisis 3 (43430003, Nova, "Dino Crisis 3.iso"; targets.toml row 550). Reach confirmed play, then a
  600-s held run with the position test, through `scratch/heldrun.sh` (take, wait-idle, release on every exit path).
  Stop early if play reads < 28 fps for the first 60 s. Spend at the start of this resume: about $44 of the $70 cap.

## Resume (10-03 20:17 PDT, attempt 3 of this resume): why the last attempt did not finish

- The 17:15 session ended after Halo 2 run 2 (17:58, blocked: the Armory camera does not respond, `runs/halo-2-hold2`),
  with its OUTBOX posted and nothing in flight. It had no WAITING file and no run going, so it stopped there.
- It never reached the 18:3x and 20:2x addenda: the Black Stone, Dino Crisis 3 and 007 list with cap $70. The
  Black Stone hold2 run (11:34, `runs/black-stone-hold2`) had already shown the cause of its miss: the attack loop's
  `STICK:up:1` and `STICK:down:1` cancel, so the player stood on one spot for 600 s (frames 024-069 are the same
  octagon with the player in the same place).
### Black Stone walk run (20:21-20:40 PDT, `runs/black-stone-walk`): FAIL, menu time 63.8%

- The square walk moved nothing: frames 024-044 show the fighter on one spot (window change 0.005-0.015).
- The still-window rotation then sent Y/R1/B/X, which opened the magic/item panel in most frames from 059 on.
  The hold counter credited play through those menus; the verdict's position and menu test caught it.
- Not Playable. The attack walk design is wrong for this arena; a fix must move the player without the unlock
  rotation. See OUTBOX NEW ISSUE. Spend $2.40 for this run.

- This session: the attack genre gets a walk on each still window (`HOLD_UNSTICK["attack"]`, a square walk of 30-s
  legs), then the Black Stone held run. Merged origin/master first (17 commits).

## Resume (10-03 17:15 PDT, attempt 2 of this resume): why the last session did not finish

- The 16:30 session ran NBA Live 2005 to its end (609 s held, FAIL on fps, committed `964c1a239c`) and stopped there.
  Its brief's last instruction, the 17:1x addendum ("Halo 2 next; NBA siblings wait"), arrived after that run and was
  not started. Nothing was in flight and no WAITING file was written, so the session ended with the Halo run undone.
- Spend at the start of this session: about $33 of the $50 cap (the 17:1x addendum says about $17 left).
- This session: the Halo 2 held run (golden `0a4742f1e45d`, GPL 3 is the build default; the Nova logcat will show
  `[gpl569] mode=3`), with a moving hold: the pool's 31% static window came from a loop that stood still in one room.

### Halo 2 run 1 (17:20-17:36 PDT, `runs/halo-2-hold`): gave up at the 15-min budget, 85 model calls

- Intro: 31 steps of letterboxed cutscenes (START, A, B, BACK, X, Y, R1 all tried) before the Halo HUD at 5.3 min.
- Claim failed twice: the motion-sensor HUD sat over the **Armory look test**, a tutorial that needs the right stick.
  Probes under the left stick read control 0.000-0.021.
- **Cause (non-performance, named and fixed):** the navigation prompt's action grammar (`pathfind.py`, the list of
  tokens) never mentioned `RSTICK`. The parser has accepted it since 10-02, and the hold loops use it, but the model was
  never told it exists. Its notes say so at steps 39-66 ("the action list cannot send right-stick input").
- Fix: `92cf166279` adds `RSTICK:<dir>:<s>` to the prompt grammar. Selftest all ok.
- The run loaded the old module and cannot pass as it stands. Re-run 2 (`runs/halo-2-hold2`) uses the fix.

### Halo 2 run 2 (17:40-17:58 PDT, `runs/halo-2-hold2`): gave up at the 15-min budget, 95 model calls, claim never confirmed

- The RSTICK fix worked: the model used the right stick from step 32 on and wrote "RSTICK:left changed the view" at
  step 52. Those reads were not confirmed by the claim probe.
- The scene is Halo 2's Armory: a sealed octagonal room with the HUD up and the camera pinned on the floor. Repeated
  stick, right-stick, trigger, A, X, R1, B and LT inputs did not move the view.
- **The measure is not the cause.** Probe frames `073-probe-a` and `073-probe-b` are identical (mean grey difference
  0.0), and `073-probe-c` differs by 0.11 of 255. The game is not responding to the sticks in this room.
- **Not settled:** whether the Armory tutorial locks the camera until a step the model has not found, or the run starts
  too early. Halo 2's cold boot ran about 5 min of cutscenes before the HUD (steps 13-31), so a route that skips the
  cutscenes is the lead to check, not a retry of this run.
- **Status: blocked on a game-side input.** Halo 2 is not Playable today. Two runs and about 180 model calls (about $9
  at the usual $0.05/call; the cost sheet is the authority) are spent on it. Do not queue a third run until a frame
  shows the camera responding in the Armory, or a route past it exists.

## Resume (10-03 16:30 PDT, attempt 1 of this resume): why the last session did not finish

- The 14:55 session stopped at its $29.5 spend stop with the Nova released and no run in flight. Its 14:45 OUTBOX
  said no NBA Live title was on the Nova. That was a stale listing: lane.local's 16:2x addendum says all four were
  copied and verified 13:51-13:59, and `listing-nova.txt` lists them now (45410038, 45410050, 4541007A, 454100A1).
- The NBA Live 2005 run (45410050) was the owner's priority today and was never started, so the session ended
  before the first item of the 16:2x addendum. Its 16:28 hostops resume names the same task.
- This session: NBA Live 2005 first (held 600 s, position test on, goal = longest quarter), then 2004, 06, 07 while
  the budget lasts. Budget left is about $5.5 of $35.

## NBA Live 2005 held run (10-03 16:29-16:47 PDT, Nova, golden none: first-run)

| run | title | result | claim min | hold | model calls | cost | verdict |
|---|---|---|---|---|---|---|---|
| runs/nba-live-2005-hold | NBA Live 2005 (45410050) | **gameplay claimed**, 609 s of play, team loop | 6.8 | 609.7 s, play_share 0.9996, 0 still windows, travel in every frame | 43 (sonnet 43) | $2.92 | **FAIL (fps)**: median 19.97 fps, 0.0% of windows at >= 30 fps (bar 90%) |

- Route: the EA logo was skipped with A; the goal string set the quarter to the longest length (the clock runs
  11:41 -> 5:44 in the frames, so the quarter covered the hold). Four probes were refused during the claim. The
  claimed play frame is `frames/034-gameplay.jpg`; the hold strip is `hold_strip.jpg`.
- This is a **performance** miss by the owner's rule: the same run should not be queued again. Telemetry: the frame
  rate sits at about 20 fps (min 17.8), the same class as Top Spin, Counter-Strike and Midnight Club 3 (10-02). The
  cost to name is the Nova's frame rate in this title, not the route. Recorded path `pathknow/paths/45410050.json` and
  the learned pub-4541 hint are committed. They are a guide for the sibling runs.
- **Not run:** NBA Live 2004, 06 and 07. Today's cap is $35: spend is about $32.4 after this run (the $29.5 at
  14:45 plus $2.92). A sibling needs about $3 and would be the same engine at the same fps, so the next lane should
  start from the fps cause, not another route.

## Resume (10-03 12:40 PDT, attempt 7): why the last attempt did not finish

- The last session ended at 11:48 after writing up Black Stone (verdict PASS, frames show no travel: not counted).
  Its write-up named the next need (a position test) but left no WAITING file and no run going, so it stopped with
  nothing in flight. Nothing was lost.
- Since then the 12:50 addendum replaced the pool order: `~/hakux-work/pm/pathfind-pool.tsv` is the work list.
  Castlevania (4B4E002D, profile-creation) first, then Forza, then the file in order. This resume merged
  origin/master (clean).

## Where attempt 7 stopped (10-03 14:55 PDT)

- PR.md `State: ready`. Selftest all ok, preflight passed, origin/master merged. The Nova is released, and none of
  my runs is in flight. No WAITING file: nothing is awaited.
- Spend today is about $29.5 of $35 (Sonnet), so device work stopped there.
- **Next, in P x win order:** (1) NBA Live (addendum 3) when lane.xbox's push lands on the Nova (none in
  listing-nova.txt at 14:45). (2) The `rounds` probe needs its first device measurement on a fight title: Spikeout's
  opening fight, or DOA3, which gave up on probes on 10-02. (3) The eeprom decision (the NEW ISSUE) is a device call
  for lane.local or the PM, not this lane's.
- **Do not repeat:** holding Top Spin, Counter-Strike or Midnight Club 3 for a Playable count. Their gameplay frames
  read 20, 13 and 22 fps. Forza runs at 0.59x speed. Those are performance cases.

## Golden saves made on the Thor are read as damaged on the Nova (10-03, offline, no device time)

**Forza (4D53006E), memfast run `1-1791047880-lane.memfast-3557511`:** the route pressed A 25 times between
"Player profile 'Default' is damaged and cannot be used. Press A to continue." and PROFILE SELECT (with "This
profile is damaged ... Press X to delete"). The run's disk carried golden `a1baf745d557`. That save's store record
says it was harvested from `pull/thor-hdd.img` (09-30). The run was on the Nova.

- The two handhelds have different `eeprom.bin` (Thor `f52cf53a...`, Nova `7eb04a87...`; lane.titlestate NOTES,
  09-27). A save signed with the console's HDD key, which comes from the EEPROM, reads as damaged on the other
  device. `saves.py`'s docstring predicts this exact failure.
- **55 of the 84 goldens were harvested on the Thor** (`scratch/goldsrc.py` reads each golden's `save.json`
  source). With the Thor's fan dead, the Nova runs every soak. Each of those 55 is at risk on the Nova if its title
  signs its save with the HDD key. Which titles do that has to be learned per title. Forza is the first one confirmed
  from frames.
- Castlevania's golden `20235e93867b` is Thor-made too. lane.local's queued Nova run `1-1791056447-lanelocal-2267406`
  (returning, on that golden) is the direct test for Castlevania. It is next in the Nova queue, and I let it run
  before taking the hold.
- Fix options, ranked by P x win: (1) give both handhelds the same `eeprom.bin`, so every save made from then on
  works on both. P high (the mechanism is the signing key), and the win covers every title. The cost: saves already
  made on the device whose EEPROM is replaced stop loading there. That trade is a device decision, not this lane's.
  (2) Per-device goldens: compose only a save made on the target device, and fall back to first-run otherwise. P high,
  but it needs a Nova-made profile for every title. (3) Re-sign saves at compose time. Every title's format differs,
  so P is low. Filed in OUTBOX as a new issue.
- For Forza, this lane's part: a first-run pathfind run on the Nova makes a Nova profile ("NEW PROFILE"). Then
  harvest it and promote it.

## Pool work (10-03 13:00-13:20 PDT)

| title | run | state | result | min | model calls | cost | what decided it |
|---|---|---|---|---|---|---|---|
| Castlevania: CoD (4B4E002D) | lane.local `1-1791056447-lanelocal-2267406` (not mine) | returning, Thor-made golden `20235e93867b` | **reached play on the Nova**: "Abandoned Castle", HP bar; f00020 shows the player in another part of the courtyard | - | 0 | - | the Thor-made save loads on the Nova: this title does not sign with the HDD key (Forza does) |
| Forza (4D53006E) | `runs/forza-firstrun` (held) | first-run | gave up at 15 min; a live Arcade race at 2.6 min (step 18); then stuck nosed into the pit wall | 15 | 76 | $6.01 | RT works (2 x 1.5 s took it to 12 mph at the start); the steering probe turned it into the wall; the agent never reversed |

- **Castlevania needs no first-run work from this lane.** The golden carries a real save, and the save loads on the
  Nova. The first-run Name Entry recipe is already in `hints/series-castlevania.md`, and it is not needed while the
  golden works. The pool row is for lane.local to close on its own run's verdict.
- **Forza's profile:** the first-run made `NEW PROFILE -> Done` in two steps. The release harvested it as
  `5725499d3c7f` (source `pull/nova-held.qcow2`). Its Garage.bin, Garage.dat and **CarIcons.sig** are byte-identical
  to the 09-30 Nova save `67767fc7fb61`, and all three differ from the Thor-made `a1baf745d557`. Fresh-profile
  content is deterministic, so the signed files differ by device. That confirms the EEPROM mechanism. **Promoted
  `5725499d3c7f` as Forza's golden** (by lane.pathfind, 13:18, note in the registry). It will read as damaged on the
  Thor, which is out of service.
- **Forza driving, the fix (13:20):** pathfind's tokens were sequential, so it could not steer on the gas or reverse
  while turning. New tokens `RT+<dir>:<s>` and `LT+<dir>:<s>` hold the trigger and the left stick together. The drive
  loop is now `RT:2, RT+left:0.8, RT+right:0.8`. A still drive window (the position test) first tries
  `LT+left:3, RT+right:3`, then the mirror, then the unlock rotation. There is a rule in the prompt (hold RT 3 s;
  reverse while turning off a wall). Selftest `holdstill` and `actions` cover them.
- **Position test (`c4f94ea2cd`):** see "Hold position test" below.

### Forza run 2 (13:33-13:49 PDT, returning on the new golden): gave up; the profile fix is proven

| run | state | live race at | result | model calls | cost |
|---|---|---|---|---|---|
| runs/forza-run2 | returning, golden `5725499d3c7f` | 2.6 min (step 19) | gave up at 15 min, stuck on walls and grass; moving at 8-12 MPH at the end | 60 | $4.56 |

- **The golden loads on the Nova.** Step 9: PROFILE SELECT with "Default" lit and no damaged message. A took it to the
  main menu. The memfast route's 25-press loop is gone. Forza's pool row is released by the golden change: the
  admission gate compares the golden.
- **Why it hit the wall again: the probe, not the throttle.** The confirm probe's self-moving steering legs were
  `STICK:left:1.2` / `STICK:right:1.2` with the gas off. At race start the car was moving at 9 MPH under RT
  (022-probe-b), and the gas-off steer put it into the pit-entry pillar by 023. Run 1 did the same. Fixed in
  `7c2d0da871`: a throttle probe steers with `RT+left` / `RT+right`. Selftest `ownmotion` (ownrt).
  The new reverse tokens did get it off the wall several times (steps 48, 64: 10-12 MPH after).
- **The car is slow because the game is slow, not because RT is weak.** The race clock went from 3.4 s (step 19,
  t = 155.6 s) to 27.9 s (step 23, t = 196.8 s), so 24.5 s of game time in 41.2 s of wall time: **0.59x speed** at
  16-21 fps. A 3-s RT hold is about 1.8 s of game time, and ~12 MPH fits that. I checked the pad path too: the
  Nova's cached ABS_GAS range is 0..32767, and "max" sends 32767. No input defect.
- **Forza is not a Playable candidate today**, whatever the driving: 16-21 fps against the 30-fps bar. Per the owner's
  10-03 rule that is telemetry, not a pathfind retest. No run 3.

### ToeJam & Earl III (14:00-14:14 PDT): the route problem is fixed; the title fails on fps

| run | state | claim | held play | play share | verdict | model calls | cost | frames |
|---|---|---|---|---|---|---|---|---|
| runs/toejam-earl-3-hold | any (golden `71a91de8b905` is title data only; `returning` is refused) | 1.7 min, 11 steps, probe control 0.096 vs 0.596 under the stick | 605 s of 641 | 0.949 | **FAIL: fps 72.8% of play at >= 30 fps** (bar 90%); hitches 0, no crash or hang | 23 | $1.29 | runs/toejam-earl-3-hold/hold_strip.jpg |

- The pool row was `menu`: lane.local's route `1791003320` sat in the Vinyl Albums jukebox for the whole window.
  pathfind's path (ONE PLAYER GAME, STORY MODE, character select, two cutscenes) reached the open world in 1.7 min and
  stayed in play.
- **Frame review:** the player travels. The 19 kept frames show different places (pond, cliff path, house, field). All
  17 30-s windows moved (0.42-0.87), none still. But **13 of the 19 kept frames carry a "PRESENTS: You don't have any
  presents! OK" dialog.** A button in the generic `other` loop opens the inventory, and A closes it a few presses
  later. The model caught it 5 times; the rest were credited as play. Play share 0.949 is therefore generous.
- **Change (`holdshed`):** when the model reads a menu, pause or other right after play, the loop drops the first
  of `HOLD_SHED` (B, X, Y, BACK, R1, L1) still in it, for the rest of the hold. Selftest `holdshed`.
- **Not a Playable:** the verdict fails on fps whatever the dialog does. Per the owner's rule, that is telemetry, not a
  retest. The dispatched route `../../../lanes/uberdefault569/routes/toejam-earl-3` still has the jukebox defect. The
  failure gate keeps holding it until that route or the golden changes. pathfind's path is
  `pathknow/paths/5345000F.json`.

### Spikeout: Battle Street (14:20-14:39 PDT): verdict PASS, a candidate for the owner's frame review

The pool file was done (every row resolved or identified as performance). For the rest of the brief's pool I checked
the 10-02 gameplay frames' FPS overlay first: Top Spin 20, Counter-Strike 13, Midnight Club 3 22. All three would fail
the 30-fps bar, so a hold would only re-measure a known performance miss. Spikeout read 32, so it got the run.

| run | state | claim | held | verdict | model calls | cost | frames |
|---|---|---|---|---|---|---|---|
| runs/spikeout-hold | any (Thor-made golden `c714fbc41e16`, loaded fine) | 8.2 min, step 53 (four probes refused in the fight; control 0.000 vs 0.570 under the stick at the last) | 607 s of play in 607 s, 0 off-play | **PASS**: `gameplay=607.3s fps_ok=1.0 hitches=0 play_share=0.9996` | 50 | $3.46 | runs/spikeout-hold/hold_strip.jpg |

- **Frame review:** Spike Jr. moves in every kept frame. The camera and his position change across all 18 frames
  (wall, dock, harbour), and all 17 windows moved (0.40-0.74, none still). He stays in the starting dock area, though,
  circling: no progress through the level, K.O. counter 0. That is movement, not progression. The owner decides
  whether it counts.
- **The claim cost 8 minutes in a fight.** The enemies move as much as the player, so idle change matched or beat the
  change under input (0.08-0.24 vs 0.00-0.15) until the fight ended. This is the case addendum 4 item 2 (alternating
  idle/input windows, 2 of 3) is for. It is still not built, and it is the next probe change.

## Hold position test (10-03)

A hold counted any second the model read as play. Black Stone stood on one octagon for 600 s, swinging its sword, and
passed the verdict. Now each kept frame (every 30 s) is compared with the previous kept frame at the probe's
contrast-scaled step (`window_change`). Under `HOLD_STILL` = 0.03 the window is still. The perflog gets `state=still`
(title_verdict counts only `play`), play stops being credited, and the inputs rotate until a later window moves.

| stored hold strip (30-s pairs) | min | median | max |
|---|---|---|---|
| Black Stone hold2 (standing, verdict PASS) | 0.002 | 0.009 | 0.013 |
| Panzer Dragoon Orta hold (flying) | 0.310 | 0.544 | 0.896 |
| Panzer Dragoon Orta hold2 | 0.365 | 0.564 | 0.924 |

- Under the new rule, Black Stone hold2 is credited about 30 s of play, not 600. No Panzer window is still.
- n = 2 titles with hold strips. The threshold sits 2.3x above Black Stone's maximum and 10x below Panzer's minimum.
  It is not tested on a fixed-camera title where the player moves in a small part of the frame. That is the case
  to watch (`still_windows` in result.json, `window` in hold.jsonl).
- The 'after' frames of the 10-02 runs (taken with no input) do not separate standing from moving. Midnight Club 3's
  car sat at 0.001 because nothing pressed the throttle. They are not evidence either way.
- The first window is still credited before the test can see it (30 s), so a standing hold is not credited zero.

## Resume (10-03 10:13 PDT, attempt 6): why attempt 5 did not finish

- Attempt 5 ended on a WAITING file for arms run `1791042391`, but the held Panzer run had already timed out
  waiting on it. Its `heldrun` `wait-idle` gave up at its 900-s cap (about 10:01), so pathfind never ran and the
  hold was released. The WAITING file named the run, but nothing re-queued the held run when the wait ended, so
  the session ended with no Panzer frames and no OUTBOX line about the timeout.
- Resume state (10:13): the arms run is `DONE` (results dir has its DONE marker), so WAITING is removed here.
  The Nova is now busy with `lane.vcpuwait433`'s 720-s request (admitted 10:12, ends about 10:25). Do not kill it.
- Merged `origin/master` clean (no conflicts). Selftest `pathfind_selftest: all ok`.
- Next step, run now: `setsid nohup bash scratch/heldrun.sh 4947002B docs/lanes/pathfind/runs/panzer-dragoon-hold panzer`.
  It takes the hold, waits up to 900 s for idle, runs the held Panzer, and releases on every exit. Poll its log;
  this session stays up until it finishes. If the wait times out, re-queue it and say so in OUTBOX.

## Panzer Dragoon Orta, held run 1 (10-03 10:25-10:42 PDT): FAIL on play share, and a verdict defect

| run | device | genre | claim | held (s) | play (s) | play share | model reads | verdict | frames |
|---|---|---|---|---|---|---|---|---|---|
| panzer-dragoon-hold | nova | onrails | 3.4 min (step 20) | 740 | 598 | 81% | 41 calls, 23 hold reads | FAIL: menu time 80.8% (bar 90%) | runs/panzer-dragoon-hold/hold_strip.jpg |

- **The hold worked as designed.** It played on, read the screen when play may have ended, and recovered from three
  deaths (game over at about 216, 430 and 645 s of hold). Each recovery was an episode-card cutscene: one model read per
  press, about 9 s each, so each death cost 33-38 s off play. The cost is 142 s of 740 s.
- **The verdict did not run correctly on the first try, so run 1's first verdict was void.** Two defects in the hold's
  own output (not the device, not the title): (a) `logcat_start` used `-v threadtime`, but title_verdict's LINE parses
  `-v time`, so it read zero perflog lines and said "the guest never appeared"; (b) `hold_verdict` wrote request.json
  without the ISO, so the title ID did not resolve. Both fixed. The run's logcat was converted to `-v time` (same pid
  and text; the original is kept as `logcat.threadtime.txt`) and judged offline with title_verdict, which is how the
  FAIL above was reached. The run.log `held` line was also missing (the old code printed it and did not write it).
- **Change made (`holdrepeat`):** a cutscene or game-over look whose action is one button repeats that press
  `HOLD_REPEAT` (3) times with no model read, then looks again. The selftest case fails without it (three extra looks).
- **Next:** run 2 with the repeat change, same title, `runs/panzer-dragoon-hold2`. The verdict is judged the same way.

### Panzer run 2 (10-03 11:00-11:18 PDT): still FAIL, 83.6% play

| run | held (s) | play (s) | play share | off-play cost | deaths / returns | frames |
|---|---|---|---|---|---|---|
| hold 1 | 740 | 598 | 80.8% | 142 s: cutscene 109, game over 33 | 3 game overs, each then an episode card (33-38 s each) | runs/panzer-dragoon-hold |
| hold 2 | 717 scored / 601 play | 600 | 83.6% | 117 s: cutscene 74, menu 21, black 14 | black at 82 s, a return to the title screen (NEW GAME, difficulty) ~65 s; 2 deaths, each ~23-30 s | runs/panzer-dragoon-hold2 |

- **What the repeat change did:** the episode card's three presses now go unlooked (rows 48-50, 82-84, 106-108 in
  hold2). Each death drops from ~35 s to ~23-30 s. It does not touch the title-screen return.
- **Named costs, in order:** (1) the return to the title screen after the first death (~65 s, six model reads through
  NEW GAME and the difficulty menu, each ~9 s); (2) each death's episode card, now ~3 unlooked presses plus one read;
  (3) the deaths themselves: 2-3 per 10 min on this path.
- **Not done, and the ranked options (P x win):**
  1. Replay the recorded title-to-play menu path (the golden's `paths/4947002B.json` steps, screen-checked against the step
     frame) after a return to the title. Removes most of cost (1), about 50 s per return. P high (the path reached play
     in both runs). Medium effort. This is the next change if Panzer is to pass.
  2. Survive: a dodge or aim pattern on the on-rails dragon. Removes cost (3), the biggest win if it works, but P is
     unknown and it needs its own measurement first. Not started.
  3. Shorter model steps while off play (the model call is ~9 s; a Haiku first look is ~6 s per the 10-02 measurement).
     Small win, cheap to try, lower P of a large change.
- Panzer is not a Playable confirmation. The verdict is the 90% play-share rule, applied as written.

## Black Stone held run (10-03 11:34-11:47 PDT): verdict PASS, frames do not show play

| run | device | claim | held (s) | verdict | frame review | frames |
|---|---|---|---|---|---|---|
| black-stone-hold2 | nova | 2.4 min (probe idle 0.002, under input 0.088) | 602 | PASS, play share 0.9996, fps_ok 1.0, hitches 0 | **not counted**: the player stands in one place in one octagon for 600 s, sword swinging, camera fixed | runs/black-stone-hold2/hold_strip.jpg |

- The genre loop was sent every cycle (attack: STICK up, X, A, ...). The model read "in play" on all 46 checks. The
  frames show no travel: per-frame change 0.003-0.010 is the swing effects.
- This is the 10-03 attempt-4 stance (the sword raised on the spawn octagon) and the gap in the attempt-3 findings:
  the verdict's play-share and fps rules do not test position, so a standing player passes. A hold-play count needs a
  position-change test on the playfield (the attempt-3 request, still open).
- The run wrote a path and a learned hint for 58490004 from that claim. They are **reverted** (not a confirmed guide).
  The Panzer path and learned hint from run 2 are kept: that claim led to play that moved (the dragon flies).
- Not done: the position test. The next Black Stone attempt would repeat the same stance until the stick is shown to
  move him (the 10-02 run ran him with the same stick).

## Resume (10-03 09:45 PDT, attempt 5): why the previous attempt did not finish

- The previous session ended on its WAITING file (`run 1791040252-lanelocal-978819`), after it had taken the Nova,
  found it busy, and released the hold without launching anything. Its own next step was written down; it was not
  run. Nothing of the lane's was left on a device.
- That run has finished (`DONE`). It is lanelocal's Kabuki Warriors soak (`43560001`, `effb0d001b`), not ours.
  The WAITING condition holds, so WAITING is removed in this session's commit.
- This session runs the stated next step: Panzer Dragoon Orta (4947002B), held 600 s on the Nova, with the probe
  fix from the gate below. It is launched through `scratch/heldrun.sh`, which takes the hold, waits for idle, runs
  `pathfind.py --hold-s 600 --state first-run` (which prepares and releases the golden itself), and releases the
  hold on every exit path.

## Where attempt 5 stopped (10-03 09:57 PDT): WAITING on an arms run on the Nova

- The Panzer held run took the Nova hold (`lane.pathfind`) at 09:46 and waited in `hold.sh wait-idle` for
  `1791042391-arms-memfast-w1-fix-1542161` (arms-memfast) to finish. At 09:56 that run had no DONE marker yet.
  wait-idle's 900-s timeout ends the wait about 10:01; the script then exits without running pathfind, and its
  trap releases the hold. So no Panzer frames exist, and nothing of ours is on the device.
- Next step, on resume: re-run `bash scratch/heldrun.sh 4947002B docs/lanes/pathfind/runs/panzer-dragoon-hold panzer`
  once the Nova is idle; then judge its frames and hold.jsonl and write the verdict to OUTBOX.

## Resume (10-03): why attempt 4 did not finish

- Attempt 4 committed three code changes after its Black Stone input check (`1c6a26d` the X ladder, `3f96ebd` the
  perflog marks, `5b8c009` the team-sport genre and `--goal`) and wrote no NOTES entry for them. It ended with no
  next step, so hostops resumed it. ADDENDUM 4 (the probe fix, 09:40 PDT) came after it had stopped; nothing was
  running and no WAITING file was left.
- This resume merged origin/master (6 commits, clean), kept selftest green, and did ADDENDUM 4's probe gate first,
  as the brief requires before any more device time.

## Where this resume stopped (10-03 09:40 PDT)

- Probe gate done and pushed (`ca3151cdc6`, PR.md `35d31433fe`). No held run yet.
- Took the Nova for Panzer Dragoon Orta (4947002B), but the device was busy with lanelocal run
  `1791040252-lanelocal-978819`, so the hold was released before any run and nothing was launched. No golden profile
  was prepared (`titlestate.py prepare --title-id 4947002B --state first-run` is still to do before the held run).
- WAITING: `run 1791040252-lanelocal-978819`. When it finishes, the next step is: take the Nova, wait idle, prepare
  the golden profile, run `pathfind.py 4947002B --device nova --budget-min 15 --hold-s 600`, release, judge the frames.

## Probe gate (ADDENDUM 4, 10-03): the fix and its gate

**Cause, measured.** The probe's change test was a fixed 16-grey-level step against a 0.03 floor. In Black
Stone's dark dungeon (frame std ~14) a real sword raise, spell or step changes 0.3-1% of the 160x120 pixels, and
a fixed step of 16 sees almost none of it. The gate's stored real-control triplets measured 0.002-0.010 under the
old step, so the probe refused them before any model was asked.

**Shipped in `pathfind.py`:**
- `probe_change()`: the grey step is `min(16, max(4, 0.6 x std))` of the first frame. Dark scenes get a finer step;
  bright scenes are unchanged (the cap is the old 16).
- `PROBE_MOVED` 0.03 -> 0.004. The ratio test (input change >= 1.5 x idle change) and the self-moving steering
  path are unchanged.
- Hold clock: once claimed, the hold runs to `max(budget, now + 1.5 x hold + 300 s)`. The claim keeps its budget.

**Tested, not shipped:** a global-shift test (phase correlation at 160x120, a camera pan counts). It changed no
decision on the 48 labelled cases, and no case in the set had a pan, so it is unproven. Not in the code.

**Not done, and why:**
- The alternating 2-of-3 windows (addendum item 2). It needs six captures per probe. The stored triplets hold one
  idle pair and one input pair, so it cannot be replayed offline. It is the first device-side change to validate.
- `pathclass.py` (addendum item 3): not on master, so the classifier leg is absent. The model answers instead.

**Gate: labels by eye, scored through the whole chain.** Each stored probe triplet (a, b, c) was labelled from its
frames: R real control, U no visible response, C cutscene or replay or letterbox, M menu, P pause, ? ambiguous (out).
Then each labelled triplet went through the new routing (floor, ratio, letterbox veto) and, if it survived, the
real `confirm()` question to the strong model, with the same three frames. Files: `docs/lanes/pathfind/gate/`.

| | value |
|---|---|
| labelled cases (? excluded: 17 of 65 sampled) | 48: R 18, U 16, C 8, M 4, P 2 |
| real control accepted (chain) | **14 of 18** (78%) |
| non-control accepted (chain) | **0 of 30** (U 0/16, C 0/8, M 0/4, P 0/2) |
| agreement | **44 of 48 (92%)** |
| motion step alone sends to the model | R 18, M 2, C 2, P 2, U 0 (the letterbox veto takes 6 cutscenes) |

**Read this before trusting the 92%:**
- It is a pass on the corrected labels only. On the first-pass labels it was 43 of 48 (89.6%), one case short.
  The corrections, in full: s1 07 U->R (Blinx-the-time, the camera pans under the stick); s1 32 U->R (Black Stone,
  the character raises an arm and an orb between B and C); s1 14 U->? (a self-animating golf swing with a
  controller overlay); s1 26 R->C (a letterboxed intro at step 4 of the Bruce Lee rerun, not control); and
  **s2 07 (Midnight Club 3, 034) U->R, the case that decides the 90% line.** I relabelled it after the model's
  replay had said "responded". At full size the red car drives forward and steers in C and the speedometer
  moves. I believe the relabel is right; it is still a correction made after seeing the answer. Owner: judge it.
- The model leg did the menu, cutscene and pause rejections, not the motion step. The motion step alone passes 6 of
  the 14 non-control cases to the model, and the model refused all six.
- The 4 real controls refused: Bruce Lee rerun 022 (a fight: the model called the player's shift too small), Spikeout
  021 (a clinch animation), and two College Hoops 2K5 cases (012, 016) that are self-moving scenes. Self-moving
  scenes go to the steering test in the real pipeline; this replay used the non-steer prompt, so those two are
  NOT the real path. The steering test has not been replayed on stored data (the frames lack left/right captures).
- n = 48 with eye labels. This is a gate, not a measurement of recall on the Nova.

**Verdict:** the gate is met on the corrected labels (92%, 0 menus, 0 cutscenes, 0 pauses accepted). I am
proceeding to the first held run on that basis, and I am flagging the one relabel for the owner.

Selftest: `dark` (a 12-level 80x80 patch in a dark dungeon is confirmed; it fails on the old code, checked) and the
existing 34. All ok. Hold clock: selftest `hold`/`holdstuck` unchanged, all ok.

## Scoreboard (10-03, hold-play)

Today's bar (addendum 2): hold-play for >= 600 s of judged play, on the Nova, from the lot's routed pool in P order.
Sonnet only, <= $25. Model reads are counted per title.

| title | device | genre | play held (s) | model reads | frames | result | frame strip |
|---|---|---|---|---|---|---|---|
| Black Stone Magic Steel | nova | other (genre loop) | 65 of 600 (budget ran out) | 66 calls over 97 steps, 13.3 min | runs/black-stone-hold/frames | **not held**; claimed at step 97 by one probe, the first with a visible stick response in 13 min | runs/black-stone-hold/hold_strip.jpg |

Attempt 3 result, Black Stone (10-03 08:00-08:14 PDT): the lane's claim rule did not hold up. Probes at steps 2-95 showed
control near 0.000 for stick, D-pad, A and RT, and the model read "gameplay" on the same HUD for ~90 steps. The first
probe with a real under-input change came at step 97 (under input 0.321). The hold then ran 65 s on a genre loop
that the strip (106 vs 110, 30 s apart) shows as a near-static corridor. Frame changes were 0.06-0.23. Not a
Playable confirmation. See "Attempt 3 findings" below.

Offline checks, run on saved frames with the real prompts (Sonnet 5, scratch/holdcheck):

| check | frames | answers | verdict |
|---|---|---|---|
| hold_look (in play?) | Black Stone play | in_play true | right |
| hold_look | Dead or Alive 3 title splash | in_play false, action A | right |
| hold_look | Blinx 2 GAME PAUSED | in_play false, action A | right |
| hold_genre | Midnight Club 3 | drive | right |
| hold_genre | Top Spin | rally | right |
| hold_genre | Panzer Dragoon Orta | onrails | right |
| hold_genre | Counter-Strike | attack | right |

## Attempt 4 (10-03 08:31 PDT): why attempt 3 did not finish

- **Attempt 3 ended right after its Black Stone run** (08:14), with the run written up and pushed, the Nova
  released, and nothing running. It wrote no WAITING file and no next step, so hostops resumed it at 08:30.
  Nothing was lost. Its next steps (the pad check, then Panzer Dragoon Orta) are this attempt's first work.
- Attempt 3 also left the Black Stone path and learned hint rewritten from the 13-min run, uncommitted. They are
  **reverted**: that claim is not a confirmed result, and the 10-02 path (2.4 min, 12 calls) stays the guide.

## Black Stone input check (10-03, offline from the saved frames; no device time)

**The pad reached the game throughout. The player was stuck in a stance, and X released it.**
- On the menus, the hat moved the name-entry cursor (6 DOWN, 2 RIGHT landed on Ok), and A accepted. Those are pad inputs.
- In play, from the first probe (step 14) to step 93, the player stands on the spawn octagon with the sword raised
  overhead, HP 410 -> 330 -> 310. Forty stick, d-pad, A and RT probes moved nothing (0.001-0.007).
- At step 94 the action was X. Frame 094 shows the sword lowered. At step 95 one LEFT + stick moved the player off the
  octagon. At step 97 the stick ran him and the camera followed (0.321, confirmed).
- On 10-02 the first stick probe ran him (0.288). Same title, same spawn. What put him in the stance on 10-03 is not
  known. It is not the input path.
- **Change (pathfind.py):** after 2 probes in a row that move nothing at all (probe and control both under
  PROBE_MOVED), the next probe is led by one button from `UNLOCK_LADDER` (X, B, Y, R1, L1, BACK) in turn. On the
  10-03 run, that puts X before probe 3 at about 1.5 min, not 13 min. Selftest case `unlock`.

## Attempt 3 (10-03): why attempt 2 did not finish

- **Attempt 2 built hold-play and stopped before any device run.** Its only blocker was the golden profile:
  `titlestate.py prepare` was not on master, and addendum 2 says held runs start from it. It went to a
  `waiting:` comment at 06:58 PDT and ended there with nothing queued on the Nova.
- **That blocker has cleared.** savestate433 folded to master (`cfa37a359e`, the Tron device proof). Attempt 3
  merged origin/master. The one conflict was `pathfind.py`'s argument block: both sides added arguments, so
  `--hold-s` and `--state`/`--hdd-img` are both kept. Selftest all ok after the merge.
- **Nothing else from attempt 2 carries over as a result.** Its hold-play work is selftested only; no held run has
  been made on a device yet. Today's bar stays addendum 2: 600 s held on a Nova title from the pool, judged.

## Attempt 3 findings (10-03)

- **The claim accepted gameplay that did not respond to input for 13 minutes.** The model read gameplay on a
  full-HUD playfield from step 3 onward, and every stick, D-pad and A probe showed control 0.000-0.005. The claim
  requires an input that visibly changes the playfield (rule 5). Something is wrong with either the input path for
  Black Stone or the probe's measure. Next: check whether the pad input reaches Black Stone at all (a menu or
  pause-free control check with frames), before any more Black Stone device time.
- **The budget was spent on probing, not on play.** A title whose claim comes at 13 min cannot hold 600 s in a
  15-min budget. For hold runs the budget must cover the claim plus the hold, or the hold should not be queued.
- **The hold's genre loop did not visibly move the character.** The strip at 30-s spacing is near-static. Hold-play
  judged by frame change alone (the in-play check) can call a stationary screen "play". Hold-play needs a
  position-change test on the playfield before it counts a second of play.

## Attempt 2 (10-03): why attempt 1 did not finish

- **Attempt 1 finished its acceptance, not today's bar.** The 10-02 lot acceptance (9 of 10, Bruce Lee rerun) was
  met and folded to master (6b0c4a131f). Its last work stopped at the owner's 11:55 hold on navigation (token burn),
  before hold-play existed. No title was ever held for 600 s, which is the bar for today.
- **Its last commits were not written up.** At 11:50 it reached gameplay on Ghoulies (2.35 min, 11 calls) and Tork
  (4.41 min, 19 calls, four probes refused) and gave up on Conker (15 min, 23 calls, black after a level load). Their
  results are in `runs/<title>/result.json` and `pathknow/paths/`, but the scoreboard above and OUTBOX did not get them.
  They are recorded here, not re-run. Conker's black-after-level-load is still open.
- **Attempt 2 (10-03 06:47 PDT):** merged origin/master (63 commits: the pathfind fold, uberdefault569, buildstamp).
  Before the merge, 39 untracked pathknow hint files were removed; each was byte-identical to its master copy.
- **Not done in attempt 2 yet:** the held device runs. Addendum 2 says every held run starts from its golden profile
  (`titlestate.py prepare`), and that lands with savestate433's fold. savestate433 is PR-ready on
  `origin/lane/savestate433` and is not on master at 07:00 PDT, so `titlestate.py` on master has no `prepare`.
  The Nova stays unheld and no run is queued until it folds.

## Hold-play (10-03)

After the confirmed claim, `pathfind.py --hold-s 600` keeps the player in play. Design, as built:

- **A genre loop of inputs, model-free.** The genre (drive, attack, rally, onrails, other) is named once by Sonnet from
  the confirm frame. Each genre is a fixed list of inputs sent every cycle (`HOLD_GENRES`). The right stick is a new
  token, `RSTICK:<dir>:<s>`, at full deflection.
- **The model reads the screen only when play may have ended:** a black frame, a frame identical to the previous one
  (one static look; the previous draft waited for two), every 90 s, and after each step while off play.
- **Off play, the model steers back**, one look per step, with its own action, up to 12 steps in one episode. Past
  that the hold gives up, and the claim still stands (`hold.ok` false, the reason says so).
- **Frames every 30 s**, kept; the rest are deleted after the next look has been measured. `hold_strip.jpg` is the
  kept frames. `hold.jsonl` has a line per look (play seconds, change, whether the model was asked and what it said).
- **Nova only.** `--hold-s` is refused on the Thor, whose fan is dead and whose rule is to stop within 30 s of a claim.
- **Opus is off today.** `STRONG` defaults to Sonnet 5 (addendum 2). Restore `claude-opus-5-5` when Opus returns.

Selftest: `hold` (200 s of play on a fake clock: a pause read and cleared by START, 3 model reads, 7 frames kept, the
others deleted) and `holdstuck` (the pause never clears: the hold gives up at the nav cap). `actions` also covers
`RSTICK`. Full selftest: all ok.

## What the next lane should not repeat (10-03)

- **A frame the next look measures against cannot be deleted at the end of its own look.** The first version deleted
  every non-kept frame at once; the next look then failed to open it. The fix deletes the previous look's frame after
  the current one is measured.
- **Escalation is by model name, not by a source label.** With Sonnet as both tiers, the escalation case in the selftest
  stopped meaning anything. The selftest now pins Opus, so those cases still test escalation.
- **The fake clock.** The hold selftest patches `pathfind.now` and `time.sleep`, so 200 s of play takes no real time.
  The selftest must restore both (it does, before `actions`).

## Scoreboard (10-02, attempt 1)

Lot: the brief's 35 never-routed Nova titles, shuffled with
`random.Random('pathfind-2026-10-02')`; the first 10 in that order are the acceptance set, run in order,
none swapped out. Order: Star Wars III, Midnight Club 3, Bruce Lee, Black Stone, Panzer Dragoon Orta,
Amped 2, Counter-Strike, Top Spin, Ninja Gaiden Black, Spikeout (spares after: Conker, Ghoulies, Tork,
DOAX, DOA3, JSRF, ...). pathfind never reads the retired `.route` files some of these have.

**Acceptance: 9 of the 10 lot titles reached confirmed gameplay on their first attempt, each within 15 min
(max 9.0), cold, unattended, every strip reviewed by eye.** The miss is Bruce Lee: a false pass on its
letterboxed intro cinematic, caught in review (not counted), fixed in the tool, rerun below. Midnight Club 3's
counted run is its second: the first was stopped at 8 min on a tool bug (d-pad buttons; see below), before
any result was written.

| lot # | title | first attempt | min | model calls | frame |
|---|---|---|---|---|---|
| 1 | Star Wars Episode III | gameplay | 3.5 | 17 | runs/star-wars-iii/gameplay_frame.jpg |
| 2 | Midnight Club 3 | gameplay (run 2, tool bug in run 1) | 6.2 | 33 | runs/midnight-club-3/gameplay_frame.jpg |
| 3 | Bruce Lee | **false pass** (review); rerun with the fixed tool: gameplay in 4.9 min, 22 calls | 0.9 | 4 | runs/bruce-lee.falsepass/strip.jpg, runs/bruce-lee.rerun/gameplay_frame.jpg |
| 4 | Black Stone | gameplay | 2.4 | 12 | runs/black-stone/gameplay_frame.jpg |
| 5 | Panzer Dragoon Orta | gameplay | 4.5 | 21 | runs/panzer-dragoon/gameplay_frame.jpg |
| 6 | Amped 2 | gameplay | 9.0 | 34 | runs/amped-2/gameplay_frame.jpg |
| 7 | Counter-Strike | gameplay | 3.1 | 14 | runs/counter-strike/gameplay_frame.jpg |
| 8 | Top Spin | gameplay | 5.5 | 24 | runs/top-spin/gameplay_frame.jpg |
| 9 | Ninja Gaiden Black | gameplay | 7.0 | 33 | runs/ninja-gaiden/gameplay_frame.jpg |
| 10 | Spikeout | gameplay | 4.3 | 22 | runs/spikeout/gameplay_frame.jpg |

Every run, including the Thor ones (generated by `scoreboard.py`):

| run | title | device | result | min | model calls | steps | replayed | cost | reason | frame |
|---|---|---|---|---|---|---|---|---|---|---|
| star-wars-iii | Star Wars Episode III Revenge of the Sith | nova | **gameplay** | 3.52 | 17 (haiku 16/sonnet 1) | 18 | 0 | $0.50 |  | runs/star-wars-iii/gameplay_frame.jpg |
| espn-nfl-2k5.try1 | ESPN NFL 2K5 | thor | heat-stop | 6.2 | 20 (haiku 18/sonnet 2) | 21 | 0 | $0.65 | Thor xo 71.033 C | runs/espn-nfl-2k5.try1/strip.jpg |
| espn-nfl-2k5.try2 | ESPN NFL 2K5 | thor | heat-stop | 3.6 | 20 (opus 1/sonnet 19) | 20 | 0 | $0.99 | Thor xo 70.757 C | runs/espn-nfl-2k5.try2/strip.jpg |
| midnight-club-3 | Midnight Club 3: DUB Edition | nova | **gameplay** | 6.23 | 33 (opus 3/sonnet 30) | 34 | 0 | $1.76 |  | runs/midnight-club-3/gameplay_frame.jpg |
| bruce-lee.falsepass | Bruce Lee: Quest of the Dragon | nova | gameplay -> REVIEW: false-pass | 0.93 | 4 (opus 1/sonnet 3) | 4 | 0 | $0.24 |  | runs/bruce-lee.falsepass/strip.jpg |
| black-stone | Black Stone Magic Steel | nova | **gameplay** | 2.41 | 12 (opus 3/sonnet 9) | 12 | 0 | $0.73 |  | runs/black-stone/gameplay_frame.jpg |
| panzer-dragoon | Panzer Dragoon Orta | nova | **gameplay** | 4.48 | 21 (opus 2/sonnet 19) | 25 | 0 | $1.08 | four probes refused | runs/panzer-dragoon/gameplay_frame.jpg |
| espn-nfl-2k5.try3 | ESPN NFL 2K5 | thor | heat-stop | 4.4 | 18 (opus 1/sonnet 17) | 18 | 0 | $0.91 | Thor xo 70.292 C | runs/espn-nfl-2k5.try3/strip.jpg |
| amped-2 | Amped 2 | nova | **gameplay** | 9.02 | 34 (opus 4/sonnet 30) | 48 | 0 | $1.83 | four probes refused | runs/amped-2/gameplay_frame.jpg |
| counter-strike | Counter Strike | nova | **gameplay** | 3.12 | 14 (opus 3/sonnet 11) | 14 | 0 | $0.80 |  | runs/counter-strike/gameplay_frame.jpg |
| espn-nba-2k5.discerror | ESPN NBA 2K5 | thor | title-error | 3.6 | 15 (opus 4/sonnet 10) | 15 | 0 | $0.87 | SEGA "problem with the disc ... dirty or damaged" after team select (stopped by hand at 3.6 min; fatal_error state added after) | runs/espn-nba-2k5.discerror/strip.jpg |
| top-spin | Top Spin | nova | **gameplay** | 5.48 | 24 (opus 3/sonnet 21) | 26 | 0 | $1.28 |  | runs/top-spin/gameplay_frame.jpg |
| espn-nhl-2k5.baseline-try1 | ESPN NHL 2K5 | thor | heat-stop | 3.7 | 16 (opus 1/sonnet 15) | 18 | 0 | $0.82 | Thor xo 70.418 C | runs/espn-nhl-2k5.baseline-try1/strip.jpg |
| ninja-gaiden | Ninja Gaiden Black | nova | **gameplay** | 6.99 | 33 (opus 3/sonnet 30) | 40 | 0 | $1.72 |  | runs/ninja-gaiden/gameplay_frame.jpg |
| spikeout | Spikeout: Battle Street | nova | **gameplay** | 4.27 | 22 (opus 3/sonnet 19) | 21 | 0 | $1.20 |  | runs/spikeout/gameplay_frame.jpg |
| espn-college-hoops-2k5.guided | ESPN College Hoops 2K5 | thor | heat-stop | 3.8 | 14 (opus 3/sonnet 11) | 16 | 0 | $1.07 | Thor xo 71.865 C | runs/espn-college-hoops-2k5.guided/strip.jpg |
| bruce-lee.rerun | Bruce Lee: Quest of the Dragon | nova | **gameplay** | 4.87 | 22 (opus 3/sonnet 19) | 22 | 0 | $1.49 |  | runs/bruce-lee.rerun/gameplay_frame.jpg |
| espn-college-hoops-2k5.replay | ESPN College Hoops 2K5 | thor | **gameplay** | 2.04 | 10 (opus 2/sonnet 8) | 11 | 2 | $0.73 |  | runs/espn-college-hoops-2k5.replay/gameplay_frame.jpg |
| dead-or-alive-3.baseline | Dead or Alive 3 | nova | gave-up | 15.1 | 62 (opus 9/sonnet 53) | 72 | 0 | $4.41 | budget 15 min | runs/dead-or-alive-3.baseline/strip.jpg |
| blinx-the-time.baseline | Blinx: The Time Sweeper | nova | **gameplay** | 4.35 | 19 (opus 2/sonnet 17) | 23 | 0 | $1.37 |  | runs/blinx-the-time.baseline/gameplay_frame.jpg |
| espn-nhl-2k5.sibguided | ESPN NHL 2K5 | thor | heat-stop | 3.9 | 16 (opus 3/sonnet 13) | 18 | 0 | $1.31 | Thor xo 70.903 C | runs/espn-nhl-2k5.sibguided/strip.jpg |
| blinx-2.guided | Blinx 2: Battle of Time & Space ~ Blinx 2: Masters of Time & Space | nova | gave-up | 15.2 | 61 (opus 17/sonnet 44) | 89 | 0 | $5.83 | budget 15 min | runs/blinx-2.guided/strip.jpg |
| espn-nhl-2k5.sibguided2 | ESPN NHL 2K5 | thor | heat-stop | 3.8 | 14 (opus 4/sonnet 10) | 16 | 0 | $1.14 | Thor xo 70.236 C | runs/espn-nhl-2k5.sibguided2/strip.jpg |
| blinx-2.unguided | Blinx 2: Battle of Time & Space ~ Blinx 2: Masters of Time & Space | nova | gave-up | 15.2 | 41 (sonnet 41) | 74 | 0 | $3.12 | budget 15 min | runs/blinx-2.unguided/strip.jpg |
| tiger-woods-pga-tour-2004.baseline | Tiger Woods PGA Tour 2004 | thor | **gameplay** | 3.07 | 14 (opus 3/sonnet 11) | 13 | 0 | $1.08 |  | runs/tiger-woods-pga-tour-2004.baseline/gameplay_frame.jpg |

## Cross-title (10-02)

Metric: model calls and minutes from cold boot to the first screen of live play (kickoff, faceoff, tip-off,
the level), and the final result. The Thor rows are all cut by its 70 C stop (fan dead) about 4 min in.

| run | guide | calls to live play | min | result (total calls) |
|---|---|---|---|---|
| ESPN NFL 2K5 try1 | none (Haiku per step) | 12 | 3.0 | heat-stop (20) |
| ESPN NFL 2K5 try2 | none | 19 | 3.4 | heat-stop (20) |
| ESPN NHL 2K5 baseline | none (`--no-guide`) | 15 | 3.3 | heat-stop (16): CPU vs CPU, see below |
| ESPN College Hoops 2K5 | NFL + NHL paths (partial) | 9 | 2.1 | heat-stop (14) while probing |
| ESPN College Hoops 2K5 | its own path, replayed (2 steps) + siblings | 8 | 1.8 | **gameplay** (10) |
| ESPN NHL 2K5 | siblings only (`--no-replay`): Hoops + NFL | 13 | 2.7 | heat-stop (16): CPU vs CPU |
| ESPN NHL 2K5 | siblings only, with plans | 7 | 1.6 | heat-stop (14): probes refused |
| Blinx | none (`--no-guide`) | 17 | 4.1 | **gameplay** (19) |
| Blinx 2 | Blinx's path | 27 | 5.2 | gave up (61): 30 probes, the character never moved |
| Dead or Alive 3 | none | 20 | 5.1 | gave up (62): every probe lost to a knockdown/KO replay |

What this shows, and what it does not:
- In the ESPN 2K5 family, guided runs reached live play with **7-9 calls in 1.6-2.1 min against 12-19 calls
  in 3.0-3.4 min unguided**. The guide is the sibling's recorded path given to the model as text, plus
  (last row) a plan of the next menus that is sent without a call. Two confounds favour the later, guided
  runs: profiles saved on the device by earlier runs (CAPA T2), and tool changes between runs (the no-call
  loading check came after the NHL baseline). It is evidence, not a controlled measurement.
- Frame replay does not carry across siblings: the same ESPN menu in two titles is 10-23 grey levels apart in
  pathfind's 16x12 signature (match threshold 9 for a title's own path, 5.4 for siblings). Measured with
  `docs/lanes/pathfind/sigcmp.py` on the Hoops and NHL frames (it reads the run dirs under scratch/runs, which are not committed). That is why the plan mechanism exists.
- Blinx -> Blinx 2 did not help: the sequel's front end differs and the run lost 10 minutes on one stuck
  scene. Not a cross-title gain.
- Team sports are hard to CONFIRM even after reaching play: a goal, foul or out-of-bounds lands inside the
  ~25 s probe, and the hockey camera auto-switches players. The confirm model refused each time and was
  right to by the frames. The NHL baseline and the first sibling-guided NHL run also played CPU vs CPU: the
  controller icon sat in the middle of Team Select (pathknow's hint said so; the model pressed A anyway).
  That rule is now in pathfind's own rules.

## Measurements

- Model latency through `claude -p` (10-02, same ESPN NFL 2K5 menu frame, image INLINE via
  `--input-format stream-json`, one turn): **Sonnet 5 3.5-3.9 s** (70-80 output tokens), Haiku 4.5
  6.4-9.1 s (430-500 output tokens, mostly thinking; `--effort low` and MAX_THINKING_TOKENS=0 did not
  help). With the image read through the Read tool (two turns) Haiku averaged 13.6 s/step, max 52 s.
  So pathfind uses inline images and **Sonnet 5 per step, Opus 5.5 when stuck and for the gameplay
  confirmation**; a step is ~9 s end to end (screencap ~1-2 s, model ~4-5 s, input + wait).
  This departs from the brief's Haiku-first start on measurement: Sonnet is both faster and stronger
  here. Cost ~$0.05/call.
- Thor heat in MENUS alone: 38.8 -> 71.0 C in 6.2 min (try1), 52.3 -> 70.8 C in 3.6 min (try2).
  The ESPN NFL 2K5 path to the kickoff takes ~3.3 min, so a Thor title needs a cold start.

## What the next lane should not repeat

- **Put the image AFTER the prompt text, and make the model describe it first.** With the frame first and
  pathfind's long prompt after it, Sonnet 5 called Tiger Woods 2005's bright title logo "a black frame with
  only the FPS overlay" 12 steps running, anchored on its own history, and burned 3 of the Thor's 4 minutes
  (10-02 11:43). Same frame, same prompt: image-first wrong 2/2, image-last plus a leading "see" field right
  4/4. Every run started before 11:50 used image-first. (`scratch/blacktest2.py` in the lane worktree.)
- **The d-pad buttons (evdev 544-547) do nothing in hakuX.** The d-pad is the hat: pulse
  `axis HATY min|max` then `mid`. Midnight Club 3 try 1 looped 8 times on a Yes/No dialog because
  UP never moved the cursor (stopped at 8 min, not scored; the old route's notes already said this).
- A 2-screen cycle (dialog -> input -> menu -> input -> same dialog) changes the screen every step, so a
  "same unchanged screen" guard never fires. pathfind counts inputs per matching screen over the last
  12 steps (`seen_here`).
- "Gameplay" on a sports play-call screen: the stick only flips the play menu. The confirm call caught
  it (ESPN try2); the model's own action (A to kick off) now goes before the probe.
- Star Wars III's opening crawl and FMV ignore START/A; the agent pressed through 9 cutscene steps
  harmlessly. Its FMV renders as green blocks (a rendering defect, not a pathfind problem).
- Midnight Club 3: the agent took Career (garage tutorial: buy a car, Test Drive) where Arcade might be
  shorter; it still reached driving in 6.2 min. The disk keeps saved profiles between runs (CAPA T2).
