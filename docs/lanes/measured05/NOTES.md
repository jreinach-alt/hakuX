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

## Why attempt 1 did not finish

The first session built Measured, the bars, the chart and the one-handheld
counts (a6e1b59e66), then took Addendum 1 (the Copied mark) and ended with it
uncommitted in the worktree, before the hostops addendum and Addendum 2 arrived.
Attempt 2 committed that work, merged origin/master (9ca5329a86), and did the rest.

## Attempt 2: Copied, the runaway, and the fps column

- **Copied (Addendum 1).** A tick on ANY handheld; the hover names the Thor, the
  Nova, or both. No half mark; PIPE, the legend and the source line say
  "copied to a handheld". The Ghoulies gate's "both handhelds" is untouched.
- **The runaway (hostops 22:39).** `md_to_html`'s paragraph branch excluded lines
  starting with `|`, so a `|` line with no separator after it (a table header as
  the last line, a STATUS.md cut mid-write) matched no branch, `i` never moved,
  and `out` grew by `<p></p>` forever: the 41 min, 5.2 GB tick. The paragraph now
  always consumes its first line. status.sh runs the build under
  `timeout ${STATUS_BUILD_TIMEOUT:-120}` and writes the timeout into
  status_html.err. A truncated facts.tsv or lanes.json does NOT hang master's
  renderer (both exit 0); a STATUS.md cut just before its last table's separator
  (a below-the-fold table) does: master exit 124 at a 20-30 s bound, branch exit 0.
- **The fps column (Addendum 2).** One row per title: title (tap for detail) with
  the next step under it | status | fps | four marks. The fps cell: the median
  large, right-aligned, tabular (green 30+, amber 25-29.9, red under 25); "N% at
  30+" under it; a small line "Thor · 09-26 · MAX, soak / hand-reviewed"; another
  handheld's median under that. "not measured" when there is none. Soaks now
  carry a share (samples at 30+ in 90-240 s, `_soak_read`); cache entries without
  one are re-read once. Default order: measured first by fps, highest first, then
  status order. A radio control (fps / status / A-Z) and a "Measured only" box,
  inline JS; with scripts off the server order stands. The not-copied fold holds
  only unmeasured titles.
- lane.titles05's `assert_titles.py` `lines` and `order` checks encoded the
  two-row layout (title across the row, fps in the status cell, red first). They
  now assert the one-row layout (every word fits its column at 360 and 400 px;
  the median fits; one `<tr>` per title) and measured-first-by-fps then status.
  A title can now take 3-5 lines on a phone: the owner asked for one row with a
  dedicated fps column, and at 400 px that costs title width.

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

### Attempt 2 (origin/master 9ca5329a86 vs this branch)

master's renderer (`.scratch-master.sh`: git archive of origin/master's jobs dir):

```
FAIL copied: no row whose Copied hover names exactly one handheld; half marks in Copied: ['50 Cent: Bulletproof', 'Black', 'Bruce Lee: Quest of the Dragon']; the page still says 'copied to both handhelds' or 'one handheld of two'
FAIL fpscol: 50 Cent: Bulletproof: 2 rows; 50 Cent: Bulletproof: fps in the status cell '   blocked  no fps yet '; Black: 2 rows; ...
FAIL lines    ... no fixed layout: table.tt needs table-layout:fixed and a colgroup with pixel [widths, fps its own]
FAIL order    measured titles first, highest fps first; then red, ... -- no measured rows or no unmeasured rows
build on STATUS.md cut before its last table's separator: exit 124 (killed by the bound)
md_to_html("## x\n| a | b |"): exit 124 at a 5 s bound
```

this branch: proof.sh 7 PASS (glance order bar chart json copied fpscol),
assert_titles.py 12 PASS, the cut STATUS.md build exit 0. Fragments 60-67:
171 passed, 1 failed; the failure is 60's arms-refusal check, which needs the
state fragments 10-50 leave (the same on master, above).

## Live (status.sh --print, STATUS_OUT_DIR in the worktree, 2026-09-26 22:22 PDT)

Measured 30 / 145, Benchmarked 0 / 145, Playable 0 / 50. 7 titles from the
backfill, 1 from a verdict (Black), the rest from soaks; the first reading is
Galleon's soak in mid-September. Screenshots at 400 px (attempt 2, 22:55 PDT): `screenshots/live-400-{light,dark}-top.png`
(the top line, the bars, the chart) and `screenshots/live-400-{light,dark}-table.png`
(the first screen of the table with the fps column).

## For the next lane

- A markdown loop whose branches can all decline a line must still consume it.
  Test status_html.py on a cut-off input, not just a well-formed one.

- A soak counts on any gfps in 90-240 s, including a menu that logs gfps.
  Reading gameplay from a soak needs the route's frames; the brief's rule (and
  the Ghoulies gate's) is the window, and that is what is counted.
- Do not put `now` into anything the page's content key covers.
- The row dict already has a `measured` key (the list of readings); the flag is
  `fps_read`. A duplicate key in the literal silently wins.
