# CAPA: why there is no path builder, and what to change (#433)

lane.routerca433, 2026-10-02.  Analysis only: no device time, no runs queued.
Evidence is in this directory:
- `ledger.tsv`: 218 dispatch requests, from `ledger.py`.
- `review.tsv`: 18 runs whose frames I opened.
- `devtime.py`: per-minute device states from devwatch.
- `NOTES.md`: method, the per-requester tables, held sessions and process history.
Every number below names a run id or a file.

## The answer (for the owner)

**Cause.** We hand-wrote a blind button script per title. It presses on a
timer and declares "gameplay" at a fixed step, whatever is on screen; a slower
load or another save leaves it on a menu. The check had no picture of the
600 s, so it passed menus. 4 of the 9 passes I could check sat on a menu or
name-entry screen the whole time, and 10 of the 11 accepted titles have no
picture past their first moment of play.
The orchestrators (lane.local, hostops) filled the devices with runs too short
to show 600 s. At 04:10 they ordered more blind routes, hours after you asked
for screen reading. The screen-reading driver has never run in a dispatched
job. Since 09-26: about 49 device-hours, and one run shows 600 s of play.

**Change.**
1. Frames across every judged window.
2. One screen-aware builder: a vision model for unseen screens, saves reset
   per run, accepted on 10 never-seen titles before more title work.
3. No run without a written expected result.

**Stop tonight:** surveys, short replays, blind confirmations, Thor screens.

**Cost.** About 10 device-hours, an estimated $1 per title for the model.

## 1. The ledger, in totals

**Dispatch: 218 requests, 29.2 device-hours, 09-26 14:32 to 10-02 06:16
PDT.** Held time + cooldown + learned overhead per run.

| outcome | runs | device-h |
|---|---|---|
| a died before the mark | 4 | 0.6 |
| b reached play, then stuck | 4 | 1.1 |
| c reached the mark, < 600 s | 57 | 8.9 |
| **d 600 s of play, frames show it** | **1** | **0.24** |
| d? gate passed, window never seen | 10 | 3.7 |
| e void: heat 32, foreground 12, emulator exit 2, other 2 | 48 | 3.7 |
| f wrong screen: menu, Name Entry, pause | 6 | 1.6 |
| m reached a mark, never judged (benchmarks, surveys) | 61 | 7.8 |
| n no route at all (09-26 hands-off bench) | 27 | 1.7 |

**Outside dispatch: held sessions and screen cooling** (devwatch and the
dispatcher log):
- Thor: about 12.0 h, of which 9.0 h held and 3.0 h cooling between screens.
- Nova: about 7.8 h.
- lane.titleroutes alone used 12.5 h.
- 78 nav.py sessions drove 47 titles, and 41 of those got a route file. Input
  bursts were 5.2 h of the roughly 17 h held. The rest was replays, reading
  frames and waiting.

**Total route device time since 09-26: about 49 device-hours.**
- The only (d) is **1-1790804473-lane.verdict433-1767161**: Crimson Skies,
  Nova, 0.24 h, with frames in flight from the mark to +647 s.
- Counting every gate PASS not yet shown wrong (d + d?): 11 runs, 4.0 h.
- **172 of 218 dispatch requests (16.6 h, 57%) asked for under 700 s.** After
  boot and route, they could not have held 600 s whatever the route did.

**Thor:** 116 dispatch requests plus about 12 h held or cooling. That produced:
- 0 (d);
- 1 d? (Alien Hominid, 09-27, before the fan failed);
- 32 dispatch heat voids;
- heat stops in 33 of 40 cold slots, 8 of them 1.1-6.1 min after a cold start
  (logs/thor-coldconfirm.log).

**By title** (dispatch device-minutes):

| title | min | runs | outcome |
|---|---|---|---|
| Castlevania | 113 | 12 | 2 a, 3 f, 6 void, 1 c; no d |
| Azurik | 108 | | |
| Baldur's Gate | 72 | | |
| 187 | 59 | | 1 f, 1 d? |
| Forza | 43 | | 1 b |
| Sonic Heroes | 42 | | 1 f, 3 heat |
| Gunvalkyrie | 38 | 5 | 420-s replays |
| Super Monkey Ball | 29 | | 1 f, 3 heat |
| Buffy | 20 | | 1 b |

