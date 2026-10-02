# issuerecon: reconstruct the GitHub issue log from local transcripts for the forge import

State: draft

Lane: issuerecon            Issue: #433
Base: master @ 66bce0c222
Files: docs/lanes/issuerecon/PR.md, docs/lanes/issuerecon/NOTES.md, docs/lanes/issuerecon/OUTBOX.md, docs/lanes/issuerecon/recon.py
Prediction: none: analysis-only (no emulator code, no pixels)
Needs device: no    Needs NDK: no

Work in progress: a streaming parser over the agent transcripts that rebuilds each
issue and PR (title, body, state, labels, comments) into `~/hakux-work/forge-import/`
(outside the repo; the recovered content is never committed here).

Release note (none): tooling only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
