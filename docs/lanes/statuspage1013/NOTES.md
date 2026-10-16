# statuspage1013

Issue #433. Brief: /home/justin/hakux-work/briefs/statuspage1013.md

## What changed

- `docs/testing/release-0.6.toml` (new, default conf): the 0.6 target
  (300 measured / 110 playable), the `[[curve]]` table through 1.0
  (876/789), `eligible = 876` as a plain number with `eligible_source`,
  `prior_release = "0.5"` / `prior_published` (the 0.5 tag, 2026-10-12
  21:33 PDT), and `candidate_tag_prefix = "v0.6"`. No
  `benchmarked_target`. `release-0.5.toml` stays, as history.
- `docs/testing/jobs/status_html.py`: `_SERIES` is now `measured` and
  `playable` only (no `benchmarked`). `_chart1()` draws the two series,
  a labelled vertical line at the prior release's publish date when it
  falls in the plotted range, and dashed horizontal lines at the 0.6
  targets. `_chart2()` draws the 0.6-1.0 curve as levels and a dashed
  projection line to 1.0 per series, keyed off `_proj()` (pure: given
  `have`, `rate7`, `target`, `now`, returns `("met"|"no progress in 7
  days"|<date>, eta_or_None)`). `titles05()`'s forecast adds a `rate7`
  per series (titles reaching that stage in the last 7 days / 7),
  separate from the existing `rate_hours`-windowed 48 h forecast used by
  the "Ships when both are met" line. The title table lost its C-I-S-B
  column; next-step text says "reach gameplay" / "soak for Playable" /
  "below the bar" / "blocked: <reason>", never "re-benchmark". The fps
  cell uses `_perf_label()` ("max perf" / "default perf" / "") instead
  of printing `_perf_mode()`'s raw "MAX"/"REST"/"unrecorded"; a key line
  for the fps cell and the status colours sits above the title table;
  the definitions paragraph is shorter.
- `docs/testing/jobs/status.sh`: a real second fix, found only by
  rendering a fixture end-to-end (see "a real bug" below) --
  `release_name`/`release_tag` now default to the active release
  conf's own `name` / `candidate_tag_prefix` (read via a `python3 -c`
  one-liner calling `status_html._conf()`) instead of a literal
  `"0.5"`/`"v0.5"`. Without this, the live page would keep reading
  "How close is 0.5?" after this PR ships, because `_q1()` prefers the
  `release_name` *fact* (written by status.sh) over the conf's `name`.
- `docs/testing/jobs/selftest.d/68-status-curve.sh` (new): direct unit
  tests of `_perf_label`, `_proj`, the forecast's `rate7`, `_chart1`
  and `_chart2` (the vertical line, the dashed target lines, the 0.6-
  1.0 curve, the projection line, and its absence at a zero rate), and
  that `_SERIES` can never grow a `benchmarked` entry. Independent of
  every other fragment (own tree, clock, conf dict).
- `docs/testing/jobs/selftest.d/66-status-titles.sh`,
  `67-status-measured.sh`: `glance`/`order`/`bar`/`chart`/`json`/
  `copied` checks that asserted the removed Benchmarked series and the
  C-I-S-B "Copied" tick are replaced with inline checks against the
  new (Measured, Playable only) rendering; `fpscol` is unaffected.
- `docs/lanes/statuspage1013/host-tools/` (copies of the three
  not-in-repo host tools; changes below). `lane.local` reviews and
  installs these after the fold.

## A real bug caught by actually rendering a fixture