**What the totals cannot show:**
- Held time before 09-26 18:01 (hold.sh keeps no history).
- Whether the 10 d? titles held play after their mark. No frame exists, and
  the two caveats below point the wrong way.
- Driving versus waiting inside a hold.
- Results removed by the 09-29 16:25 dispatch wipe.

## 2. Failure taxonomy

The candidates the brief named come first. Each is CONFIRMED, REFUTED or
NOT SHOWN.

| # | cause | verdict | count / evidence |
|---|---|---|---|
| T1 | Blind button loops against variable boot/load timing | **CONFIRMED: the main technical cause** | 61 of 65 route files on master are open-loop: fixed waits, `mark gameplay` at a fixed step, then `repeat forever` input. Castlevania's New-Game-to-Name-Entry load varies 10+ s (header of routes/castlevania-cod.first-run.route). 1790903439-titleroutes-1317193 and 1790902028-titleroutes-1005086 marked "gameplay" on Name Entry. All 6 (f) runs are a blind mark or a blind play loop. titleroutes session 46's mark audit (titleroutes NOTES:3017-3057): of 45 routes ever soaked, the newest mark was NOT on gameplay for 16, including KOF and Azurik ("the window needs a review"), and on gameplay for 28. |
| T2 | Per-title state that changes between launches | **CONFIRMED** | Disks are kept between runs (titlestate plan `keep`; 82 title ids in dispatch/titlestate/saves). 187's returning route met four Empty slots and marked on the keyboard (1-1790775886-lane.verdict433-3086875). Castlevania's returning route took the New Game path (1790897326-autoverdict-3745925). Buffy keeps 10 saves and makes one per Start Game; replays had already added "Buffy 2" and "Buffy 3" (routedriver2 NOTES, run b12). |
| T3 | No screen understanding until routedriver, then only proof titles | **CONFIRMED, worse than stated** | **No dispatched run has ever executed drive.py.** No result dir has `route-state.tsv`; no route.txt in the 54 runs since 10-01 20:00 has a `drive` step. Five hand-made profiles, each with crops and per-title thresholds. The vision-model fallback has made 0 calls (no key on the host). |
| T4 | Driver not reachable from dispatched runs | **CONFIRMED, and still true now** | drive.py folded at 7efa13af89 (10-02 01:54), but the dispatcher snapshot fix (lane/snapdrive 4f570d1b71) **was refused by the fold gate at 06:20 and 06:36** (territory: two selftest fragments; offline-git/fold-failures.log). Not on master (b71f92a12a). |
| T5 | waitfor crop paths unresolved in the result dir | **CONFIRMED, not fixed** | 1790918365-titleroutes-76920 died at step 73 on a missing ref crop, then ran 661 s on the intro. route.sh builds `refs/route.txt/<name>.png` and nothing writes it. snapdrive only makes request.sh refuse such routes (unfolded). |
| T6 | Verdict gates that accept a static window or a menu | **CONFIRMED** | 4 gate PASSes on the wrong screen for the whole window: 187 at 59.94 fps on a keyboard for 1286 s; Castlevania twice; Super Monkey Ball, 10.6 min on Stage Select. Blood Wake, owner-accepted: collapse433's counters are flat from mark+136 s, very probably a static screen (collapse433 NOTES section 3). `static_window()` (added 10-01) needs post-mark frames, and the accepted titles' routes take none. |
| T7 | Driving/combat titles needing real control | **CONFIRMED** | Forza at 0 MPH (1-1790826491-lane.verdict433-3477700). routedriver2 f1/f2: a 1.1 Hz screencap loop cannot steer. Gunvalkyrie, Buffy and 007 AUF wedged on geometry after the mark (review.tsv). Sonic stalls at obstacles until Game Over (routedriver2 t4). BF2: not shown either way. |
| T8 | Heat; Thor out of service | **CONFIRMED** | 32 dispatch heat voids; 33/40 cold slots heat-stopped; 0 (d) from about 26 Thor route-hours. The Thor rule (<= 480 s, later 300 s; stop at xo 70 C) cannot produce a 600-s window by construction. |
| T9 | Survey cost model | **CONFIRMED** | 48 surveys + 17 titleplay = 6.4 h. 300-420 s each, and the generic route never writes `mark gameplay` (survey.route:10), so 0 could be a (d). Its START/A cycle pauses live play (1790823803-titleroutes-2951964: Sonic PAUSE). |
| T10 | Lane churn: attempt cap, successors start from NOTES | **CONFIRMED** | titleroutes: 51 sessions; the 4-attempt cap was reset four times (briefs/titleroutes.md:231, :404, :592; #603) before retiring 10-02. From session 38 most headings begin "why session N did not finish" (stranded background tasks, broken waiters, turn caps). Session 51: "the evidence it left is now gone". routedriver hit 4/4 in about 3 hours. The counter counts resumes, not failures (models.env; lane.sh:187-215). |
| T11 | Lanes verifying each other's routes late | **CONFIRMED** | Nominations rested on "a full unattended route.sh replay" that checked the mark and seconds after it (host-tools/nova-nominations.tsv: SMB, Castlevania). The window was first seen in a 15-min confirmation and caught by the owner's frame review after it. lane.local's own ADDENDUM 5 read a Castlevania run as "SUCCEEDED" on a frame taken before the HUD; titleroutes session 56 corrected it (titleroutes NOTES:3889-3899). |

Causes the ledger shows that the list missed:

| # | cause | count / evidence |
|---|---|---|
| T12 | **Runs too short to show what is judged** | 172/218 requests (57% of dispatch time) asked for < 700 s. Gunvalkyrie x5 overnight: "FAIL duration 251 s < 600 s" five times (verdicts.log 10-02 04:39-06:14). |
| T13 | **No frames of the scored window** | `frames.every` is 0 on all 218 requests. 10 of the 11 accepted titles have 0 route frames after the mark; their contact sheet stops at the mark. |
| T14 | **"Gameplay" is self-reported** | `reached_gameplay` = the route printed `mark gameplay` plus one guest flip (title_verdict.py:9-10, 434-437). |
| T15 | **Tools run from the dispatch snapshot, not the request's ref; the same defect three times** | #206 (09-24: SCRIPT_DEPS listed 4 of 9 shipped files, devices idle 18 h); vsh_score.py missing from bin/ (09-25); drive.py/classify.py/profiles missing (10-02). Also 1790902215-autoverdict-1078702 ran the OLD Sonic route (WITHDRAWN.txt), 1790905334-titleroutes-1780552's route.sh had no `waitfor` (904 s held), and four "refusing to queue: no route" (verdicts.log 10-01 15:09-15:55). |
| T16 | **The soak keeps running after the route dies** | The two runs in T5/T15: about 26 min on two one-line errors. |
| T17 | **Foreground loss** | 12 voids: ES-DE, Daijishou, the notification shade or odin.settings holding display 0. |
| T18 | **The pilot gate judges execution, not the question** | titleroutes2.ok (10-02 04:28): "PROCEED (route replays, Nova, <=420 s each)". A 420-s replay licensed more 420-s replays. titleroutes.ok is written by the requesting lane itself. |
| T19 | **The bar for "live play" is undefined** | The driver calls a stuck character `stalled` and fails the window (Sonic, Forza, Buffy). The verdict calls a 60-fps menu gameplay. No written owner rule says how much the bot must play (D1 below). |
| T20 | **A 1 Hz control loop through adb** | A Nova screencap takes about 0.9 s (routedriver2 NOTES, Forza f1). That is fine for menus and too slow for steering. The emulator sees every frame. |
| T21 | **No expected result on any device run** | **218 of 218 route requests used `--no-expect`.** request.sh's prediction gate exists, and every title run waived it: "a measurement of a title, not a test of a change" x80, "route validation + benchmark, not an A/B arm" x23, "Playable confirmation, judged by autoverdict" x12 (request.json `no_expect`). No route-lane brief stated a hypothesis (titlerun, titleplay "Prediction: none"; titleroutes `Prediction: none: route data`). |
| T22 | **Rejected PASSes still count** | The verdict.json of 1790900520-autoverdict-566484 (SMB), 1790897326-autoverdict-3745925 and 1790902028-titleroutes-1005086 (Castlevania) still say `"pass": true` with no WITHDRAWN.txt. host-tools/autoverdict.sh treats any `"pass": true` for a title id as "already Playable" and never queues it again. |
| T23 | **The fold gate blocked route tooling on the critical path four times** | waitfor (10-01 19:18), routedriver (10-02 00:19), titleroutes' final review (05:01), snapdrive (06:20, 06:36) (fold-failures.log). Each time, dispatched runs kept the stale snapshot. |
| T24 | **Route work was classed as clerical** | The 09-29 token policy: "Opus for emulator engineering, Sonnet for measurement, routes, docs". titleroutes ran 28 of its 49 real sessions on Sonnet (memory token-balance; lane logs). |

## 3. Five whys

Central question: about 65 titleroutes sessions, ten other route lanes and
about 49 device-hours since 09-26. Why is there no builder that takes an
unseen title to 600 s of live play unattended?

### Technical chain

1. **Why no unattended 600 s?** Runs mark gameplay blind, then send blind
   input. Wherever the title differs from the authoring session, the run
   sits on a menu or a wall (T1, T2, T7). Examples of the difference: load
   time, save state, a stage ending, THPS2x's 2-min session timer, KOF's lost
   round at the mark.
2. **Why blind?** Until 10-01, route.sh could only `wait`, `press`, `axis`,
   `shot` and `mark`.
   - `shot` saves a picture for a person to read later; the route never
     branches on it.
   - Seeing the screen meant a lane agent reading nav.py screenshots in a
     held session (78 sessions, 47 titles).
   - What they saw was written down as fixed timings, which the unattended
     run cannot check.
3. **Why was closed-loop control not built first?** Blind routes appeared to
   work. They PASSED the gate, because the gate's only picture is the mark:
   - 187 at 59.94 fps on a keyboard;
   - Castlevania on Name Entry;
   - SMB on Stage Select;
   - fps-share nominations: "Four of four were menus. A menu runs at the
     frame cap, so a 97-100% share is what a menu looks like" (titleroutes
     NOTES:3059-3063).

   (T6, T13, T14.)
