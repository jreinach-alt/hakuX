# The nightly's release notes drop every lane commit written more than a day before it folds

Lane: nightlynotes            Issue: none (a harness defect, brief only)
Base: origin/master (fetch first).
Files: docs/testing/nightly_build.sh, docs/testing/jobs/selftest.d/86-nightly-notes.sh,
docs/lanes/nightlynotes/**
Needs device: no. Needs NDK: no. Prediction: none, because this is harness work. The proof is the selftest.

## The defect, measured 2026-09-25

The owner asked: "The nightly build shows zero emulator changes. Why did no
emulator work make it into the nightly?"

`nightly_build.sh:200` sets `SINCE` to "yesterday 00:30", and `:236` selects the
commits with `git log --no-merges --since="$SINCE"`. That is a window over COMMIT
DATES. A lane's commits keep the dates they were written, and they reach
master in a fold merge days later, so the window drops them.

- `nightly-2026-09-25` built `82e460e863` over `nightly-2026-09-24` (`3fe18366cd`).
  The build added **14** non-merge commits (`git log --no-merges
  3fe18366cd..82e460e863`). The notes listed **4**, the ones committed on 09-24,
  and said "0 emulator". The one emulator commit, `637b4f1d2a nv2a/gl: clear to
  the surface's pad-bit constant (#164)`, was committed on 09-19 and folded (PR
  #172) at 09-24 23:41, and it is missing.
- Tonight's run would repeat it for everything folded since then: `40ca2bcb22`
  (#194, 09-20), `77cc17bf6e` (#211, 09-21) and `63a24f9834` (#222, committed
  09-25 00:16, 14 minutes before the window opens) are all outside
  `--since "2026-09-25T00:30"`.

## The fix

Select by ANCESTRY, not by date: `git log --no-merges <previous nightly>..HEAD`.
The previous nightly is the newest `nightly-*` tag that is an ancestor of HEAD
(`git tag -l 'nightly-*' --sort=-creatordate`, then keep the first one for which
`git merge-base --is-ancestor <tag> HEAD` holds). Fall back to the date window
only if no tag qualifies, and SAY so in the notes. `TOTAL` (`:240`) and the tally
line must use the same range. The `notes [SINCE]` override the fixture uses
can become `notes [BASE-REF]`, or keep both. Your call; say which.

Keep everything else as it is: the emulator/harness/other classification, the
caps, and the "built from `<sha>`" line.

## Falsify before claiming

Add a fixture to `selftest.d/86-nightly-notes.sh`: a repo where a commit dated
three days ago reaches the tip through a merge made today, after a tag from
yesterday. The OLD script must omit it. Prove that in a scratch worktree running
the old file, red for that reason and not a setup error, and assert on the
output words. The new script must list it, classified correctly (a `hw/` path
counts as emulator). The existing fixtures must stay green.

## Also

Say in NOTES whether `nightly-2026-09-25`'s published notes should be regenerated.
The host session has already appended a correction to that release by hand.

## Done when

The selftest is green (and red on the old file for the right reason), the PR
carries the lane template with its `Files:` line, preflight passes, NOTES are
written, and the PR is marked ready, all well before 00:30 America/Los_Angeles,
when the next nightly runs.
