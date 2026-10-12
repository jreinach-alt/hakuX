# release05: the 0.5 gate is measured on the Nova (#433, 0.5)

State: ready

Lane: release05          Issue: none (#433 umbrella)
Base: master @ 1ed3ac8f39
Files: docs/testing/release-0.5.toml, docs/testing/jobs/status_html.py, docs/testing/jobs/status.sh,
docs/testing/jobs/selftest.d/64-status-html.sh, docs/lanes/release05/PR.md
Prediction: none (no emulator change)
Needs device: no    Needs NDK: no

The owner, 2026-10-12: "0.5 can ship on the Nova test results alone. The
Thor hardware is identical." The gate was "both handhelds", so the status
page could not read MET with only the Thor's older soak (17.5 gfps on
6bfce4a685) beside the Nova's 29.0 on v0.5.0-rc1.

- `release-0.5.toml`: `gate` ends "on the Nova", and a new `gate_devices =
  ["nova"]` names the handhelds the gate is measured on, with the owner's
  words.
- `status_html.py release05` writes one `r05gate` row per `gate_devices`
  handheld (both when the field is unset), so `_gate` judges only those.
  The panel line names the handhelds from the rows ("on the Nova", or "both
  handhelds" for the pair) instead of a fixed "both handhelds".
- `status.sh` no longer writes its own copy of the gate's text; the page
  reads `release-0.5.toml`'s, and `STATUS_RELEASE_GATE` in limits.env still
  overrides it.

Checks: `64-status-html` gains six: with `gate_devices = ["nova"]` there is
no Thor row, the Nova's newest soak is read, a Nova soak on the candidate's
ref is "MET on the candidate", the panel says "on the Nova" and never "both
handhelds", and the repository's `release-0.5.toml` names the Nova only. The
existing panel checks run against a conf with no `gate_devices` and still
read both handhelds.

Release note: none

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
