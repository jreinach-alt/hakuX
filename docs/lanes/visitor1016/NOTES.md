# lane.visitor1016 -- first-contact files a stranger meets on GitHub (#433)

## Changed

- `.github/ISSUE_TEMPLATE/config.yml`: added a `contact_links` entry pointing
  at `docs/COMPATIBILITY.md` ("Check compatibility first" / "Check here
  first: is your game already rated?"), ahead of filing either issue form.
  No link to SECURITY.md added -- it does not exist; that is the owner's
  call, not this lane's.
- `.github/ISSUE_TEMPLATE/general-issue.yml`: `install-type` and
  `device-chip` (SoC/GPU) are now `required: false`, each with a line
  telling the reporter to leave it blank if they don't know it. `id:` keys
  unchanged. Version, device make/model, and "What happened"
  (`bug-description`) stay required, as briefed. I did not touch
  `android-version`, `device-ram`, `steps-to-reproduce`, `expected-behavior`
  or `frequency` -- the brief named only install type and SoC/GPU for the
  optional change, and touching the rest wasn't asked for.
- `.github/ISSUE_TEMPLATE/title-issue.yml`: `title:` changed from
  `"Title Name: Short description"` to `"[Title]: "`, matching the
  `"[Bug]: "` prefix style already used by `general-issue.yml`. A reporter
  now has nothing to delete, only a game name to add after the colon.
  Required fields on this form are untouched -- the brief only flagged the
  title prefill here, and a compatibility report needing the device detail
  it already asks for is not the friction that was flagged.
- `CONTRIBUTING.md`: line ~6 reworded. "then this fork" became "then this
  project, hakuX CE" -- true (that's the project's name now) and no longer
  than the original. Bumped the `_Last updated_` line to 2026-10-16 (still
  version 0.5.0) since the text changed.
- `docs/reporting-bugs.md`: both "hakuX (fork)" labels (the Android Settings
  path, and the release row of the build table) became "hakuX CE". Bumped
  the `_Last updated_` line to 2026-10-16 for the same reason.

## Left alone, and why

- `KNOWN_ISSUES.md`: read it in full as a stranger. It already carries no
  lane names, no issue-number-only references, and no harness words --
  lane.docsrewrite1012 (#433) already rewrote it for players, per its
  commit `4957f3047a`. Nothing to change; left it untouched rather than
  bumping its date for no edit.
- `.github/pull_request_template.md`: checked every item. "Built
  successfully", "Tested on a device", "Tested titles / scenarios", and the
  `COPYING` link (`../COPYING`, resolving to the repo root) are all fine for
  an outsider; nothing links to AGENTS.md, a lane, the board, or any private
  path. No change needed.
- `.github/ISSUE_TEMPLATE/feature-request.yml`: no required-field or naming
  friction found; out of scope for this pass as briefed (not named in
  "What to change").
- Did not touch the plain word "hakuX" anywhere -- only the specific
  "hakuX (fork)" label (now "hakuX CE") and the "this fork" phrase in
  CONTRIBUTING.md. Everywhere else "hakuX" names the emulator, the upstream,
  or the project, which the brief says to leave alone.
- Stayed out of README.md, PRIVACY.md, ROADMAP.md, android/**,
  docs/COMPATIBILITY.md, CHANGELOG.md, docs/releases/**, host-tools, and all
  `id:` keys in the issue forms, per the brief's "Do NOT change" list.

## Unverified

- The labels `triage`, `compatibility` and `enhancement`, referenced by
  `general-issue.yml`, `title-issue.yml` and `feature-request.yml`
  respectively, cannot be confirmed to exist on GitHub from here (no GitHub
  access in this lane). Left as-is rather than guessed at.

## Owner decides (not this lane, not created)

- `SECURITY.md` does not exist. `config.yml` has no link to it, as briefed.
- `CODE_OF_CONDUCT.md` does not exist and was not created.
- No "getting your Xbox files" doc exists; none was created.
- The Playable-count wording lives in `docs/COMPATIBILITY.md`, outside this
  lane's territory, and was not touched.

## Verify

- All four `.github/ISSUE_TEMPLATE/*.yml` files parse with
  `yaml.safe_load` (PyYAML is installed in this environment): `config.yml`,
  `general-issue.yml`, `title-issue.yml`, `feature-request.yml` -- all OK.
- `python3 /home/justin/hakuX/docs/testing/docs_freshness.py --repo
  /home/justin/hakux-work/wt/visitor1016` reports `public docs: 11 OK, 0
  not` after the edits (the script's own default `--repo` resolves to
  `/home/justin/hakuX`, not this worktree -- pass `--repo` explicitly or it
  silently checks the wrong tree).
- Every relative link in the changed Markdown resolves from its own file:
  `android/README.md`, `LICENSE`, `COPYING`, `COPYING.LIB`,
  `docs/reporting-bugs.md`, `.github/pull_request_template.md`,
  `KNOWN_ISSUES.md`, `docs/COMPATIBILITY.md` all exist at the paths their
  links use. No absolute `github.com/.../master/...` link in the changed
  files points at a path that doesn't exist on this branch.
- `git grep -n "fork" -- CONTRIBUTING.md KNOWN_ISSUES.md
  docs/reporting-bugs.md .github/pull_request_template.md
  .github/ISSUE_TEMPLATE/*.yml` after the edits: no hits. (Before: two in
  `docs/reporting-bugs.md`, one in `CONTRIBUTING.md`, all fixed above.)
