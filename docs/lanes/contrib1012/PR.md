# contrib1012: structured bug reports and a contributor guide (#433, 0.5)

State: draft

Lane: contrib1012          Issue: none (#433 umbrella)
Base: master @ 1ed3ac8f39
Files: .github/ISSUE_TEMPLATE/config.yml, .github/ISSUE_TEMPLATE/feature-request.yml, .github/ISSUE_TEMPLATE/general-issue.yml, .github/ISSUE_TEMPLATE/title-issue.yml, .github/pull_request_template.md, CONTRIBUTING.md, docs/reporting-bugs.md, docs/lanes/contrib1012/PR.md
Prediction: none (no emulator change)
Needs device: no    Needs NDK: no

- Rebuilt the bug report form (`general-issue.yml`) with structured,
  mostly-required fields: device make/model, SoC/GPU, Android version, RAM;
  hakuX version (read from the Game Library screen's corner label, or
  Android Settings > Apps > hakuX > App info) and install type
  (release vs. test/debug); optional game fields; steps/expected/frequency/
  settings-changed; and a diagnostics field pointing at the new doc.
- Repurposed `title-issue.yml` into a Title / Compatibility Report form:
  the same device/version fields, game title/region/title ID/image format,
  and a compatibility-tier dropdown, for "how well does game X run" reports
  separately from general bugs.
- Trimmed `feature-request.yml` and `config.yml` to drop the xemu Discord
  invite and xemu.app docs/FAQ links -- those point at upstream xemu support
  channels and would misdirect hakuX users there instead of here. Replaced
  the one contact link with one pointing at the new reporting-bugs.md.
  Upstream credit stays intact in the app's own About screen and in
  README's Lineage section, both outside this lane's files.
- Added `docs/reporting-bugs.md`: one page covering what to gather (device,
  version/install type, game) and how (a copy-paste `adb logcat` recipe,
  and how to enable and pull the in-app Debug Capture).
- Added `CONTRIBUTING.md`: desktop and Android build commands (verified
  against `android/README.md`, `AGENTS.md`'s Building section and
  `android/app/build.gradle.kts` -- SDK 36 / NDK 29.0.14206865 / CMake
  3.30.3 / JDK 21, the meson+ninja-on-PATH gotcha, where the debug APK
  lands), testing titles, and submitting PRs (fork/branch from master, one
  change per PR, GPL-2.0 licensing, no sign-off -- this repo's own commits
  don't use one -- and an honest note that hosted CI isn't running, so a PR
  states what was actually built and tested).
- Added `.github/pull_request_template.md`: a testing checklist (what was
  built, what device, what was tested) plus the one-change-per-PR and
  licensing checklist CONTRIBUTING.md refers to.
- All four YAML issue-form files were parsed with `python3`'s
  `yaml.safe_load` before committing.

Did not touch README.md, AGENTS.md, CLAUDE.md, `.github/workflows/*`, or
`docs/testing/**`, per brief.

Release note: Docs: bug reports use structured forms (device, game,
version, steps, diagnostics), and CONTRIBUTING.md explains building,
testing titles and submitting PRs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
