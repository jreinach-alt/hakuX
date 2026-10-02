# routerca433 NOTES (#433): root cause of the missing path builder

Analysis lane, no device, no runs queued.  The deliverable is `CAPA.md`; this
file is the evidence behind it and what the next lane should not repeat.

## Tools in this directory (all read-only over the dispatch tree)

- `ledger.py` -> `ledger.tsv`: one row per route-related dispatch REQUEST since
  09-24.  Requesters: titleroutes, titleroutes2, titleplay, titlebench,
  host-titlebench, lane.verdict433, autoverdict, routedriver, the lane.local /
  lanelocal #433 confirmations, titlestate, hostops #433.  Perf lanes that only
  CONSUME routes (lane.pacing, lane.ibcache, forza414 ...) are out of scope.
  A request can have two result dirs (queue-prefixed and a bare-id alias); the
  ledger keeps one per request id.  Columns: device time (`held_s` from
  run.log's `held ... for Ns`, `cool_s`, `over_s` the learned per-run overhead),
  route progress (`steps`, `marks`, `ended`), the verdict (`gameplay_s`, `pass`,
  `failing`), `post_frames`/`post_span_s` (route frames taken AFTER the mark,
  the only pictures of the scored window that exist), and the class.
- `review.tsv`: the 18 runs whose frames I opened, with what each showed.  It
  overrides the automatic class.
- `devtime.py`: device-minutes by state from `~/hakux-work/logs/devwatch/*.tsv`
  (one sample per device per minute, 09-26 00:00 to 10-02 ~07:00 PDT).

Rerun: `python3 docs/lanes/routerca433/ledger.py > docs/lanes/routerca433/ledger.tsv`.

## Classes

The brief's letters, plus three the data forced:

| class | meaning | how assigned |
|---|---|---|
| a | died or hung before the mark | route started, no `mark` line |
| b | reached the mark, then stalled/static/looped | frame review only |
| c | reached the mark, under 600 s (or >= 600 s and failed fps/thermal: `c+` in the tsv) | verdict |
| d | 600 s of live play, judged by frames | frame review only |
| d? | the verdict PASSED (>= 600 s after the mark) but no frame shows the window (`u` in the tsv when I looked at the mark frame and it was live play) | verdict + review |
| e | void: heat stop, foreground loss, adb, emulator exit (`x`) | run.log / verdict void |
| f | wrong state: menu, name entry, pause, save prompt | frame review only |
| m | reached a mark, never judged (benchmarks, surveys, screens) | no verdict.json |
| n | no route at all (09-26 hands-off 240 s title bench) | no ROUTE lines |

## Ledger totals (dispatch only; held sessions are separate, below)

218 requests, **29.2 device-hours** (held + cooldown + overhead), 09-26 14:32 UTC
to 10-02 13:16 UTC.  Nova 102 runs / 15.7 h, Thor 116 runs / 13.6 h.

| class | runs | device-h | share of h |
|---|---|---|---|
| a died before the mark | 4 | 0.63 | 2.1% |
| b stalled after the mark | 4 | 1.09 | 3.7% |
| c under 600 s (incl. c+) | 57 | 8.88 | 30.4% |
| **d 600 s, frames show play** | **1** | **0.24** | **0.8%** |
| d? gate PASS, window unseen | 10 | 3.73 | 12.8% |
| e void | 48 | 3.66 | 12.5% |
| f wrong state | 6 | 1.60 | 5.5% |
| m mark, never judged | 61 | 7.75 | 26.5% |
| n no route | 27 | 1.66 | 5.7% |

- **One run in 218 is a (d) by the brief's own definition**:
  1-1790804473-lane.verdict433-1767161, Crimson Skies, Nova, 824 s held,
  frames in flight from the mark to +647 s.  0.24 of 29.2 device-hours.
- **172 of 218 requests (16.6 h, 57%) asked for under 700 s of device time**,
  so after boot and route they could not have held 600 s of play whatever the
  route did.  They were benchmarks, surveys (300 s), Thor screens (<= 480 s
  by the Thor rule) and route checks (300-420 s).
- The 10 d? runs are the 11 accepted titles minus Crimson Skies: Alien Hominid
  (lanelocal-1183547), KOF MI (-1456797), Azurik (-1456876), WWE Raw 2
  (-1456493r2), 50 Cent (-1456544r2), Baldur's Gate DA (-366130), Kabuki
  (-3477568), 187 (autoverdict-1510236), THPS2x (autoverdict-1937886), Blood
  Wake (autoverdict-2155592, owner-accepted over an audio miss).  Every one of
  them has **zero frames after the mark** (`post_frames` 0, `frames.every` 0):
  their window rests on fps/flip counters only.

By requester (runs / device-h / a b c d d? e f m n):

| requester | runs | h | a | b | c | d | d? | e | f | m | n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| titleroutes | 104 | 11.3 | 4 | 1 | 34 | 0 | 0 | 36 | 2 | 27 | 0 |
| lane.verdict433 | 22 | 6.6 | 0 | 2 | 4 | 1 | 6 | 7 | 1 | 1 | 0 |
| autoverdict | 12 | 2.8 | 0 | 0 | 5 | 0 | 3 | 1 | 3 | 0 | 0 |
| titleplay | 17 | 1.9 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 16 | 0 |
| host-titlebench | 27 | 1.7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 27 |
| titlebench | 15 | 1.6 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 11 | 0 |
| titleroutes2 | 12 | 1.5 | 0 | 1 | 9 | 0 | 0 | 0 | 0 | 2 | 0 |
| lanelocal / lane.local / hostops | 5 | 1.6 | 0 | 0 | 1 | 0 | 1 | 2 | 0 | 1 | 0 |
| routedriver | 3 | 0.2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 |
| titlestate | 1 | 0.1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |

By device: the Thor's 116 runs produced 38 voids (32 of them the
thor_coldconfirm HEAT STOP at xo 70 C, `ROUTE STOPPED ... daijishou` in run.log,
"HEAT STOP at xo 70 C -- run voided" in logs/thor-coldconfirm.log) and one d?
(Alien Hominid, 09-27, before the fan died).  81 of the 116 asked for <= 480 s.
**The Thor's route time cannot produce a (d) under the current Thor rule.**

