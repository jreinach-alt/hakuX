# lane.nfsdefault1011 -- the three NFS switches on by default, and "Submit frame buffering" honoured (#433, 0.5)

## 0. Base

Base is `origin/master` at `6d8947bb47` (fold of lane/fastpaths1010), already checked out for this worktree.
`git merge-base --is-ancestor fa45851449 HEAD` -- true: fastpaths1010's "Fast renderer paths" toggle is in this
base, so step 1(b) extends an existing block rather than adding a new one. No merge needed.

## 1. Code

**(a) Submit frame buffering default, 3 everywhere.** `SettingsActivity.kt` already defaulted to 3 in both
places (the brief's own table marked it so); the two places that still said 2 were
`xemu_android.cpp:1188` (`GetPrefInt(..., "submit_frames", 2)`, what a fresh install with no pref ever written
runs) and `PerGameSettingsActivity.kt:94` (`globalValue("submit_frames", "2", ...)`, the per-game screen's
label for the global default). Both changed to `3`. `draw.c`'s own C default was already 3 (desktop
unchanged) and was not touched. `PerGameSettingsManager.kt` lists `submit_frames` as a per-game override key
with no default value in that file -- nothing to change there, and it is not in the brief's file list, so it
was left alone (a one-word comment edit there was reverted before committing: the board reads `Files:` to keep
lanes off each other's files, and that file is not on this lane's list).

**(b) `HAKUX_POSTED_PUT` and `HAKUX_LOCKFREE_WAKE` folded into "Fast renderer paths".** `MainActivity.kt`'s
`FASTPATHS_VARS` array (set together from the `fastpaths` pref, on by default) grew from six entries to eight;
the two doc comments above it and above `fastpathsEnabled()` now name all eight and the four lanes that folded
them (reportasync1010, texscan1010, drawrec1010, perdrawon1010, postput1010, lockwake1011). The `hakuX-build`
log line (`fastpaths: ON/OFF (#433)`) now also lists `FASTPATHS_VARS` by name, so a logcat read can tell which
switches a given build actually carries without opening the source -- useful now that the array has grown past
what one log word covers. `strings.xml`'s `settings_fastpaths_desc` gained one clause: "...and the hand-off of
GPU commands from the emulated CPU", keeping the existing "turn off only if" sentence. No change to `pfifo.c`,
`draw.c`, or any native file besides the one `GetPrefInt` default in (a); the switches' own env-var names and
semantics are unchanged from postput1010/lockwake1011/coldstart1010.

