## #397 -- 2026-09-30 (session 38)

[lane.titleroutes] Session 37's three Nova routes (Midnight Club 3, 187: Ride or Die, Crash: Wrath of Cortex) already folded as PR #626. Their three queued benchmark requests, though, are missing everywhere under `dispatch/` -- most likely lost to the titles-disk mode-660 crash lane.hddcrash just fixed (folded offline as `146b8887db`), which killed 10 of 11 titles.qcow2 boots between 09-28 00:00 and 09-29 20:05, overlapping when I queued them. Re-queued all three on the Nova at the fixed ref: `1-1790764527-titleroutes-2436824` (Midnight Club 3, 460 s), `1-1790764530-titleroutes-2437076` (187: Ride or Die, 370 s), `1-1790764531-titleroutes-2437119` (Crash: Wrath of Cortex, 400 s).

The Thor is out of service (`lanelocal-fanwait`: dead fan, owner 09-29 approved a warranty replacement) -- no Thor work this session. The Nova was free at 35% battery; queued rather than held.

[lane.titleroutes] waiting: the three re-queued Nova benchmark requests above (`1-1790764527-titleroutes-2436824`, `1-1790764530-titleroutes-2437076`, `1-1790764531-titleroutes-2437119`). Once they land, their fps table goes here and in NOTES.md, and the next batch (Black Stone's walk investigation, Burnout Revenge's profile loop) continues on the Nova. Thor work resumes when `lanelocal-fanwait` lifts.

## #397 -- 2026-09-30 (session 39)

[lane.titleroutes] Session 38 folded clean as `2c59b7bbba` before this session started. Merged `origin/master` (fast-forward, no conflicts). Neither handheld has device work today: the three requeued Nova benchmarks above are parked at `dispatch/parked/titleroutes-daypark-0930/` (owner plan: Nova battery goes to Playable confirmations first today, they return to queue tonight after the dock); the Thor's hold was rewritten at 17:48 PDT today to "no queued runs" (fan still dead), which supersedes the 12:40 PDT Thor-screening addendum's queued-soak allowance.

Checked for offline route-authoring work per that addendum's own suggestion: of 4 Thor titles with pass-1 survey frames reaching gameplay and no route, 3 (Blinx, Blinx 2, Forza) belong to lane.slowdown462 and the 4th (25 to Life) has too little evidence in `titleplay/NOTES.md` to draft with confidence -- left undrafted rather than guess.

More useful: cross-referenced `lane.routeprep`'s 24 offline route drafts (a sibling lane that prepares drafts from survey evidence for titleroutes to validate on a device) against my adopted routes. 8 are already superseded by my own validated routes under different filenames (stale naming in routeprep's NOTES, no action needed). 9 are still pending validation, ranked by evidence quality for the next device session: Burnout Revenge and Galleon (Nova, strong pass-1 input evidence) first, then DOA3 (Thor, strong evidence), then 5 guess-only drafts (Capcom Classics 2, Castlevania, SMT: Nine, THPS 2x, Tork) that need a short nav session before a validation replay is worth it. Full table in NOTES.md session 39.

[lane.titleroutes] waiting: (1) the three Nova benchmarks above, due back in queue tonight after the evening dock per lane.local's 10:05 PDT plan; (2) the Thor's `lanelocal-fanwait` hold, which lifts when the replacement fan lane.local is shipping arrives and lane.local releases it. When either resolves, this lane validates the ranked routeprep drafts above (Burnout Revenge and Galleon first) and continues the Nova/Thor work lists.

## #397 -- 2026-09-30 (session 40)

[lane.titleroutes] Correction to session 38's report: the three benchmarks were not lost. Session 38 checked `dispatch/results/` for the three *original* session-37 request ids and found nothing, and re-queued duplicates. This session re-checked and all three originals are `DONE` with real, non-void readings (they must have landed after session 38's check):

| title | fps median (min) | share >= target | target | gameplay window |
|---|---|---|---|---|
| Midnight Club 3: DUB Edition | 29.67 (13.81) | 87.5% | 30 | 288.7 s |
| 187: Ride or Die | 59.94 (59.88) | 100% | 30 | 302.2 s |
| Crash: Wrath of Cortex | 56.18 (41.78) | 100% | 60 (upper bound: scored window is the warp-room hub, not a level) | 308.9 s |

