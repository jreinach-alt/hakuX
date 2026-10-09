# lane.verdict433 outbox

Offline protocol (GitHub suspended ~2026-09-29 21:00 PDT): issue posts
accumulate here instead of going to `gh issue comment`. lane.local relays a
summary per issue after reinstatement.

## #433 -- 2026-09-30 05:20 UTC

Session 7's batch-4 results are in: **two new Playable titles, both on the
Nova at the default confirmation regimen.**

- **KOF: Maximum Impact - Maniax** -- PASS Playable, fps_ok=0.9936,
  gameplay 1282.6s, no crash/hang, audio_short=0.0005, 0.1121 J/frame.
- **Azurik: Rise of Perathia** -- PASS Playable, fps_ok=0.9521, gameplay
  1292.3s, no crash/hang, audio_short=0.0, 0.228 J/frame. (This is the same
  title that FAILED its Thor confirmation on heat in session 2 --
  moving heat-sensitive confirmations to the Nova per your 12:00 PDT
  addendum is what turned it Playable.)

The other four in the batch did not read clean verdicts, for two different
reasons, neither of them a real fps/crash finding:

- **WWE Raw 2** and **50 Cent: Bulletproof** voided on a harness bug:
  `titles.qcow2` (the shared Nova HDD file) was pushed with `adb push`'s
  default `rw-r--r--`, one group-write bit short of what xemu needs to open
  it -- same bug as PR #627/lane.hddperm, #397. hostops root-caused it
  mid-batch and already re-queued both (`-1456493r2`, `-1456544r2`); this
  lane did not queue a third attempt.
- **007: Agent Under Fire** hit the same bug from the other side: its run
  started just before hostops's interim chmod-660 fix landed, and instead
  of voiding cleanly it hung silently at `qemu_init` for the full 1475s
  timeout (no crash line, nothing in logcat after `sdl2_display_early_init`
  until the timeout). Not a read on the title -- rerun queued
  (`-366094`).
- **Baldur's Gate: Dark Alliance** booted clean (after the fix) and played
  its full route into gameplay for 1684 of 1760 planned seconds (1190s of
  gameplay, 10s short of the 1200s bar) before an adb capture flake aborted
  the soak. No crash, no hang, no low-fps reading -- a single-run device
  flake this close to the bar. Rerun queued (`-366130`).

Full detail, including the tier A/B/C ranking and prior sessions' work, is
in `docs/lanes/verdict433/NOTES.md` on this branch.

**Note on process:** GitHub returns 403 for this account as of last night,
so this post and the PR body are landing in `docs/lanes/verdict433/` per
the offline protocol addendum instead of `gh issue comment` / `gh pr`.

**Waiting on:** the two reruns just queued (`-366094`, `-366130`) and
hostops's two r2 requeues (`-1456493r2`, `-1456544r2`), all on the Nova,
each 20-30 min once running. Not polling from inside this session per the
offline protocol's scope note -- parking here for the next resume.

## #433 -- 2026-09-30 06:55 PDT

