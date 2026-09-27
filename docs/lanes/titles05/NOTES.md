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

## Attempt 2 (2026-09-26, resumed)

Attempt 1 did not finish because it ended its session waiting on the full jobs
selftest, which it had started as a background task. The task died with the session,
so nothing ever reported back and the PR stayed in draft. The full selftest runs
longer than the Bash tool's 10-minute limit (a foreground run was cut off at 580 s
inside "the delivery channel" fragment). Attempt 2 merged origin/master (14 commits, clean),
re-ran `proof.sh` (the before run fails all 10 checks, the after run passes all 10, as above), and
ran the full selftest in this session, polling its log until it finished:
`selftest: 2055 passed, 0 failed`, exit 0.

## Attempt 3 (2026-09-26, 20:45-21:30 PDT): the owner's layout review

Why attempt 2 did not finish: it did. It merged master, re-ran the proof and the full
selftest (2055 passed), and marked #458 ready. Then, about 20:45 PDT, the owner looked
at the live page and asked for a revision: no fixed column widths, even "Thor" and
"Nova" wrapping, text cut off mid-word ("needs a gamepl..."), and pipeline marks
("TN ISB") that an outsider cannot read. lane.local took `fold-ready` off #458 and
resumed this lane with Addendum 2. This attempt is that revision, on master merged
again.

What changed:
- **Fixed columns.** `table.tt` is `table-layout:fixed` with a colgroup: a status/fps
  column (116 px on a phone, 170 px on a desk), a next-step column that takes the rest,
  and four 22 px pipeline columns (30 px on a desk). Each title is one `<tbody>` of two
  rows. Row 1 is the title (tap for detail), across the full width, so a title gets
  the most room. The longest live title, Blinx 2's 66 characters, is two lines at
  360 px. Row 2 is the status chip and word, then fps, then the next step with the
  issue and in-flight line under it, then the four marks.
- **Nothing is truncated.** The phone grid with `nowrap; overflow:hidden;
  text-overflow:ellipsis` is gone. Titles and next steps wrap inside their own column.
  Status words, fps figures and Thor/Nova are `nowrap` spans, each on its own line in
  the status column. A blocked row's blocker is shown in full under its next step.
  The next step is a few words ("fix the crash", not "fix: " plus the whole failure
  string). The queued or running request id moved from the next step to the in-flight
  line.
- **Pipeline marks.** There are four labelled mini-columns, Copied, Inputs, Save and
  Bench, with vertical headers. Each cell holds ✓, – or, for Copied, ½ (on one
  handheld of two). Save can read n/a (no profile step). Each cell carries a tooltip.
  A one-line legend sits above the table. No letter codes.
- **Inputs see lane.titleroutes' work.** `_registry` used to need both
  `<route>.first-run.route` and `.returning.route`. Now inputs are programmed when the
  title's own route exists in targets.toml: a single `routes/<route>.route` (no
  profile step, so no save is needed and Save reads n/a), or the first-run variant,
  which sets up the profile. A first-run route with no extracted save stays "copied",
  with "extract the profile save" as its next step. Live at 20:56 PDT: Kabuki
  Warriors, 007: Nightfire, DOA Xtreme Beach Volleyball, Fuzion Frenzy and Crimson
  Skies read **inputs ready**. GoldenEye: Rogue Agent (first-run only) and Burnout 3
  (both variants, no save in titlestate's store) read copied, with "extract the
  profile save". Live counts: 60 titles, 5 blocked, 5 inputs ready, 48 copied,
  2 not copied. Benchmarked 0 / 145, Playable 0 / 50.

Proof (`proof.sh` now runs two bases, and shoots at 400 and 360 px). The assertions
gained `nocut` (no ellipsis rule on the section's tables, no ellipsis glyph, and every
title and next step in status.json appears whole on the page) and `pipe` (the four
headers, the legend, ✓/–/½/n/a only, and the two titleroutes-shaped synthetic titles).
`lines` now reads the colgroup's pixel widths and word-wraps each title and next step
at 360 and 400 px, at a generous 0.58 em per glyph: at most two lines each. The
extracted old trees now include `docs/testing/titles`, `extract_results.py` and
`tools/make_xbox_hdd.py`. Without them the old renderer's titlestate import failed and
every title read "copied", so the "before" failures were a fixture artifact, not a
renderer difference.

```
== before-deb0903b51   (#448)          all 12 FAIL
== before-cd78454e6a   (#458, first cut)
FAIL word     -- Zz Purple Single Route reads 'copied', want 'inputs ready'
FAIL lines    -- no fixed layout: table.tt needs table-layout:fixed and a colgroup with pixel widths
FAIL nocut    -- ellipsis rule: table.tt td.l1,table.tt td.l2
FAIL pipe     -- headers []
PASS counts target nodate fold order forecast flight watch
== after                               all 12 PASS
```

Screenshots in `screenshots/`: `before-448-phone.png`, `before-458a-phone-{400,360}.png`,
`after-phone-{400,360}.png` (the same fixture), and `live-{400,360}.png` (`status.sh
--print` via `docs/lanes/dash432/fixtures/live_print.sh`, 20:56 PDT).

Not done: the owner's earlier remark that the lanes table (Q2, "Finished today") cuts
off the result of finished lanes. That is a different section and outside this
addendum's five items. The next status lane should take it.

## For the next lane

- The full `selftest.sh` takes over 10 minutes here. Run it where you can poll it in the
  same session. Never end a session waiting on it.

- The rows are only as good as the registry. Today no title has a save extracted, so
  nothing reaches "inputs ready" until lane.titlestate's harvest runs. That is correct,
  not a renderer bug.
- The status column must fit "soak pending" (8.2em at 13 px). At 6.4em the word was
  clipped. The word is the part that must never be lost.
- Headless Chrome for screenshots: lane.dash432's copy under
  `wt/dash432/.scratch/pup/` works as `CHROME` for `fixtures/shoot.sh`.