4. **Why could the gate not see it?** Every run had `frames.every 0`, and
   `reached_gameplay` is the route's own claim. Each owner withdrawal
   patched the gate (`static_window`, play_share) instead of removing the
   blind mark. Those patches need post-mark frames or a driver timeline,
   and the accepted routes produce neither.
5. **Why is the driver that fixes 1-4 not working yet?**
   - It started on 10-01 at 21:45, day 8, after the owner asked for it.
   - It is hand-tuned per title: crops and thresholds in 5 profiles.
   - It sees the screen at about 1 Hz through adb.
   - It treats a stuck character as failure, which makes 600 s a
     game-skill problem (Sonic obstacles, Forza steering).
   - It has never run in a dispatched request: the snapshot fix is
     unfolded (T3, T4, T19, T20, T23).

### Process chain

1. **Why was device time spent this way?** Work was specified and counted
   in titles (routes written, nominations, the Playable count), not in
   builder capability.
   - Each brief asked for the next titles.
   - The 09-26 owner ask was "program profile setup inputs and gameplay
     inputs ... whenever the devices are free" (host-tools/hostops-inbox.md:8).
   - The orchestrators read that as "keep the devices busy with routes".
2. **Why did nobody stop the pattern?** Nothing asked a run what it
   expected (T21). The pilot gate checks execution, not question-fit (T18).
   - A 300-s survey, a 420-s replay and a 480-s Thor screen each passed
     their gates, and none could show a (d) (T12).
   - Benchmarks went out at 300 s with "Do not wait for the result"
     (lane.local 09-26 20:50, briefs/titleroutes.md:83-116).
   - "queue every ready benchmark now ... do not wait for earlier results"
     (lane.local 09-27 19:55, :308-321).
