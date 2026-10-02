# routerca433: root cause and corrective action for the missing path builder (#433)
State: ready

Lane: routerca433            Issue: #433
Base: master @ b71f92a12a
Files: docs/lanes/routerca433/PR.md, docs/lanes/routerca433/NOTES.md, docs/lanes/routerca433/OUTBOX.md, docs/lanes/routerca433/CAPA.md, docs/lanes/routerca433/ledger.py, docs/lanes/routerca433/ledger.tsv, docs/lanes/routerca433/review.tsv, docs/lanes/routerca433/devtime.py
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

This is an RCA/CAPA for #433's path builder. It used no device time and
queued no runs. `CAPA.md` is the deliverable, and its first page is the
owner's answer.

What is in the directory:
- `ledger.py` -> `ledger.tsv`: every route-related dispatch request since
  09-24, deduplicated by request id. 218 requests, 29.2 device-hours, each
  with an outcome class.
- `review.tsv`: 18 runs whose frames were opened, overriding the automatic
  class.
- `devtime.py`: device-minutes by state from devwatch.
- `NOTES.md`: method, tables, held-session and process history, and what the
  next lane should not repeat.

| outcome (dispatch) | runs | device-h |
|---|---|---|
| d: 600 s of play shown by frames | 1 | 0.24 |
| d?: gate PASS, window never seen (the other 10 accepted titles) | 10 | 3.7 |
| f: wrong screen all window (4 were gate PASSes) | 6 | 1.6 |
| asked for < 700 s, so a 600-s result was impossible | 172 | 16.6 |

Main causes:
- Open-loop routes with a self-reported `mark gameplay`.
- A gate with no frames of the window.
- A screen-aware driver that never reached a dispatched run.
- Orchestration that kept devices busy with runs unable to answer the
  question, every one queued with `--no-expect`.

Corrective actions C1-C9 are ranked in CAPA section 5.

Local checks, offline protocol (no CI):
- `python3 docs/lanes/routerca433/ledger.py` regenerates `ledger.tsv`
  byte-identically.
- `python3 docs/lanes/routerca433/devtime.py` runs clean.
- No harness, board or emulator file is touched, so `jobs/selftest.sh` is not
  required.
- `git diff --stat origin/master...HEAD` lists exactly the Files: line.

Release note (none): analysis only, no emulator or harness code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
