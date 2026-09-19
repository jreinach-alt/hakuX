# lane.cloudterritory -- the audit outlet writes its own territory row

Status: in progress. `jobs/cloud.sh` claims a unit (label, brief, worktree,
`systemd-run`) and writes no `territory.toml` row, so every audit and every
remediation is invisible to `check_territory.py` until a board tick notices
and spends a model session writing the row by hand. Seven such FAILs in one
night, five of them from this outlet.

Findings and decisions follow as they are made.
