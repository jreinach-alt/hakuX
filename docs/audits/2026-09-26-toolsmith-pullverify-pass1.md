# Audit pass 1: PR #369, lane/toolsmith-pullverify (defect 15)

Head audited: `a3f2d528a8`. Read: the diff of `run_disc.sh`,
`extract_results.py`, `selftest.d/58-pull-verify.sh` and the
`51-dispatch-hardening.sh` comment, against `origin/master`.

**Result: no HIGH, no MEDIUM, three LOW.** Next state: `needs-audit-2`.

## What was checked

- **The retry loop in `run_disc.sh`.**
  - The device md5 is taken once, after the guest-wait loop. On the timeout path that is after the `force-stop`, so the file is not being written when it is hashed.
  - A mismatch skips extraction and re-pulls. After `PULL_TRIES` mismatches the script exits 1 with `$HDD` removed and nothing extracted.
  - A match with no SHORT breaks the loop. A match with SHORT breaks with the on-device message.
  - With no md5, SHORT re-pulls until `PULL_TRIES` and then proceeds.
  - `rm -rf "$RESULTS"` and the vsh ledger copy both run inside the loop, so a re-pull does not score a mix of two extractions.
  - `DEV_MD5` must be 32 hex characters. An adb error string or an empty answer becomes "no md5", not a false mismatch.
- **The extractor.**
  - `read_file` stops when the chain ends (a zero FAT entry, via `while cluster`), so `len(data) < size` is the right test.
  - `short` is passed through the recursion.
  - The summary is still one line, and the last line, which `tail -1` depends on.
- **Selftest 58, on CI at this head (job 108354276402).** All 14 checks are `ok`: the five run_disc cases and the three mutants, each red on its named case.
  - The fixture is a real qcow2 holding a real FATX volume, so the extractor reads real bytes.
  - Case (a) is the falsifier: the good pull sits in the middle of the sequence.

## CI

The `selftest` job is red at this head. The only failure is 51 part I, "check_territory names where it read the tracker". Nothing in this diff causes it:

- The check reads live `origin/board`, and live board rows now carry `released = [...]`.
- Master taught `check_territory.py` to read `released` in 50d452fbc4, which this branch predates. The branch is 63 commits behind.
- Master's `jobs selftest` is green at 3a78b533.
- `git merge-tree origin/master HEAD` merges cleanly.

The PR body blames three concurrent host selftests. That is not the cause on CI, which runs alone. The branch needs a merge of `origin/master` before it can go green (L3).

## Findings

### L1 (LOW): without a device md5, SHORT can only see holes in a file's own FAT chain

- **Scenario:** the device gives no md5 (the unverified toybox case the PR names). The pull's hole falls on something other than a file's own FAT chain:
  - a data cluster, so a PNG keeps its size but carries a zeroed run;
  - a directory's FAT entry past its first cluster, so every entry after the first 16 KiB of `nxdk_pgraph_tests` is missing;
  - the directory cluster itself.

  The extractor reports no SHORT and the run proceeds on one pull.
- **Bound:** this happens only on the no-md5 path, and the log says `pull: NOT VERIFIED` on every such run. A zeroed data run reads as `unreadable` or a pixel diff, and missing files show as lost coverage. Nothing is silently scored as exact.
- **Suggestion:** say in the `NOT VERIFIED` line, or in the `run_disc.sh` comment, that the SHORT check covers file chains only.

### L2 (LOW): a run whose SHORT files survive every attempt exits 0

- **Scenario:** either the device image itself is holed (case d), or the device has no md5 and all `PULL_TRIES` pulls come back SHORT. `run_disc.sh` prints the SHORT line and the explanation, then exits 0 with the one-cluster PNGs in `$RESULTS`.
- **Bound:** since #224, part A of 51 makes `score_sweep`/`ab_compare` treat those PNGs as `unreadable` and then VOID. They can no longer count as "repaired to exact". The damage is bounded to a VOID-heavy result that names itself.
- **Suggestion:** a non-zero exit, or a distinct status word, would stop the arm earlier. That is a design choice, not a defect.

### L3 (LOW, process): the head is red on a stale base

See the CI section above. Merge `origin/master` and push, and the part-I check should read the live board correctly. This is not a defect in the diff.

## For pass 2

- L1 and L2 are LOW. Pass 2 need only confirm whether the wording was adopted or consciously declined.
- L3 must be resolved before the fold: CI green on a head that contains `origin/master`.
