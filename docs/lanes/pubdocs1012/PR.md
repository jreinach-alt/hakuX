# pubdocs1012: public docs pass for 0.5 (README, compatibility, limitations, attribution) (#433, 0.5)

State: draft

Lane: pubdocs1012            Issue: none (#433 umbrella)
Base: master @ 1ed3ac8f39
Files: README.md, KNOWN_ISSUES.md, docs/COMPATIBILITY.md, android/README.md, PRIVACY.md, docs/lanes/pubdocs1012/PR.md
Prediction: none (docs only, no emulator code changed)
Needs device: no    Needs NDK: no

- **README.md**: rewrote the "State of the project" section to drop a stale
  "Rough, a handful of games boot" framing and a stale pgraph pass-rate figure
  that predates v0.4.0-j1's rendering fixes; both are replaced with accurate,
  non-stale text that points at `docs/COMPATIBILITY.md` and the issue tracker
  instead of quoting a number that will go stale again. Replaced the
  agent/process-flavoured "Contributing, with or without an agent" section
  with plain Compatibility / Building / Contributing / Privacy sections.
  Added a note on the current release (0.5.0) linking to `docs/releases/`,
  and extended the documentation table with the new and existing docs.
- **docs/COMPATIBILITY.md** (new): states the project's Playable bar (held
  run, play share, fps bar, audio, frame review, per-handheld) sourced from
  `docs/testing/title_verdict.py` and `docs/testing/flicker.md`, and lists the
  52 titles currently accepted as Playable, sourced from
  `pm/playable-accepted.tsv`.
- **KNOWN_ISSUES.md**: added an entry for the audio DSP being off by default,
  verified against `SettingsActivity.kt` and `strings.xml`.
- **android/README.md**: replaced a stale "core not yet wired" opening and a
  stale Rust/Cargo XISO-converter requirement (removed in v0.3.1 per
  CHANGELOG.md) with the current, verified toolchain and build steps;
  replaced a stale SDL3-migration note with one stating this port
  intentionally stays on SDL2.
- **PRIVACY.md** (new): what the app sends over the network, verified from
  `AndroidManifest.xml` (INTERNET is the only permission; no storage
  permission, SAF is used instead), the dependency list in
  `android/app/build.gradle.kts` (no analytics/crash-reporting SDKs), and the
  two features that use INTERNET: box-art lookup against
  `raw.githubusercontent.com/izzy2lost/X1_Covers` (on by default, togglable)
  and the emulated Xbox's own network adapter / Insignia (off by default,
  user-controlled; its sign-up and guide links open in the browser via
  `Intent.ACTION_VIEW`, confirmed in `SettingsActivity.kt`). Linked from
  README.md.

Left out, not fixed (outside this lane's scope or not independently
verifiable):

- `CHANGELOG.md` has no entries for v0.4.0-j1, v0.4.1-j1 or 0.5.0 (release
  notes for those exist separately under `docs/releases/`). Scope for this
  lane was "check accuracy only"; flagged rather than filled in.
- `ROADMAP.md` still carries the same stale pgraph pass-rate figure removed
  from README.md, as a historical checklist item. Scope for this lane was
  "fix inaccuracies only" and this reads as a record of a past state rather
  than a current claim, so it was left alone.
- `.github/FUNDING.yml` (points to the upstream xemu author's Patreon) was not
  touched — out of this lane's file ownership. Flagged for the project owner
  in the PR body, not changed here.

Release note: Docs: the README, compatibility list and known limitations describe the 0.5 build, with upstream credits.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
