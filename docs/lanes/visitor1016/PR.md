# visitor1016: fewer required fields, no placeholder text, and "hakuX CE" in the first-contact files (#433)

State: ready

Lane: visitor1016       Issue: #433
Base: master @ 2636e89f4a
Files: .github/ISSUE_TEMPLATE/config.yml, .github/ISSUE_TEMPLATE/general-issue.yml, .github/ISSUE_TEMPLATE/title-issue.yml, CONTRIBUTING.md, docs/reporting-bugs.md, docs/lanes/visitor1016/**
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Release note (none): docs and GitHub issue-form changes only, no emulator code touched.

A read-only audit of what a first-time visitor sees on GitHub (the `home` branch) found friction in a handful of
first-contact files; this lane fixes the parts that need no owner decision.

**Naming.** "hakuX (fork)" is replaced with "hakuX CE" in the two places it appeared: the Android Settings path and
the release row of the build table in `docs/reporting-bugs.md`, and the lineage sentence in `CONTRIBUTING.md`
("then this fork" -> "then this project, hakuX CE"). Only that label changed -- the plain word "hakuX" is untouched
everywhere else, since it names the emulator, the upstream, and the project. A sibling lane, ce1016, is doing the
same rename in README.md, PRIVACY.md, ROADMAP.md, android/MIGRATING.md, docs/frontends/** and docs/es-de/**, none of
which this lane touches.

**Issue-form friction.**
- `general-issue.yml` (Bug Report): `install-type` and `device-chip` (SoC/GPU) are now optional, each with a note
  telling the reporter to leave it blank if they don't know it. Version, device make/model, and "What happened"
  stay required. `id:` keys unchanged.
- `title-issue.yml` (Title / Compatibility Report): the prefilled title changed from the literal
  `"Title Name: Short description"` to `"[Title]: "`, matching the `"[Bug]: "` style already used by the bug form --
  nothing left for the reporter to delete.
- `config.yml`: added a `contact_links` entry pointing at `docs/COMPATIBILITY.md`, "check here first: is your game
  already rated?". No link to SECURITY.md -- it doesn't exist yet; that's the owner's call.

**Left alone.** `KNOWN_ISSUES.md` was already rewritten for players by lane.docsrewrite1012 (#433, commit
`4957f3047a`) and carries no lane names, bare issue numbers, or harness words -- nothing to change. The PR template
and `feature-request.yml` were checked and found outsider-ready. Full reasoning, the unverified GitHub labels
(`triage`, `compatibility`, `enhancement`), and the owner-decision items noticed but not created (SECURITY.md,
CODE_OF_CONDUCT.md, a "getting your Xbox files" doc) are in `docs/lanes/visitor1016/NOTES.md`.

Docs and `.github` templates only: all four issue-template YAML files parse with `yaml.safe_load`, and
`docs/testing/docs_freshness.py --repo <this worktree>` reports 11/11 OK after the two date bumps. No selftest, no
device run.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
