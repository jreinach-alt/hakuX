# lane.titles05 notes

Issue #433: the status page's 0.5 section becomes a title table against the new goals
(145 benchmarked, 50 Playable). Base: master @ deb0903b51 (PR #448 folded). PR #458.

## What changed

- `docs/testing/release-0.5.toml` (moved from `docs/lanes/dash432/`): `target` with no date,
  `benchmarked_target = 145`, `playable_target = 50`, `decided` with the #433 comment link,
  `benchmark_copies = 2`, `rate_hours = 48`, and an explicit `[issues]` map (title name ->
  issue). `STATUS_RELEASE_CONF` still overrides it.
- `status_html.py`:
  - `titles05()` gives every title in the pipeline one stage from the fixed scale.
  - `_q1()` renders two progress bars (counted from the table), the forecast line, the
    target line, and the table. The table sorts red first, then from the most advanced
    stage down, and folds the "not copied" tail after 10 rows. The Ghoulies gate is one
    line and the levers are a small table.
  - Q4 carries the device watchdog (addendum).
- The table's columns: status (a chip AND a word), title (tap for the full detail), fps,
  pipeline marks, issue and in flight, next step. On a phone each row is a two-row CSS
  grid, and every cell is held to one line (nowrap, ellipsis). The fps provenance line
  (date, build, mode, hand-reviewed) shows on a desk and is inside the tap-to-open detail
  on a phone.

## The stage rule (what the counts mean)

A title's stage is the furthest step of the owner's definition that ALL earlier steps
reach. The owner's definition: copied to both handhelds, inputs programmed, save
extracted, fps measured at MAX on one handheld.

| stage | needs |
|---|---|
| not copied | nothing; the title is only staged (xiso manifest) or named in `[issues]` |
| copied | on a handheld: push logs, targets.toml `iso`, the backfill, a verdict, or already-on-handhelds.json (device not recorded, shown `?`) |
| inputs ready | both routes exist (`titlestate.route_path` for first-run and returning is not survey.route) AND a save is extracted (titlestate's store, or a device row naming a save) |
| below 30 / soak pending / Playable | the above, plus copied to `benchmark_copies` (2) handhelds, plus a measurement at MAX (perf_regimen.json's read-back) that reached gameplay. The fps bar is title_verdict.py's (share at 30+ >= 0.90). Soak pending: the bar is met. Playable: a `pass` verdict with `pass_kind = confirmation` on the measured device. |
| blocked | the chosen measurement crashed or hung, or could not reach gameplay on the title's own inputs (a pass-1 run on the generic route does not block a title that has routes since) |

So pass 1's 17 hand-reviewed titles count as **copied**, not benchmarked. Pass 1 was
not at a recorded MAX, and no title has a save extracted. Their fps still shows, marked
"unrecorded, hand-reviewed". Live at 19:06 PDT: 57 titles, 6 blocked, 49 copied,
2 not copied; **Benchmarked 0 / 145, Playable 0 / 50**; "no rate yet".

## Data read (read only)

- Titles: `titles/already-on-handhelds.json`, `logs/titlepipe/batch-*.tsv` (now with
  their title_id), targets.toml through `titlestate.targets()`, and the xiso
  `manifest.csv` (title_id and name only; its source paths are never read onto the page).
  I did not read the device listing (adb). It is not cheap from the status tick, and
  targets.toml's `iso` plus the push logs already say which device holds what.
- Inputs and saves: `titlestate.py`'s API only (`targets`, `load`, `store_saves`,
  `route_path`), with `TITLESTATE_DIR` defaulting to `$D/titlestate` as titlestate
  does.
- fps: `results/*/verdict.json`. #448 read `fps_median`, `share_30`, `judged_utc` and
  `perf_mode`, and title_verdict.py writes none of them. This reads
  `fps_window_median`, `fps_ok_share`, `reached_gameplay`, `crash`, `hang`,
  `pass_kind`, `route` and the file's mtime, plus `perf_regimen.json` beside it for
  MAX/REST.
- Issue state: `gh issue view N --json state` for each `[issues]` entry. Without an
  answer it falls back to the board's word, marked "board: ...". Lanes come from
  territory.toml's issues, with their Q2 state and queue position. Runs are the
  dispatch requests whose `title` (the ISO file) is the title's.
- Alarm: an open `[issues]` issue with no lane, no run and no tracker row is a "needs a
  person" item for the host. With a tracker row, the board owns it: the row says
  "nothing in flight" and raises no alarm.
- Watchdog: `$WORK/status/devwatch.json` (`STATUS_DEVWATCH` overrides it). Q4 shows the
  state word and since, and "last hour: N running, N hands-on, N waste
  (idle-waiting + held-idle + overdue)". If the file's `updated` is over 5 min old,
  that is an alarm for lane.local. A missing file is said in Q4, not alarmed: the
  16:24 fixture predates the watchdog.

## Proof

`docs/lanes/titles05/fixture/`:
- `synth.py` adds the synthetic registry to a copy of lane.dash432's 16:24 fixture:
  one title per stage (via targets.toml, the save store, verdict.json and
  perf_regimen.json), 12 staged titles, an unowned issue, and a stale devwatch.json.
- `render.sh` renders it with a given status.sh.
- `assert_titles.py` holds the 10 checks.
- `proof.sh` runs #448's renderer with #448's own config (before), then this tree's
  (after).

`bash docs/lanes/titles05/fixture/proof.sh <scratch>`, 2026-09-26 19:05 PDT:

```
== before  (deb0903b51, docs/lanes/dash432/release-0.5.toml)
FAIL word     every row carries exactly one status word from the scale ... -- no title rows (no table.tt)
FAIL counts   the header's Benchmarked and Playable counts equal the rows' ... -- no rows or no 'Benchmarked N / 145' and 'Playable M / 50' header
FAIL lines    no title renders as more than two lines at 400 px ... -- no title rows
FAIL target   the target line says 145 and 50 and carries no date -- no target line
FAIL nodate   '~2026-09-28' appears nowhere on the page -- present
FAIL fold     the 'not copied' tail folds after 10 rows, with its count -- no folded tail
FAIL order    red first, then green, orange, yellow, purple, blue, grey -- no title rows
FAIL forecast the header forecasts from the last 48 h rate ... -- no forecast line
FAIL flight   an issue shows its state and what is in flight ... -- missing an issue state, its lane, or the alarm
FAIL watch    Q4 carries the watchdog's word, since, the last hour ... -- watchdog lines or alarm missing
== after
PASS word     ... -- 68 rows, one word each; the 18 synthetic titles at their stages
PASS counts   ... -- header (3, 145, 1, 50), rows (3, 145, 1, 50)
PASS lines    ... -- 68 rows, each two lines
PASS target   ... -- 'Target: 0.5 ships when 145 titles are benchmarked and 50 of them are Playable on the Thor/Nova handhelds (#433).'
PASS nodate   ... -- absent
PASS fold     ... -- 2 folded (2 rows), 10 shown
PASS order    ... -- in order
PASS forecast ... -- Ships when both are met. At the last 48 h rate: about 2027-01-02.
PASS flight   ... -- issues, lanes and the alarm present
PASS watch    ... -- present
```

`selftest.d/66-status-titles.sh` runs the after side, plus a check that the default
config path is `docs/testing/release-0.5.toml` with 145 and 50. Fragments 60-66 pass
(202 checks). Run alone, 60 fails only "arms refusal in full", which reads state from
fragments 10-50. The full selftest is the preflight's.

Selftest edits outside 66:
- 65 passes `STATUS_RELEASE_CONF` (run_fixture.sh's default still names the old path).
- 65 drops #448's `titles`/`no145` checks, which asserted the replaced target, and keeps
  "pass 1's 17 titles are on the page".
- 64's gate string follows the gate's new one-line form.

Screenshots: `screenshots/before-448-phone.png` and `after-phone.png` (same fixture,
400 px), and `live-first-screen.png` (`status.sh --print` via
`docs/lanes/dash432/fixtures/live_print.sh`, 19:06 PDT).

## For the next lane

- The rows are only as good as the registry. Today no title has a save extracted, so
  nothing reaches "inputs ready" until lane.titlestate's harvest runs. That is correct,
  not a renderer bug.
- The status column must fit "soak pending" (8.2em at 13 px). At 6.4em the word was
  clipped. The word is the part that must never be lost.
- Headless Chrome for screenshots: lane.dash432's copy under
  `wt/dash432/.scratch/pup/` works as `CHROME` for `fixtures/shoot.sh`.
