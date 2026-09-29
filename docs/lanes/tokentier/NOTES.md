# lane.tokentier -- #507: match each session's model to its work

## What changed

1. **`docs/testing/lane.sh`**: `next_attempt()` now reads
   `$WORK/briefs/<name>.model` (one line, a model id) and uses it ahead of
   `MODEL_LANE`, on every `start` AND every `resume` -- both call
   `next_attempt()`, so this was the one place that needed to change for the
   file to survive a resume. `HAKUX_MODEL` still overrides it for that one
   start (checked first, as before). The escalated attempt (past
   `LANE_ESCALATE_AFTER`) still always runs on `MODEL_LANE_ESCALATED`
   regardless of the file: three failed passes is a signal about the work,
   not about which model started it.

2. **`docs/testing/jobs/cloud.sh`**: pass 2 (`kind=audit2`) downgrades to
   `MODEL_BOOKKEEPING` when the pass-1 audit file(s) on the branch
   (`docs/audits/*-<lane>-pass1*.md`, the exact glob the audit2 task string
   already points the session at) carry no `## HIGH` or `## MEDIUM` finding
   heading. Surveyed all 118 existing `*-pass1*.md` files: finding headings
   are consistently `## ` or `### ` immediately followed by `HIGH`/`MEDIUM`
   and a non-letter (`-`, ` `, `:`); no false positive against the 45 files
   whose prose says "no HIGH, no MEDIUM" but might have mentioned either word
   in a heading for other reasons (checked by script, none did). This is
   deliberately keyed on pass 1's own findings, not the PR's current label:
   a PR that reached `needs-audit-2` via a remediation round had a HIGH or
   MEDIUM in its history even though the label looks the same as a PR that
   never needed one, so it stays on `MODEL_AUDIT`. `HAKUX_MODEL` and the
   attempt-escalation model both still win, checked the same way the
   existing attempt loop above already decides `MODEL`. Pass 1's own model,
   and every label and next-state outcome, are unchanged.

3. **`docs/testing/jobs/roles/board.md`**: three lines telling the board to
   write `$WORK/briefs/<name>.model` before `lane.sh start`, sonnet for
   docs/measurement/route/harness/status work, opus for emulator-code
   engineering.

4. **`docs/testing/jobs/selftest.d/99-lane-model-file.sh`**: proves both
   pieces against real `lane.sh` and `cloud.sh` runs (throwaway git origins,
   the harness's global `systemd-run`/`gh` shims as the oracle -- the
   `--model` argument actually spawned, read off the logged command line).

## A mutant-harness bug found and fixed on this branch, not upstream

My first version of the lane.sh mutants copied the *whole* `jobs/` directory
into scratch so the mutated `lane.sh` could find its siblings
(`models.env`, `window.sh`, `remote-lane.sh`) by relative path. That broke
`remote-lane.sh`'s own relative climb to `board_files.py`, which then ran
`git -C <scratch>/jobs show origin/board:...` against a directory that is
not a git checkout at all. `git` failed, `board_files.py`'s importer read
that as "unreadable", and `refuse_if_remote` -- correctly, per its own
contract -- REFUSED every mutant run before it ever reached `systemd-run`.
Every one of the four legs' logs was empty, and three of the four "is red"
assertions were `!=` checks that an empty log satisfies for the wrong
reason: they passed whether or not the mutation did anything. Only the one
check phrased as equality to a real value (the "does not touch the start
leg" check under the `resumedrop` mutant) caught it, by failing honestly.

Fixed by not copying the tree at all: the mutated `lane.sh` is written
directly into `$TESTING` (a temp file removed right after each use, plus a
defensive sweep at the end), so `$(dirname lane.sh)/jobs` resolves to the
REAL jobs directory and `remote-lane.sh` runs unmutated, from its real
location, against the real fetched `origin/board`. Verified this actually
changes the outcome: re-ran with the fix and all four "is red" assertions
now come from a non-empty log showing the wrong `--model` value, not a
REFUSED exit. `cloud.sh`'s one mutant did not have this problem (`cloud.sh`
never sources `remote-lane.sh`), confirmed by checking its own mutant run's
log was non-empty from the first version.

**For the next lane building a mutant of a script that calls
`refuse_if_remote` (directly or through something it sources): do not copy
`jobs/` into scratch. Write the mutated file next to the original, or
inside the original jobs directory, so every unmutated sibling it sources
still resolves to its real, git-checked-out location.**

## Proof

`SELFTEST_ONLY=99-lane-model-file` and the neighbouring lane/cloud fragments
(99-limits-env, 96-fleet-registry, 98-lane-shape, 70/71/72/73-cloud-*,
98-audit-outlet, 97-board-gate) all green, 285 checks, 0 failed.
`selftest.sh --check-shards 4` still covers all 109 fragments (the new one
is picked up by the directory glob; no shard-table edit needed).

## Do not

Did not touch `$WORK/limits.env`, `$WORK/briefs/*` outside what the board
writes per its own new rule, host-tools, or board files, per the brief.