3. **Why the overnight runs, specifically?** They were ordered.
   - 18:30: owner ADDENDUM 11 established that routes are open-loop and
     that a route which cannot see must stop.
   - 21:45: the owner asked for screen-reading input (routedriver brief).
   - 22:45: "re-do that with intelligence".
   - 23:10: hostops ADDENDUM 15: "Do not end this session on 'no device
     work tonight' again without first queuing whatever offline/survey
     work is available" (briefs/titleroutes.md:789).
   - 04:10: the titleroutes2 brief: "Write routes open-loop", replays
     <= 420 s, "end every session with something queued"
     (briefs/titleroutes2.md:10, 77-80).
   - Result: 33 requests and 4.5 device-hours between 10-01 17:00 and
     10-02 06:16 PDT, 0 (d).
   - **The main cause of the overnight spend is orchestration:** a
     keep-busy rule, applied after the evidence said the work could not
     succeed.
4. **Why did knowledge not accumulate?**
   - Short sessions under an attempt cap that counts resumes.
   - The same route re-derived in held sessions.
   - Evidence lost to stranded sessions.
   - Route lanes put on the cheaper model by policy (T10, T24).
   - Route tooling stuck behind the fold gate while runs used the old
     snapshot (T23).
   - Successors inherited NOTES full of "do not repeat" rules, not a
     working design.
