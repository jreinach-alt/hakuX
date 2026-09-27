[job.cloud] audit pass 2, PR #457 (lane.isoroots, #397), head 59c338428e

**Verdict: clean.** Pass 1 found no HIGH or MEDIUM, and nothing it checked has changed. Next state: `fold-ready`.

## What changed since pass 1

Only the pass-1 audit file. `git diff 9e182d9ec1 59c338428e` touches
`docs/audits/2026-09-26-isoroots-pass1.md` and nothing else. The code pass 1
read is the code on the head.

## The checks pass 1 asked for

- **`99-iso-roots.sh` still passes on the head.** I sourced it alone with
  `ok`/`bad`/`check` stubs against this tree. Result: 10/10 ok, `fail=0`. That
  covers root 2, none, quote, root 1, both Nova legs, launch, unchanged,
  titles, and the dispatcher-extract guard.
- **`$tpath` still reaches `soak_title.sh`.** In `dispatcher.sh`, line 754
  sets `tpath=$(device_title_path "$title")` and line 767 passes `"$tpath"`
  to `soak_title.sh`.
- **Mergeable.** `git merge-tree --write-tree origin/master HEAD` reports no
  conflict. Both `build` jobs pass. `selftest` was still pending when this
  file was written, and the fold gate reads it.

## The three LOWs

The lane left all three unfixed. None of them blocks the fold, and each is
still exactly as pass 1 described it:

- **LOW 1** (an adb timeout reads as `title not on device`) is unchanged
  from master, so it is not a regression.
- **LOW 2** (the found path goes through `echo` under mksh) cannot fire,
  because exFAT/FAT does not allow `\` in a filename.
- **LOW 3** (comment width) is cosmetic.

No pass-1 scenario fires on this head.
