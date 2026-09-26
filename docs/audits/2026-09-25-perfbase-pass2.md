# Audit pass 2: PR #310, lane/perfbase (#68)

Auditor: job.cloud, 2026-09-25.  Head verified: `6ca6f9df62`, which is
pass 1's audited head `16d9fbefaa` plus the pass-1 audit file and nothing
else (`git log 16d9fbefaa..6ca6f9df62` is that one commit).

**Result: not clean.**  Next label: `needs-remediation`.

Pass 1 found no HIGH and no MEDIUM, so nothing blocks the fold on severity.
It found seven LOWs.  AGENTS.md's audit loop, item 3, says every LOW is
either remediated or carries a logged decision ("reviewed, not fixed,
because X"), and silence is not acceptable.  Pass 1 made that the pass-2
check.  None of the seven has either one.  No commit touches the flagged
code.  No PR comment or review from the lane answers the audit.
`docs/lanes/perfbase/NOTES.md` does not mention it.

## Each pass-1 scenario, re-checked at `6ca6f9df62`

| LOW | Scenario | Still occurs? | Evidence at head |
|-----|----------|---------------|------------------|
| 1 | `hakuX-build` collected after the line has been cleared | yes | `run_perf.sh:108` `logcat -c` still precedes the collector at `:114`, which still names `hakuX-build` |
| 2 | P3 has no failing fixture | yes | `pace_check.py` is unchanged, and the selftest has no `vpf` mutant |
| 3 | restart detected only when `f` decreases; ZeroDivisionError / StatisticsError on empty input | yes | `pace_check.py:90` divides by `60 * n` unguarded, and `:100` calls `statistics.median(fps)` unguarded |
| 4 | bare StopIteration in `profile_report.py` | yes | `next(...)` without a default at `:123` and `:126` |
| 5 | PR body says "within 0.2%", but `galleon-r2` is 0.33% off at 16.667 ms | yes | PR body line 29 still reads "to within 0.2%" |
| 6 | "up from the 35-40% read on 09-11" has no source and a new grouping | yes | `perf-baseline-2026-09.md:29` is unchanged, with no citation and no lookup sub-share |
| 7 | a failed prefs restore leaves exit status 0; the superseded prediction does not point forward | yes | `restore_prefs` (`run_perf.sh:80-92`) still only echoes; `perfbase-pace.json` still has no forward pointer |

## What clears this

The lane does not have to fix anything.  One logged decision per LOW
clears it: a fix, or "reviewed, not fixed, because X".  The decisions can
go in NOTES.md, a PR comment or a commit message.  LOW 5 and LOW 6 are
statements of fact in the PR body and the investigation doc, and a
reader will take them as settled.  Those two are the ones to correct
rather than decline.  The other five can be declined with a reason.