5. **Why did the orchestrators not catch it?**
   - They relayed and queued; neither kept a notes file of its own (no
     lane.local NOTES under docs/lanes).
   - Neither asked of the batch as a whole: can any of this produce a (d)?
   - lane.local's ADDENDUM 5 itself misread a run as a success.
   - The owner's 09-28 "cheap quick fixes that rarely pan out" went into
     roles/lane.md as a rule for lanes ranking options. It was never
     applied to how the orchestrators spent the devices.

### Decisions that spent device time with no hypothesis the run could test

| decision | who, when | runs / time | why it could not answer |
|---|---|---|---|
| Pass-1 generic survey of every title | titleplay brief 09-26; titleroutes pass-1 surveys 09-30 to 10-02 | 65 runs, 6.4 h | 300-420 s, no `mark gameplay`. Its only output is "where blind presses stopped". |
| 300-s same-pass benchmarks, "do not wait for the result" | lane.local 09-26 20:50, 09-27 19:55 | about 50 titleroutes bench runs, 8.7 h for all benches | Cannot meet a 600-s rule; the routes were never judged after the mark (class m) |
| Thor screening, <= 480 s then 300 s, with a 90%-share nomination | lane.local, owner-approved 09-30 12:40 / 15:40 | 40 slots, 33 heat-stopped | Cannot reach 600 s by rule. 4 of 4 fps-share nominations were menus. |
| Re-queue 6 heat-voided Thor screens | hostops 10-01 04:11 | 6 | The same batch had just voided entirely |
| Castlevania re-runs, a timing tweak each | titleroutes s53-60, lane.local | 12 runs, 113 min plus holds | A timing tweak cannot fix a variable load; the route file's own header says so |
| Confirmations of blind routes nominated on a mark frame | autoverdict.sh (owner 10-01), lane.local | 12 runs, 2.8 h | The nomination evidence was the mark; 3 of 12 PASSes were wrong screens |
| "Queue something before ending"; "write routes open-loop" | hostops 10-01 23:10, 10-02 04:10 | 33 requests overnight, 4.5 h, 0 d | Keep-busy, not a question |

## 4. What "functioning" means

### Two owner decisions first

- **D1, the play bar.** What must happen in the 600 s? Recommendation:
  - The title must be in a gameplay scene that responds to input for >= 90%
    of the window.
  - These do not count: menus, pause, results, Game Over, black, a lost-round
    or continue screen.
  - These do count, if the scene is live and input visibly acts: stuck
    against a wall, a crashed car, falling and respawning, a CPU round in
    progress.
  - The driver must leave every non-play state. It does not have to make
    progress through the game.

  Without D1 the builder turns into a game-playing AI for each title (Sonic,
  Forza), and that is not what Playable measures.
- **D2, the start state.** Does a confirmation start from a cold boot, or
  from a saved machine state in play (C3b)? Recommendation: boot to the title
  menu cold, and allow the 600-s window to start from a state in play.

### Acceptance

All criteria are measured on dispatched runs, with no human between the
request and the verdict.

| # | criterion | bar |
|---|---|---|
| F1 | Unseen titles | 10 titles drawn by lot from the library, with no route, profile or prior run, and none of the 18 below |
| F2 | From cold | Boot, with the disk reset to the title's declared start state (F8); no held session first |
| F3 | Reaches play | The classifier's first `play`, confirmed by the frame at that time: >= 8 of 10 titles within 2 attempts each |
| F4 | Holds play | Play share >= 0.90 of the 600-s window by D1, with a frame every <= 30 s across the window and a 1-in-5 human check agreeing: >= 7 of 10 |
| F5 | Repeatable | The profile/route recorded in F3 repeats F4 on a second cold attempt: >= 6 of 10 |
| F6 | Cost | Device time from first boot to a confirmed window: median <= 45 min, max 90. Human time 0. |
| F7 | State-aware | On first sight, with no hand-written rule for that title, it recognises and leaves: logo, intro and cutscene; title; main and in-game menus; Name Entry and keyboards; save/load prompts and slot lists; loading and black; pause; death, retry and Game Over; results and stage end. It also recognises play and stalled. Bar: >= 4 of 5 titles that have the state, frame-checked. |
| F8 | Disk state | Before every run, saves are reset to the state the route declares (`first-run`: none; `returning`: a stored image). 0 runs meet a different state. |
| F9 | Honest failure | When the route or driver gives up, the soak ends within 60 s with a named state and a frame. The result is VOID-ROUTE, not a soak of the intro. |