By kind: confirmations 36 runs / 10.2 h (1 d, 10 d?, 4 f, 10 e); benchmarks 82
/ 8.7 h; surveys 48 / 4.5 h (0 d by construction: 300 s, generic route,
`mark play` never `mark gameplay`); route checks 29 / 3.6 h (0 d: 300-420 s).

Device time from devwatch (09-26 00:00 to 10-02 ~07:00 PDT, 132.6 h per device):

| state | Nova h | Thor h |
|---|---|---|
| dispatch run, route lanes | 14.6 | 11.8 |
| HELD route session (nav.py/drive, hands-on) | 6.5 | 8.5 |
| cold-slot holds (Thor, cooling between runs, mixed lanes) | - | 6.3 |
| dispatch run, other lanes | 44.2 | 37.1 |
| idle / idle-waiting | 32.6 | 2.6 |
| resting / absent / overdue (battery, heat, fan) | 30.3 | 59.7 |

Route work, dispatch plus held: **about 41 device-hours since 09-26** (Nova 21.1,
Thor 20.3, cold slots not counted).  Output: 1 frame-proven 600-s window.

## Frame review (18 runs, across classes)

`review.tsv` has each with the file looked at.  Summary:

| run | title | verdict said | frames show | class |
|---|---|---|---|---|
| 1-1790775886-lane.verdict433-3086875 | 187 | PASS 1286 s, 59.94 fps | profile-name keyboard at the mark (owner withdrew 09-30) | f |
| 1790897326-autoverdict-3745925 | Castlevania (returning) | PASS 613.5 s | Name Entry from before the mark to the end | f |
| 1790902028-titleroutes-1005086 | Castlevania (first-run) | PASS 672.8 s | Name Entry, empty name, at the mark | f |
| 1790900520-autoverdict-566484 | Super Monkey Ball | PASS 653.8 s | one rolling frame, then Stage Select for 10.6 min | f |
| 1790902215-autoverdict-1078702 | Sonic Heroes | (withdrawn) | the route's own START paused play; PAUSE menu to the end | f |
| 1790903439-titleroutes-1317193 | Castlevania (first-run) | (stopped) | Name Entry "AAIIIIII" at the mark | f |
| 1-1790804473-lane.verdict433-1767161 | Crimson Skies | PASS 708.9 s | in flight, mark to +647 s | **d** |
| 1790860858-autoverdict-1510236 | 187 | PASS 752.2 s | race at the mark; nothing after | u (d?) |
| 1790866838-autoverdict-1937886 | THPS2x | PASS 708.3 s | skating at the mark, 1:43 left on a 2-min session; nothing after | u (d?) |
| 1-1790826491-lane.verdict433-3477568 | Kabuki | PASS 1258.8 s | fight round at the mark; nothing after | u (d?) |
| 1790876348-autoverdict-2155592 | Blood Wake | FAIL audio, owner-accepted | boat at the mark; "No later frame from this run exists" | u (d?) |
| 1-1790745234-lane.verdict433-366094 | 007 AUF (generic) | unconfirmed 1251 s | in level, the same vault-door view for 20 min | b |
| 1-1790826491-lane.verdict433-3477700 | Forza (generic) | FAIL fps 1253 s | in race at 0 MPH, 8/8, race clock 18:11 | b |
| 1790944628-titleroutes2-2686999 | Gunvalkyrie | FAIL duration 247 s | the same canyon-wall view after the mark | b |
| 1790932722-titleroutes-3976729 | Buffy | FAIL duration 236 s | the same tree/sky view after the mark | b |
| 1790918365-titleroutes-76920 | Castlevania (first-run) | withdrawn | route.sh died at step 73 (waitfor ref crop missing); intro loop to the end | a |
| 1790823803-titleroutes-2951964 | Sonic Heroes (survey, Thor) | heat stop | the survey's START/A cycle PAUSED live play | e |

