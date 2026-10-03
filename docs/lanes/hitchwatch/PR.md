# hitchwatch: count the hitches, and catch a frozen/looping scored window (#433)

State: ready

Lane: hitchwatch            Issue: #433 (0.5: 50 Playable)
Base: master @ bfb8c145fb (merged clean mid-session; see NOTES.md)
Files: docs/testing/hitch_report.py, docs/testing/title_verdict.py, docs/testing/titles/targets.toml, docs/testing/jobs/selftest.d/99-hitch-report.sh, docs/testing/jobs/selftest.d/99-power-per-frame.sh, docs/lanes/hitchwatch/NOTES.md, docs/lanes/hitchwatch/PR.md
Prediction: none: a test-harness rule change (offline logcat/frame analysis), not a device-behavior arm
Needs device: no

## Summary

The owner played Sonic Heroes on the Nova and saw brief (<1s) delays the
sustained-fps rule cannot see (one stall is a rounding error in a 600s,
time-weighted window). This implements the two checks the brief asked for,
both offline, from data already on disk:

1. **`docs/testing/hitch_report.py`** (new): from a result's logcat.txt,
   lists every per-window `hakuX-pace` line whose `max=` is >= 100 ms in the
   scored window, classifies each from the SAME window's `[shd413]` line
   (shader-cache misses / pipeline-compile ms) and the `[rdc]` lines whose
   own timestamps fall inside that window's span (texture-dirty-bit-clear
   microseconds, the nearest proxy to texture work the existing counters
   give) as shader / texture / both / unexplained, and reports totals, rate,
   worst, classification counts, and the 5 worst. `title_verdict.py` wires
   this into `judge()`: `v["hitches"]`, and a new fail reason "hitches: ..."
   past the owner's bars (>6/min after the first 60s, or any hitch >=500ms
   after that), unless the title's targets.toml entry sets
   `hitch_allowance` (documented, not set on any title -- see below).
2. **Whole-window liveness** (same module, `static_window()`): Super Monkey
   Ball and Castlevania both scored PASS on a menu because
   `reached_gameplay` only reads the mark frame. A plain frame-to-frame
   pixel diff does NOT separate a looping menu animation from real gameplay
   (Super Monkey Ball's Stage Select has an animated background and
   measures a BIGGER frame-to-frame diff than a confirmed-Playable capture
   -- see NOTES.md's table). What does separate them: the fraction of
   pixels that never drift far from the window's own FIRST sampled frame,
   across every post-mark route-frame. Validated on both of the brief's
   required cases: `1790900520-autoverdict-566484` (Super Monkey Ball)
   FAILs at frozen_frac 0.32, a confirmed-Playable run (Crimson Skies) PASSes
   at 0.027. A window with fewer than 3 post-mark route-frames (most routes
   take none) is `measured: false` and never fails on this check -- absence
   of frames says nothing about the title.

**The central finding, stated plainly because the brief asked for it
explicitly rather than tuned thresholds:** the owner's proposed hitch bars
(6/min, 500ms, after a 60s warmup) do NOT separate the one available Sonic
Heroes capture from the confirmed-Playable population -- they invert it.
That capture turns out to be a withdrawn, stale-route run that was frozen on
a pause menu for its whole window (confirmed by reading its route-frames:
the pause screen's timer reads the same value 7 minutes apart), so it is a
LIVENESS case, not a hitch-rate case, and clears the hitch bars easily (one
434ms stall, 0.10/min). Meanwhile four already-Playable titles (Azurik: a
single 5.4s pipeline-compile stall; KOF: 1.28/min, 1.6s worst; Kabuki
Warriors: 0.65/min, 650ms worst; THPS2x: 11/min) would newly fail the same
bars. I did not tune the numbers to make this go away -- the brief explicitly
says not to, and two of those titles (Kabuki Warriors, Forza) already carry
`confirmation_s = 1200` in targets.toml for the owner's own "random stalls" /
"slow-building defects" reasoning, so a stall-tolerant path already exists
for exactly this situation if the owner wants it applied here. Full survey
table, the frame-diff-vs-frozen-frac comparison, and what would resolve this
are in NOTES.md.

**Mid-session**: while this survey was running, `lane.titleroutes` session
58 folded to `origin/master`, fixing the exact route bug this PR's own
reading of 1078702 found (a START press pausing live play with no un-pause
step) and confirming the diagnosis independently. No fresh confirmation soak
exists yet for the fixed route (it's nominated, not yet run) -- merged
clean, changes nothing in this PR's conclusions.

Release note (none): a test-harness/judging change (offline logcat and
route-frame analysis in title_verdict.py), not emulator code -- nothing a
player's build behavior changes from this PR.

## Verification

- `SELFTEST_ONLY="99-hitch-report" bash docs/testing/jobs/selftest.sh` --
  12 passed, 0 failed. Fixtures are built from VERBATIM real logcat lines
  (Sonic Heroes' one captured stall, Azurik's 5.4s stall and its
  shader+texture "both" window, Alien Hominid's unexplained hitch), plus
  pure-Python boundary tests of the judging functions and two mutants.
- `SELFTEST_ONLY="89-title-verdict 99-verdict-10min 99-thermal-pause
  99-default-regimen 99-power-per-frame 99-display-covered 66-status-titles
  99-status-fullwindow" bash docs/testing/jobs/selftest.sh` -- 185 passed, 0
  failed (after fixing `99-power-per-frame.sh`'s sign-mutant fixture, which
  copies `title_verdict.py` alone into an isolated dir and needed
  `hitch_report.py` copied alongside now that the former imports the
  latter -- found by running the suite, not assumed).
- `SELFTEST_ONLY="60-status 62-status-freshness 63-status-lanes
  64-status-html 65-status-objective 67-status-measured 94-arms-verdict-scope
  99-status-degraded 99-status-escalation-items 99-status-escalations
  99-title-state"` -- 199 passed, 1 failed on a cherry-picked fragment list
  that skipped `40-arms-refusal.sh`, whose fixture `60-status.sh`'s own
  header comment says it depends on; unrelated to this change (NOTES.md has
  the read-through and the corrected re-run).
- `python3 -c "import ast; ast.parse(...)"` on `hitch_report.py` and
  `title_verdict.py`; `tomllib.load()` on `targets.toml`: all OK.
- Whole `selftest.sh` (18-25 min) not run end to end this session; the
  fragments above cover every file this change touches or anything that
  could plausibly import/copy it.
- `static_window()`'s PIL-dependent half (frame reading) was validated by
  hand against real route-frames (the numbers in NOTES.md's table), not in
  a selftest -- the CI runner has neither PIL nor numpy
  (`selftest-runner-has-no-numpy`), so the committed selftest exercises only
  the pure-Python judging half (`static_window_fail`), per the project's own
  established pattern for this exact gap (`title_verdict.py`'s
  `contact_sheet()`).

## What's left, deliberately

`hitch_allowance` is documented but unset on every title. Whether Azurik,
KOF, Kabuki Warriors and THPS2x get one, whether the bars get revised once a
real Sonic Heroes confirmation exists, or both, is an owner call -- see
NOTES.md's closing section for the three options named plainly.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
