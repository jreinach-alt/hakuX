# lane.measured05: Measured N / 145 on the status page (#433)

The owner, 2026-09-26 ~21:55 PDT: show "Measured x / 145" at the top and chart it in
"How close is 0.5?", so the titles with an fps reading show as progress.

## What changed

- `status_html.py` `titles05()`: a title is **Measured** when it has at least one
  gameplay-window fps reading, on either handheld, at any build and mode. Sources:
  the pass-1 backfill's rows with `fps_median`, every `verdict.json` with
  `fps_window_median`, and every finished soak whose request names the title and
  whose logcat has hakuX-perf gfps in 90-240 s from the first perf line
  (`_soak_median`, the Ghoulies gate's own reader). Titles dedupe as the table
  does: the registry's ISO names and title ids, else `_iso_name()` of the file.
  Each row carries `fps_read`, `measured_at` (its FIRST reading: the result's
  DONE mtime, the verdict's mtime, or the backfill's `source_utc`) and
  `soak_read` (its newest soak).
- A soak reading never changes a title's stage. It enters the stage logic only
  for a title with no verdict and no backfill row; otherwise the fps cell falls
  back to it when the stage's own run had no fps (e.g. 50 Cent: pass 1 never
  reached gameplay, a later soak read 59 gfps; it stays blocked, and shows 59).
- Soak medians are cached in `$S/soak-gfps.json` by result id (a DONE result
  does not change). Uncached, the live 344 titled results take ~22 s; cached,
  the tick pays only for new results.
- The 0.5 at-a-glance line: `0.5: Measured N / 145 · Benchmarked M / 145 · Playable K / 50`.
- "How close": a Measured bar first (blue), then Benchmarked (amber) and Playable
  (green); under them one inline SVG chart, cumulative titles over time, three
  step lines told apart by colour, dash (solid / 7-4 / 2-3) and an end label;
  a dotted line at 145 ("target 145") and a marker at 50 ("50 Playable"). X is
  Pacific (localtime.tz()). The chart never reads the clock: the axis ends at
  the newest point, so a tick with nothing new keeps the same content key
  (fragment 64 caught the first version, which ended at `now` and would have
  republished every tick).
- `status.json`: `first.titles.series` = `{measured, benchmarked, playable}`,
  each `[[epoch, cumulative n], ...]`; `counts.measured`.
- One handheld is enough (owner 18:10 PDT, #433 comment 5851512534):
  `release-0.5.toml` `benchmark_copies = 1` and its comment; the code default is
  1; the Copied mark is a tick on one handheld; `PIPE` text and the legend no
  longer say "both". lane.titles05's `assert_titles.py` pipe check expected ½
  for a one-handheld title; it now expects a tick.

## Proof

`docs/lanes/measured05/fixture/`: `render.sh` renders lane.titles05's fixture
plus four soaks (`soaks.py`): a title no registry names (measured), a registry
title on both handhelds (one title), and a soak whose gfps stop at 60 s (NOT
measured). `soaks.py` writes `measured.json`, the expected titles, from the
inputs alone (13). `proof.sh <jobs dir> <out>` prints each check.

master's renderer (f805f978ad, a detached worktree):

```
render exit 0
FAIL glance: no '0.5: Measured N / 145 · Benchmarked M / 145 · Playable K / 50' in:    0.5 : Benchmarked 3 / 145, Playable 1 / 50; gate no candidate is cut yet, ...
FAIL order: no counts
FAIL bar: [('Benchmarked', '3', '145'), ('Playable', '1', '50')]
FAIL chart: no <svg class="chart"> under the bars
FAIL json: measured []
```

this branch:

```
render exit 0
PASS glance: Measured (13, 145), want (13, 145); titles ['007: Agent Under Fire', '25 to Life', 'Blinx 2: ...', 'Blinx: The Time Sweeper', 'Crimson Skies: High Road to Revenge', 'Dead or Alive 1 Ultimate', 'Forza Motorsport', 'Zz Green', 'Zz Orange', 'Zz Purple', 'Zz Red', 'Zz Soak Only', 'Zz Yellow']
PASS order: 13, 3, 1
PASS bar: [('Measured', '13', '145'), ('Benchmarked', '3', '145'), ('Playable', '1', '50')]
PASS chart: ends {'measured': '13', 'benchmarked': '3', 'playable': '1'}, dashes ['', 'stroke-dasharray:7 4', 'stroke-dasharray:2 3']
PASS json: measured [[1790457873, 11], [1790461473, 12], [1790461533, 13]]
```

Fragments 60-67 (a scratch copy of selftest.sh sourcing only `6[0-7]-status*`):
branch 164 passed, 1 failed; master 157 passed, 1 failed. The one failure on
both is 60's "status shows the arms refusal in full", which reads state that
fragments 10-50 leave and the filtered run skips. The full selftest.sh hangs
in this sandbox at fragment 51 ("dispatch hardening E"), which this change does
not touch (not run on master here); CI runs the whole thing.

## Live (status.sh --print, STATUS_OUT_DIR in the worktree, 2026-09-26 22:22 PDT)

Measured 30 / 145, Benchmarked 0 / 145, Playable 0 / 50. 7 titles from the
backfill, 1 from a verdict (Black), the rest from soaks; the first reading is
Galleon's soak in mid-September. Screenshots at 400 px:
`screenshots/live-400-light.png`, `screenshots/live-400-dark.png`.

## For the next lane

- A soak counts on any gfps in 90-240 s, including a menu that logs gfps.
  Reading gameplay from a soak needs the route's frames; the brief's rule (and
  the Ghoulies gate's) is the window, and that is what is counted.
- Do not put `now` into anything the page's content key covers.
- The row dict already has a `measured` key (the list of readings); the flag is
  `fps_read`. A duplicate key in the literal silently wins.