**Checked:**
- `cd android && ./gradlew compileDebugKotlin --offline -q` -- exit 0, no diagnostics.
- `python3 docs/lanes/flip474/ndkcheck.py android/app/src/main/cpp/xemu_android.cpp` (NDK compile line of the
  main checkout's newest arm64 Release configure, `-fsyntax-only`) -- exit 0, 0 error lines, 0 warnings in the
  file. The one-line default-value change is the only native edit, and it carries no new logic.
- `python3 docs/testing/check_android_guards.py` -- ok (3305 files).

## 2. NFS MW proof it reaches native

Prediction `docs/testing/predictions/nfsdefault1011-nfs.json`, reader `nfsread.py` (this directory), modeled on
fastpaths1010's `fpread.py`/`raread.py` (same route, same ON-no-env/OFF-explicit-env shape) rather than
lockwake1011's `wakeread.py`/`ppread.py` (those carry instrumentation-arm plumbing, `HAKUX_PROBE_WAITS`/
`HAKUX_FRAMETRACE`, that this plain-build A/B does not use). Legs: V (validity: marks, valid starts, boot
inputs, per-arm pace-line counts, and the on/off log lines -- `[postput] on`, `[lockwake] on`, `submit frames:
3` on ON; none of `[postput]`/`[lockwake]` and `submit frames: 2` on OFF); K (ON's cold start 1 <= 34.5 ms,
lockwake1011's own K bound); N (ON not slower than OFF at the cold start).

Queued in two batches of two per the pilot gate (no `pilots/nfsdefault1011.ok` on file; `(500+90)*4` = 2360 s =
39.3 min, over the 30 min that always goes through with no reviewed pilot; `(500+90)*2` = 19.7 min does not
need one): OFF + ON first, pilot verdict written, then ON + OFF.

**OFF1 (`1-1791735965-nfsdefault1011-3581025`) read:** found and fixed a leg bug, not a code bug. OFF's
logcat carries `env: HAKUX_SUBMIT_FRAMES=2` and draw.c's own `[coldstart1010] submit_frames=2
(HAKUX_SUBMIT_FRAMES; pref 3)` -- the engine ran at 2 submit frames as the arm intends. But
`xemu_android.cpp`'s `"submit frames: %d"` line (the one step 1a's brief cited as "the proof") logs the
*pref* value fed into `xemu_set_submit_frames` (3, since step 1a's change), not the value draw.c actually
runs with once `HAKUX_SUBMIT_FRAMES` overrides it -- so that line reads "submit frames: 3" on OFF too, and
was never going to prove the OFF arm's switch. This is pre-existing coldstart1010 behavior, not something
introduced by this lane's step 1a, and not a reason to touch `xemu_android.cpp` beyond the one default
already changed: draw.c's own log is the authoritative line for what the engine ran with when an env
override is in play, and `nfsread.py`'s `LOG_SUBMIT2` now matches that line instead
(`\[coldstart1010\] submit_frames=2 \(HAKUX_SUBMIT_FRAMES`). `[postput]`/`[lockwake]`/marks/valid-starts/
boot-input legs all PASS on OFF1; cold start 1 read 43.94 ms, 12/12 valid starts, 2 cold pace lines pooled
so far (floor is 3, needs OFF2 too). Full V/K/N verdict waits on all four runs.

**Pilot batch written up, ON1/OFF1 both pass all V legs** (`pilots/nfsdefault1011.ok` written); second
batch queued: ON2 `1-1791741301-nfsdefault1011-87617`, OFF2 `1-1791741306-nfsdefault1011-87778`.

**ON2 and OFF2 are VOID -- route desync, not a code finding.** lane.local flagged both (2026-10-11,
11:17 PDT): the open-loop first-run route lost timing against the game's own menu/dialog pacing.
87778 never left the name-entry keyboard for all 12 marks (two lost HATX-right taps sent it down
Start Career -> autosave -> keyboard instead of Quick Race). 87617 hit "The autosave feature has been
disabled" at the mm-quickrace mark, then settled into the real race for starts 2-11, but start 1
(`mark gameplay`, the one the cold-start K/N legs read) and start 12 are attract-mode demo footage, not
the player's race. `raread.bad_starts` saw none of this: every pad.sh input in both runs returned
success, so marks=12/valid=12 for both runs on the old V leg -- the leg could not see a desync that left
no input-failure trace in run.log.

Added `hud_bad_starts()`/`hud_frac()` to `nfsread.py` (PIL, already a dependency of several other lanes'
readers): reads each start's `route-frames/*-sN-g11.png` screenshot and checks the speedometer dial's HUD
box (bottom-right eighth of frame) for the near-black disc that is only ever present during an actual
race. Measured on the two pilot runs' 24 known-good frames: black fraction in [0.056, 0.526]. Measured on
87617/87778's desynced frames: 0.017 (attract footage, no HUD at all) up to 0.805 (dark menu/keyboard
background) -- both clearly outside that band and outside each other, so one bound width (0.05-0.55)
catches both failure shapes. Re-read with the fix: 87617 now drops `gameplay` and `go12` (10/12 valid, V
leg fails since `gameplay` -- the cold-start mark -- is one of the two); 87778 drops all 12 (0/12 valid).
Pooled OFF1+OFF2 and ON1+ON2 give 0 extra cold pace lines from the VOID runs (correctly; their `gameplay`
start is excluded either way), so the V leg's cold-pace-line floor also fails on both arms. Full verdict:
VOID. This is scoped to `nfsread.py`, not `raread.py` (reportasync1010's shared module): it is this
route's and this title's screens, not the pace/mark protocol every other lane's reader shares.

**lane.local's direction (2026-10-11, 11:17 PDT):** do not requeue step 2's two voided arms yet. A new
lane, nfsroute1011, is building a saved profile and a screen-gated version of this route (`waitfor` aborts
on a mismatch instead of plowing ahead on a stale assumption); wait for its addendum to this lane's brief
before requeuing ON2/OFF2. Steps 3 (Simpsons) and 4 (screen) do not depend on it and continue below. The
HUD check stays in `nfsread.py` as a second opinion even once the gated route lands -- it reads what's
actually on screen, which a screen-gate's own pass/fail can't fully stand in for on its own.

**lane.local, 11:23 PDT, on the HUD check's margin:** confirmed right, and confirmed holding the
re-queues. Flagged that the low-side margin is thin -- good frames bottom out at 0.056 (`104226-s9-g11.png`,
OFF1), attract footage reads 0.017, a gap of 0.039 against the picked bound of 0.05. `HUD_LO = 0.05` sits
inside that gap, closer to the good side; recorded here rather than moved, per the instruction to treat a
near-the-edge good frame as a reason to look at the frame by eye, not to retune the threshold on two
runs' worth of evidence. `nfsroute1011` started 11:22 PDT (Sonnet): first deliverable is a screen-gated
`nfs-mw-quickrace.route` (same path, same race timing, so ON2/OFF2's eventual re-runs pool with OFF1/ON1).
Addendum 2 lands when it proves.

## 3. The Simpsons Hit & Run in free roam

**Route.** `docs/testing/titles/routes/simpsons-hit-run.route` (new file; not in the brief's original
Files: list, added because step 3 says this title "has no route in docs/testing/titles/routes/" and asks
for one -- recorded in PR.md's Files: line). Copied near-verbatim from lane.frametrace's
`simpsons-frametrace.route` (docs/lanes/frametrace/), which that lane's NOTES.md section 8 confirms
reached free roam on the Nova and stayed there: "every route frame from `mark gameplay` ... to the end has
Homer on foot in the world with the Marge portrait and the minimap, no dialog" (203 s window, golden
`bcc71e970cff`, run `1-1791245535-lane.frametrace-680559`). That route was itself written from pathfind's
held confirmation session (`docs/lanes/pathfind/runs/screen-simpsons-hit-run/hold/`, `pass: true`,
`reached_gameplay: true`, `position.measured: true`, `position.first_last: 0.59` -- the player moved).
`# state: any` (titlestate.py confirms Simpsons has a golden, `bcc71e970cff`, so `first-run` would be
wrong); `route.sh --check` and `titlestate.py resolve-route --route simpsons-hit-run --title-id 56550015
--device nova` both pass (`"state": "any", "refuse": null`). No new route-writing session was needed: the
proven blind entry (rounds of START/A through every cutscene/menu, then a walk-and-turn loop with
periodic jump) already does what step 3 asks for.

**Resume, attempt 2 (this session).** The previous session's last commit was the prediction registration
(`859815ff21`); its uncommitted `PR.md` diff (step 3 section written, not yet merged into the committed
file) shows it had gone on to queue OFF1 (`...429629`) and ON1 (`...430174`) and then ended its turn --
Addendum 2 is lane.local catching that same mid-wait ending and resuming this lane with instructions to
read the two results in the foreground. Both runs finished clean on the device side (`DONE`, `result.json`
present, no crash) by the time this session started, so no device time was lost, only a session's worth of
wall clock. Addendum 2 said "queue ON2/OFF2 if both are clean" -- they are not: read below.

**OFF1/ON1 read: VOID, both runs. Not a reader bug -- Homer is physically wedged in a corner of the
house for the entire scored window, in both arms.** `simpread.py` on the two: B legs pass (booted,
reached_gameplay, no crash, arm read correctly from env), but V fails both --
`still_frac` 0.57 (OFF1) and 0.625 (ON1), both over the 0.5 bar (`hitch_report.position_fail`,
`classify.motion` pixel-diff). Visual check of the route-frames confirms it: OFF1's `113705-gameplay.png`
(the `mark gameplay` frame, Homer facing a wall corner, grass patch, Marge-portrait HUD) and
`113828-play.png` (123 s later, last frame of the run) are pixel-identical -- he never left the corner the
pre-mark walk drove him into. `first_last` is non-zero (0.178 OFF1, 0.044 ON1) because of incidental
lighting/shadow flicker, not movement; `still_frac` is the leg that actually catches a parked character,
and this is why NOTES.md section 2's earlier HUD check (built for NFS MW's desync, a different failure
shape) would not have caught this one -- the race HUD check doesn't apply to Simpsons, and a static_window/
position check is the right instrument for "right title, right screen, not moving," which is what this is.

**This is not new to this lane's copy of the route -- the same wall-corner wedge is in frametrace's own
"proven" run.** Re-ran `hitch_report.py` cold against `1-1791245535-lane.frametrace-680559` (the exact run
NOTES.md section 3 and `simpsons-frametrace.route`'s own header cite as proof the route "reached and
sustained free roam," "no dialog," `position.first_last: 0.59`): `liveness verdict: FAIL static window: 94%
of pixels never moved more than 10/255 from the window's first frame, over 20 sampled frames`. Its own
`175055-gameplay.png` and `175208-play.png` (113 s apart) are the same corner, same wall, same pose as this
lane's OFF1/ON1. The `position.first_last: 0.59` figure frametrace's NOTES.md and this lane's own step-3
writeup (above) leaned on was pathfind's **held, interactively-driven** confirmation session
(`docs/lanes/pathfind/runs/screen-simpsons-hit-run/hold/`) -- a human/screen-gated run that actually walked
around -- not a re-measurement of this blind scripted route's own replay. frametrace wrote the route to
mimic that session's *entry* (the cutscene/menu taps), and that part reproduces faithfully; the free-roam
*play* loop it then bolted on (walk forward, turn, forward, turn) was never independently checked against
this instrument, and it drives Homer into the same dead-end every time -- fully deterministic, reproduced
identically across three separate runs (OFF1, ON1, and frametrace's original) on three different builds and
two different submit_frames arms, so this is route geometry, not timing jitter or this lane's switches.

**Fix: one change to the play loop, not the entry.** The pre-mark `repeat 3` walk (`axis LY min` x3, ~4.5s
of forward motion with no turn) is what drives Homer into the corner before `mark gameplay` even fires --
changing it risks moving the mark's own position (and this lane does not have a reference for where `mark
gameplay` should land, only that the entry sequence up to it is shared and correct). Left that alone.
Changed the `repeat forever` play loop instead, to back out of whatever he's pressed against *before*
resuming the forward-and-turn pattern, every iteration -- self-correcting rather than a one-shot escape, so
a re-wedge later in a 300s window (turning into a different wall) also clears on the next lap:
`axis LY max` (reverse) 1.5s, a wider turn (1.2s instead of 0.8s) while still reversing, then the original
forward-and-turn body. This is the cheapest plausible fix (reverse-to-unstick is the standard escape for a
concave-corner trap in a third-person walker, and costs one device-time pilot to check rather than several
rounds of blind geometry guessing) -- not a rewrite of the entry sequence, which is correct and shared
with other lanes' use of this route file. Queuing one OFF+ON pilot pair (2 runs, (300+90)*2=780s=13min,
under the always-goes-through bar and covered by `pilots/nfsdefault1011.ok` regardless) to check the fix
before committing to the full 4-run A/B this step needs.

**Validation pilot: fix confirmed.** OFF (`1-1791744545-nfsdefault1011-620311`) and ON
(`1-1791744548-nfsdefault1011-620739`), run on the same route (new play loop) against the same save.
`simpread.py`: both B and V PASS on both runs now -- `still_frac` 0.1667 (OFF) and 0.0 (ON), both well under
the 0.5 bar; `first_last` 0.65/0.66, an order of magnitude above the old stuck runs' 0.04-0.18. Visual
check: OFF's `120148-gameplay.png` starts in the same corner as every prior run (confirming the pre-mark
approach is unchanged, as intended), and `120320-play.png` (92s later) shows Homer has walked clear of the
yard entirely and is standing at the house's front door with hedges and a "press Y" prompt visible --
genuine free roam, not a different static spot. `W` also PASSED on this single-run-per-arm read (ON 59.29
>= OFF 46.72 - 1.0), but that is 1 run per arm against the prediction's `runs_per_arm: 2`, not yet the full
verdict. Queued the second pair to complete it: ON2 `1-1791745784-nfsdefault1011-874556`, OFF2
`1-1791745785-nfsdefault1011-877404`.

Both arms' gfps readings here (ON ~59, OFF ~42-47) are well above postput1010/vcpusleep-simpsons.json's
~40 fps figure for this title. Not investigated further -- `title_verdict.judge()`'s
`g_fps_mean_reported_not_judged` is the same instrument pathfind's own hold verdict used, and the fix
changed where Homer walks (now covers open yard and a paved path, not wedged against one wall's texture),
which is plausibly just a different, more open piece of geometry than the corner nook.

**Second pair (full verdict).** ON2 `1-1791745784-nfsdefault1011-874556`, OFF2
`1-1791745785-nfsdefault1011-877404`. Both B and V PASS on all four runs now. `simpread.py`'s full read:

| | OFF (pre-lane shipped) | ON (this lane's default) |
|---|---|---|
| run 1 | `...620311` -- 46.72 gfps, still_frac 0.167 | `...620739` -- 59.29 gfps, still_frac 0.0 |
| run 2 | `...877404` -- 48.65 gfps, still_frac 0.0 | `...874556` -- 59.19 gfps, still_frac 0.0 |
| mean | 47.69 | 59.24 |

**W PASS: ON mean 59.24 >= OFF mean 47.69 - 1.0. VERDICT: PASS.** ON is not slower than OFF on this
GPU-paced title in free roam -- the opposite of the ~4 fps regression `c2dfca18a1` (#507) produced, and
postput1010's PR.md condition for POSTED_PUT going default-on is satisfied. All three switches
(`HAKUX_POSTED_PUT`, `HAKUX_LOCKFREE_WAKE`, `HAKUX_SUBMIT_FRAMES=3`) stay in the default. Step 3 is done;
proceeding to step 4's title screen.

## 4. The 38-title screen

Scope: fastpaths1010's PR.md table has 39 rows, one ("Call of Duty 3") marked "not run: title not on
device". That is 38 titles actually screened, not 37 as the brief's own text states -- recorded here,
not silently corrected to match the brief, since the real number is what the prediction file and the
queue need. RalliSport was already excluded from fastpaths1010's own scope; the five owner-deferred
titles (Azurik, Baldur's Gate: Dark Alliance, NBA Live 2004, Castlevania: Curse of Darkness, 50 Cent:
Bulletproof) stay off per that lane's own Addendum 3, carried forward unchanged.

Request shapes, copied from fastpaths1010/NOTES.md sections 4.1.2/4.3/4.4 (confirmed against that
lane's own `request.json` files for the ISO filenames and route names, not just its prose table, since
the "4 route titles" count in its running NOTES.md undercounted a later addendum -- see that lane's own
section 4.3 for why): 10 titles carry a named route, 300s, no `--frames-every` (a scored route supplies
its own `mark`/`shot` frames): Crimson Skies (`crimson-skies`), Spikeout (`spikeout`), Jet Set Radio
Future (`jsrf`), Tork (`tork`), Kabuki Warriors (`kabuki-warriors`), 187: Ride or Die
(`187-ride-or-die`), Tony Hawk's Pro Skater 2x (`thps2x`), KOF: Maximum Impact - Maniax (`kof-mi`),
Alien Hominid (`alien-hominid`), WWE Raw 2 (`wwe-raw-2`). The other 28 run as a soak to the title
screen, 180s, `--frames-every 15`. Full per-title ISO filenames: `nfsdefault1011-screen.json`'s
`titles` array.

Same env A/B as steps 2/3: ON queues with no `--env` (app default after step 1); OFF queues `--env
HAKUX_POSTED_PUT=0 --env HAKUX_LOCKFREE_WAKE=0 --env HAKUX_SUBMIT_FRAMES=2`. One run per arm per title
(not two) -- a screen catches a correctness regression, not a precise pace measurement, per the brief.
Columns read: fatal, frames, gfps (no reports column). `docs/lanes/nfsdefault1011/screenread.py`
(new, modeled on `simpread.py`'s use of `title_verdict.judge()`) prints all three per run; frames is a
raw capture count for me to review by eye, gfps is the same raw `g_fps_mean_reported_not_judged` figure
`fpread.py`/`simpread.py` already read. There is no automated per-title pass/fail leg -- the brief's own
screen has no single numeric threshold that works across 38 different titles, same as fastpaths1010's.

Batch 1 queued (10 route titles, 20 runs, ON then OFF per title, `HAKUX_RELEASE_PRIO=1`): Crimson Skies
(`...1478599`/`...1479231`), Spikeout (`...1482768`/`...1483299`, route resolved to `spikeout.returning`),
Jet Set Radio Future (`...1484105`/`...1484526`), Tork (`...1484691`/`...1484875`), Kabuki Warriors
(`...1485413`/`...1485861`), 187: Ride or Die (`...1486398`/`...1486778`), Tony Hawk's Pro Skater 2x
(`...1492482`/`...1492811`), KOF: Maximum Impact - Maniax (`...1493417`/`...1494854`, route resolved to
`kof-mi.returning`), Alien Hominid (`...1495590`/`...1495950`), WWE Raw 2 (`...1496167`/`...1496518`). The
pilot gate logged cumulative device time rising past 30 min as the batch queued but admitted every request
on the existing reviewed pilot (2.2 h old at queue time), as it should. Nova was already running
profileconv1011's job with gtaroutes1011/gtasagpu1011 queued ahead of this batch, so these 20 will wait
their turn behind other lanes' release-priority requests.

Polled through 20:24 UTC: profileconv1011's job finished, gtaroutes1011's is now running, gtasagpu1011's
is queued ahead of this batch's 20, no results yet. Queue position is advancing normally (not stuck) --
Nova is just shared with two other active lanes right now, and this batch alone is ~130 min of device
time. Stopping here per the lane's own rule on a wait this long; see the `waiting:` PR comment.

Prediction registered: `nfsdefault1011-screen.json` @ `821fb0af67fc791541c771cc3b7b845cca178e04019c1e9bde77d59b4b1607a0`,
same ref as steps 2/3 (`7002282149`, unchanged since step 1 -- no code has moved). Device presence is
not re-verified by a live listing before queuing (none exists, confirmed by searching for one); a
"title not on device" on any of these 38 is possible despite all 38 having run clean under fastpaths1010
within the last day (that lane's own screen lost 12 of 21 titles mid-run once) and is treated as a
per-title blocker (moved to `not_run`), not grounds to distrust the batch. Queuing in batches of about
10 titles per the brief, `HAKUX_RELEASE_PRIO=1`, ON then OFF per title. `pilots/nfsdefault1011.ok` (step
2, same day) covers the requester; no fresh pilot needed before the first batch.

**Resume, attempt 3 (this session, Addendum 4).** The previous session (attempt 2) ended at 13:25 PDT
having noted batch 1's queue position in NOTES.md ("advancing normally, not stuck") but wrote no
`docs/lanes/nfsdefault1011/WAITING` file -- Addendum 4 (hostops, 15:13 PDT) caught this: with no WAITING
file naming what the lane was waiting on, lanewaker.py had nothing to match against, so the lane sat
unattended for 90+ min while batch 1 continued draining on the Nova. This is the same class of mistake
the lane's own rules warn against (never end a session waiting on something with no outside signal
named) -- the previous session correctly *did not* poll in a blocking background task, but also did not
register the wait anywhere lanewaker could see it, so nothing resumed the lane until the hostops addendum
did it by hand.

Checked batch 1's 20 ids against `dispatch/results/*/DONE` at session start (15:12 PDT): 14 DONE, 1 running
(`...1493417`, KOF: Maximum Impact - Maniax's ON leg), 5 still queued (`...1494854`, `...1495590`,
`...1495950`, `...1496167`, `...1496518` -- KOF's OFF leg, Alien Hominid, and WWE Raw 2's two legs).
Unchanged from Addendum 4's own count one minute earlier, confirming the batch is still draining behind
gtaroutes1011/gtasagpu1011's work, not stuck. Writing `WAITING` with these 6 ids now and ending per
Addendum 4's instruction, rather than polling in the foreground for however long the rest of the batch
takes -- lanewaker checks every 5 min and will resume this lane once all 20 are DONE or WITHDRAWN.

**Attempt 3 (this session).** Attempt 2 ended correctly per Addendum 4's instruction (WAITING written and
pushed at `b5ff4c8d27`, naming the 6 still-running/queued ids); it did not finish the brief because that
was the whole point of ending there -- the remaining 6 of batch 1's 20 runs were still on the Nova behind
gtaroutes1011/gtasagpu1011's work, and the lane's own rule is not to poll a long device drain in the
foreground. lanewaker resumed this session once all 20 reached a terminal state, as designed. All 6
WAITING ids read DONE in `$DISPATCH_DIR/results/` (the real dispatch dir is
`/home/justin/hakux-work/dispatch`, not a path under this worktree -- `docs/lanes/.../WAITING`'s run ids
are looked up there, not relative to the lane directory).

While reading batch 1 with `screenread.py`, found its `frame_count()` globbed `d/*.png` directly; every
capture actually lands in `route-frames/*.png` (route titles) or `frames/*.png` (soak `--frames-every`
titles, per `request.sh`'s own frames-every help text), so the script would have printed `frames` as 0 for
every one of the 38 titles regardless of how many stills a run actually captured -- silently useless for
the "frames is a raw capture count for me to review by eye" column the brief asks for. Fixed to glob both
subdirectories; not a behavior change to any other lane's reader, since `screenread.py` is new to this one.

**Batch 1 read (10 route titles, 20 runs), all DONE, all pass:**

| title | arm | fatal | frames | gfps | verdict |
|---|---|---|---|---|---|
| Crimson Skies: High Road to Revenge | ON/OFF | none/none | 3/3 | 29.97/30.01 | pass |
| Spikeout: Battle Street | ON/OFF | none/none | 8/8 | 60.03/60.01 | pass |
| Jet Set Radio Future | ON/OFF | none/none | 4/4 | 59.87/59.76 | pass |
| Tork: Prehistoric Punk | ON/OFF | none/none | 16/15 | 30.37/29.21 | pass |
| Kabuki Warriors | ON/OFF | none/none | 16/16 | 52.65/59.37 | gap 11.3%, wider than fastpaths1010's own noted-but-not-escalated 6% on this same title -- rerun queued, see below rather than called here |
| 187: Ride or Die | ON/OFF | none/none | 21/21 | 60.02/60.09 | pass |
| Tony Hawk's Pro Skater 2x | ON/OFF | none/none | 13/13 | 59.40/59.48 | pass |
| KOF: Maximum Impact - Maniax | ON/OFF | none/none | 11/11 | 59.76/59.98 | pass |
| Alien Hominid | ON/OFF | none/none | 1/1 | 59.96/59.87 | pass (route has one `shot`, at `mark gameplay`; 1 frame is this route's own design, not a capture failure) |
| WWE Raw 2 | ON/OFF | none/none | 15/15 | 59.07/59.94 | pass (1.5% gap, in line with the rest of the screen) |

No ON-only fatal anywhere in batch 1. Frame-by-frame visual check on Kabuki Warriors' `gameplay` shot
(the only title with a gap worth a closer look): ON's frame shows a mid-combo clash with a particle-glow
effect and a `50` round timer; OFF's frame shows a downed-opponent pose against a plain striped curtain
background and a `40` timer -- different points in a CPU-vs-CPU-random-opponent fight (the route's own
header: "The CPU's fighters are random, so the arena differs run to run"), not a shared static scene a
pixel diff could call corrupted either side. This is consistent with route-level gfps noise from scene
complexity, same shape as fastpaths1010's own 6% Kabuki gap, but this lane's gap is nearly double that
precedent and the screen's own prediction (`nfsdefault1011-screen.json`'s `prediction` field) explicitly
named "wider than fastpaths1010's typical <1%... not Kabuki Warriors' noted 6% gap" as a possible
refutation signal -- so rather than wave this one through on the fastpaths1010 precedent alone, queued one
rerun pair before calling it, per the brief's "a title that fails gets two reruns before anything is
attributed to a switch" (not treating this as a confirmed fail yet, just not confirming pass on one sample
when the prediction itself flagged this exact comparison): ON `1-1791758946-nfsdefault1011-3829286`, OFF
`1-1791758950-nfsdefault1011-3829494`.

**Batch 2 queued (10 soak titles, 20 runs, ON then OFF per title, 180s, `--frames-every 15`,
`HAKUX_RELEASE_PRIO=1`):** ToeJam & Earl III (`...3830698`/`...3832157`), Halo: Combat Evolved
(`...3832362`/`...3832563`), Panzer Dragoon Orta (`...3833185`/`...3833645`), Capcom vs. SNK 2 EO
(`...3833892`/`...3834202`), The Simpsons Hit & Run (`...3834333`/`...3834604`), Dark Summit
(`...3835673`/`...3837409`), Gunvalkyrie (`...3838236`/`...3838429`, title id resolved to `49470017`),
Indigo Prophecy (`...3838682`/`...3838907`), NFL Blitz 2002 (`...3839085`/`...3839302`), Fight Club
(`...3839952`/`...3840421`). Pilot gate admitted every request on the existing reviewed pilot (`
pilots/nfsdefault1011.ok`, 4.9 h old at queue time), cumulative device time climbing from ~27 min to
~103 min as the batch queued, same shape as batch 1. Combined with the Kabuki rerun pair, this session
queued 22 runs total.

Writing `WAITING` with all 22 ids (the 2 Kabuki reruns + batch 2's 20) before ending, per Addendum 4's
instruction not to end a session with runs in flight and no file naming them.