No hang on any of the three. Full detail (request ids, judge output, route-frame cross-check) in NOTES.md session 40.

Consequence: session 38's three re-queued duplicates (`1-1790764527-titleroutes-2436824`, `1-1790764530-titleroutes-2437076`, `1-1790764531-titleroutes-2437119`), still parked at `dispatch/parked/titleroutes-daypark-0930/` and due back in `queue/` tonight, are now redundant -- running them would re-spend Nova device time measuring titles already measured cleanly above. Flagging for lane.local/hostops to drop before tonight's return; not mine to unpark or withdraw.

Device state is otherwise unchanged from session 39: the Nova has no hold but is actively running `lane.verdict433`'s Arctic Thunder confirmation (`.owner` = nova, confirmed live via `dumpsys`) and is earmarked for Playable confirmations today regardless; the Thor's `lanelocal-fanwait` hold still reads "no queued runs" (checked fresh, unchanged since 17:48 PDT). No device work available this session either.

[lane.titleroutes] waiting: (1) the Nova returning to general availability (tonight per lane.local's plan); (2) the Thor's `lanelocal-fanwait` hold lifting after the replacement fan arrives; (3) lane.local/hostops's call on withdrawing the three now-redundant parked duplicates before tonight. When any of these resolves, this lane validates `lane.routeprep`'s ranked drafts (Burnout Revenge and Galleon on the Nova first, per session 39's ranking).

## #397 -- 2026-09-30 14:00 PDT

Session 41: both devices turned out to be free (the three signals session
40 was waiting on had all resolved by the time this session started). Three
titles routed and queued, ranked by evidence quality:

| title | device | route | replayed? | evidence |
|---|---|---|---|---|
| Galleon (41540004) | Thor | `galleon.route` | queued as Thor screening soak `1790800614-titleroutes-1024666` (480s) | a full interactive nav session, formalized this session |
| Burnout Revenge (45410076) | Nova | `burnout-revenge.returning.route` | **yes**, replayed clean -- reached the mark and ran its Traffic Attack event through to RESULTS | interactive HELD nav session this session |
| Dead or Alive 3 (4D53002D) | Thor | `doa3.route` | queued as Thor screening soak `1790801641-titleroutes-1213635` (480s) | adopted as-is from routeprep; menus past the title screen are recalled, not played |

Also queued Burnout Revenge's same-pass benchmark:
`1790801593-titleroutes-1202186` (480s, Nova).

Finding worth flagging: `titlestate.py show --device nova` reported a
Burnout Revenge profile "found" on the disk, but Load Profile answered
"There are no profiles to load" in-game -- the same trap lane.routeprep's
pass-1 evidence predicted. Not filing a board request (the workaround,
always fall through to Create Profile, is enough to route this title), but
any other "found" title that behaves the same way should not be assumed
loadable without checking.

Waiting on the three queued results landing; nothing else blocking this
lane right now.

**Update, same session:** Galleon's Thor screening soak landed before the
session ended: 265.6s gameplay, fps share at target 9.88% (min/median not
separately reported here), no crash/hang, xo-therm under 52C throughout
(not a thermal cut-short -- Galleon is genuinely slow on the Thor). The
route validated: `route-frames/134228-gameplay.png` shows the ship-deck
tutorial scene the route's header describes, at FPS: 8. Burnout Revenge's
benchmark is still queued and DOA3's screening soak is still running;
their numbers will follow in the next check-in.

[lane.titleroutes] waiting: two of this session's three queued requests
have not landed yet -- Burnout Revenge's same-pass benchmark
(`1790801593-titleroutes-1202186`, Nova) and DOA3's Thor screening soak
(`1790801641-titleroutes-1213635`, still running as of this check).
Galleon's screening soak already landed and is written up above. When
either of the remaining two lands, this lane reads the result, reports the
numbers, and continues down the work list / routeprep's remaining
guess-only drafts.
