# Audit pass 2: PR #309, lane/tcgchurn (#68, #311)

Auditor: job.cloud, 2026-09-25.  Head audited: `a3361339bc`.  Pass 1:
`docs/audits/2026-09-25-tcgchurn-pass1.md`, at `4ef1300091`.

**Result: clean.  No HIGH or MEDIUM was raised in pass 1, and none is raised
here.  The four LOWs still stand, unchanged, and none blocks the fold.**
Next label: `fold-ready`.

## What changed since pass 1

`git diff --stat 4ef1300091 a3361339bc` shows one file: the pass-1 audit
itself.  No code changed, so pass 1's reading of the code diff still applies
to this head without a re-read.  That covers the counters, the orphan fix,
the two env switches, and hunks (a) and (b) compiling to nothing.

- `git merge-tree --write-tree origin/master HEAD` is clean.  GitHub reports
  the PR MERGEABLE, and CI (build ×2) is green on `a3361339bc`.
- The branch is 17 commits behind master.  The fold job merges, so that
  needs no action here.

## The pass-1 findings, one by one

Every finding was LOW, and no remediation round ran.  Each scenario can
therefore still occur.  This file logs the decision pass 1 asked for.

| # | Scenario still possible? | Decision |
|---|---|---|
| L1 | Yes: the `[tlb68]` line is printed unconditionally, every 2 s, in XBOX builds. | Accept for the fold.  It matches `tb_cache_maybe_log_stats()`, and soak tooling reads the line.  Gating the print is follow-up work, not a blocker. |
| L2 | Yes: `cputlb.c:121` still says "written from the vCPU thread except the rd\*o ones", and the `jc`/`jci`/`jcx`/`ka`/`kafb` counters can still lose a count to a device-thread invalidate. | Accept.  This affects instrument accuracy only, and the Xbox has one vCPU.  A reader of those counters should treat them as a lower bound when device DMA writes code pages. |
| L3 | Yes: a cause set off the vCPU thread (reset, `loadvm`) can be charged to the next untagged flush. | Accept as a known limitation of the cause breakdown: at most one misattributed count per such event. |
| L4 | Partly: `hakux-tlb68.h:12-21` still describes hunks (a) and (b) as fix candidates and does not mention the #311 verdict (Mb failed, Ma void). | Accept.  Both are 0 by default, and an `#error` refuses a build that sets both.  The verdict is in the lane NOTES and on #311.  A lane that turns either one on registers a prediction, and that prediction's arm is the check. |

None of the four scenarios produces wrong guest behaviour, a crash path or
unsafety.  All four are instrument quality or code hygiene, which is the
definition of LOW.

## Verdict

Clean.  Remove `needs-audit-2` and add `fold-ready`.  L1, L2 and L4 are
cheap follow-ups: gate the print, correct the comment or use `qatomic_add`,
and add one line at each `#if` citing the #311 verdict.  Any later lane that
touches these files can pick them up.
