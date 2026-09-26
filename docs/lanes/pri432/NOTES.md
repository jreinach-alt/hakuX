# lane.pri432 -- #432: 0.5 issues first, a release focus, a 0.5 status panel

Issue #432, release tracker #433. Harness only: no device, no arm.
`Prediction: none: no arm (harness only)`.

## Why attempt 1 did not finish

Attempt 1 wrote items 1 and 4 (board.sh, roles/board.md, the 97 legs) and
opened draft PR #438, then was stopped by the host to receive the brief's
addendum (item 4) mid-way through a full jobs selftest. Nothing was committed
past the notes stub; the edits sat uncommitted in the worktree, and the
selftest log was cut off. Attempt 2 committed them first, merged master, and
found that the old/new comparison had never been run, and that it showed a
problem (below).

## 1. Dispatch order (board.sh board_filter)

An open issue labelled `0.5` sorts ahead of every issue that is not; inside
each group the five old tiers are unchanged (game-visible, impact
descending, unestimated, measured zero, no tracker row; oldest first). The
line's key starts `[0.5]`. The labels are the ones the same `gh issue list`
already returned for the SKIP filter. A row whose `labels` is not a list of
`{name: str}` is printed, ranked with the non-release group, and tagged
`[labels unreadable]`.

## 4. BOARD_FOCUS_LABEL (addendum)