### The current titles against it

All 11 accepted titles ran on blind routes, with no state awareness and no
disk-state reset.

| title | best evidence | frames in the window | meets F4 today? |
|---|---|---|---|
| Crimson Skies | 1-1790804473-lane.verdict433-1767161 PASS 708.9 s | yes, to +647 s | **yes, once** |
| Alien Hominid | 1-1790515369-lanelocal-1183547 PASS 1273.6 s (Thor, 09-27) | none | unknown |
| KOF MI | -1456797 PASS 1282.6 s | none; **the mark frame is a lost round** (CPU "WINNER", "PERFECT"; review.tsv, titleroutes NOTES:3040) | doubtful |
| Azurik | -1456876 PASS 1292.3 s | none; the mark frame is a modal tutorial dialog (titleroutes NOTES:3041) | unknown |
| WWE Raw 2 | -1456493r2 PASS 1276.9 s | none | unknown |
| 50 Cent | -1456544r2 PASS 1348.3 s | none | unknown |
| Baldur's Gate DA | -366130 PASS 1303.9 s | none | unknown |
| Kabuki Warriors | -3477568 PASS 1258.8 s (warm launch) | none; a fight at the mark | unknown |
| 187 | autoverdict-1510236 PASS 752.2 s | none; a race at the mark, and a 4-lap race ends | unknown; an earlier PASS was a menu |
| THPS2x | autoverdict-1937886 PASS 708.3 s | none; the mark has 1:43 left of a 2-min session | doubtful |
| Blood Wake | autoverdict-2155592, owner-accepted over an audio miss | none | **probably not**: counters are static after +136 s (collapse433) |

The other titles, none of which has a 600-s window:

| title | route | best evidence | meets F4 today? |
|---|---|---|---|
| Castlevania | blind, waitfor and drive (held only) | held `drive --find` reached play (routedriver a3); dispatched runs died or sat on Name Entry | no |
| Sonic Heroes | blind; drive (held only) | PAUSE menu (autoverdict-1078702); the driver stalls at obstacles | no |
| Super Monkey Ball | blind | autoverdict-566484: Stage Select for 10.6 min | no |
| Buffy | blind; drive (held only) | titleroutes-3976729: wedged | no |
| Forza | generic; drive (held only) | -3477700: car stopped at 0 MPH | no |
| BF2 | blind | autoverdict-2187810 FAIL at 515 s | no |
| Galleon | blocked by the owner | | n/a |

**No title meets F1-F9.**
- Crimson Skies meets F4 once, on a blind route with no state awareness.
- The other 10 accepted titles are unproven past their mark frame.
- KOF, THPS2x and Blood Wake have evidence pointing the wrong way.

## 5. Corrective and preventive actions

Ranked by probability x size of the win. Effort is a constraint, not the sort
key.

