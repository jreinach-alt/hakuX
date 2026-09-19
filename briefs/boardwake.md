# lane.boardwake -- #119

Base: 05e25ca29b (origin/master).
Files (yours, no others): docs/testing/jobs/board.sh, docs/testing/jobs/selftest.sh.
Issue: #119.

GOAL: `board.sh`'s gate at board.sh:69-74 only wakes the model tick on a
FAIL from fleet.py or check_coverage.py -- both are error reports, so a
healthy fleet with idle capacity and startable work never triggers a tick.
Add a positive trigger beside the two negative ones: wake when
`lanes_running < LANE_MAX` (read the same way lane.sh does, via
`systemctl --user list-units 'hakux-lane-*'` and `$WORK/limits.env`) AND at
least one open issue is startable -- open, no `lane:` label, no
`claimed:cloud`, none of `blocked:*`, `decision-needed`, `upstream`,
`unmodellable`, `xbox-hardware`, `harness-status`. Query the label set with
`gh issue list`, matching the style already used in check_coverage.py's
`open_issues()`.

Also in scope (same mechanism, per the issue): the board never wakes for a
ready PR with no state label (no `needs-audit-*`, `fold-ready`, `folded`,
and not a draft). Add that as a second positive trigger.

Keep the cap: this is a wake condition, not a dispatch decision -- the
brief already tells the model what to do once woken (jobs/roles/board.md).
Do not change LANE_MAX or lane.sh's own refusal.

FALSIFIER: run the new gate against the current fleet.py/check_coverage.py
output right now (both clean per this tick's earlier state) plus one open,
unlabelled issue -- it must fire. Run it against a fleet at LANE_MAX with
no startable issues -- it must stay silent. If it fires in the second case
or stays silent in the first, the condition is wrong, not the threshold.

DONE WHEN: `board.sh` starts a tick when there is capacity and startable
work; a selftest case added to `docs/testing/jobs/selftest.sh` that fails
against the current gate (before your patch) and passes after; `nothing
actionable` still logged when there genuinely is nothing. Open a draft PR
from lane/boardwake. Do not queue device arms; this issue needs none.
