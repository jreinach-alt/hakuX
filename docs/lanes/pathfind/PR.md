# pathfind: a screen-reading agent that drives a title from boot into gameplay

State: ready

Lane: pathfind            Issue: #433
Base: master @ 425ffe1ad1 (origin/master merged into lane/pathfind 10-04 08:15 PDT)
Files: docs/lanes/pathfind/NOTES.md, docs/lanes/pathfind/OUTBOX.md, docs/lanes/pathfind/PR.md, docs/lanes/pathfind/runs/, docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py, docs/testing/titles/pathknow/hints/learned-pub-454D.md, docs/testing/titles/pathknow/hints/learned-pub-4553.md, docs/testing/titles/pathknow/hints/learned-pub-4D53.md, docs/testing/titles/pathknow/hints/learned-pub-5341.md, docs/testing/titles/pathknow/hints/learned-pub-5655.md, docs/testing/titles/pathknow/hints/learned-series-rallisport.md, docs/testing/titles/pathknow/paths/
Prediction: none: no arm (tooling and a probe measure; no emulator code)
Needs device: yes (held, direct driving; no dispatcher requests)    Needs NDK: no

10-04, the owner's screening (`pm/screen-1004.tsv`): each title is pathed first-run, its profile promoted, then a 600-s
held measurement against the 30 fps bar. Per-title lines are in OUTBOX.md and the scoreboard is at the top of NOTES.md.
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

Local checks (no CI), at the head after merging origin/master 10-03 14:55 PDT:
`python3 docs/testing/titles/pathfind_selftest.py` -> all ok (adds `holdstill`, `holdshed`, `rounds`, `ownrt` and the
RT+/LT+ `actions` checks; `holdstill` and `rounds` fail on the old code). `bash docs/testing/preflight.sh --allow-tracker`
-> "preflight passed - safe to push". No harness file under docs/testing/jobs is changed.

Release note (none): test tooling only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## 10-03 evening -- Black Stone and Dino Crisis 3 holds FAIL (#797, #795, #793); Panzer Dragoon Orta hold run 3 PASSED (counted Playable, ledger row 16); evidence runs/panzer-dragoon-hold3
