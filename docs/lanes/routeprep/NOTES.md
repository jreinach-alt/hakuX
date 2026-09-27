# lane.routeprep: boot-to-gameplay route drafts, offline

Issue #397 (0.5 tracking #433). Brief: `briefs/routeprep.md` (lane.local,
2026-09-26 21:27 PDT). Base `e5db66fa37`. PR #468. No device.

Drafts go in `drafts/`. lane.titleroutes validates each one on a device and
adopts it into `docs/testing/titles/routes/`. Every draft passes
`route.sh --check`. None has been played.

## How to read a draft

- The header names every frame the draft rests on, by result dir and file.
- Each step carries a tag: `[seen <frame>]` = the screen or its effect is in
  a frame on disk; `[inferred]` = follows from frames, not itself seen;
  `[<title>]` = taken from a played route of a sibling title (PGR1 for PGR2,
  Burnout 3 for Revenge); `[guess]` = nothing on disk.
- Every menu step is followed by a `shot`, so one unattended replay shows
  where a draft leaves the path. The replay's frames replace the guesses.
- `mark gameplay` is a placeholder wherever it is tagged `[guess]`: move it to
  the first frame with control. Titleroutes' rule stands: mark as soon as
  control shows, not after an idle.
- Cursor moves are left-stick flicks (`axis LY max`, 0.15 s, `mid`), per
  titleroutes' finding that pad.sh's D-pad keys moved nothing in two games.
- Skip loops before the mark use A only: a START that lands in gameplay
  pauses it (pass 1's generic rounds toggled pause).
- A title with no profile step on the path gets one file, `<stem>.route`, as
  titleroutes did for Kabuki and Nightfire; `request.sh --route <stem>` reads
  it directly.

## Evidence on disk (read with python3; ls/cp are blocked in dispatch/)

| source | what it holds | titles |
|---|---|---|
| `dispatch/results/0-0-y-1790433159-titleplay-p1-<t>/route-frames/` | survey route: a frame at 20/40/60 s, after every START and A, then every ~25 s | 50cent, brucelee, burnout-rev, galleon, doa3 (+ the titles already routed) |
| `dispatch/results/0-0-y-17904*-titlebench-<n>/frames/` | hands-off 240 s, one frame per ~10 s: boot-to-title timing and the attract | PGR (6), WWE Raw 2 (11), PGR2 (14), MC3 (19), Crash Twinsanity (20) |
| `dispatch/results/1790365*-gamecheck-*/`, `0-0-y-1790432892-hotfix041-*` | hands-off soaks with frames | Galleon, Tork, RalliSport 2, Spikeout, Ghoulies, Conker, DOA3, JSRF |
| `~/hakux-work/nav/<session>/` | titleroutes' nav sessions: nav.tsv + every frame | PGR1 (menus model PGR2), Burnout 3, Black, ... |

Tools (in `scratch/`, not committed): `sheet.py`/`sheet2.py` build a contact
sheet of a result dir's frames (consecutive same-size frames collapsed),
`navsheet.py` prints a nav session's log with its frames, `find.py` lists
every result dir whose request names a title.

## Route drafts

Work list: titleroutes' NOTES table, in its order. Skipped: titles with a
route in `routes/` (Kabuki, DOAX, Black, Nightfire, GoldenEye RA, Burnout 3,
Crimson Skies, Forza, Fuzion Frenzy), PGR (titleroutes' nav sessions at
21:03 and 21:23 PDT), the #462 set, and Batman: Dark Tomorrow (titleroutes
reached its gameplay; it is blocked on combat, not on a route).

### Batch 1 (posted on #397, 2026-09-26)

- route draft: `50cent.route` (Nova) -- evidence: pass-1 frames 073540-073629. The profile keyboard is avoidable: the Create New Profile list's button bar has **X = Continue without saving**, so one route serves first run and returning. Path START (skips FMV), START, New Game (A), Thug (A), X. Open: a YES/NO confirm after X; whether cutscenes after it take A; where control starts.
- route draft: `bruce-lee.route` (Thor) -- evidence: pass-1 frames 111133-111246. New Game lands on a Player Info / Purchase Moves / **Continue** menu with Player Info highlighted; A opened a status screen pass 1 never left. Flick down twice to Continue, then A. Open: that the stick moves this cursor; what follows Continue; the attack buttons.
- route draft: `burnout-revenge.first-run.route`, `.returning.route` (Nova) -- evidence: pass-1 frames 075152-075340 up to the SAVE/LOAD prompt (Load Profile highlighted, Create Profile one down); the rest from Burnout 3's played routes. Open: the name keyboard (Burnout 3's had Done highlighted), the save YES/NO default, a race-training video before the first race.
- route draft: `pgr2.first-run.route`, `.returning.route` (Thor) -- evidence: titlebench-14's hands-off frames (PRESS START at ~120-140 s, attract from ~150 s); the menus from titleroutes' PGR1 sessions. Open: PGR2's main-menu items (the draft takes the highlighted one at every step), whether the intro FMV skips.
- route draft: `wwe-raw2.route` (Nova) -- evidence: titlebench-11's hands-off frames (Press START at ~110-120 s, then FMV and DEMONSTRATION attract). Everything past the title is a guess: a possible save-data prompt, Exhibition, one-on-one, two selects, entrances. Open: all menus; the strike/grapple buttons.

### Batch 2 (posted on #397, 2026-09-26)

- route draft: `mc3.first-run.route`, `.returning.route` (Nova) -- evidence: titlebench-19's hands-off frames (PRESS START TO BEGIN at ~120-170 s, then the FMV again). Aims at Arcade -> Cruise (free driving, no timer) [recalled]. Open: the profile screen and keyboard; whether Arcade is one below Career; Cruise's place in the Arcade menu.
- route draft: `crash-twinsanity.route` (Thor) -- evidence: titlebench-20's hands-off frames (PRESS START BUTTON at ~60-110 s, attract clips, then the intro again). Past the title all [guess]: New Game, a possible save prompt, a long opening cutscene advanced with A. Open: every menu; which button spins.
- route draft: `187-ride-or-die.route` (Nova) -- evidence: **none on disk**. A survey with a frame after every press, aiming at Story's first (driving) mission. Worth one short nav session rather than a replay.
- route draft: `smt-nine.route` (Thor) -- evidence: **none on disk**; a Japan-only release, so its menus are in Japanese. New Game (first item), default name (START), then dialogue with A. Worth a nav session.
- route draft: `capcom-classics2.route` (Thor) -- evidence: **none on disk**. First game in the list, Play, BACK = coin, START = 1P start [recalled]; the play pattern feeds coins so a game over continues. Open: every menu; that BACK is the coin.

## Do not repeat

- Do not read the titlebench `frames/` as if they had input: they are
  hands-off, so they time the boot and show the attract, nothing more.
