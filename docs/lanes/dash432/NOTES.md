# lane.dash432 notes

Issue #432, the "show 0.5 progress on the status page" half. Brief:
`briefs/dash432.md`. Before-state: `fixtures/1624/` (the host's copy of the
16:24 PDT build: status.json, lanes.json, facts.tsv, STATUS.md, index.html).

## 1. Map: each owner question to the code that rendered it (master @ 916c246260)

| # | owner question | rendered by | why it read wrong |
|---|---|---|---|
| 1 | "Nova says held" | `status.sh` lane heredoc, "Each handheld" block (~l.428): `state = "held"`, `detail = cell(why, 120)`; `status_html.py render()` puts `state` in the tile's big line and `detail` in a one-line ellipsised `.d` | the holder, purpose and end time live only in the ellipsised detail; the tile's value is the bare word "held" |
| 2 | "needs attention has 5 items, some in flight" | heredoc `state_of()` returns `blocked: #N <blocked_on>` whenever an owned issue has any `blocked_on`; `build()` turns every `blocked` row into an attention item; `queued_old` (runs waiting > 60 min) becomes a `queue` item | the board writes `dispatch_state = blocked` + `blocked_on = "IN FLIGHT ..."` on every owned issue so it will not start a second lane; the page parsed that word as "stuck" |
| 2b | escalations | `status.sh` facts block greps `^\s*[-*] ` in `host-tools/escalations.md` | the host writes one decision per line with no bullet, so the six open decisions at 16:24 counted as ZERO and never reached the page |
| 3 | "blocked until after 0.5" | same `state_of()` path (`blocked_on = "after 0.5: ..."`) | parked-by-policy work is an attention row |
| 4 | "5 of 24 lanes" | `n_lanes` = active `hakux-lane-*` units; the "Lanes" tile prints `N of LANE_MAX running` | LANE_MAX is a ceiling; a lane whose device test is queued has no unit (handback resumes it) and is not counted; the page shows no queue constraint |
| 5 | xbox, remote not tracked | heredoc skips `xbox`/`remote` in the lane loop and prints them as two bullets below the table, 110-char first lines | they are not rows of the table and never on the first screen |
| 6 | "last session ended never", cut-off comments | lane table columns `last session ended` (`hm(ts) if ts else "never"`) and `it said` = `cell(said)`, 90 chars of index.tsv's 120-char head | "never" for timer jobs, first sessions and standing rows alike; every summary truncated mid-word; timers, live, parked and ~20 retired rows in one table |
| 7 | 0.5 target / titles / fps | `status.sh` `fact release_titles_target ${STATUS_RELEASE_TITLES:-145}`; `status_html.py release05()` counts only `results/*/verdict.json`; `panel_lines()` prints `N of 145` | pass 1 (#397) wrote no verdict.json, so "Tested 0 of 145" beside 17 measured titles; 145 is the per-minor quota from 0.6 on; no title and no fps on the page |

Other outputs that must survive: `STATUS.md` (the #107 legacy comment and
the details below the fold), `status.json`, `lanes.json`, `idle-lanes` (the
#107 body header), the gh-pages publish and its content key.

## 2. Design

`status_html.py gather()` computes the first screen from facts; `status.sh`'s
lane block is now one call, `status_html.py lanes`, which writes `lanes.json`
(old keys kept: `idle` = the stranded lanes, `blocked` = [], `fold_stuck`,
`queued_old`, `devices`, `prs_ok`, `terr_ok`; new: `first`), `idle-lanes`
and the lane sections of STATUS.md. `build()` folds `first` into
`status.json` (schema 2) and `render()` lays out: at a glance (one line per
question), then Q1..Q4, then the fold and the old details.

| question | what answers it | from |
|---|---|---|
| Q1 target | one sentence + who decided; the numeric target or "not set yet" | `docs/lanes/dash432/release-0.5.toml` (STATUS_RELEASE_CONF overrides) |
| Q1 gate | per device: median, n, soak id, ref, age; verdict against the candidate (`release_candidate_sha` fact); open release blockers | status.sh's `r05gate` rows (unchanged logic) |
| Q1 titles | one row per title: `already-on-handhelds.json` + every `logs/titlepipe/batch-*.tsv` push + backfill titles; measurements from `results/*/verdict.json`, else `pass1-backfill.json`; counts computed from the rows | `titles05()` |
| Q1 levers | words (issue title), owner lane (territory), effect: board close note / last `[job.arms] VERDICT` on its PR / "not measured yet" + why; expected = the board's `impact_basis` | `_levers()` |
| Q2 lanes | one state per lane, in order: running (unit) > parked (every issue labelled `blocked:after-0.5`) > waiting on owner (`decision-needed`) > waiting on a file (the CURRENT `blocked_on` names a path another live lane holds in territory.toml AND names that lane) > finished (PR merged) > waiting on device (queued/running requests, position and estimated start from a drain simulation) > in a device session (it owns a hold) > waiting on audit/fold (ready PR + label) > stranded | `gather()` |
| Q2 sessions | lane.xbox: `hakux-xbox-titlepush` unit + batch tsv progress + its last `[lane.xbox]` comment; lane.remote: its last `` `[lane.remote]` `` comment and whether the host answered (attention.sh's rule) | comments, systemctl |
| Q2 latest result | `first_sentence()` of the last session's JSON `result`; from the 120-char index head only up to a sentence stop, else nothing | logs/lane |
| Q2 finished / automation | retired rows + merged lanes since local midnight (or 6 h); timers with last run (timer LAST or the job's own tick log), next run, last outcome | territory, systemctl, logs/<job> |
| Q3 | escalations.md lines whole (the old grep wanted a `- ` bullet: 6 open read as 0), `decision-needed` issues, stranded lanes, hold past its end, run past 2x expected, device idle >5 min with runnable work, gate failing on the candidate, recovery needs-hands for this boot (deduplicated against a decision it repeats), CI red / failed timer / page lapse / stuck fold | |
| Q4 | device: running (purpose, requester, since = `.owner` mtime) / in use by (hold file's first word, `.why` text, start = mtime, end = "until HH:MM" or start + "~N min") / idle (since the last DONE); queue counts, 0.5 share (requester's lane owns a `0.5` issue), oldest 0.5 wait, drain, idle tier, constraint; console meter + push | dispatch dirs |

Estimates are labelled as such: a title run = its seconds + 8 min, a suite run
= 5 min + 1.5 min per suite, per run.

Phone first: the lane, finished and title tables become one compact block per
row under 640 px; the board's free text is a collapsed "board note"; the
finished list shows six rows and folds the rest (all still on the page).
Untested titles are listed by device in one paragraph, so every title is on
the page without 33 empty rows.

## 3. The fixture

`fixtures/1624/` is the host's copy of the 16:24 build (outputs). A renderer
cannot be re-run on outputs, so `fixtures/capture_1624.py` copied the SOURCES
(`fixtures/1624/src/`: board files at origin/board e62d272ea7, the dispatch
queue/holds/results, escalations.md, lane logs, titlepipe records, gh answers,
systemd). The capture ran at 16:28-16:38; it reconstructs 16:24 where the
state had moved (the Nova hold lifted at 16:31, a run claimed after it, the
Thor hold lifted before 16:41) and drops anything queued after NOW. Check: 23
queued + 99 idle tier, the same request ids as the 16:24 lanes.json.
`systemd.json` is written by hand from STATUS.md (units, timers).
`run_fixture.sh <jobs dir> <out>` renders it offline with replayed gh /
systemctl / adb and `STATUS_NOW` pinned; `old_renderer.sh` extracts the base's
renderer; `proof.sh` runs both and `assert_objective.py` on each.

Do not re-run `capture_1624.py` without `BOARD_ONLY=1`: the host has moved
on, and it would overwrite the 16:24 queue with the current one (it did
once; restored from git).

## 4. Proof

`bash docs/lanes/dash432/fixtures/proof.sh <scratch>`, 2026-09-26 ~17:10 PDT:

```
== the old renderer (916c246260)
FAIL held     -- a device state reads a bare 'held' (2)
FAIL person   -- lists blinx372d, flatlm13, forza414, fmv303c, queued over
FAIL sessions -- no row for lane.xbox, lane.remote
FAIL never    -- 0 on the first screen, 4 cells reading 'never'
FAIL results  -- 32 of 33 cut: nce and fan before the app starts and... | ...
FAIL titles   -- no 0.5 title table
FAIL no145    -- says 'of 145'
== the new renderer
PASS held     -- Nova: in use by host: A/B simpleperf profile, ... Since 16:19, until 16:39 (start + stated duration); Thor: in use by lane.titlestate: ... Since 16:13, until 16:41
PASS person   -- 7 items: 6 escalations and lane.perfregimen
PASS sessions -- rows for lane.xbox and lane.remote
PASS never    -- absent
PASS results  -- 45 cells, all whole
PASS titles   -- counts (50, 16, 7, 0), rows say (50, 16, 7, 0)
PASS no145    -- absent
```

"never": a PR title quoted below the fold says "never claim a number..." (PR
#446), so the check is the first screen plus any cell whose whole value is
"never" -- which is what the owner read.

`selftest.d/65-status-objective.sh` runs the same seven on this tree plus
file-wait, parked, finished and lanes.json/status.json shape checks.

Fragments changed, and why (each file's header says so too):
- 63: the vocabulary replaced IDLE/blocked; blockx (blocked only in words,
  nothing in flight) is now stranded with the words as a note; jobx is an
  Automation row; xbox/remote are table rows; the hostops tick is an
  Automation row; the fixture's index head gained a full stop.
- 64: the fixture JSON carries `first`; the order check is glance < Q1 < Q2
  < Q3 < Q4 < details; the attention item is `action` with `who`; the key's
  moving part is `first.queue`; "queued over 60 min" is no longer an alarm;
  the panel has no "of 145".
- 60, 62: unchanged, pass.

## 5. Found on the live render (status.sh --print, fixtures/live_print.sh)

- A hold file's first line can be a sentence ("lane.xbox title push 827868
  <stamp>"): the holder is its first word.
- A claimed request keeps its queue-time mtime (the dispatcher moves it), so
  "running since" came out 3 h early and raised a false "past twice its
  expected time". The start is the `.owner` file's mtime.
- escalations.md changed between 16:24 and 17:00 (the owner proposed 145
  benchmarked / 50 Playable, pending confirmation). release-0.5.toml's
  `numeric_target` is where that lands once confirmed; it is still empty.

## 6. Next lane: do not repeat

- Do not parse `blocked_on` or `status_note` into a state. The one exception
  here (a file wait) needs the path to be held by another live lane in
  territory.toml AND that lane named in the same current `blocked_on`; the
  looser rule turned #13's history (vk/draw.c) into a wait.
- The Windows Chrome under /mnt/c does not run from a lane session (interop
  is blocked silently). `npx @puppeteer/browsers install
  chrome-headless-shell@stable --path <scratch>` works; `fixtures/shoot.sh`
  takes it as CHROME.
- Run fragments 60-65 alone with a copy of selftest.sh whose loop sources
  only `$FRAGS` (30 s instead of ~35 min for the whole suite).
