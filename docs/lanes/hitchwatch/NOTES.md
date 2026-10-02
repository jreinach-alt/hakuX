# hitchwatch (#433): hitch counting + whole-window liveness

## Resuming (attempt 1, this session)

No prior commits existed on `lane/hitchwatch` (it sat at `origin/master`) and
`docs/lanes/hitchwatch/` did not exist, so the previous session left no
NOTES.md to read. The only trace of earlier work was three untracked scratch
scripts in the worktree root (`scratch_diff_check{,2,3}.py`), exploring
frame-to-frame perceptual diffs on `route-frames` PNGs for the three cases
the brief names (Super Monkey Ball 566484, the withdrawn Sonic Heroes
1078702, and a Castlevania titleroutes capture). That exploration is why
part 3 below did not start from a naive frame-to-frame diff: the scratch
output already showed Super Monkey Ball's diff fractions (0.03-0.40) were
*not* small, which turned out to be the key fact (see WHOLE-WINDOW
LIVENESS). The scratch files are left in place for the record but are not
part of the change; `python3 scratch_firstlast.py` / `scratch_static2.py`
(added this session, same reason) reproduce the numbers below.

## Mid-session: origin/master landed the Sonic Heroes route fix

While this PR's survey (below) was already concluding that the only
available Sonic Heroes capture (1078702) was a stale/frozen artifact and not
evidence about the owner's observed hitches, `lane.titleroutes` session 58
folded to `origin/master` (`bfb8c145fb`, 2026-10-01 19:02 PDT) confirming
exactly that: `sonic-heroes.route`'s old 9-cycle START/A version pressed
START during already-live play, pausing it with no un-pause step -- the
route was rewritten from nav.py observation and replayed clean
(`scratch/judge/sonic-heroes-171639`: mark gameplay 172133, three `play`
shots with score/rings/timer all advancing). It is "Nominated for the Nova
fps confirmation" (`host-tools/nova-nominations.tsv`, a host file, not this
repo) but **no fresh `dispatch/results/*sonic-heroes*` Playable-confirmation
soak exists yet** -- that nomination had not been picked up as of this merge.
Merged into `lane/hitchwatch` clean (only `targets.toml` touched by both
sides; no conflict). This changes nothing below: it is independent
confirmation that 1078702 was never a valid hitch-rate data point, and the
real confirmation this survey needs is still pending, not something I can
produce myself (no device work, no dispatch requests, per the brief).

## What exists now

- `docs/testing/hitch_report.py` (new): parses hakuX-pace / [shd413] / [rdc]
  lines already in logcat.txt for the scored window, lists every window
  whose `max=` is >= 100 ms, classifies it (shader / texture / both /
  unexplained) from the SAME window's shd413 line and the [rdc] lines whose
  own timestamps fall inside that window's span, and reports counts, rate,
  worst, and the 5 worst. It also judges whole-window liveness
  (`static_window` / `static_window_fail`) from route-frames. Both halves
  are also runnable stand-alone: `python3 hitch_report.py <result-dir>`.
- `docs/testing/title_verdict.py`: calls both, adds `hitches` and
  `static_window` to verdict.json, adds their failures to `fails` (reasons
  "hitches: ..." and "static window: ...") unless the title's targets.toml
  entry sets `hitch_allowance`, and prints the hitch/liveness figures in the
  VERDICT line.
- `docs/testing/titles/targets.toml`: documents the new `hitch_allowance`
  field. **Not set on any title** -- see THE SURVEY below for why.
- `docs/testing/jobs/selftest.d/99-hitch-report.sh`: fixtures built from
  REAL cut logcat lines (Sonic Heroes' one captured stall, Azurik's 5.4 s
  stall, Alien Hominid's unexplained hitch, Azurik's shader+texture "both"
  window), plus pure-Python boundary tests of `hitch_fail`/
  `static_window_fail`, plus two mutants. 12/12 pass
  (`SELFTEST_ONLY="99-hitch-report" bash docs/testing/jobs/selftest.sh`).
