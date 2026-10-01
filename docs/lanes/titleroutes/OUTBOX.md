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

## #397 -- 2026-09-30 15:00 PDT

Session 42 (Thor screening program).

- **DOA3's first screen is void by heat, and the frames show a route
  timing error, not a title problem.** In `1790801641-titleroutes-1213635`,
  the runner stopped the soak at xo 70 C at 284 s, before the route's first
  press. The route waited 300 s blind, which is the timing of pass 1's
  cold-cache boot. With the cache warm, the attract was already playing at
  t100: t200 a cutscene at 46 fps, t260 a fight at 54 fps. The route is
  re-timed (START at t~75) and re-queued.
- **Galleon is blocked by the owner** (14:40 PDT). Its screen (9.88% at
  target) is on record, but it is not counted as a screen or a nomination.
- **Six Thor screens are queued** (480 s, hard-pinned, ref `5b193af6d0`):

| title | route | request | replayed? |
|---|---|---|---|
| Dead or Alive 3 | doa3 (re-timed) | 1790805442-titleroutes-2050455 | no: the screen is its validation |
| THPS2x | thps2x | 1790805442-titleroutes-2050654 | no |
| Capcom Classics Collection Vol. 2 | capcom-classics2 | 1790805455-titleroutes-2055173 | no |
| Castlevania: Curse of Darkness | castlevania-cod.first-run | 1790805456-titleroutes-2055301 | no |
| Shin Megami Tensei: NINE | smt-nine | 1790805456-titleroutes-2055567 | no |
| Tork: Prehistoric Punk | tork | 1790805457-titleroutes-2055759 | no |

  The last five are lane.routeprep's drafts, which are guesses past the
  boot. Each soak takes a frame at every step, so a miss revises the route.
- Burnout Revenge's Nova benchmark (`1790801593-titleroutes-1202186`) is
  still queued.

## #433 -- 2026-09-30 15:00 PDT

