# A title with one measured stall reaches the owner the same day

State: ready

Lane: stallraise1017            Issue: none (harness fix; owner 10-17 via lane.xbox: "a brief, not an issue")
Base: master @ 427164f2e050e12e6ddaa804646a8ff0c4f7efc7
Files: docs/lanes/stallraise1017/**, docs/testing/title_registry.py, docs/testing/jobs/selftest.d/99-stall-raise.sh, pm/stall-raised.tsv (live host file under /home/justin/hakux-work, NOT git-tracked -- not in this diff), host-tools/hourly_report.sh (live host file under /home/justin/hakux-work, NOT git-tracked -- not in this diff)
Prediction: none: analysis-only
Needs device: no    Needs NDK: no
Selftest: 99-stall-raise -- the only fragment this lane touches; builds its own throwaway registry, reads nothing from the live host's pm/

Owner 10-17: "the rule should be to raise them when you have a title with
one measured hitch like this, not bury it in some report and then forget
about it for days, thats the real failure." Marvel Nemesis (hold
`marvel-851`) sat 10-06 to 10-17 with no row ever asking the owner.

## What this adds

A **single-stall candidate** is a registry row with `status=BELOW_BAR` and
`failing_all=="hitch"` -- read from columns `title_registry.py` already
derives, not a second parser of verdicts (see NOTES.md Step 0 (c)).

1. `docs/testing/title_registry.py`: `is_stall_candidate()`,
   `stall_asks()`, `stall_overdue()`, `validate_stall_raised()`, a new
   `Paths.stall_raised` (`pm/stall-raised.tsv`, hand-appended, outside the
   staleness digest), a visible `status_rule` suffix on candidates, and
   CLI `check --stalls`.
2. `pm/stall-raised.tsv` (live host file, seeded): the five titles
   lane.xbox raised 10-17 22:00 PDT -- DOA3 (4D53002D, 621ms, LOADING), MK
   Deadly Alliance (4D57000C, 5475ms, LOADING), Pac-Man World 2 (4E4D0006,
   590ms, LOADING), Gene Troopers (544D0011, 530ms, PLAY), GTA SA
   (54540082, 624ms, LOADING). `owner_answer` blank for all.
3. `host-tools/hourly_report.sh` (live host file, confirmed via
   `hakux-hourly.service`'s `ExecStart` to be the copy the timer runs): a
   new **STALL ASKS** section, distinct from the pre-existing, unrelated
   **STALLS (stallwatch...)** section (`pm/stalls.md` -- general stalled
   asks/decisions, not this lane's per-title ledger). Lists unraised
   candidates and raised-but-unanswered rows with age in hours; "none" when
   empty; degrades to "stall registry unreadable" (no crash) until this PR
   merges, since `stall_asks` doesn't exist on master's `title_registry.py`
   yet.
4. `check --stalls`: fails (rc 3) on any single-stall candidate with no
   `pm/stall-raised.tsv` row past the 2h grace, naming title id, name, and
   age. Validates the ledger's own rows (`title_id`, `raised_pdt`,
   `stall_ms`, `frames`) so a malformed hand-append doesn't pass silently.
5. The standing rule itself is documented only in
   `docs/lanes/stallraise1017/NOTES.md`, per the brief -- `AGENTS.md` is not
   touched (lane.local owns that file).

## Verification

- `python3 -m py_compile docs/testing/title_registry.py`: clean.
- `title_registry_selftest.py`: still 5/5 (pre-existing, unrelated).
- A real `build --no-forge` against current host data reproduced exactly
  lane.xbox's five hand-found titles as the only single-stall candidates --
  end-to-end confirmation the derivation matches the brief's manual
  precedent.
- `check --stalls` against the real registry + the seeded ledger: passes.
  Against an empty/no-raise-row scratch root: fails rc 3, five "STALL NOT
  RAISED" lines, correct ages.
- `SELFTEST_ONLY=99-stall-raise bash docs/testing/jobs/selftest.sh`: 9
  passed, 0 failed. Covers raised+within-grace (green), raised row
  *removed* -- the exact shape of how Marvel Nemesis went unasked -- (red,
  names the title), a within-grace candidate never raised (green, not yet
  due), a BELOW_BAR title failing more than just `hitch` (never called a
  candidate), and malformed ledger rows (rejected, 3 bad fields caught).
- `host-tools/hourly_report.sh`'s new block checked both pre-merge (against
  `/home/justin/hakuX`'s master `title_registry.py`, no `stall_asks` yet --
  graceful `AttributeError` fallback, no crash) and against this lane's
  worktree copy (post-merge shape) -- correct `WAITING ON OWNER <tid>
  (<run>) raised <N>h ago` lines for all five currently-unanswered seeded
  rows.

## Not in this diff

`pm/stall-raised.tsv` and `host-tools/hourly_report.sh` live under
`/home/justin/hakux-work`, which has no `.git` -- they are edited directly
on disk, not through this branch. `hourly_report.sh` was backed up first to
`hourly_report.sh.bak-20261017-stallraise1017`. Full detail in NOTES.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
