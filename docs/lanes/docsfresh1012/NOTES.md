# docsfresh1012

Scope: `docs/testing/docs_freshness.py`, `docs/testing/docs_freshness_selftest.py`,
`docs/testing/public_docs.txt`, one step in `android/RELEASING.md`, one new section in
`AGENTS.md`, and `docs/lanes/docsfresh1012/**`. Base: master @ dd5e3cb3c6. No device, no
`gh`, no network. `lane.local` owns the actual doc rewrite (the date lines themselves) in
its own lane; this lane is the process around it.

## What I did

- **`docs/testing/public_docs.txt`**: the eleven paths from the brief, one per line, with a
  comment pointing at `AGENTS.md`'s "Public docs" section. All eleven exist in this worktree.
- **`docs/testing/docs_freshness.py`**: reads the date line
  (`_Last updated YYYY-MM-DD, for version X.Y.Z._`) as the first non-blank line after each
  doc's H1 -- a line matching that shape anywhere *else* in the file (a code block, further
  down) does not count, which the selftest checks directly. Versions compare as integer
  tuples, not strings (`0.10.0 > 0.9.0`, which a string compare gets backwards). The "current
  version" comes from `android/app/build.gradle.kts`'s own fallback literal
  (`"0.5.0-unknown"`) -- see the comment by `GRADLE_VERSION_RE` for why: the real
  `versionName` is computed at build time by `version_stamp.sh` against the exact commit
  being built, which this script has no access to without running a build, so the gradle
  file's one literal X.Y.Z string is the base version both already agree on by convention.
  `--release` overrides it for a release in progress, matching `release_build.sh`'s own
  `-PversionedRelease`. Read-only throughout; it never touches a doc.
- **`docs/testing/docs_freshness_selftest.py`**: 15 cases over throwaway fixture repos
  (never this worktree) -- every state (OK/STALE/MISSING-FILE/MISSING-LINE/BAD-DATE), the
  14-vs-15-day boundary, `--release` overriding the Gradle version, the numeric-not-string
  version comparison (0.10.0 doc against a 0.9.0 build must read OK), the H1-anchored date
  line (a matching line inside a code block is MISSING-LINE), and all three exit codes.
  All 15 pass.
- **`android/RELEASING.md`**: one new section, "Before tagging a release", between "Wiring
  it in" and "Building and verifying" -- review every public doc and bump its date line, then
  `docs_freshness.py --release X.Y.Z` must pass. Nothing else in the file touched.
- **`AGENTS.md`**: one new section, "Public docs", right after "Public-facing text carries no
  process commentary" (closest existing rule) and before "Non-negotiables". Covers the
  reader, the no-process-commentary rule (pointing at the existing rule above it), style,
  the date line, same-PR doc updates, and the 14-day/release cadence with the hourly alarm.
- **Staged, not installed**: `/home/justin/hakux-work/lanes/docsfresh1012/hourly_report.sh.new`
  (copy of the live script with one new section after "--- ops (jams)") and
  `hourly_report.sh.diff`, both also copied into this directory for the git record. The
  section runs the checker against `/home/justin/hakuX` under `timeout 30`; prints the
  summary line alone when every doc is OK, otherwise `  ALARM: public docs stale: <paths>`
  followed by the non-OK state lines. Tested standalone against this worktree (produces the
  ALARM form, paths below) and against an all-OK fixture (produces the bare summary line) --
  see the commands in this file's history for how; `lane.local` installs it after review.

## What I measured

`python3 docs/testing/docs_freshness_selftest.py` on this branch: all 15 cases `ok`, exit 0.

`python3 docs/testing/docs_freshness.py` against this worktree (= master's content for every
file this lane did not touch, so every public doc fails the same way today, as the brief
said to expect -- none of the eleven carry the date line yet; `lane.local`'s doc rewrite adds
it):

```
MISSING-LINE README.md                        -            -          (- d)
MISSING-LINE KNOWN_ISSUES.md                  -            -          (- d)
MISSING-LINE ROADMAP.md                       -            -          (- d)
MISSING-LINE CONTRIBUTING.md                  -            -          (- d)
MISSING-LINE PRIVACY.md                       -            -          (- d)
MISSING-LINE docs/COMPATIBILITY.md            -            -          (- d)
MISSING-LINE docs/reporting-bugs.md           -            -          (- d)
MISSING-LINE docs/es-de/README.md             -            -          (- d)
MISSING-LINE docs/releases/README.md          -            -          (- d)
MISSING-LINE android/README.md                -            -          (- d)
MISSING-LINE android/MIGRATING.md             -            -          (- d)
public docs: 0 OK, 11 not: README.md, KNOWN_ISSUES.md, ROADMAP.md, CONTRIBUTING.md,
PRIVACY.md, docs/COMPATIBILITY.md, docs/reporting-bugs.md, docs/es-de/README.md,
docs/releases/README.md, android/README.md, android/MIGRATING.md
```

Exit 1, as expected for 11 not-OK docs.

## What the next lane should not repeat

- Don't look for a literal `versionName = "X.Y.Z"` in `android/app/build.gradle.kts` --
  there isn't one. It's `versionedRelease ?: stampedVersionName()`, computed at build time
  by `docs/testing/version_stamp.sh` against the exact commit being built. The one literal
  X.Y.Z string that actually lives under `android/` is the `"0.5.0-unknown"` fallback a
  few lines down; that's what this script reads, and `--release` is there for anyone who
  needs the real in-progress release version instead.
- The date-line regex must anchor on the H1, not just search the whole file -- a doc that
  happens to show an example of the date-line syntax somewhere in its body (e.g. explaining
  the convention) would otherwise false-positive as OK. The selftest's
  "line only right after H1" case exists because this was the first version I wrote, before
  checking the brief's requirement twice.
- `docs/testing/public_docs.txt`'s eleven paths are unverified as to CONTENT -- I only
  confirmed they exist in this worktree. `lane.local`'s rewrite is what actually gives them
  the date line; this lane's checker will keep reporting all eleven not-OK until that lands.
