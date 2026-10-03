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

## #397 -- 2026-09-30 (session 45)

Read session 44's four pending requests. Phantom Dust voided with no result at all (HEAT STOP at the
old 480s cap, nothing to review) -- requeued at 300s. Psychonauts landed but never passed its title
screen in 7 menu-loop cycles before a NEW focus-steal defect (Android's own `com.android.launcher3`,
not Daijishou this time) killed it at 136s of 300s -- well inside budget, so this is evidence of
another focus-steal hit, not evidence the title's menu needs different input. Requeued the identical
survey. Ninja Gaiden (Europe) and Deathrow are still working through the Thor cold-slot queue
(one running, one parked), nothing to read yet.

**The work-list table this lane built 2026-09-26 (48 titles) is effectively exhausted.** Refreshed it
by listing both Thor ISO roots directly (`adb shell ls`, no hold needed): 42 titles on the external
card, 347 on the internal-storage root added since lane.xbox started copying from the owner's PC
library -- 389 total, matching the scale lane.local's 12:40 PDT addendum already named ("321 titles,
only 23 routed"). Cross-referencing against `targets.toml`'s 70 entries found 327 internal-root
titles with no entry at all. Ranked them against `xemu-compat-2026-09-25.csv` (rating, then
xemu_rank) and checked `host-tools/blocked-titles.txt` (only Galleon). Queued the top five plus the
two requeues as this session's Thor batch (seven requests total, listed in
`docs/lanes/titleroutes/NOTES.md` session 45): Super Monkey Ball Deluxe, Family Guy: Video Game!,
Gauntlet: Dark Legacy, Sonic Heroes, Bistro Cupid, plus Phantom Dust and Psychonauts requeues.

