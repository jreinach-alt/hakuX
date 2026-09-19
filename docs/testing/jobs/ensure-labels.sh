#!/usr/bin/env bash
#
# The labels the jobs read and write, created idempotently. Run by
# install-host.sh; safe to run again. A label a job sets that does not exist
# is a silent no-op in gh, which is how a state machine loses a state.
set -u
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
mk() { gh label create "$1" --repo "$GH_REPO" --color "$2" --description "$3" --force >/dev/null 2>&1 && echo "label $1"; }
mk dispatchable        0e8a16 "board: free files, no blocker; a lane may start"
mk cloud               1d76db "board: analysis or audit work a cloud session may claim (no device)"
mk claimed:cloud       c5def5 "a cloud session is working this now"
mk needs-audit-1       fbca04 "PR is ready; wants the pass-1 diff audit"
mk needs-audit-2       fbca04 "pass-1 findings remediated; wants the pass-2 verification"
mk needs-remediation   d93f0b "audit found HIGH/MEDIUM; the lane fixes before the fold"
mk fold-ready          0e8a16 "audited and green; the fold job folds it into master"
mk folded              6f42c1 "folded into master by the fold job"
mk needs-rebase        d93f0b "the fold conflicted; bring master into the lane branch"
mk verified            0e8a16 "arms job: registered prediction PASSED on the device"
mk regressed           b60205 "arms job: registered prediction FAILED on the device"
mk decision-needed     e99695 "the owner decides; jobs move on"
mk blocked:needs-owner e99695 "escalated attempt failed too; owner's call"
mk harness             bfd4f2 "the harness itself (jobs, scripts, hooks)"
# NOT CREATED HERE, AND THAT IS THE DESIGN: `regression-accepted:<issue>`.
# fold.sh refuses to fold a PR labelled `regressed` (it folded #102 onto
# master on 2026-09-19 because nothing read that label), and this is the way
# through for a regression that is a measured trade someone owns -- e.g.
# `regression-accepted:91` for Color_zeta_overlap/Swap under #88's
# colour-wins policy. Every other label in this file exists because a JOB
# sets it and a label a job sets that does not exist is a silent no-op. No
# job sets this one and none may: it is the owner saying "I accept this
# regression", which is a sentence only a person can mean. It names its
# issue, so there is one label per accepted trade and no reusable blanket
# pass -- which is also why it cannot be pre-created. The owner creates the
# one they mean, at the moment they mean it:
#
#   gh label create regression-accepted:91 --repo "$GH_REPO" --color b60205 \
#       --description 'owner: the regression on this PR is the trade argued on #91'
#   bash docs/testing/jobs/gh-label.sh add <pr> regression-accepted:91
mk harness-status      bfd4f2 "the one issue whose comment is the live status roll-up"
mk xbox-hardware       0052cc "needs real Xbox silicon; not dispatchable as a device run until a hardware listener exists"