- `docs/testing/jobs/selftest.d/99-power-per-frame.sh`: one-line fix. Its
  sign-mutant test copies `title_verdict.py` alone into an isolated
  directory to run a mutated `thermal_state.py` against it; now that
  title_verdict.py imports hitch_report.py, that copy needs to travel too,
  or the copy's import fails and the mutant assertion reads "[exit 1]"
  instead of the judged value. Found by running the existing suite, not by
  guessing -- see VERIFICATION.

## HITCHES: what the counters actually say, and the survey (part 2)

### The regexes, checked against real output, not the brief's paraphrase

The brief names the tags loosely ("hakuX-perf [pbN]", "tex=<n>/<us>/<bytes>");
the brief itself says it names them, not defines them. Reading
`hw/xbox/nv2a/pgraph/profile.c` and `system/physmem.c`:
- `hakuX-pace`: `f=<flips> v0..v4=<counts> vb=<total> max=<ms> ms=<window ms>`,
  once per 60 guest flips -- the SAME cadence title_verdict.py already scores
  fps windows on.
- `hakuX-perf [shd413]`: same `f=`, `dsm=` (shader-cache misses this
  window), `dpc_ms=` (pipeline-compile ms this window), `dvs_ms=`/`dgs_ms=`/
  `dfs_ms=` (per-stage compile ms), emitted in the same tick as the pace
  line above it (matched by `f=`).
- `hakuX-perf [rdc]` (`system/physmem.c`, `RDC_TCD_TEX` site): `tex=<n>/
  <us>/<pages>/<hits>` is calls/microseconds/pages/hits of texture-region
  dirty-bit clears, NOT literally texture upload bytes as the brief's
  paraphrase suggested -- a reasonable proxy for "texture work happened",
  but on the probe's OWN clock, not tied to the flip count. `hitch_report.py`
  sums `[rdc]` lines whose own timestamp falls inside `[t - window_ms, t]`
  of the hitch's pace line, not by matching `f=`.
- `[pb569]` exists (compile_worker.c), not a generic `[pbN]`; not used here
  -- shd413 already carries the pipeline-compile time the hitch needs.

### The survey (score every finished Playable result with a logcat)

`verdict.json` across `dispatch/results/*/` with `pass: true` and
`rating_candidate` in (Playable, Playable (2x)): **13 results, 12 distinct
titles** (Castlevania: Curse of Darkness appears twice; see LIVENESS below).
Hitch figures (`hitch_report.py <dir>`), scored window from `mark gameplay`
to `soak end`:

| title | hitches (>=100ms) | /min after 60s | worst | classification |
|---|---|---|---|---|
| Sonic Heroes (1078702, withdrawn, owner-flagged) | 1 | 0.10 | 434 ms | shader |
| Ride or Die | 0 | - | - | - |
| 50 Cent: Bulletproof | 1 (pre-warmup) | 0.0 | 100 ms | unexplained |
| Alien Hominid | 3 | 0.15 | 166 ms | unexplained x3 |
| **Azurik: Rise of Perathia** | 15 | **0.58** | **5463 ms** | shader x10, both x5 |
| Baldur's Gate: Dark Alliance | 0 | - | - | - |
| Crimson Skies | 6 | 0.19 | 296 ms | shader x3, both x2, unexp x1 |
| **KOF: Maximum Impact** | 29 | **1.28** | **1555 ms** | shader x27 |
| **Kabuki Warriors** | 19 | **0.65** | **650 ms** | shader x15 |
| Super Monkey Ball Deluxe | 0 | - | - | - (frozen on a menu; see below) |
| **Tony Hawk's Pro Skater 2x** | 121 | **11.01** | 836 ms | shader x5, unexplained x116 |
| WWE Raw 2 | 6 | 0.30 | 354 ms | shader x4, unexp x2 |

**The owner's bars (>6/min after 60s, OR any hitch >=500ms after 60s)
do NOT separate Sonic Heroes from the confirmed-Playable population --
they invert it.** The only available Sonic Heroes capture clears both bars
(0.10/min, 434 ms) by a wide margin, while four already-Playable titles
(bolded) would newly fail: Azurik on a single 5.4 s pipeline-compile stall,
KOF at 1.28/min with a 1.6 s worst, Kabuki Warriors at 0.65/min with a
650 ms worst, and THPS2x at 11/min (almost every window has SOME sub-200ms
jitter, mostly unexplained). Per the brief: **say so, do not tune the
thresholds to fit.** I did not. Two further things worth saying plainly:

