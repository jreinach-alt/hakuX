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

## 2. Design (in progress)