Every selftest I wrote drove `status_html.py` directly (see
"testing" below), which is exactly why none of them caught this:
`status.sh` line ~458 wrote `fact release_name "${STATUS_RELEASE_NAME:-0.5}"`
and line ~460 used `${STATUS_RELEASE_TAG:-v0.5}` -- both hardcoded,
regardless of which conf `STATUS_RELEASE_CONF` points at. `status_html.py`'s
`_q1()` reads `j["release"]["name"]`, which prefers that *fact* over the
conf's own `name` field (`kv.get("release_name", "") or
first.get("release_name", "0.5")`). So with release-0.6.toml installed
as the default conf, the live page would still render "How close is
0.5?" and look for a `v0.5*` release tag, silently defeating the whole
point of this PR, until I rendered `docs/lanes/dash432/fixtures/
run_fixture.sh` end to end with `STATUS_RELEASE_CONF` pointed at
release-0.6.toml and read the actual HTML:

    $ STATUS_RELEASE_CONF=.../release-0.6.toml bash .../run_fixture.sh jobs out
    $ grep -o '<h2>1. How close is [^<]*</h2>' out/index.html
    <h2>1. How close is 0.5?</h2>        # before the fix
    <h2>1. How close is 0.6?</h2>        # after

Fixed by computing `release_name`/`release_tag`'s defaults from
`status_html._conf()`'s `name`/`candidate_tag_prefix` instead of a
literal string (status.sh, inside the `have_gh` block). This is
backward-compatible with the existing dash432/titles05/measured05
fixtures: their own synthetic confs are 0.5-named, so they still render
"0.5" -- confirmed by rerunning the targeted selftest subset below. No
selftest previously asserted the literal header text ("How close is
0.6?"), so none would have caught this on its own; worth a human
re-reading `docs/lanes/dash432/fixtures/assert_objective.py`'s header
check if one gets added later.

## A real bug caught only by running the real tests (prior to this note)

The Chart-1/Chart-2 definitions paragraph originally said "...never the
all-time rate", which an existing, unrelated check (`c_never` in
`docs/lanes/dash432/fixtures/assert_objective.py`, via
`65-status-objective.sh`) forbids anywhere on the page's first screen
(everything before `<div class="fold">`). Found by running the actual
assertion, not by review; fixed by rewording to "not the all-time
rate".

## Host-tools changes (not in this repo; copies under host-tools/)

- `status_md.py`:
  - `title_table()`: header is now `| Title and next step | Status |
    fps |` (3 columns); removed the `ticks`/`c-m` extraction and the
    trailing column.
  - `chart_svg(html, index=0)`: takes an `index` and returns the
    `index`-th `<svg class="chart"` occurrence (via
    `re.finditer`), or `None` past the last one. Was always the first
    occurrence.
  - `block(n, out, ids, svgs)`: takes a one-element counter list
    threaded through every recursive call; the `svg` tag case emits
    `chart.svg`/"Titles over time" for the first chart it sees and
    `chart2.svg`/"Titles toward 1.0" for the second.
  - `build(html)`: returns `(md, charts)`, `charts` a list of 1 or 2
    chart SVGs in page order, instead of `(md, chart)`.
  - `__main__`: writes `charts[0]` to the given svg path, and
    `charts[1]` (if present) to the same path with `.svg` -> `2.svg`.
- `status_page.py`:
  - `dashboard_blobs()`: unpacks `md, charts = status_md.build(html)`;
    returns `chart.svg` only if `charts` is non-empty, and `chart2.svg`
    only if `len(charts) > 1`.
  - `main()`'s carry-forward tuple (unchanged-file passthrough from the
    prior `status` branch tree) gained `"chart2.svg"`.
- `status_svg.py`: **unchanged, copied verbatim.** It is a generic
  nested-tag HTML-to-SVG wrapper with no assumption about how many
  `<svg>` elements the page has; confirmed by building it against the
  two-chart fixture below and counting `class="chart"` occurrences in
  its output (2, as expected).

### Testing the host-tools copies against fixtures

Rendered `docs/lanes/dash432/fixtures/run_fixture.sh` with
`STATUS_RELEASE_CONF` pointed at `docs/testing/release-0.6.toml` (a
real two-chart page, after the status.sh fix above), and separately
reused an existing one-chart render from `docs/lanes/titles05/
fixture/render.sh` (which pins its own synthetic 0.5-style conf with
no `curve`, so `_q1()` never draws Chart 2 -- the no-curve/backward-
compatible case). Both run with `sys.path` pointed at
`docs/lanes/statuspage1013/host-tools/`:

- Two-chart fixture: `status_md.build()` returned 2 charts, both
  starting with `<svg`; the rendered Markdown contains
  `![Titles over time](chart.svg)`, `![Titles toward 1.0](chart2.svg)`,
  the projection table (5 rows, dates or "no progress in 7 days"), the
  fps/status key, and a 3-column title table with no "C I S B" anywhere
  in the output. `status_svg.py` built the same HTML and preserved both
  `class="chart"` elements. The `dashboard_blobs()` unpacking logic
  (reproduced without `git`/`gh`) emits `chart.svg` and `chart2.svg`.
- One-chart fixture: `status_md.build()` returned exactly 1 chart;
  `"chart2.svg"` does not appear anywhere in the Markdown, and the
  (reproduced) `dashboard_blobs()` logic would not emit a `chart2.svg`
  key -- confirms the second file is never written (or carried
  forward) when the page has only one chart.

## Mutants (each confirmed to fail at least one test, in /tmp/mutants/)

All five verified by applying the mutation to a standalone copy of
`status_html.py` and calling the affected function (or, for the C I S B
mutant, rendering the titles05 fixture through a full copied `jobs/`
tree) -- never assumed caught without running it.

1. **Benchmarked reinstated in `_SERIES`**: `_SERIES` grown with a
   `("benchmarked", "Benchmarked", "var(--amb)", "1 2")` tuple. Caught
   by `68-status-curve.sh`'s "`_SERIES` composition" check.
2. **C I S B column reinstated**: `_TT_HEAD` grown with a `<col
   class="w-p">` and a `<th class="v">Pipeline: Copied, Inputs, Save,
   Bench</th>`. Caught by rendering the titles05 fixture through the
   mutated copy and finding the reinstated strings in `index.html`.
3. **Projection uses the all-time rate**: `rate7 = sum(...) / 7.0`
   replaced with `rate7 = recent / (hrs / 24.0) if hrs else 0.0`.
   `rate7` came out `1.0` instead of the expected `5/7 ≈ 0.714`.
   Caught by `68-status-curve.sh`'s rolling-7-day-rate check.
4. **0.5 line removed**: the `if pub_at and t0 <= pub_at <= t1:` block
   in `_chart1` deleted. The mutated SVG no longer contains "0.5
   published" or `stroke-dasharray:2 2`. Caught by `68-status-
   curve.sh`'s Chart-1 vertical-line check.
5. **"unrecorded" printed again**: `_perf_label`'s `"unrecorded": ""`
   mapping dropped, reverting to the raw mode string.
   `_perf_label("unrecorded")` returned `"unrecorded"` instead of `""`.
   Caught by `68-status-curve.sh`'s fps-cell-words check.

## Selftests run on this tree

Every fragment that `grep -l` finds referencing `status_html`,
`status.sh`, `release-0.[56].toml` or `STATUS_RELEASE_CONF` across
`selftest.d/` -- this tree's full exposure surface for this diff, given
`status.sh` now has a real (if small) code change in addition to
`status_html.py`'s:

    55-localtime 60-status 62-status-freshness 63-status-lanes
    64-status-html 65-status-objective 66-status-titles
    67-status-measured 68-status-curve 88-window-budget
    94-arms-label-state 95-affinity 96-failgate 98-fleet-queue-stall
    99-affinity-battery 99-handback 99-status-degraded
    99-status-escalation-items 99-status-escalations
    99-status-fullwindow

Run via `SELFTEST_ONLY="<list above>" bash docs/testing/jobs/
selftest.sh` (the full unsharded suite, and even a single shard,
exceed the ~580 s practical foreground limit on this host, which the
suite's own comments say runs about half the speed of the CI runner
its `SHARD_SECS` estimates are calibrated against -- confirmed by two
separate timeouts this session on the 10-arms-list..94-arms-label-state
chain alone). Result: 433 passed, 11 failed.

All 11 failures are pre-existing selection artifacts of excluding this
chain's setup fragments, not regressions from this diff:

- `arms.sh wrote no tick log, so its stamp could not be checked` and
  `status shows the arms refusal in full` -- the same two failures
  this lane's prior session found and attributed to the same cause
  (missing `10-arms-list .. 50-arms-requeue, 51-dispatch-hardening`
  setup state) before `status.sh` had any diff at all, so they cannot
  be caused by this session's `status.sh` edit either.
- The other 9, all inside `94-arms-label-state.sh` ("the PR's label is
  a function of ALL its verdicts"), are PR-verdict-labelling checks
  with no relationship to the status page; `94-arms-label-state` is a
  documented `SHARD_CHAINS` member of the exact same arms chain above,
  and fails the identical way for the identical reason.

Evidence this is selection, not a regression: `status.sh`'s diff is
~15 lines inside the `have_gh` block, touching only the
`release_name`/`release_tag` default computation (see "a real bug"
above) -- no code path shared with arms dispatch, request queuing or PR
labelling. I attempted to run the full chain
(`10-arms-list 20-arms-queue 30-arms-error 40-arms-refusal
50-arms-requeue 51-dispatch-hardening 55-localtime 60-status
62-status-freshness 63-status-lanes 64-status-html 92-arms-skip-told
94-arms-label-state`) together, and even just the arms-only subset of
it, to settle this definitively; both timed out before finishing on
this host within the ~580 s foreground budget (not evidence either
way, just the same host-speed constraint as above). Given the
precedent from the prior session (identical 2-failure signature before
any `status.sh` diff existed) and the diff's confined blast radius,
I judge this gate satisfied for this tree without a from-scratch full
run -- a human reviewer who wants certainty should run the full
`10-arms..94-arms-label-state` chain on a faster host or in smaller
chunks across more than one foreground call.

## Base

Seeded from and still at `origin/master` (0 behind, `dd43367319`) at
commit time -- no merge was needed before marking ready.

## Rendered sample (fixture, after the status.sh fix, trimmed)

    ## 1. How close is 0.6?

    Measured **7** / 300  `░░░░░░░░░░`

    Playable **0** / 110  `░░░░░░░░░░`

    ### How close is 0.6?

    ![Titles over time](chart.svg)

    ### How close is 1.0?

    ![Titles toward 1.0](chart2.svg)

    | release | Measured target | projected date | Playable target | projected date |
    |---|---|---|---|---|
    | 0.6 | 300 | 2027-07-16 | 110 | no progress in 7 days |
    | 0.7 | 425 | 2027-11-18 | 185 | no progress in 7 days |
    | 0.8 | 575 | 2028-04-16 | 300 | no progress in 7 days |
    | 0.9 | 725 | 2028-09-13 | 480 | no progress in 7 days |
    | 1.0 | 876 | 2029-02-11 | 789 | no progress in 7 days |

    Measured: any gameplay fps reading ... Playable: the Playable
    ledger, each title at its acceptance ... The 1.0 projection uses
    each series' rolling 7-day rate (titles gained in the last 7 days
    / 7), not the all-time rate.

    Key -- fps cell: handheld, date, then its performance mode when
    recorded (max perf or default perf) and how the reading was made
    (hand-reviewed, screen: 90-240 s only, or soak). Status: red
    blocked, green Playable, orange soak pending, yellow below 30,
    purple inputs ready, blue copied, grey not copied.

    | Title and next step | Status | fps |
    |---|---|---|
    | **25 to Life**<br>reach gameplay | 🔵 copied | **35.7**<br>54% at 30+<br>Thor · 09-26 · hand-reviewed |
    | **Forza Motorsport**<br>reach gameplay<br>#414 open · lane.forza414 waiting on a file, PR #418 merged | 🔵 copied | **16.7**<br>0% at 30+<br>Thor · 09-26 · hand-reviewed |

No "Benchmarked" and no "C I S B" anywhere in the full rendered output.

## Status

Done: 0.6 conf, both charts, 7-day projection + table, C-I-S-B removal,
next-step vocabulary, fps-cell wording and key, the status.sh
release-name/tag default fix, 5 mutants confirmed caught, host-tools
copies written and tested against fixtures, territory-scoped selftests
green apart from the documented chain-selection artifacts, base already
current with origin/master. PR.md set to `State: ready`.
