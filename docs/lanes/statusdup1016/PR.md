# statusdup1016: a pathfind held run joins its title's row on the status page (#433)

State: draft

Lane: statusdup1016          Issue: #433
Base: master @ fb6ebcff40
Files: docs/testing/jobs/status_html.py, docs/testing/jobs/selftest.d/66-status-titles.sh, docs/lanes/statusdup1016/fixture/heldrun_falsifier.py, docs/lanes/statusdup1016/PR.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

## The defect

A pathfind held run's verdict.json names the title by its ISO
("Bad Boys Miami Takedown USA") and carries no title_id. The title table
keys rows by catalog name, which no ISO spelling matches, so each such run
made a second row beside its title's own row: one row with the rating and
no frame rate, the other with the frame rate and no rating. Both counted
toward Measured.

On the host's data at fb6ebcff40: 69 titles had a second row; 31 Playable titles
showed no frame rate, because it sat on the twin row; the page listed 620
titles where 551 exist, and Measured read 260 where 232 titles have a
reading.

## The fix

`_run_tid()` reads the title_id from the run directory's request.json or
result.json (both carry it), looking in the verdict's own directory and the
one above it (a verdict under provisional/ or hold/ belongs to the run
above). The held-run loop passes that id to `resolve()` and `add()`, so the
row is the catalog title's. A verdict that does carry a title_id is
unchanged.

## The check

`docs/lanes/statusdup1016/fixture/heldrun_falsifier.py` builds a held run
(title_id only in request.json and result.json, an ISO spelling in the
verdict, a ledger row under the catalog spelling) and renders it. It
requires one Playable row under the ledger name, with the run's fps, and
Measured 1. On master's status_html.py the same fixture renders two rows
and Measured 2; the fixture checks that too, so it cannot pass against
code without the fix. Fragment 66 runs it.

Run on this branch: fragments 60-68 and the 99-status-* fragments pass
(60 after the arms fragments 10-50, whose state it reads).

Not changed here: a title's fps cell still prefers a MAX-mode reading (Jet
Set Radio Future shows 24.2 from a MAX run), and Need for Speed: Most
Wanted shows a 25.8 sweep reading although its accepted run was a hand-played
29.9. Both are which-reading-wins questions, not duplicate rows.

Fold: status_html.py and fragment 66 are harness paths, so the fold runs
the full selftest. No device run.

Release note (other): none -- status page only, no emulator/app code touched.