No Nova nominations yet. The one landed Thor screen is Galleon (9.88% at
target), and the owner has since blocked it. Six screens are queued on the
Thor (see #397).

[lane.titleroutes] waiting: seven dispatch requests. Six Thor screens:
1790805442-titleroutes-2050455, -2050654, 1790805455-titleroutes-2055173,
1790805456-titleroutes-2055301, -2055567, 1790805457-titleroutes-2055759.
One Nova benchmark: 1790801593-titleroutes-1202186. The waiter's resume on
their results is the signal. The next session reads each one's
route-frames, revises the misses, and nominates any screen at 90% or more
at 28.5+ with no hang.

## #397 -- 2026-09-30 ~16:05 PDT

Three of the six queued Thor screens heat-stopped at xo 70C before landing
any result (`logs/thor-coldconfirm.log`, not the results tree, has the
record for a voided run): Dead or Alive 3 (v2, `0-0-s-...-2050455`, ~9 min
from a 34C start), THPS2x (`...-2050654`, ~10 min from a 50C start) and
Capcom Classics Collection Vol. 2 (`...-2055173`, ~15 min from a 48C
start). These three are the direct evidence behind lane.local's 15:40 PDT
addendum dropping the Thor screening cap to 300s.

**Dead or Alive 3 has now heat-stopped twice** (session 41's v1 timing
failure, session 42's v2 mid-attempt) -- two strikes, no third Thor try per
the screening program's own rule. It is Thor-only (no Nova copy), so the
rule's fallback ("needs the Nova") is not mine to act on; flagged here and
in `targets.toml`'s notes for lane.local/hostops.

**THPS2x and Capcom Classics 2** have one heat stop each, so each gets its
one retry, now at the new 300s cap: `1790808339-titleroutes-3127689`
(THPS2x) and `1790808344-titleroutes-3128993` (Capcom Classics 2).

Castlevania: Curse of Darkness, Shin Megami Tensei: NINE and Tork are still
parked in `dispatch/parked/thor-cold-0930/` waiting for a cold slot; the
coldconfirm runner is handling that on its own schedule.

## #433 -- 2026-09-30 ~16:05 PDT

Still no Nova nominations: Galleon (the one landed screen) is owner-blocked,
and the next three screens all voided on heat before producing a reading.
Dead or Alive 3 needs a Nova copy decision that is outside this lane's
authority (owner one-copy-per-title rule, amended 09-28 for titles work is
held up on) -- see #397.

[lane.titleroutes] waiting: six dispatch requests. Two Thor retries at the
new 300s cap: 1790808339-titleroutes-3127689 (THPS2x),
1790808344-titleroutes-3128993 (Capcom Classics 2). Three still parked for
a cold Thor slot: 1790805456-titleroutes-2055301 (Castlevania),
-2055567 (SMT NINE), 1790805457-titleroutes-2055759 (Tork). One Nova
benchmark still queued: 1790801593-titleroutes-1202186 (Burnout Revenge).
The waiter's resume once the last of these lands is the signal.

## #397 -- 2026-09-30 (session 44)

All six pending Thor screens plus the Burnout Revenge Nova benchmark landed and are read in full:

| title | device | reached gameplay? | fps median | share at 28.5+ | crash/hang | real cause if it stopped early |
|---|---|---|---|---|---|---|
| Tony Hawk's Pro Skater 2x (v1, 480s) | thor | yes | - | 0.961 | crash/no | Daijishou focus steal at 260s (not heat) |
| Tony Hawk's Pro Skater 2x (retry, 300s) | thor | yes | 59.82 | 0.976 | no/no | clean |
| Capcom Classics Collection Vol. 2 (v1, 480s) | thor | yes | - | 1.0 | crash/no | silent exit at 390s, xo-therm 70.1C at the end -- plausibly real heat |
| Capcom Classics Collection Vol. 2 (retry, 300s) | thor | yes | 59.94 | 1.0 | no/no | clean |
| Castlevania: Curse of Darkness | thor | yes | 59.94 | 1.0 | crash/no | Daijishou focus steal at 381s (not heat) |
| Shin Megami Tensei: NINE | thor | yes | 29.96 | 0.967 | no/no | clean |
| Tork: Prehistoric Punk | thor | yes | 29.96 | 0.585 | crash/no | Daijishou focus steal at 290s (not heat); fps also genuinely marginal |
| Dead or Alive 3 (v2) | thor | yes | 52.22 | 0.605 | crash/hang | Daijishou focus steal at 475s (not heat) |
| Burnout Revenge | nova | yes | 39.45 | 0.972 | no/no | clean (BENCHMARKED, well below its 60 own-target) |

**Defect found and filed** (`dispatch/board-requests/titleroutes.md`, not my file): the dispatcher's
Thor cold-slot auto-diagnoser (harness_health.py) labeled 5 of these runs `.hostops-diagnosed`
"HEAT STOP at xo 70 C". Four of the five actually logged an explicit
`not-foreground: com.magneticchen.daijishou` -- the Thor's launcher regained display-0 focus and
killed xemu, caught correctly by the route engine's own guard, with xo-therm nowhere near 70C at
the time. Only the fifth (Capcom2 v1) has thermal evidence consistent with a real heat stop. This
undermines the evidence behind lane.local's 09-30 15:40 PDT addendum that cited three of these as
heat stops to justify the 300s cap -- the cap may still be reasonable for cooling cadence, but the
Daijishou focus-steal is a separate, still-live problem that a shorter timeout does not reliably
prevent (it struck at 260s, 290s, 381s and 475s, no correlation with duration). Detail in
`docs/lanes/titleroutes/NOTES.md`, "Session 44".

`targets.toml` updated for all seven titles with these results; still parses and
`titlestate_selftest.py` passes.

**Kept the Thor queue fed**: queued the next four routeless Thor-only titles from the work list as
blind pass-1 surveys (300s each, `--hard-pin --device thor`): Psychonauts (`1790822573-titleroutes-2818801`),
Phantom Dust (`1790822578-titleroutes-2819133`), Ninja Gaiden Europe (`1790822580-titleroutes-2819211`),
Deathrow (`1790822581-titleroutes-2819301`).

[lane.titleroutes] waiting: nothing of my own. The four survey requests above are newly queued, not
something this session is blocking on; a future session reads their route-frames and authors routes
from them. PR pushed and marked ready.

## #433 -- 2026-09-30 (session 44)

Nova nominations, 90%+ at 28.5+ with no hang, from this session's six Thor screens:
- **Tony Hawk's Pro Skater 2x** -- 97.6%, clean run, no caveat.
- **Capcom Classics Collection Vol. 2** -- 100%, clean run, no caveat.
- **Shin Megami Tensei: NINE** -- 96.7%, clean run, no caveat.
- **Castlevania: Curse of Darkness** -- 100% while it ran (hang=False, technically clears the bar),
  but the run ended in a crash (the Daijishou focus-steal defect above, not the game) at 204s rather
  than completing the full screen -- nominated with that caveat; a clean confirmation run would be
  worth more than trusting this one outright.

Not nominated: Dead or Alive 3 (60.5% at the bar, real hang gaps too) and Tork (58.5% at the bar,
genuinely marginal even setting the Daijishou stop aside). Both now have two failed Thor runs each
(by the real cause, not the heat label); DOA3 is Thor-only so "needs the Nova" needs a copy decision
outside this lane (owner's amended one-copy-per-title rule) -- flagged in `targets.toml`, not queued
by me.
