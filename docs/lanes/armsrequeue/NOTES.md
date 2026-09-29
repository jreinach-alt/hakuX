# lane.armsrequeue -- a REFUSED arm is re-queued once, like INCOMPLETE

Issue: none (harness defect, dispatched directly). Evidence: PR #583,
2026-09-29 13:13-13:40 PDT.

## The defect

`ab_compare.py` refuses to score a pair it cannot measure (`die()` prints
`REFUSED: ...`, no `VERDICT:` line). The commonest is a run without
`progress_log_proof`, whose text says "Requeue the arm". `arms.sh`'s judge
loop read no VERDICT line, substituted `VERDICT: (none printed; see the full
output)`, and took the normal path: one comment, then `judged/<sha>` forever,
with both result directories still clean. `already_ran()` is true on either
the judged marker or `RAN[sha]` (two clean refs), so the prediction could not
be queued again, and the ARM ERROR comment's recovery ("delete judged/ and
pairs/") did not work either: the clean results still matched RAN. hostops
had to `touch VOIDED` in both result directories by hand for #583's
`forzadecay414-fix-pixels2.json`.

## The fix (`docs/testing/jobs/arms.sh`, judge loop)

A branch before the FAIL case, keyed on "no `^VERDICT:` line and a
`^REFUSED:` line" in ab_compare's output. It follows the ARM ERROR shape
(nothing was compared; no label decision; `continue`) with INCOMPLETE's cap:

- both results get `VOIDED`, so RAN stops counting them;
- first REFUSED: `$A/refused/<sha>` is written, `pairs/<sha>.json` is removed,
  no judged marker -- the next tick queues a fresh pair;
- second REFUSED (marker present): `judged/<sha>` = `REFUSED` (no PASS/FAIL
  a label could read) and the comment says it is final. The results are
  voided on this path too, so the documented manual recovery now works.
- the comment's first line is the refusal itself, then the pair table and
  the first 80 lines of ab_compare output. `label_decide` is not called.

`refused/` is a new sibling of `incomplete/`, not shared with it: a pair that
went INCOMPLETE once and REFUSED once is two different causes, and each keeps
its own one retry.

Every `die()` in ab_compare is covered, not only the proof one. The others a
real pair can hit (an ERROR/no-DONE arm is caught earlier by arms.sh; disc_id
differs; no runs at all; a prediction naming other refs) either say "requeue"
themselves or are structural and end on the second REFUSED at a cost of one
extra pair. A crash with neither line (a traceback) is unchanged.

## Proof

`docs/testing/jobs/selftest.d/99-arms-refused-requeue.sh`, self-contained
(own work/dispatch dirs; asks `arms.sh list` whether the prediction would
queue). The fixture's fix arm has `progress_log_proof: false`, as #583's did.

| check | this branch | origin/master's arms.sh (`RF_ARMS=`) |
|---|---|---|
| R0 controls (would queue before any pair; ab_compare REFUSES, no VERDICT) | ok | ok |
| R1a no judged marker after the first REFUSED | ok | FAIL |
| R1b both results VOIDED | ok | FAIL |
| R1c pair record gone; `list` would queue it again | ok | FAIL |
| R1 once-only marker; comment carries the refusal | ok | FAIL |
| R1 posted; no label moved | ok | ok |
| R2 second REFUSED judged, not queued a third time | ok | ok (vacuously: master judged on the first) |
| R2 results voided; comment says final | ok | FAIL |
| R3 deleting judged/ + pairs/ queues it once more | ok | FAIL (the hostops hand-fix) |

16/16 on this branch, 7/16 on master (193 s each, SELFTEST_ONLY alone).
The arms chain (10 through 94-arms-label-state), 94-arms-verdict-scope,
94-arms-withdrawn, 99-arms-confounded-pair and this fragment together:
342 passed, 0 failed. preflight.sh passed.

## For the next lane

- A new judge-loop outcome needs three things or it strands: a VOIDED on
  both results (RAN), no judged marker (or a cap), and no pair record.
- `grep labels` on the gh shim log matches `pr list --json ...labels` from the
  status tail; anchor on `issues/<n>/labels`.