What the review says:

1. **Of 9 gate PASSes I could check, 4 were on a menu or Name Entry for the
   whole window (187, Castlevania twice, Super Monkey Ball), 1 was live play
   across the window (Crimson Skies), 4 show live play only in the mark frame.**
   The verdict at the time read `reached_gameplay` from the mark frame and
   fps/flips after it; a menu at 60 fps scores as gameplay.  `static_window()`
   was added on 10-01 after SMB and Castlevania (title_verdict.py:30-36), but it
   reads route-frames taken after the mark, and the accepted titles' routes
   take none (post_frames 0).  It cannot judge them.
2. **`mark gameplay` is an assertion, not an observation.**  61 of 65 route
   files on master (`docs/testing/titles/routes/`) are open-loop: fixed waits,
   then `mark gameplay` at a fixed step whatever is on screen, then `repeat
   forever { ... }` blind input.  Only castlevania-cod.first-run uses `waitfor`;
   the three `*.drive.route` files use the driver.  Every f above is a blind
   mark landing on a screen the route did not expect.
3. **The blind play loop manufactures the f and b classes.**  START in live play
   pauses Sonic Heroes; A on Stage Select keeps SMB on Stage Select; a held
   stick wedges Gunvalkyrie, Buffy and 007 against geometry; Forza sits at 0
   MPH.  The generic/survey route does the same on every title it touches.
4. **Not one dispatched run has ever executed the screen-aware driver.**  No
   result dir has a `route-state.tsv` or `classify-model-calls.jsonl` (glob
   over dispatch/results, 10-02).  drive.py reached master at 7efa13af89
   (10-02 01:54 PDT) and the dispatcher snapshot at 4f570d1b71 (10-02 05:21).
   Its model fallback has made zero calls (no key on the host).

## Harness faults that each burned a whole window

- **The soak does not stop when the route dies.**  1790905334-titleroutes-1780552:
  `route.sh: ...route.txt:73: unknown step 'waitfor'` (the dispatcher's
  route.sh was older than the route), then `held ... for 904s`.
  1790918365-titleroutes-76920: died at step 73 on a missing reference crop,
  `held ... for 661s` on the intro video.  ~26 min for two one-line errors.
- **Routes run from the dispatch checkout, not the lane's branch.**
  1790902215-autoverdict-1078702 WITHDRAWN.txt: "queued on the stale dispatch
  checkout, so it ran the old 9-cycle START/A route".  verdicts.log 10-01
  15:09-15:55: four "refusing to queue: no route 'castlevania-cod.returning'".
  request.sh learned to check a route "as the dispatched run will see it" only
  at f68cb89cf9 (10-02 05:23).
