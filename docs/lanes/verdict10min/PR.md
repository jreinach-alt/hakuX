# verdict10min: the 10-minute confirmation (#433)

State: ready

Lane: verdict10min             Issue: #433 (0.5: 50 Playable)
Base: master @ 2ba1a6e9a2
Files: docs/testing/titles/targets.toml, docs/testing/title_verdict.py, docs/testing/jobs/selftest.d/99-verdict-10min.sh, docs/lanes/verdict10min/NOTES.md, docs/lanes/verdict10min/PR.md, docs/lanes/verdict10min/OUTBOX.md
Prediction: none: a test-harness rule change, not a device-behavior arm
Needs device: no

## Summary

The owner (2026-09-30 ~12:05 PDT) agreed to move the Playable confirmation
window from 1200 s to 600 s, on lane.local's 09-30 evidence: re-scoring every
full-length confirmation as if cut at 300 s and 600 s found no verdict change
on the Nova (6/6 runs) at 5 or 10 minutes, while a Thor run (Azurik) read
99.6% at 10 minutes and failed at 15.6 minutes on the heat pause. This PR
implements the rule exactly as specified in the brief:

- `targets.toml`: `[defaults] confirmation_s = 600` (was 1200), with the
  decision and date in a comment; Forza Motorsport and Kabuki Warriors each
  keep their own `confirmation_s = 1200` (slow-building defects).
- `title_verdict.py`: honours a title's own `confirmation_s`; a scored
  window still heating at the end (xo-therm or the battery zone climbing
  faster than 1.0 C/min over its last 180 s, or a thermal pause anywhere in
  the window) still needs the full 1200 s, reported as "confirmation: 1200 s
  needed -- the device was still heating at the end" rather than the generic
  duration message. Screening (`screening_s = 600`) is untouched.
- A new selftest fragment, `99-verdict-10min.sh`: four fixtures (flat 600 s
  pass; heating tail needs 1200 s; a flagged title needs 1200 s on the
  generic message instead; an existing 1200 s shape still passes) against
  the real `targets.toml`, plus two mutants.
- Details, and what was deliberately left as process (the every-5th-pass
  audit) rather than code, are in `docs/lanes/verdict10min/NOTES.md`.

Release note (none): test harness rule -- no emulator code touched, and this
changes how a soak's own log is judged after the fact, not anything a player
would see change in a running build.

## Verification (no CI here -- GitHub is suspended; see the offline addendum)

- `docs/testing/jobs/selftest.sh` was not run whole (18-25 min against
  fragments this change does not touch). Instead, every fragment whose
  fixtures exercise `title_verdict.py` or `thermal_state.py`:
  `SELFTEST_ONLY="99-verdict-10min 89-title-verdict 99-thermal-pause
  99-default-regimen 99-power-per-frame 99-display-covered 66-status-titles
  99-status-fullwindow" bash docs/testing/jobs/selftest.sh` -> **172 passed,
  0 failed**.
- `python3 -c "import ast; ast.parse(open('docs/testing/title_verdict.py').read())"` -> OK.

No device run: this is a test-harness rule, not an emulator-behavior change,
so there is nothing for a soak to measure (`Needs device: no`, `Prediction:
none`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
