## #433 -- 2026-09-30 12:45 PDT

lane.verdict10min: implemented the owner's 10-minute confirmation rule
(2026-09-30 ~12:05 PDT: "I agree with this approach and changing the
definition to 10 minutes. That should speed up our pipeline.").

- `docs/testing/titles/targets.toml`: `[defaults] confirmation_s` 1200 -> 600
  (comment carries the decision and date). Forza Motorsport (4D53006E) and
  Kabuki Warriors (43560001) each keep `confirmation_s = 1200` (flagged for
  slow-building defects: Forza's invalid-list decay/memory growth, #517;
  Kabuki's random stalls).
- `docs/testing/title_verdict.py`: honours a title's own `confirmation_s`;
  a scored window still heating at the end (xo-therm or the battery zone
  rising faster than 1.0 C/min over its last 180 s, or any thermal pause in
  the window) still needs the full 1200 s, reported as "confirmation: 1200 s
  needed -- the device was still heating at the end", distinct from a
  flagged title's generic duration failure. Screening (600 s) unchanged.
- New selftest fragment `99-verdict-10min.sh`: four fixtures plus two
  mutants, run against the real `targets.toml`.
- The audit ("lane.verdict433 re-runs every 5th 600-s pass at the full
  1200 s") is process, not code, and is recorded as a comment in both
  changed files, per the brief.
- Existing verdicts are not re-judged; a pass already recorded at 1200 s
  stands.

Verification: `SELFTEST_ONLY="99-verdict-10min 89-title-verdict
99-thermal-pause 99-default-regimen 99-power-per-frame 99-display-covered
66-status-titles 99-status-fullwindow" bash docs/testing/jobs/selftest.sh`
-> 172 passed, 0 failed. No device run: this is a test-harness rule, not an
emulator-behavior change.

Details: `docs/lanes/verdict10min/NOTES.md`. PR (offline protocol):
`docs/lanes/verdict10min/PR.md`, State: ready.
