#!/usr/bin/env bash
#
# RETIRED 2026-09-19. This script no longer polls anything, and running it
# tells you where its job went instead of quietly doing it.
#
#   its polling            -> docs/testing/comment_sweep.sh (hakux-comments.timer, hourly)
#   its "who said what"    -> docs/testing/jobs/deliver.sh  (send / inbox / last / scan)
#   its report             -> one comment on the `harness-status` issue, and
#                             check_coverage.py's UNBRIEFED note
#
# WHY IT IS A STUB AND NOT A DELETION. It is named in
# docs/ORCHESTRATION-DESIGN.md, docs/ORCHESTRATION-WIND-DOWN.md and two
# hand-offs, none of which this lane owns. A missing file sends a reader to
# `git log`; this one answers the question in four lines. It exits non-zero, so
# anything that starts it stops instead of looping in the background for
# another five days.
#
# WHAT IT GOT RIGHT, KEPT VERBATIM BECAUSE THE NEXT MONITOR WILL NEED IT.
#
# The first version polled PR #45's comments only, because that is where the
# coordination channel was set up. The remote lane answers on the ISSUE thread
# it is working -- it said so twice, "#62 triaged in full on its thread" and
# "#60 answered in its own thread" -- so three substantive comments, including
# one that settled #66's central question, were never read. The lane then
# stalled twice waiting for direction that had been sent to the wrong place,
# and the second stall was reported by the owner rather than noticed here.
#
# The failure is worth stating precisely, because it is not the paginated-
# comments bug that cost a day earlier: the tool was correct. `gh pr view
# --json comments` and `gh api --paginate` agree exactly, 125 comments, same
# newest timestamp. THE ENDPOINT WAS WRONG, not the page. A monitor that
# watches one channel perfectly reports silence on every other one, and
# silence is indistinguishable from "nothing to say".
#
# WHAT IT GOT WRONG, AND IT IS THE SAME SENTENCE ONE LAYER OUT. Its fix was to
# poll every open issue plus the PR -- an ENUMERATION, and an enumeration can
# be wrong about a closed issue, or a thread opened after the loop started. The
# replacement asks for every issue comment in the repository in one paginated
# call (`GET /repos/{o}/{r}/issues/comments?since=`), which covers pull
# requests too and has no list to get wrong.
#
# AND IT HAD NO DESTINATION. It printed, and printing is what became a
# notification -- to a session that ORCHESTRATION-DESIGN.md §4 deleted. It kept
# polling GitHub every sixty seconds for five days afterwards, correct and
# unread. A monitor is not finished when it observes the right thing; it is
# finished when somebody who can act is holding the observation.
set -u
cat >&2 <<'EOF'
watch_remote_lane.sh is retired and does nothing.

  polling      -> docs/testing/comment_sweep.sh        (hourly, hakux-comments.timer)
  deliveries   -> docs/testing/jobs/deliver.sh send|inbox|last|scan
  reporting    -> the `harness-status` issue comment, and check_coverage.py's
                  UNBRIEFED note on its summary line

Read the header of this file for what it learned; it is still true.
EOF
exit 64