| rank | action | removes | P(works) | win | owner | device-h | test: worked / did not |
|---|---|---|---|---|---|---|---|
| **C1** | **See the whole window.** Every confirmation and route check takes a frame every <= 30 s across the window (soak `frames_every`, or drive.py `keep_every_s`). title_verdict refuses a window without them, and takes `reached_gameplay` from a classified frame, never from `mark gameplay` alone. Withdraw the three uncorrected PASS verdicts. autoverdict honours WITHDRAWN. Re-judge the 10 d? titles, Blood Wake, KOF and THPS2x first. | T6, T13, T14, T22 | 0.95 (the soak already supports `frames_every`) | Every later number becomes true; removes a 4-in-9 false-PASS rate | lane (title_verdict, soak); lane.local withdraws | 0 for the gate; about 2.5 h to re-run the 10 | Worked: every PASS has >= 20 window frames and the reviewer agrees on all sampled. Did not: a PASS whose frames show a menu |
| **C2** | **One builder: screen-aware, with a vision model for what it has not seen.** drive.py becomes the only way a run reaches and holds play. When no crop names a screen, the classifier asks the model (the existing MODEL FALLBACK, Haiku 4.5). The answer is written into the title's profile, so the next run needs no call. Play comes from genre templates, not per-title tuning: on-foot (walk a square, look), racing (hold throttle, steer by the model's left/right every few s), fighting (attack mix), flight. The goal is D1 liveness. Saves are reset per run (C3a). Accepted on section 4's ten unseen titles. | T1, T3, T7, T19 | 0.6 to reach play on 8/10 (menus and text screens are what a vision model reads best); 0.5 to hold D1 play on 7/10 | The only option that scales to titles nobody has driven, which "unseen" requires | **Owner decision** (API key and budget), then the C6 lane. Model cost is an estimate, not a quote: about 100-200 small-image calls per new title (a find, plus one call per screen no crop names; known screens are classified locally). drive.py already logs tokens and cost per call (`classify-model-calls.jsonl`), so X1 measures the real figure | about 6 h (10 titles x 2 attempts x ~15 min, plus finds) | Worked: F3-F6 met. Did not: < 8/10 reach play, or the model's state names disagree with frame review on > 1 frame in 10 |
| **C3** | **A known start state.** (a) titlestate resets the title's saves before every run to the state the route declares, and records it in the result. (b) Priced for the owner: port VM snapshots to Android. Upstream xemu saves and loads machine state; hakuX stubs it out (`android/app/src/main/cpp/xemu_snapshots_stub.c`, CMakeLists.txt:591). With it, a builder that reaches play once saves the state, and later runs start in play. This is how Dolphin, PCSX2 and RetroArch make play repeatable. No lane has considered it. | T2; T1 for repeat runs; F5, F8 | (a) 0.9; (b) 0.4, unmeasured with the Vulkan renderer on Android | (a) removes the 187/Castlevania/Buffy class; (b) makes "reach play" a one-time cost per title | (a) lane (titlestate) + hostops; (b) owner decision, then an emulator lane | (a) 0.5 h; (b) about 2 h of proof | (a) Worked: 0 of the next 20 runs open on a state other than the declared one. (b) Worked: loadvm in play resumes rendering and input 5/5 on the Nova. Did not: hang, black, input lost |
| **C4** | **No device time without an expected result.** request.sh stops accepting `--no-expect` from route/title requesters. Their requests carry `expect:` (the outcome class a hit and a miss would be, and what each changes next) and `shape:` (seconds after boot and route >= the window judged; frames on). The pilot review answers "can this shape show the result it expects?" before "did it run?". Pilot verdicts are not self-written. | T12, T18, T21 | 0.85 (a gate on a field, not prose) | Stops the 57% of dispatch time spent on runs that could not answer | lane.local (brief a harness lane for request.sh) | 0 | Worked: in the next 50 route requests, 0 are shorter than the window they judge, and each names its expect. Did not: boilerplate `expect:` lines (audit 10 by hand) |
| **C5** | **Fail fast, and run what was asked.** (a) The soak ends within 60 s of a route or driver exit or ROUTE FAIL, and marks VOID-ROUTE. (b) A run takes route, route.sh, drive.py, classify.py, profiles and ref crops from the request's `--ref`, not the dispatch snapshot. This ends the T15 defect class rather than patching its third instance. (c) The foreground guard re-asserts focus before the first input. | T5, T15, T16, T17 | 0.9 | About 15 min saved per route death; no stale-route runs | lane (dispatcher, soak) | 0.3 h | Worked: a deliberately broken route ends in < 60 s, and a route changed on a branch runs as changed. Did not: either fails |
| **C6** | **One standing builder lane with continuity.** On Opus from attempt 1. It owns drive.py, classify.py, title_verdict's play gate, the dispatcher snapshot entries for them, and the acceptance table. Its territory covers every file it must fold (T23). Its NOTES carry the section-4 table, not session logs. No title lanes until C2 passes; after that, title work is "run the builder on title X", queued by lane.local. | T10, T23, T24, process 1-4 | 0.7 | Ends the re-derivation cycle; one owner of the design | owner / lane.local (lane model) | 0 | Worked: the acceptance table advances every session, and no route file is hand-written after C2 passes. Did not: the lane retires at a cap with the table unchanged |
| **C7** | **Orchestrators: no keep-busy rule for route work.** Strike "end every session with something queued" and ADDENDUM 15's rule for route/title lanes. An idle device is the right state when the only available run cannot answer a question. lane.local keeps a NOTES file of its own device-spending decisions, each with the question it answers. | process 3, 5 | 0.8 | Removes the cause of the overnight spend | lane.local, hostops | 0 | Worked: the next overnight queue's route runs all carry an `expect:` and a 600-s-capable shape, or none run. Did not: a survey or a < 600-s replay queued "to stay busy" |
| **C8** | **A faster, in-process view for real-time control.** The emulator reports play state at frame rate: guest flips, draw and texture-dirty counts (collapse433 already tells play from a static screen with these), and a downscaled frame on a local socket. drive.py can then steer faster than adb's 1 Hz. | T20; T7 for racing | 0.5 | Needed only where D1 still asks for real control | emulator lane | about 1 h | Worked: capture-to-input under 200 ms, and Forza holds the track for 60 s. Did not: no gain over adb |
| **C9** | **Retire the Thor from route work until its fan is replaced.** | T8 | 1.0 | About 26 Thor route-hours since 09-26, for 0 (d) | owner / lane.local | saves time | n/a |