- **Disk state is kept between runs ("keep: the disk carries the store's
  saves").**  A route written for one save state meets another: targets.toml
  187 notes ("titlestate's 'found' save builds a disk with four Empty slots, so
  the returning route's mark landed on the name keyboard"); Castlevania's
  returning route took the New Game path (verdicts.log 10-01 17:01).
- **Foreground loss voids** (12 e:fg): ES-DE / Daijishou / notification shade /
  odin.settings holding display 0 (e.g. 1-1790725089-lane.verdict433-1456493).

## Held sessions and cooling (outside dispatch)

Reconstructed by a read-only subagent from devwatch, dispatcher.log, nav/
session dirs and lane NOTES. Its tables are summarised here.

| device | held route sessions | cooling for screens | total |
|---|---|---|---|
| Thor | 539 min (titleroutes 507, titlestate pilot 23, routedriver Forza ~5 est.) | 179 min (thor_coldconfirm title slots) | about 12.0 h |
| Nova | 465 min (titleroutes 244, routedriver2 102+, routedriver 42, gamecheck 28, titlerun 30, titleroutes2 16, titlestate 3) | 0 | about 7.8 h |

- `~/hakux-work/nav/` holds 78 nav.py sessions (Thor 55, all between 09-26
  16:13 and 09-27 21:43; Nova 23).
- They drove 47 distinct titles, and 41 have a route file. Having a file does
  not mean the route is validated.
- Input bursts cover 5.2 h of the roughly 17 h held. The rest went on
  replays, reading frames and waiting.

thor_coldconfirm (logs/thor-coldconfirm.log, 09-30 10:34 to 10-01 04:17):

| item | value |
|---|---|
| title slots | 40 (39 titleroutes, 1 verdict433) |
| heat stop at xo 70 C | 25 |
| heat stop at cpu-1-9 >= 90 C | 8, each 1.1-6.1 min after a cold start (xo 35-49 C) |
| ran to the end | 7 |

devwatch, 09-26 18:01 to 10-02 06:28: the Nova was idle or idle-waiting
32.6 h. The Thor was under the fan-dead hold 47.8 h.

Not reconstructible:
- Holds before 09-26 18:01 (hold.sh keeps no history).
- Driving versus waiting inside a hold.
- Thor route work under the fanwait hold beyond routedriver's Forza run.

## Process history (from briefs, attempts, lane logs, fold logs)

Also from a read-only subagent. I re-checked every item that CAPA relies on.

- **Hypotheses.** No route-building brief stated one: titlerun and titleplay
  say "Prediction: none"; titleroutes says `Prediction: none: route data`.
  All 218 ledger requests carry `no_expect`. I re-read this in request.json
  (counts in CAPA T21).
- **Attempt cap.** `LANE_MAX_ATTEMPTS=4` counts every start and every resume
  (models.env; lane.sh:187-215). titleroutes' counter was reset at
  briefs/titleroutes.md:231, :409 ("reset, not split") and :592, and it
  retired at 4/4 on 10-02. It has 51 session logs, 28 of its 49 real
  sessions on Sonnet after the 09-29 token policy ("Sonnet for measurement,
  routes, docs"), and about $290 spent.
- **Fold gate on route tooling** (offline-git/fold-failures.log):
  - waitfor, 10-01 19:18;
  - routedriver, 10-02 00:19 (folded 01:54);
  - titleroutes' final review, 05:01;
  - snapdrive, 06:20 and 06:36.

  I re-checked that 4f570d1b71 is not an ancestor of origin/master.
- **The snapshot defect, three times:**
  - #206, 09-24 (NEXT-SESSION-PROMPT.md:40-46);
  - vsh_score.py, 09-25;
  - drive.py and friends, 10-02.
- **Orchestrator keep-busy directives:**
  - "Do not wait for the result" (briefs/titleroutes.md:114, 09-26 20:50);
  - "do not wait for earlier results" (:312, 09-27 19:55);
  - "Do not end this session on 'no device work tonight' again without first
    queuing" (:789, hostops ADDENDUM 15, 10-01 23:10);
  - "Write routes open-loop" and "end every session with something queued"
    (briefs/titleroutes2.md:10, :79, hostops 10-02 04:10).

  I re-read all four.
- **Corrected claims.**
  - lane.local's ADDENDUM 5 read Castlevania `castlevania-cod.returning-144635`
    as "SUCCEEDED" on a frame taken before the HUD (titleroutes NOTES:3889).
  - The re-confirmed route then scored 613 s of Name Entry in dispatch
    (1790897326-autoverdict-3745925).
  - Session 64 thought waitfor was live in the snapshot; session 65 found it
    was not.
  - The routedriver2 brief claimed `route.sh --check` passed on the folded
    snapshot; routedriver2 refuted it ("no profile").
  - Session 44's "focus steal, not heat" was retracted in session 46, but the
    retraction is not yet in targets.toml (DOA3, THPS2x notes).
- **Rejected PASSes still count.** Three rejected PASS verdicts (SMB,
  Castlevania x2) still say `"pass": true` with no WITHDRAWN.txt, and
  host-tools/autoverdict.sh treats any `"pass": true` as "already Playable".
  I re-checked both.
- **The 11 accepted titles.** No acceptance registry exists. The list is
  verdict433's count of 10 plus Blood Wake, the only OWNER_ACCEPTED.txt.

## Session 1 (2026-10-02): done

- Ledger and devtime.
- Frame review of 18 runs.
- Code read of route.sh, drive.py, classify.py and title_verdict.py.
- Route-file census: 61 blind, 1 waitfor, 3 drive.
- Snapshot check: the Android build stubs xemu snapshots.
- CAPA.md.

## For the next lane: do not repeat

- Do not judge a title by its verdict line or its mark frame. Look for
  frames after the mark (`post_frames` in ledger.tsv). For the accepted
  titles there are none.
- Do not count `held ... for Ns` twice. A request can have two result dirs;
  ledger.py dedupes by request id.
- On the Thor, `ROUTE STOPPED ... daijishou` is the coldconfirm HEAT STOP
  (logs/thor-coldconfirm.log), not a crash. On the Nova the same line is an
  emulator exit.
- devwatch columns are: time, device, state, flags, then the request id or
  the hold reason. The hold reason is in column 5, not 4.
- Run X1 (CAPA section 7) before any device time on C2. It is offline and
  decides C2's probability.
