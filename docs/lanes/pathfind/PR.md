# pathfind: a screen-reading agent that drives a title from boot into gameplay

State: ready

Lane: pathfind            Issue: #433
Base: master @ 76a2c15333 (origin/master merged into lane/pathfind 10-12)
Files: docs/lanes/pathfind/**, docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py, docs/testing/titles/pathknow/hints/**, docs/testing/titles/pathknow/paths/**, docs/testing/jobs/selftest.d/95-stuckdetect.sh
Prediction: none: no arm (tooling and a probe measure; no emulator code)
Needs device: yes (held, direct driving; no dispatcher requests)    Needs NDK: no

10-05 to 10-12, the held-run chain on the Nova. Tool changes in `pathfind.py`:
- **A stuck detector on the hold** (`docs/lanes/stuckdetect1007/stuckdetect.py`, imported only if present). A hold
  stuck at a wall or in a menu first gets unstick rungs: the genre's own unstick moves, then the first three unlock
  buttons. It then ends as `stuck_abort` with a reason instead of spending the rest of its budget. Selftest leg `sdstuck`.
- **Weekly-limit answers** from the model end the session as void-limit, not as a path failure.
- **Two refusals before any step.** Football titles go last (owner order 10-05). A title whose latest verdict is
  below the bar with no recorded fix is refused (owner order 10-06; `docs/lanes/pathfind/below-bar.tsv`).
- **A fighter's counter prompt** (Press X/Y now) is answered on play looks.

Merged with master's profile gate. The football and below-bar refusals run first, then R3: a title with a known path
is refused unless `--path-broken` names a failed run of it. Master's `models.model_for("pathfind")` replaces the
FAST/STRONG env dials. `pathknow/paths/` gains 54 recorded paths and `pathknow/hints/` gains 30 learned-hint files,
all from the held runs since 10-07. The held runs' folders are under `runs/`, and they are the evidence for the
Playable ledger rows that cite them.

Local checks (no CI), 10-12, at the head after merging origin/master 76a2c15333:
- `python3 docs/testing/titles/pathfind_selftest.py` -> all ok, 105 checks. It had been red on master since R3 (4 ok,
  then the refusal at the second case). It had also been red on the lane since the stuck detector, which ended 7 hold
  legs' sim scenes early. The selftest now names a fake failed run for R3 and keeps a private dispatch dir. The
  detector is off for the hold-loop legs and on for its own leg. A new leg, `r3`, checks the refusal.
- `python3 docs/testing/titles/titlestate_selftest.py` -> all checks passed.
- `python3 docs/lanes/stuckdetect1007/stuckdetect.py selftest` -> all ok.

10-04, the owner's screening (`pm/screen-1004.tsv`): each title is pathed first-run, its profile promoted, then a 600-s
held measurement against the 30 fps bar. Per-title lines are in OUTBOX.md and the scoreboard is at the top of NOTES.md.
Result: 12 of 12 screened. 7 clear (3 verdict PASS: RalliSport Challenge, The Simpsons Hit & Run, Dark Summit; 4 with
fps_ok >= 0.99 that miss Playable on hold design), 1 fail (Amped, aborted at 5:04, vCPU-bound at 31.6 ms/frame),
4 can't-path (Phantom Crash, Simpsons Road Rage, Mashed, Whiteout; Whiteout's load card never finished, filed as
NEW ISSUE). Spend about $53 of $60.
Tool changes in `pathfind.py`, each with a selftest case:
- **The 3/5-min fps gate** (`FPS_GATES`, owner 10-04 ~08:10). At 3 min and 5 min of a hold, the hold's own gfps
  lines are read. Median < 22 at 3 min, or < 27 at 5 min, with under 60% at 30 x 0.95, stops the hold. One 180-s
  perflog run follows. It stopped Amped at 5:04 (median 23), and decompose.py then named the cost: guest busy
  31.6 ms per frame.
- **Kept hold frames go to `route-frames/HHMMSS-hold.png`.** Master's failgate (`de4b991a6c`) reads the scored window
  from those frames. Without them a 671-s RalliSport hold at fps_ok 1.0 scored "window unmeasured".
- **A cutscene press that advanced the same screen repeats unlooked** (3x, then a look). Phantom Crash spent 62 of
  92 calls on one dialogue.
- **A probe input refused twice is replaced** by the next untried input of `PROBE_LADDER`. In Road Rage, RT was
  probed ten times while the car never moved.

Attempt 7 (10-03 afternoon, the pool file):
- **Golden saves made on the Thor read as damaged on the Nova when the title signs with the HDD key.** The two
  eeprom.bin differ. Forza's Thor-made golden looped on "profile is damaged". A first-run on the Nova made a fresh
  profile whose CarIcons.sig and Garage files are byte-identical to an older Nova save and differ from the Thor one.
  Promoted it as Forza's golden, and run 2 loaded it. 55 of 84 goldens are Thor-made. Castlevania's and Spikeout's
  load fine on the Nova, so the effect is per title. Filed in OUTBOX as NEW ISSUE.
- **Hold position test:** a 30-s window whose kept frames barely change (< 0.03 at the probe's contrast step) is
  `state=still`, not play. On the stored strips, Black Stone's standing 600 s (a verdict PASS) would be credited about
  30 s, and Panzer is unaffected.
- **Input:** `RT+<dir>` / `LT+<dir>` tokens (trigger and stick together). The drive loop steers on the gas, and a
  still drive window reverses while turning. A throttle probe's steering legs keep the gas on: gas-off steering put
  Forza into the pit wall twice.
- **Hold loop:** a loop button that opens a menu is dropped for the rest of the hold. In ToeJam, a "Presents"
  dialog was in 13 of 19 frames.
- **Probe:** an ambiguous probe takes two more idle/input rounds, and 2 of 3 wins (addendum 4 item 2). Selftested
  only; it is not yet measured on a device.

| title | run | result | model calls | cost |
|---|---|---|---|---|
| Forza (4D53006E) | forza-firstrun, forza-run2 | live race at 2.6 min both times; gave up (walls); the game runs at 0.59x speed (16-21 fps) | 76 + 60 | $10.57 |
| ToeJam & Earl III (5345000F) | toejam-earl-3-hold | play in 1.7 min, held 605 s; FAIL fps 72.8% | 23 | $1.29 |
| Spikeout (53450029) | spikeout-hold | play in 8.2 min, held 607 s; **PASS** (fps_ok 1.0); moves, does not progress: owner frame review | 50 | $3.46 |
| Castlevania (4B4E002D) | lane.local's returning run | reached play on its Thor-made golden; no pathfind run needed | 0 | - |

Resume (10-03, probe gate, ADDENDUM 4): the probe's change test was a fixed 16-grey-level step, so a dark scene's real
control (Black Stone: a sword, a spell, a step) changed under 1% of the pixels and was refused before any model call.
`probe_change()` scales the step to the frame's contrast (floor 4, cap 16); PROBE_MOVED 0.03 -> 0.004; a claimed hold
gets its own clock. Gate on 48 labelled stored probes, scored through the whole chain (the new rule, then the real confirm
question to the strong model): real control 14 of 18 accepted, non-control 0 of 30 (menus 0/4, cutscenes 0/8, pauses 0/2),
agreement 44 of 48 (92%). It passes on the corrected labels only: one label (Midnight Club 3, 034) was changed after the
model's answer on the same frames; NOTES.md "Probe gate" gives the full history for the owner to judge. The lane's
`gate/` directory holds the labels, results and scripts.

Attempt 2-4 (earlier 10-03): hold-play (`pathfind.py --hold-s 600`, Nova only), the team-sport genre and `--goal`, the
X unlock ladder and the hold perflog marks. See NOTES.md.

Local checks (no CI), 10-04 14:25 PDT, at the head after merging origin/master:
`python3 docs/testing/titles/pathfind_selftest.py` -> all ok, 63 checks (adds `fpsgate`, `dialogue`, `proberot`).
`bash docs/testing/preflight.sh --allow-tracker` -> every gate ok except `coverage`. That gate fails on five issues
filed in the last hour (#811-#815) that have no lane or blocker row on origin/board yet. #811 is this lane's Whiteout
finding. Board rows are not a lane's to write; lane.local or the board owner classifies them. No harness file under
docs/testing/jobs is changed.

Earlier local checks, at the head after merging origin/master 10-03 14:55 PDT:
`python3 docs/testing/titles/pathfind_selftest.py` -> all ok (adds `holdstill`, `holdshed`, `rounds`, `ownrt` and the
RT+/LT+ `actions` checks; `holdstill` and `rounds` fail on the old code). `bash docs/testing/preflight.sh --allow-tracker`
-> "preflight passed - safe to push". No harness file under docs/testing/jobs is changed.

Release note (none): test tooling only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## 10-03 evening -- Black Stone and Dino Crisis 3 holds FAIL (#797, #795, #793); Panzer Dragoon Orta hold run 3 PASSED (counted Playable, ledger row 16); evidence runs/panzer-dragoon-hold3

## 10-18 (cont. 2) -- below-bar.tsv regenerated via the tool's own seed_below_bar() (30 -> 150 rows), not hand-filed; 12 genuine new fps-bar refusals, 8 pre-existing owner `cause` entries verified intact

## 10-18 (cont.) -- finished the backlog's pass=true scan; 10th title banked (Lemony Snicket, 4156001F), remaining untriaged backlog down from ~280 to 141 directories (fails + no-verdict navigation runs, named in NOTES.md)

## 10-18 -- offline reconciliation of an unattended chain's uncommitted output (attempt 3); 9 new Playable, 2 caught false

An unattended chain ran through at least 10-16 without anyone committing its output: by 10-18 the worktree held
~290 uncommitted run directories (~5.2 GB) plus 134 unstaged `pathknow/` hint and path-replay files. This session
did not run the device; it scanned every `verdict.json` under those run directories for `pass: true`, cross-referenced
each hit against `pm/playable-accepted.tsv` (16 of the candidates were already banked by an intervening lane.local
session this lane hadn't seen before), then frame-reviewed the rest against `contact.png`/`hold_strip.jpg` before
touching the ledger -- no PASS goes on the ledger from the verdict flag alone.

Result: **9 titles banked** to `pm/playable-accepted.tsv` (Mortal Kombat: Deadly Alliance, Mortal Kombat: Shaolin
Monks, RalliSport Challenge, Cel Damage, Bad Boys: Miami Takedown, Scooby-Doo: Mystery Mayhem, Nickelodeon Avatar:
The Last Airbender, Micro Machines, Tron 2.0: Killer App). 2 already carried a void marker from a past session
(Auto Modellista, Beyond Good & Evil) and needed no action. **2 caught false** despite `pass: true` -- found only by
looking at the frames, not the gate numbers:
- **Black Stone: Magic & Steel** -- the Tork STICK:up/STICK:down cancel bug (ledger row 22's known mechanism):
  the character stands turning in place for the whole ~550 s hold; 0 route-frames meant static_window/position were
  never measured, so nothing caught it automatically.
- **NHL 2K3** -- ~470 of 605 scored seconds are the post-goal instant-replay/net camera (the in-game VCR control bar
  is visible in 2 of the 4 route-frames), scored "gameplay" by the per-tick model because crowd/board blur kept the
  stuck-frame gate from firing.

Both get a `NOT-PLAYABLE.txt` in their run dir and a `false-playable` row in `pm/pathfind-pool.tsv` (a new pool class,
for a verdict that needs a code fix rather than a route fix). `pm/` is outside this git repo, so the ledger and pool
edits are disk writes only, no commit. This commit lands `pathknow/`'s hint/path accumulation in full and the 13 run
directories this session actually reviewed (9 banked + 2 void + 2 caught-false); NOTES.md names the other ~280
untracked run directories as still-unreviewed backlog for the next session, not touched here.

`Files:` is unchanged (`docs/lanes/pathfind/**` already covers `runs/**`).
Release note (none): ledger/knowledge-store data and test tooling only, no emulator code changed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