### The decisions the brief asked for

- **Device time before a hypothesis:** none. A route/title request carries
  `expect:` and `shape:` (C4). The only device time before C1/C2 land is the
  C1 re-judge and the C2/C3 acceptance pilot, whose expectations are
  section 4.
- **Surveys:** stop them.
  - A survey answers "where do blind presses end up", which nothing needs
    once the driver can find play.
  - It cannot meet the 600-s rule, and it pauses live play.
  - Its replacement is `drive --find` with the model fallback, ending at
    play or at a named state, with frames.
- **Architecture:** keep the screen-aware state machine. It is the right
  skeleton, and the only piece that has reached play by its own sight
  (Castlevania a3, Sonic t2-t4, Buffy). Change three things:
  1. Its knowledge source. The model names unknown screens on first sight,
     and hand-cut crops become the cache of those answers, not the input.
  2. Its goal: D1 liveness, not progress.
  3. Its start: saves reset every run (C3a), and savestates if C3b proves
     out, so repeat runs skip menus.

  Use model-in-the-loop for first discovery, then a recorded profile. Do not
  go back to hand-timed blind routes, even for menus.
- **How learning transfers across titles:** through three shared layers.
  1. One state vocabulary (classify.py's states).
  2. Genre play templates.
  3. A cross-title library of "screen to the button that worked". Examples:
     the skip ladder's recorded winners, Name Entry needing START then A, a
     save prompt that defaults to No.

  The model answers first-sight screens, and its answers become profile
  entries. Per-title profiles hold only what differs.
- **Lane model:** one standing builder lane (C6). Title lanes stop until it
  passes acceptance.

## 6. What I would stop tonight

1. Every route-related device request except the C1 re-judge and the C2/C3
   acceptance pilot. That means:
   - surveys;
   - 300-420 s route checks and replays;
   - Thor screens;
   - held nav.py sessions;
   - confirmations of blind routes.
2. The keep-busy rule for route lanes (ADDENDUM 15; titleroutes2's "end
   every session with something queued").
3. Hand-writing or tuning route files, including drive profiles cut by hand
   for one title.
4. Counting the 10 d? titles as Playable in any public total until C1 has
   re-judged them. Start with Blood Wake, KOF and THPS2x.
5. Route work on the Thor (C9).

## 7. Proposed experiments

Not run; this lane does not queue.

| # | question | run | hit | miss |
|---|---|---|---|---|
| X1 | Can a vision model name the screens our classifier needed crops for? | Offline, no device: the 18 reviewed runs' frames plus the routedriver/routedriver2 fixtures, through the MODEL FALLBACK prompt | State names agree with the review on >= 90% of frames (Name Entry, pause, Stage Select, lost round, play, stalled) | < 80%, or it calls a menu `play` |
| X2 | Do the 10 accepted d? titles hold play past the mark? | Their current routes, Nova, 900 s, `frames_every 30` | >= 18 of 20 window frames are live play | Any title with > 60 s of menu, results or static screen |
| X3 | Do Android VM snapshots work? | One held proof: savevm in Crimson Skies flight, then loadvm x5 | Rendering and input resume 5/5 | Hang, black, or lost input |
| X4 | Does a save reset remove the state class? | 187 and Castlevania returning with the declared save image, 2 runs each | The first frames match the declared path in 4/4 | Any keyboard or Name Entry |

X1 needs no device, and decides whether C2's probability is 0.6 or much
lower. Run it first.