`BOARD_FOCUS_LABEL` in `$WORK/limits.env` (unset: today's behaviour). Set,
board_filter's `issues` mode drops every startable issue without that label
and prints `FOCUS: N startable issue(s) outside the 0.5 focus are not offered
(BOARD_FOCUS_LABEL=0.5 in limits.env)`. positive_gate splits that line off the
capacity list, says it to the tick log and puts it in the brief. It is not a
capacity line, so the count alone never wakes a tick. A row whose labels
cannot be read cannot be shown to carry the focus, so it is dropped with the
rest. roles/board.md's order paragraph says both.

The host sets `BOARD_FOCUS_LABEL=0.5` in limits.env when this folds.

### The falsifier: every new leg, old and new board.sh

`.lanetmp/run97.sh` sources only `selftest.d/97-board-priority.sh` against a
copy of `jobs/` with a given board.sh.

| board.sh | existing 12 legs | 13 new legs |
|---|---|---|
| this branch | 12 ok | 13 ok |
| origin/master (pre-#432) | 12 ok | **13 FAIL** |

What attempt 1's legs got wrong. The `#404` fixture (labels given as a
string) was in the same issue list as every other new leg. The pre-#432
board.sh raises on it and prints nothing, so on the old file every leg
"failed" because the list was empty and not because of the order, and the
focus leg "#301 is absent" *passed* on the old file for the same reason.
Attempt 2 split `#404` into its own fixture (`issues-bad.json`). On the old
file the order legs now fail on the order: it prints `#301 #403 #302 ...
#401 #300`. The focus legs fail because the old file offers `#301`. The
unreadable-label legs fail on the empty list, which is their real defect.
Also fixed: the first leg's glob `*" #401 "*" #301 "*` needed two spaces
between the numbers, so it failed on the correct order.

Must-not-move: the full jobs selftest, see the PR.

## 2. Device-run queue priority: the request.sh site (not edited here)

request.sh is lane.pilotgate's (PR #420). Board request dropped at
`$DISPATCH_DIR/board-requests/pri432.md`.

- The order is set by the request's file name alone: `dispatcher.sh`
  ~1544-1555 serves `queue/*.req` in glob (ASCII) order. `0-*` probes come
  first, epoch-named requests follow by arrival, and `z-sweep-*` comes last.
- Site: `docs/testing/request.sh:701` `ID="$(date +%s)-$WHO-$$"`.
- One-line change: `ID="${HAKUX_RELEASE_PRIO:+1-}$(date +%s)-$WHO-$$"`.
  With `HAKUX_RELEASE_PRIO=1` the request is `1-<epoch>-...`, which sorts after
  every `0-*` and before every epoch-named request, because `-` is below any
  digit. Checked with a glob on this host (C.UTF-8 and C):
  `0-0-x-9 < 0-probe < 1-1759000500-b < 1759000000-a < z-sweep-x`.
- Its callers (ab_run.sh, arms.sh) set the variable when the prediction's
  issue carries `0.5`. That is a second change and is not in this lane's files.

## 3. The 0.5 panel on the status page

`status_html.py release05` gathers it and prints facts.tsv rows (`r05`,
`r05gate`). status.sh adds `r05issue` rows from `gh issue list --label 0.5`,
plus the target (`STATUS_RELEASE_TITLES`, default 145) and the gate floor
(`STATUS_RELEASE_GATE_MIN`, default 25). build() folds them into
`release.panel`. The page renders a second `.rel` box, and
`status_html.py panel status.json` prints the same lines as text.

Sources, and what has none:

| row | source | note |
|---|---|---|
| on the handhelds | `$WORK/titles/already-on-handhelds.json` | 23 |
| staged on host | `<HAKUX_XISO_DIR>/manifest.csv` (stage_xiso.py) | shown beside it. **No file records a staged ISO reaching a handheld** (#430). That file would be a per-device manifest written by the copy step |
| tested | `$DISPATCH_DIR/results/*/verdict.json` (title_verdict.py, as titles/table.py reads) | 0 today: no verdict.json exists yet |
| Playable | the same, latest verdict per (title, device) passing with a `Playable*` rating on every handheld tested | 0 |
| Ghoulies gate | newest finished soak per handheld whose request title names Ghoulies and that has hakuX-perf gfps in 90-240 s (clock from the first perf line, as fix311/read_soak.py) | see below |
| lane per 0.5 issue | the issue's `lane:` label, `claimed:cloud` = cloud | |

The newest Ghoulies soaks (`0-0-x/y-1790432892-hotfix041-*`, the v0.4.1-j1
candidate APK) log **no hakuX-perf lines at all**. Their logcat carries only
hakuX, hakuX-stderr, hakuX-vk, hakuX-tier1 and hakuX-route. The panel takes
the newest soak that can be read and counts the newer ones it passed over.
The thor median of 29 (n=69) and the nova median of 29 (n=71) on
`1790426955/6-lane.remote-*` match `docs/lanes/fix311/read_soak.py` on the
same runs exactly. Those runs are on a lane ref (1d9c3e4c0f), not the
candidate, so the panel says "met on these soaks (check the ref is the
candidate's)" and not "MET". If the gate is to be read on a release APK, that
APK must log hakuX-perf.

Rendered from the live host files, 2026-09-26 (Pacific afternoon):

```
Release 0.5: titles and the Ghoulies gate
Titles on the handhelds: 23 of 145 (+23 staged on the host; a staged ISO's copy to a handheld has no record yet, #430)
Tested (a title_verdict on either handheld): 0 of 145
Playable (latest verdict passes on every handheld tested): 0 of 145
Ghoulies gate (median gfps 90-240 s >= 25, both handhelds): met on these soaks (check the ref is the candidate's) -- thor 29 (n=69; 1790426955-lane.remote-2612788, ref 1d9c3e4c0f, 8h 54m ago; 2 newer soaks logged no gfps in 90-240 s); nova 29 (n=71; 1790426956-lane.remote-2612842, ref 1d9c3e4c0f, 8h 20m ago; 1 newer soak logged no gfps in 90-240 s)
0.5 issues (15 open): #433 no lane -- 0.5 release: the first tested-titles list for the ; #432 lane.pri432 -- Harness: dispatch 0.5 work first and show 0.5 prog; #431 lane.xbox -- ...; #430 lane.xbox -- ...; #429 no lane -- ...; #428 lane.vcpuprime428 -- ...; #427 lane.buildflags427 -- ...; #426 lane.remote -- ...; #425 no lane -- ...; #424 lane.tbchurn424 -- ...; #414 lane.forza414 -- ...; #413 lane.doa413b -- ...; #412 lane.aufire412 -- ...; #397 no lane -- ...; #372 lane.blinx372d -- ...
```

(Titles after #432 are shortened here; the page prints 50 characters of each.)

## For the next lane

- Do not put a malformed-row fixture in the same list as the order legs. The
  old code crashes on it, and every leg then "fails on old" for one reason.
- The panel has no selftest leg. `selftest.d/64-status-html.sh` was not in
  this lane's files. A leg there would feed `release05` a fixture results dir
  containing one Ghoulies soak with perf lines and one newer soak without, and
  check the median and the passed-over count.
