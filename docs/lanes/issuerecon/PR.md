# issuerecon: reconstruct the GitHub issue log from local transcripts for the forge import

State: ready

Lane: issuerecon            Issue: #433
Base: master @ 66bce0c222
Files: docs/lanes/issuerecon/NOTES.md, docs/lanes/issuerecon/OUTBOX.md, docs/lanes/issuerecon/PR.md, docs/lanes/issuerecon/jqtmpl.py, docs/lanes/issuerecon/recon.py, docs/lanes/issuerecon/recon_build.py, docs/lanes/issuerecon/secretscan-allow.json, docs/lanes/issuerecon/secretscan.py
Prediction: none: analysis-only (no emulator code, no pixels)
Needs device: no    Needs NDK: no

The tooling that rebuilt jreinach-alt/hakuX's issues, PRs and comment threads from the agent
transcripts, the board and git, for lane.localforge's import. The recovered content is in
`~/hakux-work/forge-import/` (outside the repo, with README.md, coverage.tsv and totals.json). It is not
committed here.

| | count |
|---|---:|
| numbers 1..629 (195 issues, 434 PRs) | 629 |
| fully / partly / not recovered | 336 / 290 / 3 |
| title / complete body / state / labels | 626 / 490 / 598 / 530 |
| comment ids seen / with full text / truncated / none | 2,621 / 2,180 / 16 / 425 |
| comments with text but no id | 459 |

Method, parser checks and limits: `docs/lanes/issuerecon/NOTES.md`. Two independent paths gave text for
the same comment in 93 cases. 90 agree, and the other 3 are comments edited after they were posted. The
secret scan redacted one credential (#445); every other hit was reviewed. The Wayback Machine has no
captures.

Local checks (no CI while suspended):
- `docs/testing/preflight.sh`: passed. The coverage gate did not run because gh returns 403; it fails
  open by design.
- `python3 -m py_compile docs/lanes/issuerecon/*.py`: ok.
- `recon.py scan && recon.py finalize`: ok. The secret scan reports 1 hit, redacted, and no unreviewed hits.
- No harness files changed, so `selftest.sh` does not apply.

Release note (none): tooling only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
