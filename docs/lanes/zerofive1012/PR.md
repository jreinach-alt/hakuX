# zerofive1012: 0.5 counts 145 measured titles, not 145 benchmarked (#433)

State: ready

Lane: zerofive1012        Issue: #433
Base: master @ 755ac97c96
Files: docs/lanes/zerofive1012/**, docs/testing/release-0.5.toml, docs/testing/jobs/status_html.py, docs/testing/jobs/selftest.d/66-status-titles.sh
Prediction: none: no arm (status page configuration and its renderer; no emulator code)
Needs device: no    Needs NDK: no

The owner, 2026-10-12: 0.5 ships at 145 measured titles and 50 Playable. Measured means any gameplay-window fps
reading on either handheld, at any build and mode, the same definition the header's Measured bar has used since
2026-09-26 21:55 PDT. Benchmarked (routes, save and a MAX-mode reading) is no longer a ship criterion.

- `release-0.5.toml`: the `target` sentence and `decided` say 145 measured. A new `measured_target = 145`;
  `benchmarked_target` stays for the Benchmarked bar, which is shown as progress and not counted toward the release.
- `status_html.py`: the forecast's goals are measured and playable (it was benchmarked and playable), the Measured
  bar and the chart's target line read `measured_target` through `_measured_target()`, and the summary line does
  too. A file without `measured_target` falls back to `benchmarked_target`.
- `66-status-titles.sh`: the default-config check asserts 145 measured, and a new check pins the fallback.

Checks: `SELFTEST_ONLY="64-status-html 65-status-objective 66-status-titles 67-status-measured"` passes on the branch.
60-status and 63-status-lanes fail five checks when run alone, identically on unmodified master 755ac97c96; the full
selftest passes them.

Release note: the status page counts 0.5 progress against 145 measured titles and 50 Playable.
