# lane.stencil99 -- #99, ANALYSIS ONLY, and treat the issue as unverified

Base: 55bc6c6c2beed87350cf1c02f67403afddc2acef (origin/master).
Files: NONE. This is reading and dating, not editing.

#99 IS A TITLE WITH AN EMPTY BODY AND NO TRACKER ENTRY: "Stencil: three ZERO
captures regressed 0 -> 100,000 px between 2501f35211 and 0026f00534". Take
the title as a report to be checked, not as a fact.

GOAL, in this order, and each step can kill the issue:

1. #79 SAYS NINE OF SIXTEEN STENCIL CAPTURES CHANGE VALUE BETWEEN RUNS ON ONE
   BUILD. So a two-sha delta over this suite is not evidence of a regression
   until the three captures are shown to be OUTSIDE #79's nine. Name the three
   and name the nine, and say whether they intersect. If they do, #99 is #79
   and should be closed into it.
2. DATE EVERYTHING before attributing anything to code. Date the goldens for
   those three captures against both shas, and date the captures themselves
   against each run's own lifetime. A golden newer than the run, or a capture
   older than the fix, reads exactly like a live defect -- that has cost this
   project a whole suite twice (#27, and again on a capture set).
3. Only if 1 and 2 both survive: what is between 2501f35211 and 0026f00534?
   Read the range and name the commits that could touch a stencil clear or a
   ZERO capture's oracle. Do not run a bisect -- come back and ask for one,
   with the range you narrowed it to.

WHAT YOUR INSTRUMENT CANNOT SEE: before a zero or an "unchanged" result
changes your conclusion, write down what that check WOULD show if the thing
were present. A capture set that does not cover one of the two shas cannot
report "no change"; it reports nothing.

FALSIFIER: if this is a real code regression rather than nondeterminism or a
stale artifact, then the three captures read 0 on repeated runs at
2501f35211 and ~100,000 on repeated runs at 0026f00534 -- repeated, because a
lone score change on one run can be a one-off band. If the value moves between
runs at EITHER sha, the regression framing is refuted and #99 is a duplicate
of #79.

DONE WHEN: a tracker entry written for #99 (title, component, suites,
disposition, blocker_falsifier, blocker_tested, status, status_note) proposed
in a comment on #99 for the board to commit, plus a verdict: duplicate of #79,
stale artifact, or a real regression narrowed to a named commit range. No
commits to hw/. No device, no build.