`targets.toml` updated (Psychonauts added, Phantom Dust's notes extended); still parses and
`titlestate_selftest.py` passes.

[lane.titleroutes] waiting: `1790823793-titleroutes-2949342`, `1790823797-titleroutes-2950719`,
`1790823800-titleroutes-2951589`, `1790823803-titleroutes-2951964`, `1790823806-titleroutes-2952343`,
`1790823811-titleroutes-2952744`, `1790823861-titleroutes-2960863` (this session's seven), plus
`1790822580-titleroutes-2819211` and `1790822581-titleroutes-2819301` (Ninja Gaiden Europe, Deathrow,
still outstanding from session 44). PR pushed and marked ready.

## #433 -- 2026-09-30 22:30 PDT (session 46)

**Nominations withdrawn: all four Thor screens from 2026-09-30 (session 44).** Their scored windows
were menus, not play. The `mark gameplay` in each route was an unverified placeholder:

| title | screen | what the mark frame shows |
|---|---|---|
| Tony Hawk's Pro Skater 2x | `1790808339-titleroutes-3127689` (97.6%, 59.82) | THE HANGAR CHECKLIST goal list |
| Capcom Classics Collection Vol. 2 | `0-0-s-1790808344-titleroutes-3128993` (100%, 59.94) | START MENU |
| Shin Megami Tensei: NINE | `0-0-s-1790805456-titleroutes-2055567` (96.7%, 29.96) | name-entry keyboard, given name empty |
| Castlevania: Curse of Darkness | `0-0-s-1790805456-titleroutes-2055301` (100%, 59.94) | Name Entry keyboard, empty name |

Please queue no confirmations for these four. THPS2x and Castlevania have been re-marked and
re-screened on the Thor (`1790830528-titleroutes-329478`, `-329599`).

**187: Ride or Die.** The confirmation `1-1790775886-lane.verdict433-3086875` scored the profile-name
keyboard. The disk's profile list was empty, so the returning route's presses typed into Create's
keyboard. The route is now a single file that creates the profile every run and marks after 6 s
of driving in the race. Its replay is `1790830434-titleroutes-311228` (Nova, 300 s). 187 will be
re-nominated if that replay's frames show the race.

**Phantom Dust (4D530046): needs the Nova.** Two heat stops on the Thor (the second
`0-0-s-1790823811-titleroutes-2952744` at 197 s). Its last frame is the first explorable room at an
FPS overlay of 30. No fps verdict exists. It is on the Thor only.

**Other routes whose mark frame is not live play** (one frame each, from the newest run that
reached the mark; any Playable built on them needs a frame review of its window): bruce-lee (title
screen), pgr.returning and pgr2 (car at 0 mph on the grid), crash-wrath-of-cortex (LOAD / SAVE),
doax (shop list), burnout (Game Over), ghoulies (transition page), kof-mi.returning (PERFECT /
WINNER result; a round may follow), azurik (tutorial dialog; the loop may dismiss it), doa3 (black),
tork (cutscene-like, FPS 7). The table is in docs/lanes/titleroutes/NOTES.md, session 46.

## #397 -- 2026-09-30 22:30 PDT (session 46)

| title | device | route | replayed? | what the frames show |
|---|---|---|---|---|
| 187: Ride or Die | nova | 187-ride-or-die (single, new) | queued `1790830434-titleroutes-311228` | old mark sat on the profile keyboard |
| Family Guy: Video Game! | thor | family-guy (new) | queued `1790830432-titleroutes-310926` | survey: Stewie walking in the nursery, ~29-30 |
| Super Monkey Ball Deluxe | thor | super-monkey-ball-deluxe (new) | queued `1790830432-titleroutes-310985` | survey: stage 1-1 at 59 |
| Sonic Heroes | thor | sonic-heroes (new) | queued `1790830432-titleroutes-311058` | survey: Seaside Hill at 59 |
| Tony Hawk's Pro Skater 2x | thor | thps2x (re-marked) | queued `1790830528-titleroutes-329478` | old mark sat on the goal checklist |
| Castlevania: Curse of Darkness | thor | castlevania-cod.first-run (re-marked) | queued `1790830528-titleroutes-329599` | old mark sat on Name Entry |
| Gauntlet: Dark Legacy | thor | none | survey `0-0-s-1790823800-titleroutes-2951589` | in-engine intro at 14 fps; pause menu at 11-14 |
| Ninja Gaiden (Europe) | thor | none | survey `0-0-s-1790822580-titleroutes-2819211` | text pages at 59; first area reached at ~270 s, dimmed |
| Bistro Cupid | thor | none | survey `0-0-s-1790823806-titleroutes-2952343` | story dialogue only |
| Psychonauts | thor | none | survey `0-0-s-1790823861-titleroutes-2960863` | title card at an FPS overlay of 1 |
| Deathrow | thor | none | survey `0-0-s-1790822581-titleroutes-2819301` | heat stop at 208 s |
| THPS3, SSX Tricky | thor | survey | queued `-311114`, `-311173` | |

Correction to the 2026-09-30 session-44 post: the Thor stops it called "Daijishou focus steals, not
heat" were heat stops. The cold-slot runner logged `HEAT STOP at xo 70 C` for each (DOA3 15:06:43,
THPS2x 15:17:44, Castlevania 16:16:24, Tork 16:45:13 PDT). The launcher line follows the force-stop
and does not cause it.

[lane.titleroutes] waiting: `1790830432-titleroutes-310926`, `1790830432-titleroutes-310985`,
`1790830432-titleroutes-311058`, `1790830433-titleroutes-311114`, `1790830433-titleroutes-311173`,
`1790830528-titleroutes-329478`, `1790830528-titleroutes-329599` (Thor) and
`1790830434-titleroutes-311228` (Nova). PR.md is ready.

## #397 -- 2026-10-01 00:23 PDT (session 47)

The eight requests from session 46 read (logs/thor-coldconfirm.log gave the ground truth; none
of the ids were findable by a flat directory listing -- see NOTES.md session 47 for why):

| title | device | outcome | mark frame shows | verdict |
|---|---|---|---|---|
| Family Guy: Video Game! | thor | DONE, no heat stop | a save-overwrite dialog (one frame early); real play confirmed 9s later | fps_ok_share 0.9763/189.4s -- **nominated for Nova (#433)** |
| Super Monkey Ball Deluxe | thor | HEAT STOP, voided | ball rolling in-level, 59fps -- route CONFIRMED | only 48.5s scored; re-screen queued |
| Sonic Heroes | thor | HEAT STOP, voided | Team Sonic running Seaside Hill, 59fps -- route CONFIRMED | only 61.4s scored; re-screen queued |
| THPS3 (generic survey) | thor | HEAT STOP, voided | no mark yet, but frames show live Foundry gameplay at 59fps by cycle 3 | routes/thps3.route authored from this evidence; first replay queued |
| SSX Tricky (generic survey) | thor | done, no heat stop | all three "play" shots are a solid black frame | hang=True; needs its own survey, not a route yet |
| Tony Hawk's Pro Skater 2x | thor | HEAT STOP, voided | the Hangar under a tutorial tip, 59fps -- re-mark CONFIRMED | only 105.1s scored; re-screen queued |
| Castlevania: Curse of Darkness | thor | HEAT STOP, voided | "Create new save data? Yes/No" -- still a menu | re-mark did NOT work; abandoning the guess route, generic survey queued |
| 187: Ride or Die (replay) | nova | VOID | n/a -- hakuX never held display 0 focus, no input sent | not a route finding; retry queued |

**Nova nomination (#433): Family Guy: Video Game! (545400B0).** Clean full-session read, 97.6%
share, real gameplay confirmed in the frames past the one-frame-early mark.

**Withdrawn from last session's implicit candidates:** Super Monkey Ball Deluxe, Sonic Heroes and
THPS2x are confirmed-good routes but their only scored windows are heat-truncated (48-105s); not
nominating until a clean re-screen lands. Castlevania's route is not confirmed at all; dropped
until a fresh survey replaces it.

Queued next (ref `2a87446629`, `--device thor --hard-pin --seconds 300` except the Nova line):
`1790839386-titleroutes-2237355` (super-monkey-ball-deluxe re-screen), `1790839390-titleroutes-2237657`
(sonic-heroes re-screen), `1790839392-titleroutes-2237866` (thps2x re-screen), `1790839395-titleroutes-2238007`
(thps3 first replay), `1790839398-titleroutes-2238193` (castlevania generic survey), and
`1790839401-titleroutes-2238360` (187-ride-or-die retry, Nova).

[lane.titleroutes] waiting: `1790839386-titleroutes-2237355`, `1790839390-titleroutes-2237657`,
`1790839392-titleroutes-2237866`, `1790839395-titleroutes-2238007`, `1790839398-titleroutes-2238193`
(Thor) and `1790839401-titleroutes-2238360` (Nova). PR.md is ready.

## #433 -- 2026-10-01 07:50 PDT (session 48)

GitHub is still suspended (36+ hours now); this and the #397 post below are relayed through OUTBOX.md
per the offline protocol, same as every post since 2026-09-29.

**Nominations (all frames checked by eye, not fps share alone -- see NOTES.md session 48):**

| title | device | evidence |
|---|---|---|
| 187: Ride or Die | nova | Full 300s route replay, no stop. Mark frame (002517-gameplay.png): a night street race, countdown "2", rival cars alongside, 46fps overlay. Re-nominated: the prior scored window (1-1790775886-lane.verdict433-3086875) measured the profile-name keyboard, not this. |
| Super Monkey Ball Deluxe | thor-only, needs the Nova | Route CONFIRMED on two separate runs (ball rolling in-level, 1-1 SIMPLE). Both heat-stopped (48.5s, then 51s scored). Two heat stops on a confirmed route, per the screening program's own rule. |
| Tony Hawk's Pro Skater 2x | thor-only, needs the Nova | Route CONFIRMED on two separate runs since the mark fix (the Hangar under a tutorial tip, not the goal checklist the original nomination measured). Both heat-stopped (105.1s, then 102s scored). Two heat stops on a confirmed route. |
| Tony Hawk's Pro Skater 3 | thor-only, needs the Nova | **Caveat: please check the Nova confirmation's own mark frame.** The route's own replay only ever caught THE FOUNDRY's level-splash card before a heat stop (010437-gameplay.png); live post-splash control has only been seen in the generic survey's frame from the same level, one step later. Two heat stops for the title (once as survey, once as its own route). |

**Not nominated -- Sonic Heroes needs a route fix, not a re-screen.** The exact same route
(`routes/sonic-heroes.route`, 9 START/A cycles) gave two different answers on two runs: session 47's
run showed real play (Seaside Hill, timer 00:34:73); this session's run spent its entire scored
window frozen on the pause menu (timer stuck at 00:15:68 across the mark frame and every frame after
it). The route presses START on a fixed schedule that sometimes lands after the level has already
started, pausing it, and the route's one recovery attempt (`press A` after the mark) did not resume
it this time. A route that reached gameplay once is not proven reliable by that one run; please do
not nominate this title from any run of this specific route until it is reworked. Full detail:
NOTES.md session 48.

**New this session: Castlevania: Curse of Darkness reaches real gameplay.** Every guess route for
this title has failed since session 44 (stuck on Name Entry, then a save-data prompt). A generic
`--route survey` soak this session used 14 START/A cycles -- more than any guess tried -- and reached
a gothic courtyard with the character under player control, facing a gargoyle, then walking toward a
gate (011651-play.png, 011717-play.png). `routes/castlevania-cod.route` is authored from this
evidence and queued for its first replay. Not a nomination yet -- the authored route itself hasn't
been confirmed as its own run.

## #397 -- 2026-10-01 07:50 PDT (session 48)

| title | device | route | replayed? | what the frames show |
|---|---|---|---|---|
| 187: Ride or Die | nova | 187-ride-or-die | yes, full 300s, `1790839401-titleroutes-2238360` | night street race, confirmed -- re-nominated #433 |
| Super Monkey Ball Deluxe | thor | super-monkey-ball-deluxe | yes (2nd time), heat-stopped at 51s, `1790839386-titleroutes-2237355` | ball rolling in-level, confirmed -- nominated #433 |
| Sonic Heroes | thor | sonic-heroes | yes (2nd time), heat-stopped, `1790839390-titleroutes-2237657` | frozen on the pause menu the whole window -- NOT confirmed this run, route needs a fix |
| Tony Hawk's Pro Skater 2x | thor | thps2x | yes (2nd time), heat-stopped at 102s, `1790839392-titleroutes-2237866` | Hangar under tutorial tip, confirmed -- nominated #433 |
| Tony Hawk's Pro Skater 3 | thor | thps3 (1st replay as its own route) | yes, heat-stopped at 97s, `1790839395-titleroutes-2238007` | THE FOUNDRY splash card (one frame short of confirmed control); nominated #433 with a caveat |
| Castlevania: Curse of Darkness | thor | survey (generic) | yes, 284/300s, `1790839398-titleroutes-2238193` | gothic courtyard under player control -- authored castlevania-cod.route from this, queued for its own replay |

**All five Thor requests this batch heat-stopped** (worse than session 47's 3 of 5): the fan-dead
Thor is not getting more reliable. See NOTES.md session 48 for the full per-title table.

Queued next (ref `d7791f6c0a`, Thor only, `--device thor --hard-pin --seconds 300`):
`1790846753-titleroutes-3234529`, castlevania-cod.route's first replay. No Nova work queued by this
lane -- the four nominations above go to lane.local/lane.verdict433 to copy and confirm.

[lane.titleroutes] waiting: `1790846753-titleroutes-3234529` (Thor). If GitHub is still down when
this resumes, read the result directly from `dispatch/results` / `logs/thor-coldconfirm.log` rather
than waiting on a PR-parking waiter that cannot arm itself.

## #397 -- 2026-10-01 (session 49)

GitHub is still suspended (now ~40 h); relayed through OUTBOX.md per the offline protocol.

**The castlevania-cod.route replay session 48 queued heat-stopped at 78s of 300s -- inconclusive, not
a route failure.** `.hostops-diagnosed` on `0-0-s-1790846753-titleroutes-3234529` confirms the CPU
thermal-gate (cpu-1-9 at 91C) stopped it 2 cycles into its 14, nowhere near its own mark. One heat
stop for the named route (the generic survey it's built from heat-stopped separately already, not
voided). Re-queued rather than escalating on one inconclusive run.

**Gauntlet: Dark Legacy authored from its own survey's frames, found the same START-during-gameplay
trap Sonic Heroes has, before any route was committed.** Walking `0-0-s-1790823800-titleroutes-
2951589`'s route-frames cycle by cycle (not just the headline frame) found that by the 8th START/A
cycle the wizard was already under player control in the dungeon (an in-engine tutorial scroll over
live 3D, FPS 14), but the survey's blind 14-cycle default kept pressing START for 6 more cycles into
that live play, and its `mark play` frame is the in-game pause menu's Audio page, not gameplay.
Authored `routes/gauntlet.route`: 8 cycles, then mark, then a movement loop that never presses START
again. Queued its first replay.

**capcom-classics2: queued a generic survey instead of guessing a second fix.** The withdrawn
nomination's mark frame is a "START MENU" structure the current guess route's arcade-coin sequence
never anticipated. A second blind guess has low odds of landing right; queued `--route survey`
instead, the method that worked for castlevania-cod and surfaced Gauntlet's trap above.

**Two new titles from the ranked untouched list, surveyed generically:** Plus Plumb 2 (544B0004,
rank 101) and Petit Copter (41510001, rank 135), both Perfect-rated, neither previously touched.

**Sonic Heroes: queued a tiebreaker, not a blind edit.** 1 good (session 47) / 1 bad (session 48) of
the same route and cycle count is a coin flip, not a verdict. Unlike Gauntlet, there's no per-cycle
frame record for this title to ground a cycle-count fix in, so guessing a new count risks a wasted
cold slot. Queued a 3rd screen of the existing route: 2-of-3 good reopens the nomination path, 1-of-3
confirms it needs a real redesign.

| title | device | route | request | purpose |
|---|---|---|---|---|
| Castlevania: Curse of Darkness | thor | castlevania-cod (2nd replay) | `1790850015-titleroutes-3951103` | confirm the route past the 78s heat stop |
| Gauntlet: Dark Legacy | thor | gauntlet (1st replay, new route) | `1-1790850024-titleroutes-3953302` | confirm the 8-cycle fix |
| Capcom Classics Collection Vol. 2 | thor | survey (generic) | `1-1790850027-titleroutes-3953658` | real frames to author a route from |
| Plus Plumb 2 | thor | survey (generic) | `1-1790850029-titleroutes-3954081` | new title, no frames yet |
| Petit Copter | thor | survey (generic) | `1-1790850032-titleroutes-3954284` | new title, no frames yet |
| Sonic Heroes | thor | sonic-heroes (3rd screen) | `1-1790850035-titleroutes-3954488` | tiebreaker: 1 good / 1 bad so far |

[lane.titleroutes] waiting: `1790850015-titleroutes-3951103`, `1-1790850024-titleroutes-3953302`,
`1-1790850027-titleroutes-3953658`, `1-1790850029-titleroutes-3954081`, `1-1790850032-titleroutes-
3954284`, `1-1790850035-titleroutes-3954488` (all Thor). GitHub is still down (~40 h); a successor
should poll `dispatch/results`/`logs/thor-coldconfirm.log` directly rather than rely on the PR-parking
waiter arming itself, same as the last three sessions.

## #397 -- 2026-10-01 04:40 PDT (session 50)

GitHub is still suspended, so this goes through OUTBOX.md under the offline protocol.

**The Thor screening program is blocked. `thor_coldconfirm.sh`'s cpu-1-9 >= 90 C stop voids every
title run, from any start temperature and under either regimen.** All six of session 49's runs
voided 64-169 s in. This session's pilot did the same: Gauntlet at `--env PERF_REGIMEN=default`,
`1790853287-titleroutes-569824`, started at cpu-1-9 39.5 C and was stopped at ~74 s, 91 C.

| run | regimen | cpu-1-9 at start | +38 s | +69 s | stopped |
|---|---|---|---|---|---|
| Castlevania `3234529` | max | 41.8 C (after 1 h idle) | 76.3 | 84.5 | ~80 s |
| Castlevania `3951103` | max | 41.4 C | 77.4 | 86.8 | ~80 s |
| Gauntlet `569824` | default (perf_mode 0) | 39.5 C | 81.0 | 86.0 | ~74 s |
| Sonic Heroes `3954488` | max | 51.6 C | 51.6 | 51.2 | 4 s after its route began (one-sample trip) |
| Castlevania survey `2238193` (before the stop existed) | max | 52.0 C | 95.0 | 94.6 | not stopped: held 94-95 C for 4 min and played 284 s to gameplay |

The 04:11 fix, a cpu-1-9 <= 55 C start gate in `coldslot.sh`, would have admitted all three cold
runs above, and all three voided. A title on the fan-dead Thor heats the die about 1 C/s and holds
it at 94-95 C. Every route marks later than the ~75 s the die takes to reach 90 C, so no screen can
reach its mark under the current stop. **I have not re-queued the six.** Six more voids would cost
six cold slots and return nothing. A host-tools decision is needed, and it is not this lane's to
make. The options:
1. raise the stop toward what a title actually reads (Castlevania held 94-95 C for 4 min without a
   crash; Psychonauts crashed at 95 C, so the margin is a judgment call);
2. trip only on several consecutive reads (this fixes Sonic Heroes' one-sample trip, not the rest);
3. stop Thor screens until the fan is replaced, and screen on the Nova instead.

**Hostops needs to resume this lane by hand** once one of these lands. Nothing of mine is queued,
and GitHub is down, so no waiter will fire. The re-queue order and the exact command are in NOTES.md,
session 50, "State for a successor".

[lane.titleroutes] blocked: thor_coldconfirm.sh CPU_STOP_C=90 (a single sample) voids every Thor title
screen. Unblocked by a decision on the stop (raise it, add a consecutive-sample rule, or route
screens to the Nova).

## #397 -- 2026-10-01 (session 51)

Fresh worktree resume, merged `origin/master` (fast-forward onto `c071ae6e60`,
session 50's fold). GitHub is still suspended (`gh api user` still 403
"account was suspended"), so this stays on the offline protocol.

**Still blocked, same decision as session 50.** `escalations.md` (10-01 05:13
PDT) and `dispatch/hold/thor.why` (UPDATE 10-01 05:09 PDT) show the owner's
call -- raise `CPU_STOP_C`, require consecutive reads, or grant a one-time
Nova exception for the six pending titles -- is still open. hostops tried to
reach lane.local directly and found no session to take it (hostops-inbox.md
line 1883); no entry after that exists in either file. Nothing new to
re-queue on the Thor.

**The six voided titles' evidence is gone.** Session 50 asked a successor to
walk `castlevania-cod`'s survey frames cycle-by-cycle offline before trusting
its route, the way Gauntlet's own trap was found. Checked: no trace of that
survey's result dir, Gauntlet's survey, or any of the six session-49/50
request ids anywhere under `dispatch/results/` or `~/hakux-work/nav/`.
`dispatch/results/` is evidently pruned sooner than this lane assumed, and
none of those results were copied into `scratch/judge/` before they went.
That offline analysis can no longer be done; the titles will need a fresh
screen once device time is available. Recorded as a process lesson in NOTES
(copy a result's frames into `scratch/` the same session you read them, not
a session later).

**Did this session: fixed `scratch/targeted_ids.txt`.** It was missing 5 of
the 50 routed title_ids (THPS3, Gauntlet, Sonic Heroes, Super Monkey Ball
Deluxe, Family Guy) and 3 mid-investigation ones (Plus Plumb 2, Petit
Copter, Bistro Cupid), so `scratch/rank_untouched.py` was re-surfacing
already-routed titles as "untouched" -- the bug session 49 flagged and
didn't have time to fix. It now correctly lists 319 genuinely untouched
titles, headed by Doom 3, Bicycle Casino, Monster Garage, Doom 3:
Resurrection of Evil, Greg Hastings' Tournament Paintball Max'd, AMF Bowling
2004, High Rollers Casino, Breeders' Cup, AMF Xtreme Bowling. All need a
device (Thor, under the same blocker, or an approved Nova exception) to act
on.

**No device work.** The Thor stays off-limits per the open decision. The
Nova has no hold file right now, but neither the 09-26 21:10 PDT device-role
split (Nova = #462 only) nor the one-copy-per-title exception for the
pending Thor titles has been lifted, and its queue still carries 30+ pinned
#462/#474/#414/#569/#507 requests per escalations.md. Took no Nova session.
13 Nova-only titles that need no copy and still lack a route (Batman --
blocked on combat specifically, Black Stone, Star Wars Ep. III, Bloody Roar:
Extreme, Gunvalkyrie, Dino Crisis 3, Buffy, Halo: Combat Evolved, Conker,
Halo 2, Ninja Gaiden Black, ToeJam & Earl III, Tron 2.0) are listed in NOTES
for whoever next gets Nova time cleared for title-pipeline work; a Nova
session for them was not taken this session either, since the Nova's queue
priority is not this lane's call.

`python3 docs/testing/titles/titlestate_selftest.py` (all checks passed) and
`targets.toml` parses (tomllib, 80 titles, unchanged) re-checked as a sanity
pass; no routes or targets.toml changes this session.

[lane.titleroutes] blocked: same as session 50 -- `thor_coldconfirm.sh`'s
`CPU_STOP_C=90` voids every Thor title-gameplay screen, and the decision to
raise it / require consecutive reads / grant a one-time Nova exception is
still with the owner (escalations.md 10-01 05:13 PDT, thor.why UPDATE 10-01
05:09 PDT). Nothing of mine is queued or running on either device.

## #397 -- 2026-10-01 (session 53, the owner-approved one-time Nova path-finding session)

Routed Castlevania: Curse of Darkness (4B4E002D) on the Nova, per the
`hostops-inbox.md` 14:16 PDT countermand of the usage-budget hold for this
one title. Both variants now reach a frame-confirmed `mark gameplay`:

| variant | trap found | mark frame |
|---|---|---|
| first-run | Name Entry needs `press START` to jump to Accept (`A` alone just types a letter); the save-creation prompt defaults to **No** (`axis LX min` onto Yes before `A`) | `scratch/nav/.../015-mark-gameplay.png`: player HUD 100/100 HP, gothic courtyard, gargoyle fountain |
| returning | one `A` on Continue only replays the recap cutscene and returns to the title; a **second** `A` reaches LOAD HARD DISK -> slot 1 -> confirm -> the cutscene plays a third time -> the same courtyard | `scratch/nav/.../018-mark-gameplay.png`, same HUD/courtyard |

Both are authored as `.route` files and both reached gameplay visibly (an
attack animation after the standard play pattern, in the frame right after
each mark). Neither is yet confirmed by an **unattended** `route.sh` replay
end to end -- a 150s foreground peek of the returning route (cut short by a
tight `timeout`, not a hang) matched the first ~115s of 268s to the mark,
but did not run the whole thing. Both stay DRAFT until that full replay
exists; see NOTES.md session 53 for the detail and the frame paths.

This exhausted the session's one-time device-time allowance (two nav.py
sessions plus the peek). Found and cleaned up a stray Nova hold the
original session had left taken (`dispatch/hold/nova`, placed by this lane
at 14:18 PDT, never released): released it, restored the Nova to its
documented rest state (performance/fan mode 0/4, screen asleep). No new
device time taken beyond that cleanup.

**Not resumed further today.** The 92%+ weekly usage-budget hold (reset
21:00 PDT) and the Thor CPU-stop decision are both still standing for
everything outside this one approved title; nothing of this lane's is
queued or running on either device now.

## #397 -- 2026-10-01 (session 56, closing out Castlevania: Curse of Darkness's returning route)

`castlevania-cod.returning.route` is now CONFIRMED by a full unattended
`route.sh` replay (`scratch/replay/castlevania-cod.returning-145541`,
copied to `scratch/judge/`): all 19 scripted frames captured, `mark
gameplay` reached at 15:00:34.692, then ~28s of the repeat-forever play
pattern (visible attack animations) before the run's own timeout ended it
cleanly. `movetest2.png`/`mark gameplay.png` both show the HUD (`Player HP
100/100`) with the character's stance shifted between them, confirming
live control. No longer DRAFT; added to `host-tools/nova-nominations.tsv`
for `autoverdict.sh`'s own 600s confirmation (not queued by this lane).

**Correcting an earlier claim:** an intervening addendum (14:55 PDT) read
the *previous* replay attempt (`castlevania-cod.returning-144635`) as
having already succeeded, citing its last frame. It hadn't: that run's own
`route.log` stops 10 scripted steps short of `mark gameplay` (no
`movetest`/`movetest2`/`check1`/`loading6`, no mark), cut off mid-wait with
only 4 of the route's 19 frames captured. The cited frame (`loading3.png`)
is a mid-route shot taken before the HUD appears, not a confirmation. See
NOTES.md session 56 for the full comparison. No harm done -- this session
re-ran it properly before acting on the claim -- but flagging it since nothing
else would have caught a route getting nominated for a benchmark off a run
that never actually played it.

`castlevania-cod.first-run.route` is still DRAFT: no unattended replay has
ever been attempted for it (today's two runs were both the returning
route), and the Nova's disk no longer has a clean, no-save state to replay
it from (session 53 wrote a save to slot 1). Left as the next step on this
title; see NOTES.md "State for a successor".

No other device work taken this session. The usage-budget hold (reset
21:00 PDT 10-01) and the Thor CPU-stop decision are both still standing
outside this one owner-approved exception.

## #397 -- 2026-10-01 (session 57, Super Monkey Ball Deluxe confirmed on the Nova)

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Super Monkey Ball Deluxe (53450038) | Nova | super-monkey-ball-deluxe | yes, unattended, full | `scratch/judge/super-monkey-ball-deluxe-165430`: all 26 scripted frames through 10 START/A cycles, `mark gameplay` at 191.5s (route.sh start) / 198.4s (launch), stage 1-1 SIMPLE, 46 mph, timer counting down; a `play` frame 11s later shows a different score/timer and a goal-clear celebration -- live, evolving play, not a frozen menu |

This title was already route-CONFIRMED on the Thor (sessions 47/48) but
both Thor runs heat-stopped at 48-51s of scored play. Per ADDENDUM 6, the
owner copied it (and Sonic Heroes) to the Nova; this session replayed it
there with no thermal limit, end to end. Nominated for `autoverdict.sh`'s
600s Nova fps confirmation via `host-tools/nova-nominations.tsv` (not
queued by this lane).

Found and fixed a bug in `scratch/premark.py` (my own scratch tool, not
part of the repo) along the way: it summed every route `wait` line once
regardless of an enclosing `repeat N { }`, so routes whose pre-mark waits
sit inside a repeat loop got a pre-mark estimate far too low -- this
title's route read 73s instead of the real 163s, and the first replay
attempt timed out 5 cycles short of the mark before the fix. Routes with
no repeat before their mark (both Castlevania variants) were unaffected,
which is why it went unnoticed through two prior sessions.

Sonic Heroes is next (ADDENDUM 6: "the next session does Sonic Heroes");
its `iso.nova` key is already added to `targets.toml`. Its own prior
history (session 48, Thor) shows the same fixed-cycle route can land on a
frozen PAUSE menu instead of live play, so it needs a careful frame check,
not a blind replay -- see NOTES.md session 57 "State for a successor".

`python3 docs/testing/titles/titlestate_selftest.py` (all checks passed)
and `targets.toml` parses (tomllib) re-checked this session.

## #397 -- 2026-10-01 17:30 PDT (session 58)

Sonic Heroes (5345002B) is CONFIRMED on the Nova and nominated for its fps
confirmation. Its route was a known coin flip (session 47 Thor screen: live
play; session 48 Thor re-screen, same route: a frozen PAUSE menu) caused by
a fixed 9-cycle START/A guess racing the title's own variable boot timing.
Fixed by driving it live with nav.py on both disk states (fresh Nova copy
with no Game Data, and the same disk after creating game data): both need
exactly one START and three A presses to reach Main Menu (different
intermediate screens, same count, default option highlighted each time), so
one route covers both. The fix for the pause trap is simply never pressing
START again once a level might already be live -- the rewritten route waits
out the ~85-90s post-team-select cutscene with no input at all.

| title | device | route | replayed? | what gameplay looked like |
|---|---|---|---|---|
| Sonic Heroes (5345002B) | nova | `sonic-heroes.route` (rewritten) | yes (17:16-17:22 PDT, one unattended `route.sh` run, no failures) | Seaside Hill, Team Sonic; score 60->80, rings 006->008, timer continuously advancing, Sonic's pose/position changing frame to frame (running, then airborne) |

Evidence: `scratch/judge/sonic-heroes-171639/` (mark frame `172133-gameplay.png`,
later frames `172141/172150/172201-play.png`).

No specific next title was named by an addendum this session. Absent one,
the next session should check for a new addendum first, then continue down
the still-open backlog from sessions 56/57: 13 Nova-only no-route titles,
and the Thor's untouched titles (all blocked on the fan/CPU-stop decision).

## #397 -- 2026-10-01 18:15 PDT (session 59)

Diagnosed and fixed a real bug in `castlevania-cod.first-run.route`: its
name-typing step raced the Name Entry screen's own load, so the route spent
900s stuck on an unaccepted empty name instead of creating a save and
reaching gameplay. Dispatch route-check `1790902028-titleroutes-1005086`
(Nova) is the evidence -- every frame after `name-a` is the same Name Entry
screen; the registry's save for 4B4E002D (`53f0a40fe626`) is unchanged.
Fixed by making the letter-type step self-healing (press A twice on the "A"
tile, a few seconds apart) plus a larger initial margin. Verification queued:
`1790903439-titleroutes-1317193` (Nova, route check, not yet landed).

Also flagging: the Sonic Heroes Playable confirmation
(`1790902215-autoverdict-1078702`, running) is building from `ref=575c480d27`,
which predates session 57/58's folds -- it's running the OLD 9-cycle route,
not session 58's rewrite. Its mid-run frames already show the known
frozen-PAUSE failure (`180609-gameplay.png` / `181308-play.png`, 7 minutes
apart, byte-identical). This is expected to FAIL, but the fix is already on
this branch (not a new bug) -- it needs a re-nomination once sessions
57-59 fold to master, not another route rewrite.

| title | device | route | status | note |
|---|---|---|---|---|
| Castlevania: Curse of Darkness (4B4E002D) | Nova | castlevania-cod.first-run | fix queued for verification | see above |
| Sonic Heroes (5345002B) | Nova | sonic-heroes | confirmation running on stale ref | expect FAIL, re-nominate after fold, don't re-fix |

Next session: read both request results first (see NOTES.md "State for a
successor"), then continue per ADDENDUM 8/9.

## #397 -- 2026-10-01 19:05 PDT (session 60)

Session 59's "self-heal" fix for `castlevania-cod.first-run.route` (a second
blind press on the Name Entry letter tile) was wrong, as the owner found
directly (ADDENDUM 11, ~18:30 PDT) by watching its own verification run
(`1790903439-titleroutes-1317193`) sit stuck on Name Entry and stopping it:
both presses landed on a still-black, not-yet-loaded screen -- confirmed by
reading `181831-name-a.png`/`181838-name-a2.png` (both black) -- not a
dropped press. The owner asked for the real fix: a route that looks at the
screen before pressing into it, not another guess.

Built it. `route.sh` gained two new step types, `waitfor` and
`press-until`, that poll a screencap region against a committed reference
crop (mean abs diff, grayscale, downscaled) instead of playing a fixed
`wait`, and ABORT the route with a clear `ROUTE FAIL` line rather than
typing blind into whatever screen is actually up. A new selftest
(`docs/testing/titles/waitfor_selftest.py`) proves the comparator against
this exact failure -- including the real still-black frame from the
withdrawn run -- before any device time was spent: 5/5 cases pass. All 58
existing `.route` files still parse unchanged. `castlevania-cod.first-run.route`'s
newgame -> Name-Entry section now waits for the Name Entry screen itself to
be up (timeout 30s, generous), then presses the letter and checks the field
itself, retrying up to 5 times -- not a fixed wait and a blind press count.

Verification queued (not replayed live, per ADDENDUM 11's own sequencing
and ADDENDUM 8's disk-state reasoning): `1790905334-titleroutes-1780552`
(Nova, hard-pinned, `--route castlevania-cod.first-run --seconds 900`, ref
`1f23c068f0`, tagged as a route check, not a Playable confirmation).

| title | device | route | status | note |
|---|---|---|---|---|
| Castlevania: Curse of Darkness (4B4E002D) | Nova | castlevania-cod.first-run | fix queued for verification (1790905334-titleroutes-1780552) | see above; route.sh now has waitfor/press-until |

Next session: read that result first (frame-by-frame, not the exit code or
mark alone -- see NOTES.md "State for a successor"). If it reaches real
play and creates a save, do the base-name run next (ADDENDUM 8 step b)
before nominating. Still open and unreached: Super Monkey Ball Deluxe's
post-mark stage-select-menu problem (ADDENDUM 9 item 2) and Sonic Heroes'
play-loop fix (ADDENDUM 10).

## #397 -- 2026-10-01 (session 61)

Session 60's Castlevania verification (`1790905334-titleroutes-1780552`) came back `WITHDRAWN`: the dispatcher's own `route.sh` snapshot still predated the `waitfor` grammar (ADDENDUM 12). At the start of this session that was still true (checkout 11 commits behind, 0 `waitfor` occurrences in the snapshot, per ADDENDUM 13), so per ADDENDUM 13 I did the two items that don't depend on it:

**Sonic Heroes (ADDENDUM 10).** Rewrote the post-mark loop to hold `axis LY min` continuously, no LX swings, `A` only occasionally -- exactly the owner's instruction. Replayed it on the Nova: it reaches `mark gameplay` and the first ~10s genuinely advance (score 60->80), but then Team Sonic gets wedged against a stone riser and stays there (score/rings frozen) for the rest of the window I tested. I drove the still-live app by hand afterward (5 more input combinations: attack, a held jump, a running jump, backing off and turning) and could not find one that reliably clears it -- one combination freed them into an open junction but a different approach just led to the same obstacle from another angle. **Not nominating.** The loop fix is committed (it's a real improvement -- no more wandering -- and the right starting point for whoever tackles the obstacle next), but whole-window advance is unconfirmed; `targets.toml`'s note has the exact clock offset (~01:02 after mark) and what a stuck frame looks like.

**Super Monkey Ball Deluxe (ADDENDUM 9) -- this turned out not to be a route bug.** Drove a fresh game live on the Nova: it reaches stage 1-1 directly (no Stage Select before the first stage), and a plain held-forward input cleared it in ~15s (GOAL!!) -- so "hold forward" genuinely works when the track allows it. The stage-clear screen then lands on Stage Select with the cursor ALREADY correctly on the next stage. From there I tried 9 different inputs against the live screen -- A (tap, held, repeated), B, the D-pad, the analog stick held hard in one direction for 2+ seconds, explicitly zeroed axes -- and NONE of them moved the cursor or changed the screen. Only START worked (opened the pause popup), which rules out a focus loss (confirmed directly via `dumpsys input` too) and proves input generally reaches the app. This matches the original rejected confirmation's frames exactly (same stage highlighted the whole 10 minutes, only the idle camera rotating) -- I'd misread that as a cursor-drifted-to-a-locked-stage problem, but the swings never moved the cursor at all on either run. **No route redesign can fix a screen that isn't reading stage-selection input.** This looks like an emulator/input-layer issue, not something `routes/**` can address -- raising it here for a decision on whether it's worth a tracked issue. Super Monkey Ball Deluxe stays nominated at stage-1-1-only (unaffected); going further is blocked on this, not on the route.

**Checkout caught up mid-session**: by the time I finished the above, `/home/justin/hakuX` had been fast-forwarded (waitfor now present in the dispatcher's `route.sh` snapshot) and the branch fold (`0f07dbfede`) confirmed on `origin/master`. So I queued session 60's still-pending Castlevania verification: `1790918365-titleroutes-76920` (Nova, hard-pinned, `--route castlevania-cod.first-run --seconds 900`, ref `c7aae3bf5c`, tagged as a route check, not a Playable confirmation).

| title | device | route | status | note |
|---|---|---|---|---|
| Sonic Heroes (5345002B) | Nova | sonic-heroes | loop fixed, replayed, NOT nominated | advances ~10s then wedges against level geometry; owner's exact fix applied but whole-window advance unconfirmed |
| Super Monkey Ball Deluxe (53450038) | Nova | super-monkey-ball-deluxe | input finding, not a route fix | Stage Select screen reads no stage-selection input on this build (9 tests); flagging for a tracked-issue decision |
| Castlevania: Curse of Darkness (4B4E002D) | Nova | castlevania-cod.first-run | verification queued (1790918365-titleroutes-76920) | waitfor/press-until fix from session 60, now that the dispatcher snapshot has the grammar |

[lane.titleroutes] waiting: `1790918365-titleroutes-76920` (Castlevania first-run route check). Once it lands: read it frame-by-frame per the usual discipline, and if it reaches real play and creates a save, do the base-name run (ADDENDUM 8 step b) before nominating `castlevania-cod`. Also still open, unreached this session: any further Sonic Heroes obstacle work and a decision on the Super Monkey Ball Stage Select input finding above.

## #397 -- 2026-10-01 (session 62)

Resolving the wait above: `1790918365-titleroutes-76920` came back `WITHDRAWN`, cancelled by the owner directly (confirmed by reading `WITHDRAWN.txt` and `run.log` myself) -- it died at `route.txt:73` because the dispatched run's `refs/` directory had no copy of the `name-entry-header` reference crop the `waitfor` step needed, so the app sat looping the intro video for the window (`frames.count=0`, held 661s of 900s, not scored). The owner has handed Castlevania's input-sequencing to `lane/routedriver` (a screen-aware state machine); this lane is not to queue or drive that title again, and has not touched `castlevania-cod.first-run.route`.

**Harness gap, for whoever owns `request.sh`/the dispatcher (not this lane's files):** a `waitfor` step's reference crop is committed next to its route in this repo, but nothing currently stages a copy of it into the per-run `refs/` directory that the dispatcher's own `route.sh` snapshot reads at run time. `route.sh --check` against the snapshot (session 60/61's own gate) proves the route *parses*, but not that its crops *resolve* once dispatched -- that's exactly how this run got 661s into a 900s hard-pinned Nova slot before failing. A fix belongs in `request.sh`'s staging step (copy/symlink each `waitfor`/`press-until` crop referenced by the chosen route into the new result dir's `refs/` before launch, and refuse to admit the request if any crop is missing) -- out of this lane's territory to make, flagging for a decision on whether it's worth a tracked issue or a direct board-request fix.

Sonic Heroes and Super Monkey Ball Deluxe are unchanged from session 61's findings (see that entry above) -- both re-read this session, nothing new to add.

**No device work this session.** `dispatch/running/*.owner` shows the Nova currently running `lane.collapse433`'s request; the Thor stays closed to all title-gameplay work (dead fan, unchanged ruling). Even once the Nova frees up, tonight's owner-granted allowance for it was scoped to re-checking Sonic Heroes/Monkey Ball specifically (both already re-checked, nothing left there) plus `lane/routedriver`'s own Castlevania need -- not a blanket grant for the 13-title Nova-only backlog (Batman, Black Stone, Star Wars Ep. III, Bloody Roar: Extreme, Gunvalkyrie, Dino Crisis 3, Buffy, Halo: Combat Evolved, Conker, Halo 2, Ninja Gaiden Black, ToeJam & Earl III, Tron 2.0) from session 51's "State for a successor", which stays blocked on the same device-role-split/Nova-queue-depth question as before.

[lane.titleroutes] blocked: this lane has nothing of its own queued, running, or newly authorized to drive tonight. What would unblock the next batch of route work: (1) a decision opening a general Nova title-pipeline session (not scoped to a single named title), or the Nova's queue actually draining so a session fits without contending with #462/#474/#414/#569/#507/#433/routedriver work; or (2) the Thor's replacement fan landing, which reopens its 300+ untouched titles to screening. Until one of those lands, the next resume should re-check both before taking any device hold, same as this session did.

## #397 -- 2026-10-01 (session 63, resumed per hostops ADDENDUM 15)

No evidence survives of whatever ran as "attempt 1" under ADDENDUM 15 (no commit, no stray hold, no new scratch output) -- treating it as having left no work behind, not as a strand to clean up.

Checked `dispatch/running/`: the Nova is still running `lane.ibcache`'s request (unchanged since session 62); no hold taken, no device touched directly this session.

Per ADDENDUM 15: checked all 13 of session 51's Nova-only, no-copy-needed, no-route titles for existing survey/nav frames before queuing anything. None of the 12 non-Batman titles have any -- Batman: Dark Tomorrow stays as session 2's combat-blocked finding, not re-touched. So queued generic blind surveys (`--route survey`, 300s, `--device nova --hard-pin`, plain priority -- `gh` is still down so the release-label read fails and falls back to plain, confirmed per-call) for 4 of the 12 before hitting this lane's own pilot gate (its `pilots/titleroutes.ok` is 32.3 h old, past the 24 h verdict window, and these 4 already used the "first 30 min always goes through" allowance):

| title | title_id | request id |
|---|---|---|
| Black Stone: Magic & Steel | 58490004 | `1790921686-titleroutes-1080767` |
| Star Wars: Episode III: Revenge of the Sith | 4C410017 | `1790921690-titleroutes-1082096` |
| Bloody Roar: Extreme | 48550001 | `1790921692-titleroutes-1082566` |
| Gunvalkyrie | 49470017 | `1790921696-titleroutes-1084287` |

The other 8 (Dino Crisis 3, Buffy, Halo: Combat Evolved, Conker: Live & Reloaded, Halo 2, Ninja Gaiden Black, ToeJam & Earl III, Tron 2.0) are not yet queued -- blocked on this session's own pilot gate, which needs a reviewed verdict written before more can be queued. Did not try to force past it or wait idle for these 4 to land, per ADDENDUM 15's own "do not wait idle for the device to clear".

[lane.titleroutes] waiting: the 4 queued surveys above on the Nova (`1790921686-titleroutes-1080767`, `1790921690-titleroutes-1082096`, `1790921692-titleroutes-1082566`, `1790921696-titleroutes-1084287`). Once the last lands: review the frames, write `dispatch/pilots/titleroutes.ok`, then queue the remaining 8 titles' surveys.

## #397 -- 2026-10-02 (session 64, resumed per hostops ADDENDUM 16)

Reviewed the 4 pass-1 surveys session 63 queued, frame-by-frame rather than from `verdict.json`'s fields alone:

| title | title_id | request id | reached_gameplay | note |
|---|---|---|---|---|
| Black Stone: Magic & Steel | 58490004 | `1790921686-titleroutes-1080767` | **no** | stuck on the character name-entry screen; blind menu-A presses typed garbage into the name field (same open-loop trap ADDENDUM 11 found in Castlevania's first-run route). Needs a `waitfor`/`press-until` route past name entry before it can be authored -- left as a dedicated next task, not attempted this session. |
| Star Wars Episode III: Revenge of the Sith | 4C410017 | `1790921690-titleroutes-1082096` | yes | real lightsaber-duel combat across two distinct scene compositions; fps_window_median 30.0, fps_ok_share 0.8766. |
| Bloody Roar: Extreme | 48550001 | `1790921692-titleroutes-1082566` | yes | **real severe slowdown**: live STAGE 1 fight, on-screen FPS counter itself reading 10, fps_window_median 10.83 / fps_ok_share 0.0. Flagging for whoever owns per-title slowdown triage (not this lane) -- this is a genuine performance finding, not a route/state problem. |
| Gunvalkyrie | 49470017 (iso prefix `5345000B`, pre-existing mismatch) | `1790921696-titleroutes-1084287` | yes | real canyon traversal across two distinct frames; fps_window_median 59.94, fps_ok_share 1.0. |

Wrote the verdict to `dispatch/pilots/titleroutes.ok`. Lesson worth repeating: Black Stone's `verdict.json` fields looked
exactly as clean as Gunvalkyrie's (no hitches, no crash, fps_ok_share 1.0) -- only opening the frames caught that it
never left the menu. Every survey needs the frame read, not just the ones a metric flags as suspicious.

Queued 2 of the remaining 8 titles (two at a time this session, not four, per session 63's own "do not repeat" note):
Dino Crisis 3 (`1790928772-titleroutes-2771139`) and Buffy the Vampire Slayer (`1790928774-titleroutes-2773088`), both
Nova, `--route survey --seconds 300 --hard-pin`.

[lane.titleroutes] waiting: the 2 queued surveys above on the Nova. Once both land: review the frames, update
`dispatch/pilots/titleroutes.ok`, queue the remaining 6 (Halo: Combat Evolved, Conker: Live & Reloaded, Halo 2, Ninja
Gaiden Black, ToeJam & Earl III, Tron 2.0: Killer App).

## #397 -- 2026-10-02 03:00 PDT (session 65, attempt 4 of 4)

| title | device | route | replayed? | what gameplay looked like | fps (screening) |
|---|---|---|---|---|---|
| Dino Crisis 3 (43430003) | Nova | `dino-crisis-3` | **yes** (`1790931260-titleroutes-3615015`) | corridor + HUD at the mark, then boosting into a switch room, activating it; live throughout | median 27.16, 15.6% at 30+; two first-compile shader stalls (15.1 s, 12.4 s) on a freshly cleared cache read as hangs |
| Buffy the Vampire Slayer (45410012) | Nova | `buffy` | replay 1 (`1790931264-titleroutes-3615749`): reached play, then stuck 4 min at a ledge gap | canyon, live for ~1 min, then one frozen view | 95.4% at 30+, no hang (over a stuck window: not a usable reading) |
| Buffy | Nova | `buffy` (B jumps) | replay 2 `1790932722-titleroutes-3976729`: reached play, stuck again at a ledge ("Push into low ledges to climb onto them") for ~4 min | live canyon at the mark, then one frozen view | 96.3% at 30+ (stuck window). Two failed replays: needs a path found by sight |

The survey for Dino Crisis 3 had scored the Options screen (a START press in play opened it); the route avoids START
after the mark. Also queued: pass-1 surveys for Halo: Combat Evolved (`1790933948-titleroutes-171581`) and Conker
(`1790933948-titleroutes-171701`). This lane is at its attempt cap: a successor should start from NOTES.md's session 65
"State for a successor", which names the three unreviewed requests above.

[lane.titleroutes] waiting: `1790933948-titleroutes-171581` (Halo CE survey) and `1790933948-titleroutes-171701`
(Conker survey) on the Nova. This session cannot be resumed; hostops
should hand them to a successor.
