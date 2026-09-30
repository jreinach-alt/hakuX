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
