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

---

# Audit pass 2, second round: PR #310 at `5086650677`

Auditor: job.cloud, 2026-09-25.  Head verified: `5086650677`, which is
`d89a8b3b9c` (round one above) plus the lane's remediation commit and
nothing else.

**Result: clean.**  Next label: `fold-ready`.

The lane fixed five of the LOWs in code, corrected LOW 5 in the PR body
and LOW 6 in the investigation, and logged a decision for each of the
seven in `docs/lanes/perfbase/NOTES.md` under "Audit decisions".  Each
scenario was re-run or re-read at this head and none still occurs.

| LOW | Scenario | Still occurs? | How it was checked |
|-----|----------|---------------|--------------------|
| 1 | `hakuX-build` collected after the clear | no | `run_perf.sh:113` dumps `-s hakuX-build` to `<tag>-build.txt` before the `logcat -c` at `:114`, and the collector no longer names the tag.  NOTES says the six 09-26 logs predate this and carry no build line. |
| 2 | P3 has no failing fixture | no | `pace_check.py --selftest`: 6 of 6 ok, including the new `ema` case (Vpf 2.30 against vb/60 2.05), which gives `FAIL P3`.  The selftest's `hakuX-perf` line now prints `w["vpf"]`, so the mutant reaches the judge. |
| 3 | one-line process scored as a step of 0; tracebacks on empty input | no | Synthetic logs: `f=60`, then a new process at `f=60,120,180,240` now gives P1 PASS on 3 steps.  All `ms=0` and all-excluded windows each print `FAIL no window left to judge` and exit 1, with no traceback.  An in-process gap (`120 -> 240`) still gives P1 FAIL, so `<=` did not blind P1.  `crimson-r1.log` judges exactly as before: PASS, P3 0.2%, P5 3.0%. |
| 4 | bare StopIteration in `profile_report.py` | no | Both `next(...)` calls now take a `None` default, and `sys.exit` names which lookup failed (`sys` is imported at `:32`). |
| 5 | "within 0.2%" in the PR body | no | The PR body now reads 0.9967-0.9990 at 16.667 ms, "the judge's P4 period", which matches pass 1's recomputation.  NOTES carries both periods. |
| 6 | "up from the 35-40% read on 09-11" | no | The phrase is gone.  The doc says the group is new, names the four lookup symbols, gives 11.8 / 11.6 points, and gives 28.6-29.3% without them (40.4 - 11.8, 40.9 - 11.6: both check).  The no-change claim now rests on the per-symbol table at `:132-142`. |
| 7 | a failed restore exits 0; the superseded prediction has no forward pointer | no | `restore_prefs` does `exit 3` on a read-back mismatch.  `bash -c 'f() { exit 3; }; trap f EXIT; true'` exits 3, so the trap's status reaches the caller.  `perfbase-pace.json` has `superseded_by` naming `perfbase-pace-2.json`.  No prediction reader in `docs/testing/` rejects an unknown key, and `check` is green on this head. |

CI on `5086650677`: build x2 and check SUCCESS, and the PR is MERGEABLE.
No new finding from the remediation diff.
