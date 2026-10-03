# ci: build only code changes and ready PRs; cancel superseded selftest runs

State: ready

Lane: cithrottle (lane.local)   Issue: none (account reinstatement commitment)
Files: .github/workflows/android.yml, .github/workflows/desktop.yml, .github/workflows/jobs-selftest.yml, docs/lanes/cithrottle/PR.md
Prediction: none: CI configuration only

Release note (none): CI configuration

- android.yml, desktop.yml: skip pushes and PRs that only touch `docs/**` or Markdown; run on PR open/sync/reopen/ready_for_review, and skip draft PRs.
- jobs-selftest.yml: a newer push to the same ref cancels the older run; draft PRs are skipped.
- Marker `hakux-ci-throttle` in android.yml: `offline-git/recover_github.py` refuses to push to GitHub without it.

Local checks: the three files parse as YAML (python yaml.safe_load); the triggers and concurrency groups read back as intended.