[lane.verdict433] waiting: three more Nova Playable confirmations queued (lane.local's 06:45 PDT addendum).

The addendum's examples don't hold the bar on the Nova when judged over the full window. Nightfire reads 52-65% at 28.5+ and Fuzion Frenzy at best 80.5%. Spikeout, GoldenEye: Rogue Agent and RalliSport 2 have no Nova route run that reached gameplay. So I picked the three titles whose newest Nova route soaks hold the bar by the widest margin:

| Title | Nova evidence | Request |
|---|---|---|
| Alien Hominid | 4 runs at 100%, median 59.94, worst window 41 fps | `1-1790775886-lane.verdict433-3086847` |
| 187: Ride or Die | 1 run at 100%, median 59.94, worst 59.88, in a race | `1-1790775886-lane.verdict433-3086875` |
| Arctic Thunder | 4 runs at 100%, median 39-42, worst 31.4 | `1-1790775886-lane.verdict433-3086903` |

All three use the defaults and 1200 s after the mark. Four earlier confirmations are still queued: WWE Raw 2, 50 Cent, Agent Under Fire and Baldur's Gate DA. All seven start when the Nova's top-up hold lifts.

Playable count from this lane: 2 (KOF: Maximum Impact Maniax, Azurik), with 7 confirmations pending.

Waiting on: the seven dispatch results above.

## #433 -- 2026-09-30 14:10 UTC

Four of the seven pending confirmations are in: **three more titles PASS Playable.** That puts this lane's count at 5, meeting the "3-5 more today" target.

- **WWE Raw 2** -- PASS Playable, fps_ok=0.9982, gameplay 1276.9s, no crash/hang, audio_short=0.0, 0.1357 J/frame.
- **50 Cent: Bulletproof** -- PASS Playable, fps_ok=0.9906, gameplay 1348.3s, no crash/hang, audio_short=0.0, 0.2498 J/frame.
- **Baldur's Gate: Dark Alliance** -- PASS Playable, fps_ok=1.0, gameplay 1303.9s, no crash/hang, audio_short=0.0, 0.1273 J/frame.

hostops's chmod-660 fix for the shared `titles.qcow2` HDD file (the bug that voided WWE/50 Cent and hung AUF last session) held for all three reruns -- clean confirmations, no capture faults.

- **007: Agent Under Fire's rerun booted and played this time, but is not a Playable read.** Reviewing `route-frames/`: the character walks up to a vault-style door at the `mark play` frame and then never moves again for the rest of the 20-minute window -- the same camera angle, same door, same crosshair position recur at the 15-minute and 20-minute marks. The renderer is live (FPS overlay keeps changing) but the scripted route just bounces off the door forever. That's a softlock, not gameplay, so this reads FAIL. AUF needs its own authored route (like KOF/Azurik/BG:DA/WWE/50 Cent already have) before it's worth another confirmation attempt -- flagging this for whichever lane does route authoring.

Also found and noted (not fixed, per standing guidance): `title_verdict.py`'s `--reviewed-gameplay no` path has a logic gap -- reviewing a generic-route run as "not gameplay" still leaves the verdict at "unconfirmed" internally rather than a reviewed "no", because the code has no branch for `reviewed == "no"` when selecting the gameplay mark. Doesn't change any verdict here (both read FAIL), but worth a harness lane's attention. Detail in `docs/lanes/verdict433/NOTES.md`, session 9.

**Five titles confirmed Playable by this lane: KOF: Maximum Impact - Maniax, Azurik: Rise of Perathia, WWE Raw 2, 50 Cent: Bulletproof, Baldur's Gate: Dark Alliance.**

Still queued, not yet run: Alien Hominid, 187: Ride or Die, Arctic Thunder (batch 6, behind three `forzadecay414` requests on an otherwise-idle Nova).

Waiting on: the three batch-6 results.

## #433 -- 2026-09-30 21:15 UTC

Batch 6 (Alien Hominid, 187: Ride or Die, Arctic Thunder) has not finished
yet -- Alien Hominid started running this session, the other two are still
queued. Nothing new to report on the Playable count.

Acted on the two newest addenda while those run:

- **Ranking by margin (09:55 PDT):** re-swept the Nova for the addendum's
  named 30-capped examples (Nightfire, Crimson Skies, Blinx 2, Grabbed by
  the Ghoulies). None clear 90% on a build from `origin/master` -- Crimson's
  only 90%+ reads are on ibcache's unmerged `#591` branch, the other three
  are unchanged from earlier sessions (52-73%) or have no new runs at all.
  Nothing added or dropped from what's queued.
- **Thor cold-start (10:20 PDT):** swept 150 Thor route soaks back to
  2026-09-26 for a light, low-power, bar-holding title. Found one real
  candidate: **Otogi: Myth of Demons**, Thor-only, four independent short
  runs at 88-96% (mean ~91%) and 4.0-5.1 W net, no hang/crash. Queued one
  cold-start confirmation (`1-1790790097-lane.verdict433-43486`, `--device
  thor --hard-pin`, defaults, 1200s after the mark). No second or third
  candidate had real evidence, so only one queued against the addendum's
  ceiling of three -- queuing untested titles for their own sake would be
  the low-probability guess the owner's ranking guidance warns against.
- **Also found, not this lane's work:** Alien Hominid already has a live
  PASS Playable confirmation **on the Thor** from before this pass
  (`1-1790515369-lanelocal-1183547`, lane.local, 2026-09-27). It already
  counts toward the status page total; this lane's own Nova confirmation of
  it (still running) would be a second, redundant read, not a new Playable
  title.

Full detail in `docs/lanes/verdict433/NOTES.md`, session 10.

Waiting on: batch 6's three Nova results and the new Otogi Thor result, all
outside this session.

## #433 -- 2026-09-30 17:59 UTC

[lane.verdict433] waiting: 187 and Arctic Thunder still queued on the Nova, Otogi still running on the Thor. No change to this lane's Playable count (still 5).

Resumed for hostops's 10:58 PDT addendum about Alien Hominid's Thor cold-start. Confirmed directly against the result: `hakux-thor-coldconfirm` force-stopped it at xo 70C, 402 of 1390s, 5.83 W net (over the ~4.5 W cold-start guidance) -- a void, not a FAIL, as hostops found. **Not re-queuing it.** It already has a separate, live Thor Playable confirmation from before this pass (`1-1790515369-lanelocal-1183547`, lane.local, 2026-09-27) -- it's already Playable and already counted, so a fresh confirmation would just spend device time without moving the total.

Also found: the Thor is now under a new hold, `lanelocal-fanwait` (placed ~10:48 PDT, light work only, no new queued runs, lifts after lane.local's fan repair). Not queuing anything further on the Thor while it's up -- on top of session 10's sweep already finding no second candidate with real evidence to queue there anyway.

Five titles confirmed Playable by this lane so far (unchanged): KOF: Maximum Impact - Maniax, Azurik: Rise of Perathia, WWE Raw 2, 50 Cent: Bulletproof, Baldur's Gate: Dark Alliance.

Full detail in `docs/lanes/verdict433/NOTES.md`, session 11.

Waiting on: 187 and Arctic Thunder (Nova), Otogi (Thor).

## #433 -- 2026-09-30 18:13 UTC

[lane.verdict433] waiting: 187 and Arctic Thunder still battery-refused on the Nova (37%, needs ~47-48%, per the 14:15 PDT addendum's own prediction). No change to this lane's Playable count (still 5).

**New finding: Otogi's Thor cold-start confirmation hit a sustained thermal pause mid-run.** Read directly from its `thermal.jsonl`: xo-therm climbed 64C -> 78C over the first 12 minutes with `fan.speed` at 0 throughout (matches lane.thorheat's #614 finding that this unit's fan doesn't spin), then the kernel's `thermal-pause-F8` cdev engaged at ~11:01 PDT and has stayed engaged for 12+ minutes since (temps now declining, 78C -> 70C). This is the OS thermal governor pausing cores, not `hakux-thor-coldconfirm`'s 70C force-stop (no diagnosis file, and xo passed 70C on the way up without the app being killed -- this request predates the coldconfirm runner and started above its 50C cold-slot floor).

Per the brief's own point 3 ("a title that hits the thermal pause during a confirmation is not sustainably Playable on the Thor"), **this disqualifies Otogi as a Thor Playable confirmation regardless of what numeric verdict it produces when it finishes.** Not re-running it there. It also undercuts the method used to pick it: the four short runs that flagged Otogi as light (4.0-5.1W) didn't predict a full 1200s window pushing the same title into a sustained pause on this unit -- a caution for whoever picks the next Thor cold-start candidate, on top of the fleet-level pattern the 12:00 PDT addendum already found.

Full detail in `docs/lanes/verdict433/NOTES.md`, session 12.

Waiting on: 187 and Arctic Thunder (Nova, battery), Otogi's final verdict (Thor, for the record only -- already disqualified by heat).

## #433 -- 2026-09-30 12:50 PDT

[lane.verdict433] waiting: 187 running on the Nova; Arctic Thunder battery-refused on the Nova (46%, needs 48.3%); Crimson Skies newly queued on the Nova. Playable count unchanged at 6 (Alien Hominid plus this lane's five).

- **Otogi (Thor cold-start) FAILS on heat.** thermal-pause-F8 engaged at +703 s, and the run read 35.0% at 28.5+ over 1278.6 s. Peak xo was 77.9 C with the fan at 0 rpm, at only 4.06 W net, which is under the ~4.5 W cold-slot guidance. Short-run power does not predict a full window on the fan-dead Thor. Not re-running.
- **The 600-s rule is applied.** 187 and Arctic Thunder were queued at 1200 s before the rule, and they stay that way: a lane has no way to withdraw a request. Each will be judged as a full confirmation.
- **Added: Crimson Skies, a 600-s Nova confirmation** (`1-1790796880-lane.verdict433-750238`, 820 s).
  - It is 30-capped, with 94.1-96.6% at 28.5+ across four 250 s Nova windows, and no hang or audio short.
  - The 94.1% is master's code path; the 96.6% runs are on unfolded ibcache builds. That puts the chance of a pass at about 0.5.
  - The run decides whether Crimson is Playable now or waits on #591.

Full detail in `docs/lanes/verdict433/NOTES.md`, session 13.

## #433 -- 2026-09-30 21:20 UTC

[lane.verdict433] waiting: Crimson Skies re-queued on the Nova (`1-1790804473-lane.verdict433-1767161`), freshly queued. Playable count now **7** (Alien Hominid plus this lane's six).

- **187: Ride or Die -- PASS Playable.** fps_ok=1.0, gameplay 1286.4 s, no crash/hang, audio_short=0.0, 0.0961 J/frame. This lane's sixth Playable title.
- **Arctic Thunder -- not Playable.** A full-length run read only 63.9% at 28.5+ over 684 s of gameplay, contradicting four earlier short (195-198 s) runs that all read 100%. The route's own scripted input loop runs out of steps at 684 s rather than sustaining the requested window (confirmed via `run.log`: a clean `ROUTE ... end`, no crash, no thermal pause, no capture fault -- the script is just short). Whatever fps it produces past that point falls well under the bar. Not re-queuing without a route that survives to a longer window; not this lane's scope to author one.
- **Found and corrected: Crimson Skies' queued confirmation was withdrawn as a false-positive "Galleon" match.** `queue/withdrawn/1-1790796880-lane.verdict433-750238.why` reads "Galleon is blocked from testing by the owner ... (host-tools/blocked-titles.txt)", but the withdrawn request's `title` field reads "Crimson Skies - High Road to Revenge...", and Galleon's title ID (41540004) appears nowhere in it. The only "Galleon" text anywhere in the request is flavour text in the `crimson-skies` route's own descriptive comment ("...is what the Galleon-era perf runs measured against"). Crimson Skies (4D530021) is not Galleon (41540004) and is not on `host-tools/blocked-titles.txt`. Re-queued as `1-1790804473-lane.verdict433-1767161`. Flagging this so it isn't read as a real block and doesn't recur on whatever withdrew it.
- **Merged `origin/master`**, folding in lane.verdict10min's native 600-s `confirmation_s` default -- `title_verdict.py --require confirmation` now reads the 600-s bar directly.

Full detail in `docs/lanes/verdict433/NOTES.md`, session 14.

## #433 -- 2026-10-01 00:14 UTC

[lane.verdict433] **Crimson Skies -- PASS Playable** (95.0% at 28.5+, 708.9 s, net 6.389 W, 0.2145 J/frame). The first 600-s-native confirmation this lane has judged under the 09-30 rule (audit counter: 1 of 5, not due for a re-run). **This lane's seventh Playable title; eight total with Alien Hominid.**

Playable so far: KOF: Maximum Impact - Maniax, Azurik: Rise of Perathia, WWE Raw 2, 50 Cent: Bulletproof, Baldur's Gate: Dark Alliance, 187: Ride or Die, Crimson Skies, plus Alien Hominid (pre-existing).

Merged `origin/master` (46 commits behind at session start; clean, no conflicts). Brought in lane.uberspike569-gpl's uber pre-raster library (#569) -- but `HAKUX_GPL` defaults to 0, same as master, so it changes nothing for any title judged at the defaults here, and lane.kabukistall's own read says the fight stall stays even with it on. Also brought in titleroutes sessions 39-42: Galleon confirmed owner-blocked in `targets.toml` too, and six new Thor routes queued as screening soaks (DOA3 re-timed, Capcom Classics 2, Castlevania: Curse of Darkness, Shin Megami Tensei: NINE, THPS2x, Tork) -- none of them validated yet. Checked directly: Forza (#583) and GTA SA/ibcache (#591) have not folded.

Re-checked 007: Agent Under Fire against two new long (1935-1941 s) runs from an unrelated lane (`lane.sustain507`, #507 Part C) that happened to use the same generic route -- same vault-door softlock this lane found in session 9 (frames pixel-identical 71 minutes apart). No change: still FAIL, needs its own route.

**Flagging for lane.titleroutes:** its new Shin Megami Tensei: NINE Thor screen looked like the best Thor cold-start candidate of the day on paper (96.7% share, no crash/hang, 4.80 W) -- but the route's `mark gameplay` is an unvalidated `[guess]` placeholder, and the one frame tagged `gameplay` is the Japanese name-entry keyboard screen, not play. The reading is a menu, not gameplay. Needs the route fixed from its own frames (same failure DOA3's v1 route had) before any confirmation is worth queuing on it. Did not queue a Thor confirmation this session -- the only fresh-looking candidate didn't hold up, and spending the day's third Thor slot on a title with no real evidence isn't worth it.

No device request of this lane's own is outstanding. Further progress is gated on other lanes: #583, #591, and titleroutes' route fixes. Nothing left to safely queue from current evidence; parking here rather than guessing.

## #433 -- 2026-10-01 00:40 UTC

No change to the Playable count (still 8: this lane's seven plus Alien Hominid). This session merged `origin/master` (3 commits, lane.titleroutes sessions 39-43's fold only -- no emulator code) and re-checked session 15's open gates directly: #583 (Forza decay) and #591 (GTA SA/ibcache) have still not folded, and titleroutes' Shin Megami Tensei: NINE route is still an unrevised `[guess]` placeholder, parked for a Thor cold slot.

Re-swept every Nova and Thor route soak finished since session 15's close: 3 new Nova runs (two Kabuki Warriors reads, still stalling/hanging; one Forza read at 17.7% share, consistent with #583 being unfolded) and 3 new Thor runs (titleroutes' own pass-1 surveys, crashed before any `mark gameplay`). None is a new Playable candidate.

Nothing of this lane's own is queued or outstanding. Not spending a Thor slot on a guess (2 of the day's 3-cap used, no third candidate with real evidence). Parking again until #583, #591, or a titleroutes route revision changes the picture.

Full detail in `docs/lanes/verdict433/NOTES.md`, session 16.

## #433 -- 2026-09-30 20:55 PDT

[lane.verdict433] waiting: Kabuki Warriors and Forza Motorsport confirmations queued on the Nova, on master `b1cea467c6`. Playable count is **7**.

- **187: Ride or Die is withdrawn: its route ends on profile creation.** The owner reviewed the frames, and its scored window (`-3086875`) is the profile-creation screen, not a race. My last two posts counted it (8). The correct count is 7: Alien Hominid (09-26) plus KOF: MI Maniax, Azurik, WWE Raw 2, 50 Cent, Baldur's Gate DA and Crimson Skies.
- **Frames of the six remaining passes reviewed.** Each mark frame shows live play: a KOF fight, a WWE match, 50 Cent's alley shootout, BG:DA's tavern with the HUD up, and Crimson in flight across five frames. Azurik's mark frame is the 3D training arena under an in-game tutorial box. The route's first A closes that box, and the authoring replay showed Azurik walking 40 s later. Kept. NOTES session 17 names each frame.
- **Batch 10, Nova, the defaults, 1200 s of gameplay (both titles are flagged):**
  - Kabuki Warriors: a 420-s warm-up launch (`-3477434`), then the confirmation (`-3477568`). P3 removes the fight's create burst only on a launch with recorded pipelines, and the dispatcher clears the caches on a new apk, so the confirmation is the second launch on that build. A pass will mean a warm launch: a player's first fight on a new install still stalls once.
  - Forza Motorsport (`-3477700`), on the #583 decay fix. Low odds: the fix's 420-s run read 20-30 fps against the 28.5 bar. The full window still measures whether the decay stays fixed over 20 minutes.

Full detail in `docs/lanes/verdict433/NOTES.md`, session 17.

## #433 -- 2026-09-30 22:10 PDT

[lane.verdict433] **Kabuki Warriors -- PASS Playable** (100% at 28.5+,
1258.8 s, 0.1186 J/frame, warm launch with recorded pipelines per P3).
**Forza Motorsport -- not Playable** (45.3% at 28.5+ over the full
1200-s window; the #583 decay fix holds fps around 20-30 through the
first ~390 s but the longer window still falls under the bar -- reduced,
not removed). Both frames reviewed under the 20:10 rule and show real
gameplay (a fight in progress / a race in progress), not menus.

**Playable count is now 8**: this lane's seven (KOF: Maximum Impact -
Maniax, Azurik, WWE Raw 2, 50 Cent, Baldur's Gate: Dark Alliance, Crimson
Skies, Kabuki Warriors) plus Alien Hominid (pre-existing, 09-26).

Re-swept both devices since session 16's cutoff: nothing else finished is
a new candidate (four more Kabuki/Forza reads on the Nova, none a
confirmation; eleven titleroutes Thor pass-1 surveys, all crashing before
`mark gameplay`). Checked the remaining tier-A/B candidates' existing
evidence (Nightfire, Spikeout, Fuzion Frenzy, GoldenEye: Rogue Agent,
RalliSport 2, Blinx 2, Grabbed by the Ghoulies) against the owner's
margin/low-watt ranking guidance: none clears or approaches the 90% bar in
any run that exists, and three have no judged evidence at all -- queuing
any of them now would be a guess, not a measurement, so none was queued.
The Nova is also at 34% battery with no active charge hold (a titleroutes
request was refused needing 37.3% at session start), which is a further
reason not to spend it on a weak candidate right now.

GTA San Andreas stays gated on #591 (lane.ibcache), confirmed not yet
folded into `origin/master`.

No device request of this lane's own is outstanding. Parking; full detail
in `docs/lanes/verdict433/NOTES.md`, session 18.

## #433 -- 2026-10-01 21:05 PDT

**Flag for lane.local/titleroutes/hostops -- two live `verdict.json`
Playable passes are false positives; please check whether the status page
reads them.**

A new host-side pipeline (`autoverdict.sh`, reading
`host-tools/nova-nominations.tsv`) is now queueing and judging Nova
confirmations itself for titles titleroutes nominates, writing
`verdict.json` directly into `dispatch/results/`. It does not do the frame
review this issue's 09-30 20:10 PDT rule requires, and two of its four
live `pass: true` results are wrong on inspection:

- **Castlevania: Curse of Darkness** (`1790897326-autoverdict-3745925`,
  route `castlevania-cod.returning`): every frame from `163049-c1.png`
  through the mark (`163403-gameplay.png`) is the same static Name Entry
  keyboard screen, not the courtyard gameplay the route describes -- the
  save slot this run's disk needed likely wasn't there (a concurrent
  titleroutes nav.py session shares the same Nova disk; several sibling
  Castlevania attempts in the same window FAILed for a missing mark or
  short duration).
- **Super Monkey Ball Deluxe** (`1790900520-autoverdict-566484`, route
  `super-monkey-ball-deluxe`): the mark frame is real play, but the ball
  rolls off within ~20s and the window spends the remaining ~630 of 654s
  sitting on the Stage Select menu (checked frames at +20s, +3min and
  near the end -- all Stage Select). `fps_ok_share` reads 1.0 because a
  menu renders fine; it can't tell menu from play.

Neither can be corrected with `--reviewed-gameplay`: `title_verdict.py`
only applies that flag to a generic/survey route's `mark play`
(`gameplay_by == "review"`); a title-authored route's `mark gameplay`
(`gameplay_by == "route"`) sets `reached_gameplay` from post-mark frame
activity alone, with no human-review override (`title_verdict.py:431-432`).
Both need a route fix from titleroutes; `title_verdict.py` itself may be
worth a follow-up so an authored-route mark can be challenged the same way
a generic one can.

The other two autoverdict passes checked out on frame review and are
genuine: **Tony Hawk's Pro Skater 2x** (mid-trick, live score/timer) and
**187: Ride or Die** (live race, HUD, cars on track) -- 187's route was
rewritten by titleroutes since this lane withdrew the old one (session 17,
which scored a profile-creation screen); the new one is real. **Playable
count is now 10**: the previous 8 (KOF: Maximum Impact - Maniax, Azurik,
WWE Raw 2, 50 Cent, Baldur's Gate: Dark Alliance, Crimson Skies, Kabuki
Warriors, Alien Hominid) plus Tony Hawk's Pro Skater 2x and 187: Ride or
Die.

GTA San Andreas got a fresh Nova confirmation too: FAIL, 84.6% at the bar
(need 90%), still without #591/lane.ibcache's fix (not yet folded).

No device request of this lane's own is outstanding -- autoverdict's
current nomination queue is exhausted bar a held Sonic Heroes, and this
lane's own tier-A/B sweep (session 18) found no further candidate. Parking;
full detail in `docs/lanes/verdict433/NOTES.md`, session 19.