- **The available Sonic Heroes capture is not evidence about the owner's
  observed hitches at all.** `WITHDRAWN.txt` already says the run played the
  stale route, and reading its actual route-frames (`180617-play.png` vs
  `181308-play.png`, 7 minutes apart) shows the SAME frame: `PAUSE / Continue
  / Restart / Quit`, timer frozen at `00:21:29` in both. The run sat on the
  pause menu, rendering at a smooth 59 fps with one brief stall, for its
  whole scored window -- which is exactly why it also fails
  `static_window()` below (frozen_frac 0.99). It is a LIVENESS case, not a
  hitch-rate case. The owner's "brief, less than a second, delays" while
  actually playing have not been captured by any automated run yet (the
  rewritten route gets its own confirmation per WITHDRAWN.txt); there is
  currently no valid positive example to calibrate hitch thresholds against.
- Kabuki Warriors and Forza already carry `confirmation_s = 1200` in
  targets.toml for "random stalls" / "slow-building defects" (owner,
  2026-09-30) -- the project already knows these titles stall and chose a
  longer confirmation window, not a fail, as the response. Azurik and
  THPS2x's hitch figures are NEW information this report surfaces, not
  previously tracked anywhere.

**What I did, given that:** implemented the rule exactly as specified
(`hitch_report.HITCHES_PER_MIN_BAR = 6.0`, `BIG_HITCH_MS = 500.0`,
`WARMUP_S = 60.0`, hitch floor `HITCH_MS = 100.0` -- all named constants in
`hitch_report.py`), wired it into `title_verdict.py`, and left
`hitch_allowance` unset everywhere. That means a FRESH judge() run on any of
the four bolded titles' existing captures would newly report `pass: false`
with reason "hitches" (existing `verdict.json` files are not retroactively
rejudged -- title_verdict.py never does that, see CONFIRMATION LENGTH in its
module doc). This is a deliberate, visible consequence, not a bug: it is the
owner's numbers meeting real data, named instead of hidden. The three ways
to close it are all owner calls, not mine: (a) a fresh, valid Sonic Heroes
confirmation (post route-rewrite) might show numbers big enough to justify
the bars as-is and the four titles get `hitch_allowance`; (b) the bars get
revised once there is a real positive example; (c) Azurik/KOF/Kabuki
Warriors/THPS2x get `hitch_allowance` now, on the same "known, accepted
stall" reasoning that already gave two of them `confirmation_s = 1200`.

## WHOLE-WINDOW LIVENESS (part 3)

### Why not a plain frame-to-frame diff

The brief's own suggestion ("count `shot play` frames whose perceptual
difference from the previous is below a small bound") does not separate the
two real false-pass cases from real gameplay. Measured on
`route-frames/*-play.png` (grayscale, consecutive pairs, mean abs diff):

| case | consecutive-frame mean diff |
|---|---|
| Super Monkey Ball (566484, Stage Select, must FAIL) | 0.106 |
| Crimson Skies (confirmed Playable, must PASS) | 0.087 |
| Sonic Heroes (1078702, frozen pause, must FAIL) | 0.0004 |

Super Monkey Ball's Stage Select has an animated background (flowing
water, an idle character) and ranks ABOVE a real gameplay capture on plain
frame-to-frame diff -- a naive bound would pass the menu and could fail real
gameplay. Visual check (`172723-play.png` vs `173301-play.png`, the first
and a mid-window frame): same "Stage Select / World 1 Jungle Island" screen,
camera and selection unchanged, 40 s apart.

### What does separate them: drift from the window's OWN FIRST FRAME

`static_window()` downsamples each post-mark route-frame to 160x90 grayscale
and asks: what fraction of pixels never move more than 10/255 from their
value in the FIRST sampled frame, across every frame in the window
(`frozen_frac`)? A looping menu animation returns near its own starting
composition the whole time; real gameplay's camera and HUD drift the whole
frame over a long window.

| case | frozen_frac | n frames | verdict |
|---|---|---|---|
| Sonic Heroes (1078702) | 0.99 | 66 | FAIL (true freeze) |
| Super Monkey Ball (566484) | 0.32 | 65 | FAIL (looping menu) |
| Crimson Skies (confirmed Playable) | 0.027 | 5 | PASS |

