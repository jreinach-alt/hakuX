# docsfresh1012: a freshness check for the public docs, an hourly alarm and a release step (#433, 0.5)

State: ready

Lane: docsfresh1012          Issue: #433
Base: master @ dd5e3cb3c6
Files: docs/testing/docs_freshness.py, docs/testing/docs_freshness_selftest.py, docs/testing/public_docs.txt, android/RELEASING.md, AGENTS.md, docs/lanes/docsfresh1012/**
Prediction: none (docs tooling)
Needs device: no    Needs NDK: no

## What this is

The owner (10-12, ~23:40 PDT): the public docs are stale and carry no last-updated
timestamp, so staleness has to be inferred from the prose. `lane.local` is rewriting the
docs themselves, in a separate lane, and gives each one a date line:

```
_Last updated 2026-10-12, for version 0.5.0._
```

as the first non-blank line after its H1. This lane is the process around that line: a
checker that reports when a public doc is stale, an hourly alarm (staged, not installed),
a release step, and the rule written into `AGENTS.md`.

## `docs/testing/docs_freshness.py`

```
python3 docs/testing/docs_freshness.py [--repo DIR] [--max-age-days N] [--release X.Y.Z] [--today YYYY-MM-DD]
```

Reads `docs/testing/public_docs.txt` and, for each doc, looks for the date line
immediately after the H1 -- not merely present somewhere in the file, which the selftest
checks for directly (a line with that shape sitting in a code block further down does not
count). Reports one of `OK` / `STALE` / `MISSING-LINE` / `MISSING-FILE` / `BAD-DATE` per
doc, then a `public docs: N OK, M not` summary with the non-OK paths. Exit 0 all OK, 1
otherwise, 2 on a usage error. Versions compare as integer tuples (`0.10.0 > 0.9.0`; a
string compare gets that backwards). Read-only -- it never edits a doc.

The "current version" comes from the one literal `X.Y.Z` string actually written under
`android/`: `build.gradle.kts`'s `"0.5.0-unknown"` fallback. The real `versionName` is a
build-time stamp (`version_stamp.sh`) against the exact commit being built, which this
script can't reproduce without running a build, so the fallback literal is the base version
both already agree on by convention. `--release X.Y.Z` overrides it for a release in
progress, mirroring `release_build.sh`'s own `-PversionedRelease`.

**Output against this worktree** (= master's content for every doc this lane didn't touch,
so all eleven fail today, which the brief said to expect -- none carry the date line yet):

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

`lane.local`'s rewrite is what actually lands the date lines; this checker will keep
reporting all eleven not-OK until it does.

## `docs/testing/docs_freshness_selftest.py`

15 cases over throwaway fixture repos (never this worktree): every state, the 14-vs-15-day
boundary, `--release` overriding the Gradle version, numeric (not string) version
comparison, the H1-anchored date line, and all three exit codes. All 15 pass:
`python3 docs/testing/docs_freshness_selftest.py` -> exit 0.

## `android/RELEASING.md`

One new section, "Before tagging a release", between "Wiring it in" and "Building and
verifying": review every public doc and bump its date line, then
`docs_freshness.py --release X.Y.Z` must pass before the tag is made. Nothing else in the
file changed.

## `AGENTS.md`

One new section, "Public docs", placed right after "Public-facing text carries no process
commentary" (the existing rule it leans on) and before "Non-negotiables". States: who the
public docs are, who reads them, the no-process-commentary rule, style, the date line
(when to bump it and to what), same-PR updates, and the cadence (every release, every 14
days, the hourly alarm).

## The hourly report section (staged, not installed)

`/home/justin/hakux-work/lanes/docsfresh1012/hourly_report.sh.new` is a copy of the live
`/home/justin/hakux-work/host-tools/hourly_report.sh` with one new section inserted after
`--- ops (jams)`, and `hourly_report.sh.diff` is the diff against the live file; both are
also committed under `docs/lanes/docsfresh1012/` for the git record. The section runs
`docs_freshness.py --repo /home/justin/hakuX` under `timeout 30`; when every doc is OK it
prints just the summary line, otherwise `  ALARM: public docs stale: <paths>` followed by
the non-OK state lines. Tested standalone against this worktree (produces the ALARM form
above) and against an all-OK fixture repo (produces `  public docs: 1 OK, 0 not` alone).
`lane.local` installs it after review -- the live file itself was never edited.

Release note (docs): none

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
