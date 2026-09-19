# lane.auditoutlet — one dispatch path for audits and remediation

Base: `master` @ bdeab36f75.

## The defect, restated from the brief

`needs-audit-1` and `needs-remediation` are terminal. Three independent
reasons, and all three have to go:

1. `cloud.sh` filtered the remediate pickup on `lane/cloud-`, so no local
   lane's PR was ever visible to it.
2. The board only starts a model tick on a `fleet.py` or coverage `FAIL`;
   an unremediated audit is neither, so `roles/board.md`'s resume rule
   never fired.
3. `hakux-cloud.timer` is disabled by the owner, so the prefix-matching
   path has no trigger at all.

## Decision: `cloud.sh` stays, as the one dispatcher, on the lane path

(Work in progress — filled in as it lands.)