Bar set at `FROZEN_FRAC_BAR = 0.20`, clearly between 0.32 and 0.027 with
both required cases on the correct side. **Both of the brief's required
validations hold**: 566484 FAILs, a confirmed-Playable run PASSes.

### Coverage gap, said plainly

Most Playable-confirmation routes take NO periodic post-mark screenshot
(`route-frames` only holds one-off setup shots before the mark, or nothing
at all) -- of the 12 confirmed titles, only Crimson Skies (5 frames) and the
two FAIL cases had enough (`FROZEN_MIN_FRAMES = 3`) post-mark frames to
judge. `static_window()` reports `measured: false` and does not fail in
that case (absence of route-frames says nothing about whether the title
played; it is a route-authoring choice, `--frames-every`). This means the
liveness check, as specified, can only catch a menu-loop bug on a route that
already takes periodic shots during play -- it is still worth having (it
catches the two cases the owner already found), but it does not retroactively
audit the other ten Playable titles' windows for the same bug. That audit
would need those routes to add periodic `shot play` calls, which is a
routes change, out of this brief's scope (no device work).

### The second Castlevania result

`1790902028-titleroutes-1005086` also scored `pass: true` /
`rating_candidate: Playable` and has a route ending right at `mark gameplay`
with no post-mark periodic frames at all (0, not just <3) -- `static_window`
reads `measured: false` for it, same as most of the other ten. It is not one
of the brief's two required validation targets (only 566484 is named for
FAIL), so it is left as `measured: false`, named here rather than silently
passed over.

## VERIFICATION

- `SELFTEST_ONLY="99-hitch-report" bash docs/testing/jobs/selftest.sh` --
  12 passed, 0 failed.
- `SELFTEST_ONLY="89-title-verdict 99-verdict-10min 99-thermal-pause
  99-default-regimen 99-power-per-frame 99-display-covered 66-status-titles
  99-status-fullwindow" bash docs/testing/jobs/selftest.sh` -- 184 passed,
  1 failed on first run (`99-power-per-frame.sh`'s sign mutant, see WHAT
  EXISTS NOW above for the fix), 185/185 after the fix.
- `SELFTEST_ONLY="60-status 62-status-freshness 63-status-lanes
  64-status-html 65-status-objective 67-status-measured 94-arms-verdict-scope
  99-status-degraded 99-status-escalation-items 99-status-escalations
  99-title-state"` -- 199 passed, 1 failed: `60-status.sh`'s "status shows
  the arms refusal in full" needs the fixture `40-arms-refusal.sh` populates
  under `$HAKUX_WORK/arms/skipped/` (60-status.sh's own header comment says
  so: "runs after them"). My `SELFTEST_ONLY` list cherry-picked fragments and
  skipped 10/20/30/40/50-arms-*, so the dependency was never built -- a gap
  in how I invoked the suite, not a regression. Confirmed by re-running with
  `10-arms-list 20-arms-queue 30-arms-error 40-arms-refusal 50-arms-requeue
  60-status`: all pass.
- `python3 -c "import ast; ast.parse(...)"` on both changed/new .py files,
  and `tomllib.load()` on targets.toml: all OK.
- Whole selftest.sh (18-25 min) was not run end to end this session; the
  fragments above cover every file this change touches or could plausibly
  break (title_verdict.py's own import, anything that copies it, status
  pages that read verdict.json's existing fields). [[ci-is-finite]]

## What the next lane/session should not repeat

- Don't recompute the survey table by hand from logcat -- `hitch_report.py
  <dir>` on each of the 13 result dirs above reproduces it in seconds.
- Don't try to make the bars "work" by tuning HITCHES_PER_MIN_BAR/
  BIG_HITCH_MS downward or upward until the 12 confirmed titles stop
  failing -- that is curve-fitting the thresholds to the ONLY available
  (invalid) negative example, which the brief explicitly asked not to do.
  Wait for a valid Sonic Heroes capture, or get an explicit owner ruling on
  the four bolded titles.
- The three `scratch_*.py` files in the worktree root are this session's
  exploration, kept for anyone re-deriving the frozen_frac numbers; they are
  not wired into anything and can be deleted once the PR is reviewed.
