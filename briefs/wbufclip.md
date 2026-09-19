# lane.wbufclip -- the ClipF phase-2 degeneracy needs one new capture, not a fix

Issue: #31 (Slope-scaled polygon offset is wrong under W buffering)
Base: master @ 415dcc6997651ae08d52bcad2249878378ee8dd0
Files: docs/testing/wbuf31_blocker_audit.py, docs/testing/wbuf_anchor_recover.py,
       docs/investigations/wbuffer-31-blocker-audit.md,
       docs/investigations/wbuffer-slope-offset.md, docs/lanes/wbufclip/NOTES.md
       (plus whatever nxdk_pgraph_tests source holds wbuf_tests.cpp -- ask if
       that tree is not already in your worktree; it is outside this repo)

## What's already done

Read nv2a_issues.toml's issue.31 entry in full first -- it is long and
answers most of what you would otherwise re-derive. TriH is FIXED (PASS,
52,800px -> 0). TriV is a refuted-model third mechanism, no candidate rule,
not this brief's job. ClipF (460,949px) is the one with a named, cheap next
step: the audit (docs/investigations/wbuffer-31-blocker-audit.md,
wbuf31_blocker_audit.py) found the corpus's clip_top values are ALL 0 mod 4
(kVertSampleCoords[3+6i] holds only multiples of 32), so "clip_top+2" and
"the absolute 4-grid at phase 2" are the same prediction on every capture
that exists today -- the two candidate rules have never been separated.

## Goal

Add ONE new ClipF (WBuf24D) variant to wbuf_tests.cpp at a clip_top that is
NOT 0 mod 4 (33, 34, or 35 all work per the audit), rebuild the test disc,
capture it on device, and run wbuf_anchor_recover.py against the new capture
to read which of the two candidate rules the recovered anchor matches.

## Falsifier

If the recovered anchor at the new clip_top matches "clip_top+2" and not
"the absolute 4-grid at phase 2" (or vice versa), the two rules are
separated and one is refuted -- that is a real result either way. If the
new capture's clip_top is STILL 0 mod 4 (a harness slip reproducing the
same degeneracy), the falsifier has not run; fix the test source and retry
before reporting.

## Done when

The new capture exists on disk, wbuf_anchor_recover.py's verdict against it
is posted to #31 with the recovered anchor value and which candidate rule
it matches (or neither, which is also informative), and nv2a_issues.toml's
issue.31 status_note is left for the board to update -- do not edit
nv2a_issues.toml yourself, no lane may.

## Out of scope

TriV's refuted-model floor and the 941,308px per-triangle plane-solve floor
are both closed questions per the issue's own note -- do not reopen them.
Do not attempt a fix for #31 itself in this pass; this brief is one
measurement that decides whether a fix is even choosable between two rules.
