# pathrules1013: pathfind no-answer steps never become a path, a hold that can't pass ends early, a perflog run never banks (#433, 0.5)

Lane: pathrules1013     Issue: #433
Base: master @ 02ba73b86a
Files: docs/lanes/pathrules1013/**, docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py, docs/testing/title_verdict.py, docs/testing/jobs/selftest.d/89-verdict-perflog.sh
Prediction: none: offline/analysis-only, no device arm of mine
Needs device: no    Needs NDK: no
Release note (none): harness-only -- fixes pathfind's path recording/replay and hold bookkeeping, and makes
title_verdict.py never read a perflog telemetry build as a Playable candidate; nothing a player sees change.
State: waiting-on-pathtele1013

## What this is

Three fixes to `docs/testing/titles/pathfind.py` plus one to `docs/testing/title_verdict.py`, done in order
(one lane, since they share the file). Full writeup, evidence tables and what-not-to-repeat:
`docs/lanes/pathrules1013/NOTES.md`.

**Part A -- a step the model never answered is not a path.** A run that never reaches gameplay can still write
a `complete: false` path containing steps where the model gave no answer (`state: "unknown"`, `why: "model gave
no answer"`, no action) -- the next run then loads that path, waits on a recorded step that was never really a
decision, and diverges in minutes. Fixed in both directions: `write_path` now cuts on the first such step before
it's ever written; `load_paths` now re-cuts any such step already on disk (via a new `cut_no_answer`, matching
on `state`+`why` since a recorded/loaded step carries no `src`). Verified against all four fixtures named in the
brief (two real diverged runs, two of lane.pathvoid1012's built fixtures) -- all reduce to 0 steps.

**Part B -- a hold that can no longer mathematically pass ends early.** New `hold_bar_unreachable(play_s,
window_s, budget_left_s, bar=0.10)`: fires when the off-play share so far already exceeds the bar even against
every second of budget remaining treated as perfect play. Wired via `Agent.hold_unsalvageable`, a new `elif`
branch parallel to (not replacing) the existing `hold_check` branch -- explicitly does not reuse
`hold_shortfall`, whose own duration gate reports "needs more duration" in exactly the case this rule needs to
catch (confirmed on real data: PoP's hold at cut=400s is still "duration: 400 s of gameplay < 600 s
confirmation" 11s before `hold_bar_unreachable` actually fires). Replayed PoP's real hold
(`n-5553001D-1013d/`, `hold.ok: false`) cut at successive points: crossover between hold_el 410s and 412s, about
26.7 minutes before the hold's actual give-up at 2013.4s, and the verdict there is a genuine FAIL (confirmed by
re-running the real `title_verdict.py` against each cut). Confirmed the rule never fires on the passing 25 to
Life hold (`n-45530018-1013r/`) at any cut, even under the strictest possible assumption (zero budget left).
Searched all 16 `ladder_round` run folders for a real "dipped, then recovered and passed" hold; none exists
(all `hold.ok: false`) -- built a fixture instead, per the brief's own fallback, and confirmed the rule never
fires across it while `hold_shortfall` still correctly calls its final checkpoint a pass. Does not touch the
step cap/ladder (10-06 owner order stands) -- this is a new, independent early exit, not a cap.

**Part C -- a perflog run never reads as a Playable candidate.** Applied pathtele1013's suggested VOID-elif to
`judge()`, extended with a `req.get("build")` fallback so a provisional (mid-hold) verdict voids before
`result.json` exists. Fixed the deeper gap pathtele1013's author flagged but couldn't reach (outside their
territory): `hold_verdict`'s own `request.json` write now also carries `build`/`env` from `self.result`, so a
perflog hold voids at its own final judge too, not just the eventual `result.json`. New
`docs/testing/jobs/selftest.d/89-verdict-perflog.sh` (fixtures + mutants, modeled on `89-title-verdict.sh`) plus
a `pathfind_selftest.py` fragment confirming `hold_verdict`'s own write. Found and fixed a bug in the new
fragment itself along the way (not in `title_verdict.py`): a mutant copy run outside `docs/testing/` can't find
`thermal_state.py` (`title_verdict.py` only ever puts its own directory on `sys.path`) -- fixed with
`PYTHONPATH="$TESTING"` around the fragment's test invocations; flagged in NOTES.md that the read-only reference
`89-title-verdict.sh` likely has the same latent issue, left untouched (out of territory).

**Verified:** `python3 docs/testing/titles/pathfind_selftest.py` -- `pathfind_selftest: all ok`. The new
`89-verdict-perflog.sh` fragment standalone (minimal harness replicating `selftest.sh`'s scaffolding, to avoid
its unrelated gh/systemd/dispatch weight) -- `pass=6 fail=0`.

## Why `State: waiting-on-pathtele1013`, not `ready`

Part C builds on pathtele1013's `--perflog` flag and its suggested `title_verdict.py` patch (PR #433,
`docs/lanes/pathtele1013/PR.md`). `git merge-base --is-ancestor <pathtele1013's fold head> origin/master` still
returns exit 1 as of this check (re-fetched and re-checked at the end of this session) -- its fold has not
landed on `origin/master` yet. This branch already has its commits merged in (see `git log`), so the code here
is consistent and tested against what's actually on disk; the `State:` line is about the *other* PR's landing
status, not a defect in this one.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
